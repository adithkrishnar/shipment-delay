from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session
from app.models import Shipment, Supplier


def analyze_suppliers(db: Session, company_id: int) -> list[dict]:
    suppliers = db.query(Supplier).filter(Supplier.company_id == company_id).all()
    results = []
    for s in suppliers:
        shipments = db.query(Shipment).filter(Shipment.company_id == company_id, Shipment.supplier_id == s.id).all()
        completed = [x for x in shipments if x.actual_delivery and x.planned_delivery]
        delays = [(x.actual_delivery - x.planned_delivery).days for x in completed]
        delay_rate = float(np.mean([d > 0 for d in delays])) if delays else max(0.0, 1.0 - float(s.reliability or 0.85))
        avg_delay = float(np.mean([max(0, d) for d in delays])) if delays else 0.0
        reliability = float(s.reliability if s.reliability is not None else max(0.0, 1 - delay_rate))
        defect = float(s.defect_rate or 0.0)
        cost = float(s.cost_index or 1.0)
        risk_score = float(np.clip((1-reliability)*60 + delay_rate*25 + defect*100*0.1 + max(0,cost-1)*10, 0, 100))
        risk = "CRITICAL" if risk_score >= 70 else "HIGH" if risk_score >= 45 else "MEDIUM" if risk_score >= 25 else "LOW"
        results.append({
            "supplier_id": s.id, "external_supplier_id": s.external_supplier_id, "name": s.name,
            "lead_time_days": round(float(s.lead_time_days or 0), 1), "reliability": round(reliability, 3),
            "cost_index": round(cost, 3), "defect_rate": round(defect, 4), "shipment_count": len(shipments),
            "completed_shipments": len(completed), "delay_rate": round(delay_rate, 4), "avg_delay_days": round(avg_delay, 2),
            "risk_score": round(risk_score, 1), "risk_tier": risk,
        })
    return sorted(results, key=lambda x: x["risk_score"])
