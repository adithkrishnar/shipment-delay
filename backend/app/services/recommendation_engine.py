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
    for r in inv:
        if r["stockout_risk"] in {"HIGH","CRITICAL"}:
            recs.append({"priority":r["stockout_risk"].lower(),"type":"inventory","title":f"Replenish {r['product_name']}","reason":f"Stockout probability is {r['stockout_probability']*100:.0f}% with {r['inventory_coverage_days'] or 0:.1f} days of coverage.","expected_impact":f"Order approximately {r['recommended_order_quantity']} units to restore the target inventory horizon.","affected_entity":r['product_name'],"product_id":r['product_id']})
        elif r["overstock_risk"] in {"HIGH","CRITICAL"}:
            recs.append({"priority":"medium","type":"inventory","title":f"Review overstock of {r['product_name']}","reason":f"Inventory coverage is high relative to recent demand.","expected_impact":"Reduce holding-cost exposure by aligning replenishment with forecast demand.","affected_entity":r['product_name'],"product_id":r['product_id']})
    for s in analyze_suppliers(db, company_id):
        if s["risk_tier"] in {"HIGH","CRITICAL"}:
            recs.append({"priority":s["risk_tier"].lower(),"type":"supplier","title":f"Review supplier {s['name']}","reason":f"Supplier risk score is {s['risk_score']}/100 with {s['delay_rate']*100:.0f}% historical delay rate.","expected_impact":"Consider alternate sourcing or increased safety stock.","affected_entity":s['name'],"supplier_id":s['supplier_id']})
    anomalies=detect_anomalies(db, company_id, 20)
    for a in anomalies[:5]:
        recs.append({"priority":"high" if a['severity']=='CRITICAL' else "medium","type":"anomaly","title":f"Investigate {a['entity_type']} anomaly","reason":a['explanation'],"expected_impact":"Validate the underlying event before it distorts planning decisions.","affected_entity":str(a['entity_id'])})
    return sorted(recs, key=lambda x:{"critical":0,"high":1,"medium":2,"low":3}.get(x["priority"],2))[:30]
