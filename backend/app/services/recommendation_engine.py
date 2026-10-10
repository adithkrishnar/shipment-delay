from __future__ import annotations

from sqlalchemy.orm import Session
from app.services.inventory_intelligence import company_inventory
from app.services.supplier_intelligence import analyze_suppliers
from app.services.anomaly_detection import detect_anomalies
from app.models import Shipment
from app.services.risk_engine import shipment_context


def generate_recommendations(db: Session, company_id: int) -> list[dict]:
    recs=[]
    inv = company_inventory(db, company_id)
    # Need product prices for impact calculation
    from app.models import Product
    products = db.query(Product).filter(Product.company_id == company_id).all()
    price_map = {p.id: float(p.unit_cost or 0) for p in products}

    for r in inv:
        price = price_map.get(r['product_id'], 0)
        shortage = max(0, r['expected_shortage'])
        lost_revenue = shortage * price
        
        if r["stockout_risk"] in {"HIGH","CRITICAL"}:
            recs.append({
                "priority": r["stockout_risk"].lower(),
                "type": "inventory",
                "title": f"Air-freight {r['recommended_order_quantity']} units of {r['product_name']}",
                "reason": f"{r['product_name']} faces {r['stockout_probability']*100:.0f}% stockout risk in {r['inventory_coverage_days'] or 0:.1f} days.",
                "expected_impact": f"Prevents ${lost_revenue:,.2f} potential lost revenue." if lost_revenue > 0 else f"Prevents stockout of {shortage} units.",
                "affected_entity": r['product_name'],
                "product_id": r['product_id']
            })
        elif r["overstock_risk"] in {"HIGH","CRITICAL"}:
            excess = max(0, r['inventory_level'] - (r['daily_demand'] * 45))
            holding_cost = excess * price * 0.2 # assume 20% holding cost
            recs.append({
                "priority": "medium",
                "type": "inventory",
                "title": f"Review overstock of {r['product_name']}",
                "reason": f"Inventory exceeds 45 days of demand by {excess:.0f} units.",
                "expected_impact": f"Reduces holding-cost exposure by approximately ${holding_cost:,.2f}.",
                "affected_entity": r['product_name'],
                "product_id": r['product_id']
            })
            
    for s in analyze_suppliers(db, company_id):
        if s["risk_tier"] in {"HIGH","CRITICAL"}:
            recs.append({
                "priority": s["risk_tier"].lower(),
                "type": "supplier",
                "title": f"Review supplier {s['name']}",
                "reason": f"Supplier has a {s['delay_rate']*100:.0f}% historical delay rate and {(1-s['reliability'])*100:.0f}% unreliability.",
                "expected_impact": "Reduces downstream stockout risks by diversifying sourcing.",
                "affected_entity": s['name'],
                "supplier_id": s['supplier_id']
            })
            
    anomalies = detect_anomalies(db, company_id, 20)
    for a in anomalies[:5]:
        recs.append({
            "priority": "high" if a['severity'] == 'CRITICAL' else "medium",
            "type": "anomaly",
            "title": f"Investigate {a['entity_type']} anomaly",
            "reason": a.get('reason', a.get('explanation', 'Unknown anomaly')),
            "expected_impact": a.get('potential_business_impact', "Validate underlying event before it distorts planning."),
            "affected_entity": str(a['entity_id'])
        })
    
    try:
        from app.models import Shipment
        from app.services.risk_engine import shipment_context
        # Get active uncompleted shipments to check for risk
        shipments = db.query(Shipment).filter(Shipment.company_id == company_id, Shipment.actual_delivery.is_(None)).order_by(Shipment.planned_delivery.asc()).limit(20).all()
        shipment_recs = []
        for s in shipments:
            try:
                ctx = shipment_context(db, company_id, s.id)
                live_score = ctx.get("live_risk", {}).get("live_risk_score", ctx["delay"]["delay_probability"])
                if live_score >= 0.7:
                    shipment_recs.append(ctx)
            except Exception:
                pass
        
        # Sort by live_risk_score descending
        shipment_recs.sort(key=lambda x: x.get("live_risk", {}).get("live_risk_score", x["delay"]["delay_probability"]), reverse=True)
        for ctx in shipment_recs[:10]:
            live_score = ctx.get("live_risk", {}).get("live_risk_score", ctx["delay"]["delay_probability"])
            title = f"Expedite Shipment {ctx['shipment']['external_id']}"
            shortage = ctx['inventory_impact']['expected_shortage']
            price = price_map.get(ctx['shipment']['product_id'], 0)
            lost_revenue = shortage * price
            
            reason = f"{(live_score*100):.0f}% live risk of delay for {ctx['shipment']['product_name']}."
            if lost_revenue > 0:
                impact = f"Prevents ${lost_revenue:,.2f} lost revenue."
            else:
                impact = f"Prevents shortage of {shortage} units."
                
            recs.append({
                "priority": "critical" if ctx['inventory_impact']['stockout_risk'] in ("HIGH", "CRITICAL") else "high",
                "type": "shipment",
                "title": title,
                "reason": reason,
                "expected_impact": impact,
                "affected_entity": ctx['shipment']['product_name'] or str(ctx['shipment']['product_id']),
                "shipment_id": ctx['shipment']['id']
            })
    except Exception:
        pass
        
    return sorted(recs, key=lambda x: {"critical":0,"high":1,"medium":2,"low":3}.get(x["priority"],2))[:30]
