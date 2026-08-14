from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Company, Product
from app.services.inventory_intelligence import company_inventory, analyze_product, inventory_summary
from app.services.supplier_intelligence import analyze_suppliers
from app.services.anomaly_detection import detect_anomalies
from app.services.risk_engine import shipment_context

router=APIRouter(prefix="/api/intelligence",tags=["intelligence"])

def company_or_404(db, company_id):
    c=db.query(Company).filter(Company.id==company_id).first()
    if not c: raise HTTPException(404,"Company not found")
    return c

@router.get("/{company_id}/inventory")
def inventory(company_id:int, db:Session=Depends(get_db)):
    company_or_404(db,company_id); rows=company_inventory(db,company_id); return {"company_id":company_id,"summary":inventory_summary(rows),"products":rows}

@router.get("/{company_id}/inventory/{product_id}")
def inventory_product(company_id:int,product_id:int,db:Session=Depends(get_db)):
    company_or_404(db,company_id)
    try:return analyze_product(db,company_id,product_id)
    except ValueError as e: raise HTTPException(404,str(e))

@router.get("/{company_id}/suppliers")
def suppliers(company_id:int,db:Session=Depends(get_db)):
    company_or_404(db,company_id); return {"company_id":company_id,"suppliers":analyze_suppliers(db,company_id)}

@router.get("/{company_id}/anomalies")
def anomalies(company_id:int,limit:int=Query(100,ge=1,le=500),db:Session=Depends(get_db)):
    company_or_404(db,company_id); return {"company_id":company_id,"anomalies":detect_anomalies(db,company_id,limit)}

@router.get("/{company_id}/shipments/{shipment_id}/impact")
def shipment_impact(company_id:int,shipment_id:int,db:Session=Depends(get_db)):
    company_or_404(db,company_id)
    try:return shipment_context(db,company_id,shipment_id)
    except (ValueError,FileNotFoundError) as e: raise HTTPException(400,str(e))
