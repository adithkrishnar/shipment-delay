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
    
    legs = []
    waiting_periods = []
    
    if scenario == 1:
        # LOW RISK: Warehouse -> Airport -> Dest Airport -> Dest Warehouse
        legs = [
            {"leg_id": 1, "sequence": 1, "mode": "ROAD", "origin": shipment.origin or "Supplier Warehouse", "destination": "Origin Airport", "distance": 50.0, "expected_duration": 2.0, "actual_or_predicted_duration": 2.0, "transport_delay": 0.0},
            {"leg_id": 2, "sequence": 2, "mode": "AIR", "origin": "Origin Airport", "destination": "Dest Airport", "distance": 1500.0, "expected_duration": 4.0, "actual_or_predicted_duration": 4.0, "transport_delay": 0.0},
            {"leg_id": 3, "sequence": 3, "mode": "ROAD", "origin": "Dest Airport", "destination": shipment.destination or "Company Warehouse", "distance": 30.0, "expected_duration": 1.5, "actual_or_predicted_duration": 1.5, "transport_delay": 0.0}
        ]
        waiting_periods = [
            {"between_leg": "1-2", "waiting_duration": 2.0}, # 2 hours
            {"between_leg": "2-3", "waiting_duration": 1.0}  # 1 hour
        ]
    elif scenario == 2:
        # MODERATE RISK: Road delay + some waiting
        legs = [
            {"leg_id": 1, "sequence": 1, "mode": "ROAD", "origin": shipment.origin, "destination": "Port", "distance": 200.0, "expected_duration": 6.0, "actual_or_predicted_duration": 12.0, "transport_delay": 6.0},
            {"leg_id": 2, "sequence": 2, "mode": "SEA", "origin": "Port", "destination": "Dest Port", "distance": 3000.0, "expected_duration": 120.0, "actual_or_predicted_duration": 120.0, "transport_delay": 0.0},
            {"leg_id": 3, "sequence": 3, "mode": "ROAD", "origin": "Dest Port", "destination": shipment.destination, "distance": 100.0, "expected_duration": 4.0, "actual_or_predicted_duration": 4.0, "transport_delay": 0.0}
        ]
        waiting_periods = [
            {"between_leg": "1-2", "waiting_duration": 48.0}, # 2 days waiting for ship
            {"between_leg": "2-3", "waiting_duration": 12.0}
        ]
    else:
        # CRITICAL RISK: Significant delays
        legs = [
            {"leg_id": 1, "sequence": 1, "mode": "ROAD", "origin": shipment.origin, "destination": "Rail Yard", "distance": 100.0, "expected_duration": 3.0, "actual_or_predicted_duration": 3.0, "transport_delay": 0.0},
            {"leg_id": 2, "sequence": 2, "mode": "RAIL", "origin": "Rail Yard", "destination": "Dest Rail Yard", "distance": 1000.0, "expected_duration": 48.0, "actual_or_predicted_duration": 96.0, "transport_delay": 48.0},
            {"leg_id": 3, "sequence": 3, "mode": "ROAD", "origin": "Dest Rail Yard", "destination": shipment.destination, "distance": 50.0, "expected_duration": 2.0, "actual_or_predicted_duration": 10.0, "transport_delay": 8.0}
        ]
        waiting_periods = [
            {"between_leg": "1-2", "waiting_duration": 72.0}, # 3 days waiting
            {"between_leg": "2-3", "waiting_duration": 48.0}  # 2 days waiting
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
