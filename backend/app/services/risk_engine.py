from __future__ import annotations

import math
import numpy as np
from sqlalchemy.orm import Session
from app.models import Company, Shipment, Supplier, Product
from app.ml.shipment_delay import predict_shipment_risk
from app.services.model_training_service import get_active_shipment_models
from app.services.inventory_intelligence import analyze_product
import pandas as pd


def shipment_context(db: Session, company_id: int, shipment_id: int) -> dict:
    shipment = db.query(Shipment).filter(Shipment.company_id == company_id, Shipment.id == shipment_id).first()
    if not shipment:
        raise ValueError("Shipment not found")
    supplier = db.query(Supplier).filter(Supplier.id == shipment.supplier_id).first()
    classifier, duration, entry = get_active_shipment_models(db, company_id)
    row = pd.DataFrame([{
        "shipment_id": shipment.id, "external_shipment_id": shipment.external_shipment_id, "product_id": shipment.product_id,
        "supplier_id": shipment.supplier_id, "origin": shipment.origin, "destination": shipment.destination, "carrier": shipment.carrier,
        "transport_mode": shipment.transport_mode, "distance_km": shipment.distance_km, "weight_kg": shipment.weight_kg,
        "quantity": shipment.quantity, "order_date": shipment.order_date, "planned_delivery": shipment.planned_delivery,
        "actual_delivery": None, "supplier_lead_time_days": supplier.lead_time_days if supplier else None,
        "supplier_reliability": supplier.reliability if supplier else None, "supplier_cost_index": supplier.cost_index if supplier else None,
    }])
    risk = predict_shipment_risk(classifier, duration, row)
    inv = analyze_product(db, company_id, shipment.product_id, risk.get("expected_delay_days") or 0)
    return {"shipment": {"id": shipment.id, "external_id": shipment.external_shipment_id, "origin": shipment.origin, "destination": shipment.destination, "quantity": shipment.quantity, "product_id": shipment.product_id}, "delay": risk, "inventory_impact": inv, "model_source": entry.model_source}


def simulate(db: Session, company_id: int, product_id: int, demand_multiplier: float = 1.0, inventory_delta: float = 0.0, delay_days: float = 0.0, lead_time_delta: float = 0.0, incoming_delta: float = 0.0, reorder_delta: float = 0.0) -> dict:
    base = analyze_product(db, company_id, product_id, 0)
    daily = base["daily_demand"] * max(0, demand_multiplier)
    inventory = max(0, base["inventory_level"] + inventory_delta)
    incoming = max(0, base["incoming_quantity"] + incoming_delta)
    lead = max(1, base["lead_time_days"] + lead_time_delta + delay_days)
    std = base["demand_std"]
    safety = max(0, 1.65 * std * math.sqrt(lead))
    horizon = daily * lead
    stockout = 1 / (1 + math.exp((inventory + incoming - horizon - safety) / max(1, daily*2)))
    reorder = max(0, daily*30 + safety - inventory - incoming + reorder_delta)
    overstock = float(np.clip(max(0, inventory / max(1, daily*45)-1) * .75, 0, 1))
    return {"product_id": product_id, "baseline": base, "scenario": {"inventory_level":round(inventory,2),"daily_demand":round(daily,2),"incoming_quantity":round(incoming,2),"effective_lead_time_days":round(lead,2),"stockout_probability":round(float(stockout),4),"stockout_risk": _tier(float(stockout)),"overstock_probability":round(overstock,4),"overstock_risk":_tier(overstock),"recommended_order_quantity":int(math.ceil(reorder))}, "delta": {"stockout_probability_change":round(float(stockout-base["stockout_probability"]),4),"recommended_order_change":int(math.ceil(reorder)-base["recommended_order_quantity"])}}


def _tier(p: float) -> str:
    return "CRITICAL" if p >= .85 else "HIGH" if p >= .65 else "MEDIUM" if p >= .35 else "LOW"
