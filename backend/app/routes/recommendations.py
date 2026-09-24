from app.auth.deps import get_current_user
from app.models.user import User
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Company
from app.services.recommendation_engine import generate_recommendations
router = APIRouter(prefix='/api/recommendations', tags=['recommendations'])

@router.get('/{company_id}')
def recommendations(company_id: int, db: Session=Depends(get_db), *, current_user: User=Depends(get_current_user)):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's data")
    if not db.query(Company).filter(Company.id == company_id).first():
        raise HTTPException(404, 'Company not found')
    return {'company_id': company_id, 'recommendations': generate_recommendations(db, company_id)}