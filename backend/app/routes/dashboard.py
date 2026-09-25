from app.auth.deps import get_current_user
from app.models.user import User
from datetime import date
import json
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Company, Product, Sale, Shipment, Supplier, InventoryRecord
from app.services.inventory_intelligence import company_inventory, inventory_summary
from app.services.supplier_intelligence import analyze_suppliers
from app.services.recommendation_engine import generate_recommendations
from app.services.explain_service import generate_situation_explanation
router = APIRouter(prefix='/api/dashboard', tags=['dashboard'])

@router.get('/{company_id}')
def dashboard(company_id: int, db: Session=Depends(get_db), *, current_user: User=Depends(get_current_user)):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's data")
    c = db.query(Company).filter(Company.id == company_id).first()
    if not c:
        raise HTTPException(404, 'Company not found')
    products = db.query(Product).filter(Product.company_id == company_id).count()
    shipments = db.query(Shipment).filter(Shipment.company_id == company_id).all()
    suppliers = analyze_suppliers(db, company_id)
    inv = company_inventory(db, company_id)
    risk_counts = {'LOW': 0, 'MEDIUM': 0, 'HIGH': 0, 'CRITICAL': 0}
    try:
        from app.services.model_training_service import get_active_shipment_models
        from app.ml.shipment_delay import predict_shipment_risk_batch
        import pandas as pd
        clf, dur, entry = get_active_shipment_models(db, company_id)
        if shipments:
            supplier_ids = list({s.supplier_id for s in shipments[:200]})
            suppliers_db = db.query(Supplier).filter(Supplier.id.in_(supplier_ids)).all()
            sup_map = {sup.id: sup for sup in suppliers_db}
            rows = []
            for s in shipments[:200]:
                sup = sup_map.get(s.supplier_id)
                rows.append({'shipment_id': s.id, 'external_shipment_id': s.external_shipment_id, 'product_id': s.product_id, 'supplier_id': s.supplier_id, 'origin': s.origin, 'destination': s.destination, 'carrier': s.carrier, 'transport_mode': s.transport_mode, 'distance_km': s.distance_km, 'weight_kg': s.weight_kg, 'quantity': s.quantity, 'order_date': s.order_date, 'planned_delivery': s.planned_delivery, 'actual_delivery': None, 'supplier_lead_time_days': sup.lead_time_days if sup else None, 'supplier_reliability': sup.reliability if sup else None, 'supplier_cost_index': sup.cost_index if sup else None})
            df = pd.DataFrame(rows)
            batch_risks = predict_shipment_risk_batch(clf, dur, df)
            for risk in batch_risks:
                tier = risk['risk_tier']
                risk_counts[tier] = risk_counts.get(tier, 0) + 1
    except Exception:
        entry = None
    has_inventory = db.query(InventoryRecord).filter(InventoryRecord.company_id == company_id).first() is not None
    total_inventory = sum((x['inventory_level'] for x in inv)) if has_inventory else 0
    products_db = db.query(Product).filter(Product.company_id == company_id).all()
    product_costs = {p.id: float(p.unit_cost or 0) for p in products_db}
    inv_value = sum((x['inventory_level'] * product_costs.get(x['product_id'], 0) for x in inv)) if has_inventory else 0
    recommendations = generate_recommendations(db, company_id)
    
    # Do not penalize health for missing data, only for actual risks
    stockout_risks = inventory_summary(inv).get('stockout_high', 0) if has_inventory else 0
    health = max(0, min(100, 100 - risk_counts.get('CRITICAL', 0) * 3 - risk_counts.get('HIGH', 0) * 1.5 - stockout_risks * 2))
    
    return {
        'company': {'id': c.id, 'name': c.name, 'industry': c.industry, 'currency': c.default_currency}, 
        'kpis': {
            'products': products, 
            'shipments': len(shipments), 
            'has_shipments': len(shipments) > 0,
            'high_risk_shipments': risk_counts.get('HIGH', 0) + risk_counts.get('CRITICAL', 0) if len(shipments) > 0 else None, 
            'stockout_risks': stockout_risks if has_inventory else None, 
            'inventory_units': round(total_inventory, 2) if has_inventory else None, 
            'has_inventory': has_inventory,
            'inventory_value': round(inv_value, 2) if has_inventory else None, 
            'supply_chain_health': round(health, 1), 
            'supplier_count': len(suppliers)
        }, 
        'shipment_risk_distribution': risk_counts if len(shipments) > 0 else {}, 
        'inventory_summary': inventory_summary(inv) if has_inventory else {}, 
        'top_suppliers': suppliers[:6], 
        'top_recommendations': recommendations[:6], 
        'model_source': entry.model_source if entry else None
    }

@router.get('/{company_id}/explain')
def explain_dashboard(company_id: int, db: Session=Depends(get_db), *, current_user: User=Depends(get_current_user)):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's data")
    data = dashboard(company_id, db, current_user=current_user)
    explanation = generate_situation_explanation(kpis=data.get('kpis', {}), risk_counts=data.get('shipment_risk_distribution', {}), inventory_summary=data.get('inventory_summary', {}), recommendations=data.get('top_recommendations', []))
    return {'explanation': explanation}