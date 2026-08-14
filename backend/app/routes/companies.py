from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, Product, Sale, Shipment, Supplier
from app.schemas.company import CompanyCreate, CompanyOut, CompanySummaryOut
from app.utils.logging_config import get_logger

router = APIRouter(prefix="/api/companies", tags=["companies"])
logger = get_logger(__name__)


@router.get("", response_model=list[CompanySummaryOut])
def list_companies(db: Session = Depends(get_db)):
    companies = db.query(Company).order_by(Company.name).all()
    out = []
    for c in companies:
        product_count = db.query(func.count(Product.id)).filter(Product.company_id == c.id).scalar() or 0
        supplier_count = db.query(func.count(Supplier.id)).filter(Supplier.company_id == c.id).scalar() or 0
        sales_count = db.query(func.count(Sale.id)).filter(Sale.company_id == c.id).scalar() or 0
        shipment_count = db.query(func.count(Shipment.id)).filter(Shipment.company_id == c.id).scalar() or 0
        date_bounds = (
            db.query(func.min(Sale.date), func.max(Sale.date)).filter(Sale.company_id == c.id).first()
        )
        out.append(CompanySummaryOut(
            id=c.id, name=c.name, industry=c.industry, is_demo=c.is_demo,
            default_currency=c.default_currency, created_at=c.created_at,
            product_count=product_count, supplier_count=supplier_count,
            sales_record_count=sales_count, shipment_count=shipment_count,
            date_range_start=str(date_bounds[0]) if date_bounds and date_bounds[0] else None,
            date_range_end=str(date_bounds[1]) if date_bounds and date_bounds[1] else None,
        ))
    return out


@router.post("", response_model=CompanyOut, status_code=201)
def create_company(payload: CompanyCreate, db: Session = Depends(get_db)):
    existing = db.query(Company).filter(Company.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"A company named '{payload.name}' already exists.")
    company = Company(
        name=payload.name,
        industry=payload.industry,
        default_currency=payload.default_currency,
        notes=payload.notes,
        is_demo=0,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    logger.info("Created company id=%s name=%s", company.id, company.name)
    return company


@router.get("/{company_id}", response_model=CompanyOut)
def get_company(company_id: int, db: Session = Depends(get_db)):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    return company
