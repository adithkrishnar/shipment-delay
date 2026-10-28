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
from app.services.replenishment_service import get_warehouse_transfer_recommendations


def generate_recommendations(db: Session, company_id: int) -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []
    inv = company_inventory(db, company_id)

    products = db.query(Product).filter(Product.company_id == company_id).all()
    price_map = {p.id: float(p.unit_cost or p.unit_price or 25.0) for p in products}
    sku_map = {p.id: p.external_product_id for p in products}

    # 1. Critical and High-Risk Stockout & Replenishment Actions
    for r in inv:
        pid = r['product_id']
        price = price_map.get(pid, 25.0)
        sku = sku_map.get(pid, r.get('external_product_id', f'SKU-{pid:04d}'))
        shortage = max(0, r.get('expected_shortage', 0.0))
        lost_revenue = shortage * price
        cov_days = r.get('inventory_coverage_days') or 0.0
        stockout_prob = r.get('stockout_probability', 0.0)
        reorder_qty = r.get('recommended_order_quantity', 50)

        if r.get("stockout_risk") in {"HIGH", "CRITICAL"}:
            priority = r["stockout_risk"].upper()
            action_type = "EXPEDITE_REPLENISHMENT" if r.get("inventory_level", 0) <= (r.get("daily_demand", 0) * 3) else "PLACE_PURCHASE_ORDER"
            recs.append({
                "action": "Expedite Emergency Replenishment" if action_type == "EXPEDITE_REPLENISHMENT" else "Initiate Purchase Order",
                "action_type": action_type,
                "priority": priority,
                "title": f"Reorder {reorder_qty} units of {r['product_name']}",
                "product_name": r['product_name'],
                "sku": sku,
                "target_type": "PRODUCT",
                "target_id": sku,
                "warehouse": r.get("warehouse_name", "Primary Facility"),
                "reason": f"Current stock ({r.get('inventory_level', 0):.0f} units) faces {stockout_prob*100:.0f}% stockout risk within {cov_days:.1f} days at daily demand of {r.get('daily_demand', 0):.1f} units/day.",
                "supporting_data": {
                    "on_hand": round(r.get('inventory_level', 0), 1),
                    "daily_demand": round(r.get('daily_demand', 0), 1),
                    "safety_stock": round(r.get('safety_stock', 0), 1),
                    "coverage_days": round(cov_days, 1),
                    "suggested_order_qty": reorder_qty,
                    "unit_cost": price,
                },
                "expected_impact": f"Prevents ${lost_revenue:,.2f} projected revenue loss across {shortage:.0f} shortage units." if lost_revenue > 0 else f"Protects stock continuity for {reorder_qty} units.",
                "status": "PENDING_REVIEW",
            })
        elif r.get("stockout_risk") == "MEDIUM" or cov_days <= 18.0:
            reorder_qty = max(25, r.get('recommended_order_quantity', 50))
            order_cost = reorder_qty * price
            recs.append({
                "action": "Initiate Proactive Purchase Order",
                "action_type": "PROACTIVE_REORDER",
                "priority": "MEDIUM",
                "title": f"Reorder {reorder_qty} units of {r['product_name']}",
                "product_name": r['product_name'],
                "sku": sku,
                "target_type": "PRODUCT",
                "target_id": sku,
                "warehouse": r.get("warehouse_name", "Primary Regional Hub"),
                "reason": f"Stock ({r.get('inventory_level', 0):.0f} units) is approaching reorder threshold ({r.get('reorder_point', 0):.0f} ROP) with {cov_days:.1f} days coverage against a 14-day lead time.",
                "supporting_data": {
                    "on_hand": round(r.get('inventory_level', 0), 1),
                    "daily_demand": round(r.get('daily_demand', 0), 1),
                    "safety_stock": round(r.get('safety_stock', 0), 1),
                    "reorder_point": round(r.get('reorder_point', 0), 1),
                    "coverage_days": round(cov_days, 1),
                    "suggested_order_qty": reorder_qty,
                    "unit_cost": price,
                    "estimated_order_cost": round(order_cost, 2),
                },
                "expected_impact": f"Prevents buffer erosion and maintains target 95% service level before reaching safety threshold.",
                "status": "PENDING_REVIEW",
            })
        elif r.get("overstock_risk") in {"HIGH", "CRITICAL"}:

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
