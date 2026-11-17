from datetime import datetime, timedelta
import pandas as pd
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Company, Shipment, Product, Supplier
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

def analyze_multi_leg_shipment(db: Session, company_id: int, shipment_id: int, scenario: int = 1) -> Dict[str, Any]:
    shipment = db.query(Shipment).filter(Shipment.company_id == company_id, Shipment.id == shipment_id).first()
    if not shipment:
        raise ValueError("Shipment not found")
        
    supplier = db.query(Supplier).filter(Supplier.id == shipment.supplier_id).first()
    
    # Get ML models
    classifier, duration_model, clf_entry = get_active_shipment_models(db, company_id)
    row_df = _row_to_single_df(shipment, supplier)
    ml_risk = predict_shipment_risk(classifier, duration_model, row_df)
    
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
                "distance": float(l.distance_km or 100.0),
                "expected_duration": float(l.expected_duration_hrs or 2.0),
                "actual_or_predicted_duration": float((l.expected_duration_hrs or 2.0) + simulated_leg_delay),
                "transport_delay": simulated_leg_delay
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
            {"leg_id": 1, "sequence": 1, "mode": "ROAD", "origin": shipment.origin or "Origin Facility", "destination": "Regional Consolidation Hub", "distance": 50.0, "expected_duration": 2.0, "actual_or_predicted_duration": 2.0, "transport_delay": 0.0},
            {"leg_id": 2, "sequence": 2, "mode": "ROAD", "origin": "Regional Consolidation Hub", "destination": "Destination Intermediate Depot", "distance": 280.0, "expected_duration": 6.0, "actual_or_predicted_duration": 6.0, "transport_delay": 0.0},
            {"leg_id": 3, "sequence": 3, "mode": "ROAD", "origin": "Destination Intermediate Depot", "destination": shipment.destination or "Destination DC", "distance": 35.0, "expected_duration": 1.5, "actual_or_predicted_duration": 1.5, "transport_delay": 0.0}
        ]
        waiting_periods = [
            {"between_leg": "1-2", "waiting_duration": 1.0},
            {"between_leg": "2-3", "waiting_duration": 1.0}
        ]
    elif scenario == 2:
        legs = [
            {"leg_id": 1, "sequence": 1, "mode": "ROAD", "origin": shipment.origin, "destination": "Regional Consolidation Hub", "distance": 50.0, "expected_duration": 2.0, "actual_or_predicted_duration": 2.0, "transport_delay": 0.0},
            {"leg_id": 2, "sequence": 2, "mode": "ROAD", "origin": "Regional Consolidation Hub", "destination": "Destination Intermediate Depot", "distance": 280.0, "expected_duration": 6.0, "actual_or_predicted_duration": 10.0, "transport_delay": 4.0},
            {"leg_id": 3, "sequence": 3, "mode": "ROAD", "origin": "Destination Intermediate Depot", "destination": shipment.destination, "distance": 35.0, "expected_duration": 1.5, "actual_or_predicted_duration": 1.5, "transport_delay": 0.0}
        ]
        waiting_periods = [
            {"between_leg": "1-2", "waiting_duration": 2.0},
            {"between_leg": "2-3", "waiting_duration": 2.0}
        ]
    else:
        legs = [
            {"leg_id": 1, "sequence": 1, "mode": "ROAD", "origin": shipment.origin, "destination": "Regional Consolidation Hub", "distance": 50.0, "expected_duration": 2.0, "actual_or_predicted_duration": 2.0, "transport_delay": 0.0},
            {"leg_id": 2, "sequence": 2, "mode": "ROAD", "origin": "Regional Consolidation Hub", "destination": "Destination Intermediate Depot", "distance": 280.0, "expected_duration": 6.0, "actual_or_predicted_duration": 22.0, "transport_delay": 16.0},
            {"leg_id": 3, "sequence": 3, "mode": "ROAD", "origin": "Destination Intermediate Depot", "destination": shipment.destination, "distance": 35.0, "expected_duration": 1.5, "actual_or_predicted_duration": 1.5, "transport_delay": 0.0}
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
    
    # Inventory Impact
    inv_analysis = analyze_product(db, company_id, shipment.product_id, delay_days=total_delay_days)
    
    # Combine ML probability with deterministic delay calculation for overall tier (simplistic for demo)
    final_risk_tier = ml_risk["risk_tier"]
    if scenario == 3:
        final_risk_tier = "CRITICAL"
    elif scenario == 2 and final_risk_tier == "LOW":
        final_risk_tier = "MEDIUM"
        
    rec = get_recommendation(final_risk_tier, inv_analysis["stockout_risk"], inv_analysis.get("inventory_coverage_days") or 999.0)
    
    return {
        "shipment_id": shipment.external_shipment_id,
        "legs": legs,
        "waiting_periods": waiting_periods,
        "total_transport_delay_hours": total_transport_delay_hrs,
        "total_waiting_delay_hours": total_waiting_delay_hrs,
        "total_delay_hours": total_delay_hrs,
        "predicted_final_arrival": predicted_arrival.isoformat(),
        "delay_probability": ml_risk["delay_probability"],
        "risk_tier": final_risk_tier,
        "inventory_impact": {
            "current_inventory": inv_analysis["inventory_level"],
            "daily_demand": inv_analysis["daily_demand"],
            "coverage_days": inv_analysis["inventory_coverage_days"],
            "stockout_risk": inv_analysis["stockout_risk"],
            "expected_shortage": inv_analysis["expected_shortage"]
        },
        "recommendation": rec
    }
