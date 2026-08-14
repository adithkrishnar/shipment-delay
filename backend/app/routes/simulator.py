from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Company, Product
from app.services.risk_engine import simulate

router=APIRouter(prefix="/api/simulator",tags=["simulator"])

class SimulationRequest(BaseModel):
    company_id:int
    product_id:int
    demand_multiplier:float=Field(1.0,ge=0.1,le=5)
    inventory_delta:float=Field(0.0,ge=-1_000_000,le=1_000_000)
    delay_days:float=Field(0.0,ge=0,le=365)
    lead_time_delta:float=Field(0.0,ge=-365,le=365)
    incoming_delta:float=Field(0.0,ge=-1_000_000,le=1_000_000)
    reorder_delta:float=Field(0.0,ge=-1_000_000,le=1_000_000)

@router.post("")
def run_simulation(req:SimulationRequest,db:Session=Depends(get_db)):
    if not db.query(Company).filter(Company.id==req.company_id).first(): raise HTTPException(404,"Company not found")
    if not db.query(Product).filter(Product.id==req.product_id,Product.company_id==req.company_id).first(): raise HTTPException(404,"Product not found")
    return simulate(db,**req.model_dump(exclude={"company_id","product_id"}),company_id=req.company_id,product_id=req.product_id)
