"""
SupplyIQ Inventory Recommendation Engine.
Generates structured, auditable decision-support recommendations exclusively
focused on inventory health, replenishment urgency, surplus transfers, and supplier lead-times.
"""
from __future__ import annotations

from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.models import Product, Warehouse
from app.services.inventory_intelligence import company_inventory
from app.services.supplier_intelligence import analyze_suppliers
from app.services.replenishment_service import (
    compute_replenishment_plan,
    get_warehouse_transfer_recommendations,
)


def generate_recommendations(db: Session, company_id: int) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []

    # 1. Replenishment Recommendations sourced directly from compute_replenishment_plan
    replen_plan = compute_replenishment_plan(db, company_id)
    for r in replen_plan["recommendations"]:
        if not r["needs_reorder"]:
            continue

        reorder_qty = r["suggested_order_qty"]
        order_cost = r["estimated_order_cost"]
        urgency = r["urgency"]
        effective_inv = r["on_hand"] + r["on_order"]
        is_breach = effective_inv <= r["reorder_point"]
        approaching_threshold = round(r["reorder_point"] + (r["daily_demand"] * 2.0), 1)

        if urgency == "CRITICAL":
            action = "Expedite Emergency Replenishment"
            action_type = "EXPEDITE_REPLENISHMENT"
            priority = "CRITICAL"
            reason = f"Critical shortage: on-hand stock ({r['on_hand']:.1f} units) covers less than 3 days of demand ({r['daily_demand']:.1f} u/d)."
        elif urgency == "HIGH":
            action = "Place Urgent Purchase Order (Safety Stock Breached)"
            action_type = "PLACE_PURCHASE_ORDER"
            priority = "HIGH"
            reason = f"Safety buffer breached: on-hand stock ({r['on_hand']:.1f} units) is below safety stock ({r['safety_stock']:.1f} units)."
        elif is_breach:
            action = "Initiate Purchase Order (ROP Breached)"
            action_type = "REORDER_POINT_BREACH"
            priority = "MEDIUM"
            reason = f"Reorder point breached: effective inventory ({effective_inv:.1f} units) fell below ROP ({r['reorder_point']:.1f} units)."
        else:
            action = "Initiate Proactive Purchase Order (Approaching ROP)"
            action_type = "PROACTIVE_REORDER"
            priority = "MEDIUM"
            reason = f"Early warning: on-hand stock ({r['on_hand']:.1f} units) is within 2 days of demand from ROP ({r['reorder_point']:.1f} units, warning threshold {approaching_threshold:.1f} units)."

        cost_note = f"${order_cost:,.2f}" if r["has_explicit_cost"] else "Cost data unavailable"
        recs.append({
            "action": action,
            "action_type": action_type,
            "priority": priority,
            "title": f"Reorder {reorder_qty} units of {r['name']}",
            "product_name": r["name"],
            "sku": r["sku"],
            "target_type": "PRODUCT",
            "target_id": r["sku"],
            "warehouse": "Primary Regional Facility",
            "reason": reason,
            "supporting_data": {
                "on_hand": r["on_hand"],
                "on_order": r["on_order"],
                "daily_demand": r["daily_demand"],
                "lead_time_days": r["lead_time_days"],
                "safety_stock": r["safety_stock"],
                "reorder_point": r["reorder_point"],
                "approaching_threshold": approaching_threshold,
                "is_formal_rop_breach": is_breach,
                "is_early_warning": not is_breach,
                "suggested_order_qty": reorder_qty,
                "unit_cost": r["unit_cost"] if r["has_explicit_cost"] else None,
                "has_explicit_cost": r["has_explicit_cost"],
                "estimated_order_cost": order_cost if r["has_explicit_cost"] else None,
                "supplier_name": r.get("supplier_name", "Primary Supplier"),
            },
            "expected_impact": f"Restores inventory to 30-day target policy with {cost_note} estimated procurement capital, protecting 95% service level.",
            "status": "PENDING_REVIEW",
        })

    # 2. Overstock Mitigation Actions (from company inventory analysis)
    inv = company_inventory(db, company_id)
    products = db.query(Product).filter(Product.company_id == company_id).all()
    price_map = {p.id: float(p.unit_cost or p.unit_price or 25.0) for p in products}
    sku_map = {p.id: p.external_product_id for p in products}

    for r in inv:
        pid = r['product_id']
        price = price_map.get(pid, 25.0)
        sku = sku_map.get(pid, r.get('external_product_id', f'SKU-{pid:04d}'))
        if r.get("overstock_risk") in {"HIGH", "CRITICAL"}:

            excess = max(0, r.get('inventory_level', 0) - (r.get('daily_demand', 1) * 45))
            holding_cost = excess * price * 0.20
            recs.append({
                "action": "Review Excess Inventory / Rebalance",
                "action_type": "OVERSTOCK_MITIGATION",
                "priority": "MEDIUM",
                "title": f"Mitigate overstock of {r['product_name']}",
                "product_name": r['product_name'],
                "sku": sku,
                "target_type": "PRODUCT",
                "target_id": sku,
                "warehouse": r.get("warehouse_name", "Primary Facility"),
                "reason": f"Inventory exceeds 45 days demand buffer by {excess:.0f} units. Holding cost accumulating at 20% p.a.",
                "supporting_data": {
                    "on_hand": round(r.get('inventory_level', 0), 1),
                    "daily_demand": round(r.get('daily_demand', 0), 1),
                    "excess_units": round(excess, 1),
                    "holding_cost_annual": round(holding_cost, 2),
                },
                "expected_impact": f"Reallocating or promotional sell-through releases ${holding_cost:,.2f} in working capital.",
                "status": "PENDING_REVIEW",
            })

    # 2. Inter-Warehouse Stock Transfer Opportunities
    try:
        transfers = get_warehouse_transfer_recommendations(db, company_id)
        for t in transfers[:5]:
            dest_name = t.get("destination_warehouse_name") or t.get("target_warehouse_name") or "Destination Warehouse"
            dest_id = t.get("destination_warehouse_id") or t.get("target_warehouse_id")
            source_name = t.get("source_warehouse_name") or "Source Warehouse"
            source_id = t.get("source_warehouse_id")
            transfer_qty = t.get("transfer_units", 0)
            source_stock = t.get("source_stock_before", t.get("source_stock", 0))
            dest_stock = t.get("destination_stock_before", t.get("target_stock", 0))

            recs.append({
                "action": "Execute Warehouse Transfer",
                "action_type": "STOCK_TRANSFER",
                "priority": "HIGH" if dest_stock <= 5 else "MEDIUM",
                "title": f"Transfer {transfer_qty} units from {source_name} to {dest_name}",
                "product_name": t.get('product_name'),
                "sku": t.get('sku'),
                "target_type": "TRANSFER",
                "target_id": f"{t.get('sku')}:{source_id}->{dest_id}",
                "warehouse": f"{source_name} → {dest_name}",
                "reason": f"{dest_name} has only {dest_stock:.0f} units, while {source_name} holds {source_stock:.0f} units surplus.",
                "supporting_data": {
                    "source_warehouse": source_name,
                    "target_warehouse": dest_name,
                    "destination_warehouse": dest_name,
                    "source_warehouse_id": source_id,
                    "destination_warehouse_id": dest_id,
                    "transfer_units": transfer_qty,
                    "source_stock": source_stock,
                    "target_stock": dest_stock,
                    "source_stock_before": source_stock,
                    "destination_stock_before": dest_stock,
                },
                "expected_impact": "Immediately resolves destination shortage without incurring new procurement costs.",
                "status": "PENDING_REVIEW",
            })
    except Exception:
        pass

    # 3. Supplier Lead Time & Reliability Bottlenecks
    try:
        suppliers = analyze_suppliers(db, company_id)
        for s in suppliers:
            if s.get("risk_tier") in {"HIGH", "CRITICAL"}:
                supp_id_str = str(s.get('supplier_id', 'SUP-01'))
                recs.append({
                    "action": "Audit Supplier Lead Time & Buffer",
                    "action_type": "SUPPLIER_BUFFER_AUDIT",
                    "priority": s["risk_tier"].upper(),
                    "title": f"Adjust Safety Buffers for Supplier {s.get('name')}",
                    "product_name": f"Supplier: {s.get('name')}",
                    "sku": supp_id_str,
                    "target_type": "SUPPLIER",
                    "target_id": supp_id_str,
                    "warehouse": "All Multi-Node Facilities",
                    "reason": f"Supplier demonstrates {s.get('delay_rate', 0)*100:.0f}% lead-time delay frequency with {s.get('reliability', 0)*100:.0f}% on-time consistency.",
                    "supporting_data": {
                        "delay_rate": round(s.get('delay_rate', 0), 3),
                        "reliability": round(s.get('reliability', 0), 3),
                        "lead_time_days": round(s.get('lead_time_days', 14.0), 1),
                    },
                    "expected_impact": "Recalibrates safety stock formulas to absorb supplier volatility and prevent upstream stockouts.",
                    "status": "PENDING_REVIEW",
                })
    except Exception:
        pass

    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    return sorted(recs, key=lambda x: (priority_order.get(x["priority"], 2), x["sku"]))[:30]
