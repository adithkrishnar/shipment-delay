from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.services.demo_data_generator import generate_demo_companies, seed_demo_for_company
from app.auth.deps import get_current_user
from app.models.user import User
from app.services.model_training_service import train_base_demand_model, train_base_shipment_models
from app.utils.logging_config import get_logger

router = APIRouter(prefix="/api/demo", tags=["demo"])
logger = get_logger(__name__)

oauth2_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def get_optional_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_optional),
) -> Optional[User]:
    if not token:
        return None
    try:
        from jose import jwt
        from app.auth.security import SECRET_KEY, ALGORITHM
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id:
            return db.query(User).filter(User.id == int(user_id)).first()
    except Exception:
        return None
    return None

@router.post("/seed")
def seed_demo_data(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
):
    """Regenerate the three demo companies and train the shared base models."""
    is_prod = str(settings.ENV).strip().lower() in ("production", "prod")
    if is_prod:
        if not current_user or not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security rejection: Global demo seeding in production environment requires active superuser authorization.",
            )
    logger.info("Seeding demo companies...")
    from app.models import Company
    demo_companies = db.query(Company).filter(Company.is_demo == 1).all()
    if len(demo_companies) == 3:
        return {"status": "ok", "message": "Demo data already exists", "companies": [{"id": c.id, "name": c.name} for c in demo_companies]}

    results = generate_demo_companies(db, reset=True)
    trained=[]; errors=[]
    try:
        trained.append(train_base_demand_model(db).model_type)
    except Exception as exc:
        logger.exception("Base demand model training failed")
        errors.append({"model":"demand_forecast","error":str(exc)})
    try:
        clf,dur=train_base_shipment_models(db)
        trained.append(clf.model_type)
        if dur: trained.append(dur.model_type)
    except Exception as exc:
        logger.exception("Base shipment model training failed")
        errors.append({"model":"shipment","error":str(exc)})
    return {"status":"ok","companies":results,"trained_models":trained,"training_errors":errors}

@router.post("/seed_mine")
def seed_mine_data(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Clear the current user's company data and replace it with Horizon Electronics demo data, then train models."""
    logger.info(f"Seeding demo data for company {current_user.company_id}...")
    
    # 1. Generate data for current user's company
    result = seed_demo_for_company(db, current_user.company_id)
    
    # 2. Train models specifically for this company now that it has sufficient data
    trained = []; errors = []
    
    from app.services.model_training_service import train_company_demand_model, train_company_shipment_models
    try:
        dm, msg = train_company_demand_model(db, current_user.company_id)
        if dm:
            trained.append(dm.model_type)
    except Exception as exc:
        logger.exception("Company demand model training failed")
        errors.append({"model": "demand_forecast", "error": str(exc)})
        
    try:
        clf, dur, msg = train_company_shipment_models(db, current_user.company_id)
        if clf:
            trained.append(clf.model_type)
        if dur:
            trained.append(dur.model_type)
    except Exception as exc:
        logger.exception("Company shipment model training failed")
        errors.append({"model": "shipment", "error": str(exc)})
        
    return {"status": "ok", "company": result, "trained_models": trained, "training_errors": errors}
