from __future__ import annotations

import math
from datetime import date, timedelta
from statistics import mean

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import InventoryRecord, Product, Sale, Shipment, Supplier


def _latest_inventory(db: Session, company_id: int):
    rows = (
        db.query(InventoryRecord)
        .filter(InventoryRecord.company_id == company_id)
        .order_by(InventoryRecord.product_id, InventoryRecord.date.desc())
        .all()
    )
    latest = {}
    for r in rows:
        latest.setdefault(r.product_id, r)
    return latest


def _daily_demand(db: Session, company_id: int, product_id: int, days: int = 30) -> float:
    rows = (
        db.query(Sale.quantity)
        .filter(Sale.company_id == company_id, Sale.product_id == product_id)
        .order_by(Sale.date.desc())
        .limit(days)
        .all()
    )
    values = [float(x[0]) for x in rows if x[0] is not None]
    return float(mean(values)) if values else 0.0


def _demand_std(db: Session, company_id: int, product_id: int, days: int = 60) -> float:
    rows = (
        db.query(Sale.quantity)
        .filter(Sale.company_id == company_id, Sale.product_id == product_id)
        .order_by(Sale.date.desc())
        .limit(days)
        .all()
    )
    values = [float(x[0]) for x in rows if x[0] is not None]
    return float(np.std(values, ddof=1)) if len(values) > 1 else 0.0


def _supplier_for_product(db: Session, company_id: int, product_id: int):
    return (
        db.query(Supplier)
        .join(Shipment, Shipment.supplier_id == Supplier.id)
        .filter(Shipment.company_id == company_id, Shipment.product_id == product_id)
        .order_by(Supplier.reliability.desc())
        .first()
    )


def _incoming(db: Session, company_id: int, product_id: int):
    return (
        db.query(Shipment)
        .filter(
            Shipment.company_id == company_id,
            Shipment.product_id == product_id,
            Shipment.actual_delivery.is_(None),
        )
        .order_by(Shipment.planned_delivery.asc())
        .all()
    )


def _risk_tier(prob: float) -> str:
    if prob >= 0.85:
        return "CRITICAL"
    if prob >= 0.65:
        return "HIGH"
    if prob >= 0.35:
        return "MEDIUM"
    return "LOW"


def analyze_product(db: Session, company_id: int, product_id: int, delay_days: float = 0.0, latest_inv_map: dict = None) -> dict:
    product = db.query(Product).filter(Product.company_id == company_id, Product.id == product_id).first()
    if not product:
        raise ValueError("Product not found for company")
    
    if latest_inv_map is None:
        latest_inv_map = _latest_inventory(db, company_id)
    latest = latest_inv_map.get(product_id)
    
    inventory = float(latest.inventory_level) if latest else 0.0
    daily = _daily_demand(db, company_id, product_id)
    std = _demand_std(db, company_id, product_id)
    supplier = _supplier_for_product(db, company_id, product_id)
    lead = float(supplier.lead_time_days) if supplier and supplier.lead_time_days else 14.0
    reliability = float(supplier.reliability) if supplier and supplier.reliability is not None else 0.85

    incoming = _incoming(db, company_id, product_id)
    incoming_qty = sum(float(s.quantity or 0) for s in incoming)
    next_arrival = min((s.planned_delivery for s in incoming), default=None)
    if next_arrival and delay_days:
        next_arrival = next_arrival + timedelta(days=delay_days)

    coverage_days = inventory / daily if daily > 0 else float("inf")
    effective_lead = max(1.0, lead + float(delay_days))
    safety_stock = max(0.0, 1.65 * std * math.sqrt(effective_lead))
    reorder_point = daily * effective_lead + safety_stock
    horizon_demand = daily * effective_lead
    shortage = max(0.0, horizon_demand + safety_stock - inventory - incoming_qty)

    # Transparent risk heuristic, deliberately separate from the ML delay model.
    stockout_prob = 1.0 / (1.0 + math.exp((inventory + incoming_qty - horizon_demand - safety_stock) / max(1.0, daily * 2)))
    stockout_prob = float(np.clip(stockout_prob, 0.0, 1.0))
    overstock_ratio = max(0.0, inventory / max(1.0, daily * 45) - 1.0)
    overstock_prob = float(np.clip(overstock_ratio * 0.75, 0.0, 1.0))

    recommended_order = max(0.0, daily * 30 + safety_stock - inventory - incoming_qty)
    if recommended_order > 0:
        recommended_order = math.ceil(recommended_order)

    return {
        "product_id": product.id,
        "external_product_id": product.external_product_id,
        "product_name": product.name,
        "category": product.category,
        "inventory_level": round(inventory, 2),
        "daily_demand": round(daily, 2),
        "demand_std": round(std, 2),
        "inventory_coverage_days": round(coverage_days, 1) if math.isfinite(coverage_days) else None,
        "supplier_id": supplier.id if supplier else None,
        "supplier_name": supplier.name if supplier else None,
        "supplier_reliability": round(reliability, 3),
        "lead_time_days": round(lead, 1),
        "simulated_delay_days": round(float(delay_days), 1),
        "effective_lead_time_days": round(effective_lead, 1),
        "incoming_quantity": round(incoming_qty, 2),
        "next_arrival": str(next_arrival) if next_arrival else None,
        "safety_stock": round(safety_stock, 2),
        "reorder_point": round(reorder_point, 2),
        "recommended_order_quantity": int(recommended_order),
        "stockout_probability": round(stockout_prob, 4),
        "stockout_risk": _risk_tier(stockout_prob),
        "expected_shortage": round(shortage, 2),
        "overstock_probability": round(overstock_prob, 4),
        "overstock_risk": _risk_tier(overstock_prob),
        "assumptions": {
            "service_factor": 1.65,
            "target_inventory_horizon_days": 30,
            "overstock_horizon_days": 45,
        },
    }


def company_inventory(db: Session, company_id: int, delay_days: float = 0.0) -> list[dict]:
    products = db.query(Product).filter(Product.company_id == company_id).order_by(Product.name).all()
    latest_inv_map = _latest_inventory(db, company_id)
    return [analyze_product(db, company_id, p.id, delay_days, latest_inv_map) for p in products]


def inventory_summary(rows: list[dict]) -> dict:
    if not rows:
        return {"products": 0, "stockout_high": 0, "overstock_high": 0, "inventory_units": 0, "avg_stockout_probability": 0}
    return {
        "products": len(rows),
        "stockout_high": sum(r["stockout_risk"] in {"HIGH", "CRITICAL"} for r in rows),
        "overstock_high": sum(r["overstock_risk"] in {"HIGH", "CRITICAL"} for r in rows),
        "inventory_units": round(sum(r["inventory_level"] for r in rows), 2),
        "avg_stockout_probability": round(float(np.mean([r["stockout_probability"] for r in rows])), 4),
    }
