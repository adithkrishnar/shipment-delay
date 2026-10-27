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


def calculate_safety_stock(
    daily_demand_mean: float,
    daily_demand_std: float,
    lead_time_mean: float,
    lead_time_std: float = 0.0,
    z_factor: float = 1.65,
) -> float:
    """
    Computes statistically rigorous safety stock accounting for both daily demand
    variability and supplier lead-time variability:
        SS = Z * sqrt( L_mean * (sigma_d ** 2) + (d_mean ** 2) * (sigma_L ** 2) )

    Fallback documentation:
    When historical delivery observations are insufficient to determine lead-time
    variability (sigma_L), sigma_L falls back to 0.0, simplifying to the classic:
        SS = Z * sigma_d * sqrt(L_mean).
    When demand is zero (mean <= 0 and std <= 0), safety stock is 0.0.
    """
    if daily_demand_mean <= 0 and daily_demand_std <= 0:
        return 0.0
    l_mean = max(1.0, float(lead_time_mean))
    d_std = max(0.0, float(daily_demand_std))
    d_mean = max(0.0, float(daily_demand_mean))
    l_std = max(0.0, float(lead_time_std))
    variance_term = (l_mean * (d_std ** 2)) + ((d_mean ** 2) * (l_std ** 2))
    return float(round(max(0.0, z_factor * math.sqrt(max(0.0, variance_term))), 2))


def get_supplier_lead_time_stats(
    db: Session,
    company_id: int,
    product_id: int | None = None,
    supplier_id: int | None = None,
    default_lead_time: float = 14.0,
) -> tuple[float, float, str]:
    """
    Computes (lead_time_mean, lead_time_std, lead_time_source) from historical completed shipments.
    If at least 2 completed shipments with valid elapsed days exist, computes sample standard deviation.
    Otherwise falls back sensibly to 0.0 lead-time variance with explicit documentation in the source string.
    """
    q = db.query(Shipment).filter(
        Shipment.company_id == company_id,
        Shipment.actual_delivery.isnot(None),
    )
    if product_id is not None:
        q = q.filter(Shipment.product_id == product_id)
    elif supplier_id is not None:
        q = q.filter(Shipment.supplier_id == supplier_id)

    completed = q.all()
    lead_times: list[float] = []
    for s in completed:
        if s.order_date and s.actual_delivery:
            days = (s.actual_delivery - s.order_date).days
            if days >= 0:
                lead_times.append(float(days))
        elif s.planned_delivery and s.actual_delivery:
            nominal = float(s.supplier.lead_time_days) if s.supplier and s.supplier.lead_time_days else default_lead_time
            diff = (s.actual_delivery - s.planned_delivery).days
            lead_times.append(float(max(1.0, nominal + diff)))

    if len(lead_times) >= 2:
        return float(np.mean(lead_times)), float(np.std(lead_times, ddof=1)), f"historical_shipments_n={len(lead_times)}"
    elif len(lead_times) == 1:
        return float(lead_times[0]), 0.0, "single_shipment_insufficient_history_fallback"

    # Check if supplier has a configured lead_time_days
    if supplier_id is not None:
        sup = db.query(Supplier).filter(Supplier.company_id == company_id, Supplier.id == supplier_id).first()
        if sup and sup.lead_time_days:
            return float(sup.lead_time_days), 0.0, "supplier_nominal_fallback"

    return float(default_lead_time), 0.0, "default_lead_time_fallback"


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
    nominal_lead = float(supplier.lead_time_days) if supplier and supplier.lead_time_days else 14.0
    lead_mean, lead_std, lead_source = get_supplier_lead_time_stats(
        db, company_id, product_id=product_id, supplier_id=supplier.id if supplier else None, default_lead_time=nominal_lead
    )
    reliability = float(supplier.reliability) if supplier and supplier.reliability is not None else 0.85

    incoming = _incoming(db, company_id, product_id)
    incoming_qty = sum(float(s.quantity or 0) for s in incoming)
    next_arrival = min((s.planned_delivery for s in incoming), default=None)
    if next_arrival and delay_days:
        next_arrival = next_arrival + timedelta(days=delay_days)

    coverage_days = inventory / daily if daily > 0 else float("inf")
    effective_lead = max(1.0, lead_mean + float(delay_days))
    safety_stock = calculate_safety_stock(daily, std, effective_lead, lead_std, z_factor=1.65)
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
        "lead_time_days": round(lead_mean, 1),
        "lead_time_std": round(lead_std, 2),
        "lead_time_source": lead_source,
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
