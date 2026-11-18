import math
from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models import Company, Shipment, Product, Supplier, User
from app.services.inventory_intelligence import analyze_product
from app.ml.shipment_delay import predict_shipment_risk
from app.services.model_training_service import get_active_shipment_models
from app.routes.shipments import _row_to_single_df

def get_recommendation(risk_tier: str, stockout_risk: str, inventory_coverage_days: float) -> str:
    if risk_tier == "CRITICAL" and stockout_risk in ["CRITICAL", "HIGH"]:
        return "EXPEDITE OR CONTINGENCY REPLENISHMENT"
    elif risk_tier in ["HIGH", "CRITICAL"]:
        return "EXPEDITE"
    elif stockout_risk in ["HIGH", "CRITICAL"]:
        return "ALTERNATE SUPPLIER"
    elif risk_tier == "MEDIUM" or stockout_risk == "MEDIUM":
        return "MONITOR"
    else:
        return "NO ACTION"

def analyze_multi_leg_shipment(
    db: Session,
    company_id: int,
    shipment_id: Any,
    scenario: int = 1,
    current_user: Optional[User] = None
) -> Dict[str, Any]:
    shipment = None
    if isinstance(shipment_id, int) or (isinstance(shipment_id, str) and shipment_id.isdigit()):
        sid = int(shipment_id)
        shipment = db.query(Shipment).filter(
            ((Shipment.company_id == company_id) | (Shipment.receiver_company_id == company_id)),
            Shipment.id == sid
        ).first()
    if not shipment:
        shipment = db.query(Shipment).filter(
            ((Shipment.company_id == company_id) | (Shipment.receiver_company_id == company_id)),
            Shipment.external_shipment_id == str(shipment_id)
        ).first()

    # Legitimate assigned-carrier access verification if requested by transporter user
    if not shipment and current_user and current_user.role == "transporter":
        base_q = db.query(Shipment)
        if isinstance(shipment_id, int) or (isinstance(shipment_id, str) and shipment_id.isdigit()):
            cand = base_q.filter(Shipment.id == int(shipment_id)).first()
        else:
            cand = base_q.filter(Shipment.external_shipment_id == str(shipment_id)).first()
        if cand:
            is_assigned = (
                not cand.transporter_org_id or
                (cand.transporter_org_id == current_user.transporter_org_id) or
                (cand.carrier and current_user.carrier_name and cand.carrier.strip().lower() in current_user.carrier_name.strip().lower())
            )
            if is_assigned:
                shipment = cand
            else:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: This shipment is not assigned to your transporter organization."
                )

    if not shipment:
        raise ValueError(f"Shipment #{shipment_id} not found for enterprise #{company_id}")
        
    supplier = db.query(Supplier).filter(Supplier.id == shipment.supplier_id).first() if shipment.supplier_id else None
    
    # Get ML models with resilient fallback
    try:
        classifier, duration_model, clf_entry = get_active_shipment_models(db, company_id)
        row_df = _row_to_single_df(shipment, supplier)
        ml_risk = predict_shipment_risk(classifier, duration_model, row_df)
    except Exception:
        ml_risk = {"risk_tier": "LOW", "delay_probability": 0.15}
    
    base_start = datetime.combine(shipment.order_date, datetime.min.time()) if shipment.order_date else datetime.now()
    
    from app.models.shipment_leg import ShipmentLeg
    from app.services.collaborative_disruption_service import ensure_shipment_legs

    real_legs = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == shipment.id).order_by(ShipmentLeg.sequence).all()
    if not real_legs:
        real_legs = ensure_shipment_legs(db, shipment)

    legs = []
    waiting_periods = []

    if real_legs:
        for i, l in enumerate(real_legs):
            # Scale simulated scenario delays if user clicks scenario 2 or 3
            simulated_leg_delay = float(l.delay_hours or 0.0)
            if scenario == 2 and l.sequence == 2 and simulated_leg_delay == 0.0:
                simulated_leg_delay = 4.0
            elif scenario == 3 and l.sequence == 2 and simulated_leg_delay == 0.0:
                simulated_leg_delay = 16.0

            legs.append({
                "leg_id": l.id,
                "sequence": l.sequence,
                "mode": l.mode or shipment.transport_mode or "ROAD",
                "origin": l.origin,
                "destination": l.destination,
                "carrier_name": l.carrier_name or shipment.carrier or "Authorized Logistics Fleet",
                "distance": float(l.distance_km or 100.0),
                "expected_duration": float(l.expected_duration_hrs or 2.0),
                "actual_or_predicted_duration": float((l.expected_duration_hrs or 2.0) + simulated_leg_delay),
                "transport_delay": simulated_leg_delay,
                "status": l.status or "SCHEDULED"
            })
            if i < len(real_legs) - 1:
                wait_dur = float(l.missed_connection_dwell_hrs or 0.0)
                if scenario == 3 and l.sequence == 2 and wait_dur == 0.0:
                    wait_dur = 12.0
                elif scenario == 2 and l.sequence == 2 and wait_dur == 0.0:
                    wait_dur = 2.0
                waiting_periods.append({
                    "between_leg": f"{l.sequence}-{real_legs[i+1].sequence}",
                    "waiting_duration": wait_dur
                })
    elif scenario == 1:
        # Fallback template if no database legs exist
        legs = [
            {"leg_id": 1, "sequence": 1, "mode": "ROAD", "origin": shipment.origin or "Origin Facility", "destination": "Regional Consolidation Hub", "distance": 50.0, "expected_duration": 2.0, "actual_or_predicted_duration": 2.0, "transport_delay": 0.0, "status": "COMPLETED"},
            {"leg_id": 2, "sequence": 2, "mode": "ROAD", "origin": "Regional Consolidation Hub", "destination": "Destination Intermediate Depot", "distance": 280.0, "expected_duration": 6.0, "actual_or_predicted_duration": 6.0, "transport_delay": 0.0, "status": "IN_TRANSIT"},
            {"leg_id": 3, "sequence": 3, "mode": "ROAD", "origin": "Destination Intermediate Depot", "destination": shipment.destination or "Destination DC", "distance": 35.0, "expected_duration": 1.5, "actual_or_predicted_duration": 1.5, "transport_delay": 0.0, "status": "SCHEDULED"}
        ]
        waiting_periods = [
            {"between_leg": "1-2", "waiting_duration": 1.0},
            {"between_leg": "2-3", "waiting_duration": 1.0}
        ]
    elif scenario == 2:
        legs = [
            {"leg_id": 1, "sequence": 1, "mode": "ROAD", "origin": shipment.origin, "destination": "Regional Consolidation Hub", "distance": 50.0, "expected_duration": 2.0, "actual_or_predicted_duration": 2.0, "transport_delay": 0.0, "status": "COMPLETED"},
            {"leg_id": 2, "sequence": 2, "mode": "ROAD", "origin": "Regional Consolidation Hub", "destination": "Destination Intermediate Depot", "distance": 280.0, "expected_duration": 6.0, "actual_or_predicted_duration": 10.0, "transport_delay": 4.0, "status": "IN_TRANSIT"},
            {"leg_id": 3, "sequence": 3, "mode": "ROAD", "origin": "Destination Intermediate Depot", "destination": shipment.destination, "distance": 35.0, "expected_duration": 1.5, "actual_or_predicted_duration": 1.5, "transport_delay": 0.0, "status": "SCHEDULED"}
        ]
        waiting_periods = [
            {"between_leg": "1-2", "waiting_duration": 2.0},
            {"between_leg": "2-3", "waiting_duration": 2.0}
        ]
    else:
        legs = [
            {"leg_id": 1, "sequence": 1, "mode": "ROAD", "origin": shipment.origin, "destination": "Regional Consolidation Hub", "distance": 50.0, "expected_duration": 2.0, "actual_or_predicted_duration": 2.0, "transport_delay": 0.0, "status": "COMPLETED"},
            {"leg_id": 2, "sequence": 2, "mode": "ROAD", "origin": "Regional Consolidation Hub", "destination": "Destination Intermediate Depot", "distance": 280.0, "expected_duration": 6.0, "actual_or_predicted_duration": 22.0, "transport_delay": 16.0, "status": "DELAYED"},
            {"leg_id": 3, "sequence": 3, "mode": "ROAD", "origin": "Destination Intermediate Depot", "destination": shipment.destination, "distance": 35.0, "expected_duration": 1.5, "actual_or_predicted_duration": 1.5, "transport_delay": 0.0, "status": "SCHEDULED"}
        ]
        waiting_periods = [
            {"between_leg": "1-2", "waiting_duration": 2.0},
            {"between_leg": "2-3", "waiting_duration": 12.0}
        ]
        
    total_transport_delay_hrs = sum(l["transport_delay"] for l in legs)
    total_waiting_delay_hrs = sum(w["waiting_duration"] for w in waiting_periods)
    total_delay_hrs = total_transport_delay_hrs + total_waiting_delay_hrs
    
    total_expected_duration_hrs = sum(l["expected_duration"] for l in legs)
    
    predicted_arrival = base_start + timedelta(hours=total_expected_duration_hrs + total_delay_hrs)
    total_delay_days = total_delay_hrs / 24.0
    
    # Inventory Impact with safe fallbacks and JSON-compliant numbers
    inv_analysis = {
        "inventory_level": 0.0,
        "daily_demand": 0.0,
        "inventory_coverage_days": None,
        "stockout_risk": "LOW",
        "expected_shortage": 0.0
    }
    if shipment.product_id:
        try:
            target_inv_comp = shipment.receiver_company_id or company_id
            target_pid = shipment.product_id
            shp_p = db.query(Product).filter(Product.id == shipment.product_id).first()
            if shp_p and shp_p.external_product_id and target_inv_comp != shp_p.company_id:
                matched_p = db.query(Product).filter(
                    Product.company_id == target_inv_comp,
                    Product.external_product_id == shp_p.external_product_id
                ).first()
                if matched_p:
                    target_pid = matched_p.id

            raw = analyze_product(db, target_inv_comp, target_pid, delay_days=total_delay_days)
            if raw:
                inv_analysis = raw
        except Exception:
            try:
                raw = analyze_product(db, company_id, shipment.product_id, delay_days=total_delay_days)
                if raw:
                    inv_analysis = raw
            except Exception:
                pass
    
    cov_days = inv_analysis.get("inventory_coverage_days")
    if cov_days is not None and (math.isinf(cov_days) or math.isnan(cov_days)):
        cov_days = None

    # Combine ML probability with deterministic delay calculation for overall tier
    final_risk_tier = ml_risk.get("risk_tier", "LOW")
    if scenario == 3:
        final_risk_tier = "CRITICAL"
    elif scenario == 2 and final_risk_tier == "LOW":
        final_risk_tier = "MEDIUM"
        
    rec = get_recommendation(final_risk_tier, inv_analysis.get("stockout_risk", "LOW"), cov_days or 999.0)
    
    return {
        "shipment_id": shipment.external_shipment_id,
        "legs": legs,
        "waiting_periods": waiting_periods,
        "total_transport_delay_hours": round(float(total_transport_delay_hrs), 1),
        "total_waiting_delay_hours": round(float(total_waiting_delay_hrs), 1),
        "total_delay_hours": round(float(total_delay_hrs), 1),
        "predicted_final_arrival": predicted_arrival.isoformat(),
        "delay_probability": round(float(ml_risk.get("delay_probability", 0.15)), 4),
        "risk_tier": final_risk_tier,
        "inventory_impact": {
            "current_inventory": float(inv_analysis.get("inventory_level", 0.0)),
            "daily_demand": float(inv_analysis.get("daily_demand", 0.0)),
            "coverage_days": cov_days,
            "stockout_risk": inv_analysis.get("stockout_risk", "LOW"),
            "expected_shortage": float(inv_analysis.get("expected_shortage", 0.0))
        },
        "recommendation": rec
    }
