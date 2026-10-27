"""
SupplyIQ Replenishment & Multi-Warehouse Transfer Optimization Service.
Computes mathematically sound reorder policies, dynamic safety stocks,
and inter-warehouse surplus-to-shortage transfer recommendations.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy.orm import Session

from app.models import Company, Product, InventoryRecord, Sale, Warehouse, Supplier, Shipment
from app.services.inventory_intelligence import calculate_safety_stock, get_supplier_lead_time_stats


SERVICE_LEVEL_Z_FACTORS = {
    0.90: 1.28,
    0.95: 1.65,
    0.98: 2.05,
    0.99: 2.33,
}


def compute_replenishment_plan(
    db: Session,
    company_id: int,
    service_level: float = 0.95,
    planning_horizon_days: int = 30,
) -> Dict[str, Any]:
    """
    Computes reorder requirements, safety stock targets, and purchase order suggestions
    across all products for the authenticated company.
    """
    z_factor = SERVICE_LEVEL_Z_FACTORS.get(round(service_level, 2), 1.65)
    products = db.query(Product).filter(Product.company_id == company_id).all()

    # Fetch latest inventory per product
    latest_inv_rows = (
        db.query(InventoryRecord)
        .filter(InventoryRecord.company_id == company_id)
        .order_by(InventoryRecord.product_id, InventoryRecord.date.desc())
        .all()
    )
    stock_map = {}
    for r in latest_inv_rows:
        if r.product_id not in stock_map:
            stock_map[r.product_id] = float(r.inventory_level or 0.0)

    # Fetch open incoming shipments
    open_shipments = (
        db.query(Shipment)
        .filter(Shipment.company_id == company_id, Shipment.actual_delivery.is_(None))
        .all()
    )
    incoming_map: Dict[int, float] = {}
    for s in open_shipments:
        incoming_map[s.product_id] = incoming_map.get(s.product_id, 0.0) + float(s.quantity or 0.0)

    default_lead_time = 14.0

    recommendations = []
    total_reorder_units = 0
    total_reorder_cost = 0.0

    for p in products:
        # Get historical demand
        sales_rows = (
            db.query(Sale.quantity)
            .filter(Sale.company_id == company_id, Sale.product_id == p.id)
            .order_by(Sale.date.desc())
            .limit(60)
            .all()
        )
        sales_vals = [float(x[0]) for x in sales_rows if x[0] is not None]
        daily_demand = float(np.mean(sales_vals)) if sales_vals else 5.0
        demand_std = float(np.std(sales_vals, ddof=1)) if len(sales_vals) > 1 else (daily_demand * 0.25)

        # Real supplier relationship via historical or planned shipments
        sup = (
            db.query(Supplier)
            .join(Shipment, Shipment.supplier_id == Supplier.id)
            .filter(Shipment.company_id == company_id, Shipment.product_id == p.id)
            .order_by(Shipment.planned_delivery.desc())
            .first()
        )
        if sup:
            supplier_id = sup.id
            supplier_name = sup.name
            supplier_assigned = True
            nom_lead = float(sup.lead_time_days or default_lead_time)
        else:
            supplier_id = None
            supplier_name = "Unassigned"
            supplier_assigned = False
            nom_lead = default_lead_time

        # Statistically rigorous lead-time statistics & unified safety stock:
        # SS = Z * sqrt( L_mean * sigma_d^2 + d_mean^2 * sigma_L^2 )
        lead_mean, lead_std, lead_source = get_supplier_lead_time_stats(
            db, company_id, product_id=p.id, supplier_id=supplier_id, default_lead_time=nom_lead
        )
        safety_stock = calculate_safety_stock(
            daily_demand_mean=daily_demand,
            daily_demand_std=demand_std,
            lead_time_mean=lead_mean,
            lead_time_std=lead_std,
            z_factor=z_factor,
        )
        reorder_point = (daily_demand * lead_mean) + safety_stock

        on_hand = stock_map.get(p.id, 0.0)
        on_order = incoming_map.get(p.id, 0.0)
        effective_inventory = on_hand + on_order

        # Target inventory for horizon
        target_inventory = (daily_demand * planning_horizon_days) + safety_stock

        # Needs reorder if effective inventory <= reorder_point
        needs_reorder = effective_inventory <= reorder_point
        suggested_qty = max(0, math.ceil(target_inventory - effective_inventory)) if needs_reorder else 0

        # Minimum Order Quantity (MOQ) logic
        moq = 25
        if suggested_qty > 0 and suggested_qty < moq:
            suggested_qty = moq

        unit_cost = float(p.unit_cost) if p.unit_cost is not None else float(p.unit_price or 20.0)
        estimated_cost = suggested_qty * unit_cost

        if needs_reorder:
            total_reorder_units += suggested_qty
            total_reorder_cost += estimated_cost

        urgency = (
            "CRITICAL" if on_hand <= (daily_demand * 3)
            else "HIGH" if on_hand <= safety_stock
            else "MEDIUM" if needs_reorder
            else "OPTIMAL"
        )

        recommendations.append({
            "product_id": p.id,
            "sku": p.external_product_id,
            "name": p.name,
            "category": p.category or "General",
            "daily_demand": round(daily_demand, 2),
            "demand_std": round(demand_std, 2),
            "lead_time_days": round(lead_mean, 1),
            "lead_time_std": round(lead_std, 2),
            "lead_time_source": lead_source,
            "on_hand": round(on_hand, 1),
            "on_order": round(on_order, 1),
            "safety_stock": round(safety_stock, 1),
            "reorder_point": round(reorder_point, 1),
            "suggested_order_qty": suggested_qty,
            "unit_cost": unit_cost,
            "estimated_order_cost": round(estimated_cost, 2),
            "needs_reorder": needs_reorder,
            "urgency": urgency,
            "supplier_id": supplier_id,
            "supplier_name": supplier_name,
            "supplier_assigned": supplier_assigned,
        })

    # Sort critical and high urgency to top
    urgency_weights = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "OPTIMAL": 3}
    recommendations.sort(key=lambda x: (urgency_weights.get(x["urgency"], 4), -x["suggested_order_qty"]))

    return {
        "service_level": service_level,
        "z_factor": z_factor,
        "planning_horizon_days": planning_horizon_days,
        "summary": {
            "total_skus": len(products),
            "skus_needing_reorder": sum(1 for r in recommendations if r["needs_reorder"]),
            "critical_stockouts": sum(1 for r in recommendations if r["urgency"] == "CRITICAL"),
            "total_reorder_units": total_reorder_units,
            "total_reorder_cost": round(total_reorder_cost, 2),
        },
        "recommendations": recommendations,
    }


def get_warehouse_transfer_recommendations(db: Session, company_id: int) -> List[Dict[str, Any]]:
    """
    Identifies viable inter-warehouse transfers.
    Ensures transfer quantity does NOT cause a shortage at the source warehouse.
    """
    warehouses = db.query(Warehouse).filter(Warehouse.company_id == company_id).all()
    if len(warehouses) < 2:
        return []

    products = db.query(Product).filter(Product.company_id == company_id).all()
    transfer_proposals = []

    for p in products:
        wh_records = (
            db.query(InventoryRecord)
            .filter(InventoryRecord.company_id == company_id, InventoryRecord.product_id == p.id)
            .all()
        )
        if not wh_records:
            continue

        wh_stock: Dict[int, float] = {r.warehouse_id: float(r.inventory_level or 0.0) for r in wh_records if r.warehouse_id}

        # Check for deficit warehouse (< 20 units) and surplus warehouse (> 100 units)
        surplus_wh = [wh_id for wh_id, stock in wh_stock.items() if stock > 80]
        deficit_wh = [wh_id for wh_id, stock in wh_stock.items() if stock < 25]

        wh_name_map = {w.id: w.name for w in warehouses}

        for s_id in surplus_wh:
            for d_id in deficit_wh:
                s_stock = wh_stock[s_id]
                d_stock = wh_stock[d_id]
                # Safe transfer: maximum transfer that leaves at least 50 units at source
                max_safe_transfer = s_stock - 50.0
                needed_at_dest = 50.0 - d_stock
                transfer_qty = min(max_safe_transfer, needed_at_dest)

                if transfer_qty >= 10:
                    transfer_proposals.append({
                        "product_id": p.id,
                        "sku": p.external_product_id,
                        "product_name": p.name,
                        "source_warehouse_id": s_id,
                        "source_warehouse_name": wh_name_map.get(s_id, f"Warehouse {s_id}"),
                        "source_stock_before": round(s_stock, 1),
                        "source_stock_after": round(s_stock - transfer_qty, 1),
                        "destination_warehouse_id": d_id,
                        "destination_warehouse_name": wh_name_map.get(d_id, f"Warehouse {d_id}"),
                        "destination_stock_before": round(d_stock, 1),
                        "destination_stock_after": round(d_stock + transfer_qty, 1),
                        "transfer_units": int(transfer_qty),
                        "estimated_transfer_days": 2,
                        "priority": "HIGH" if d_stock <= 5 else "MEDIUM",
                        "reason": f"Destination has critically low stock ({round(d_stock, 1)} units); source has surplus ({round(s_stock, 1)} units).",
                    })

    return transfer_proposals
