from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.demo_data_generator import generate_demo_companies
from app.services.model_training_service import train_base_demand_model, train_base_shipment_models
from app.utils.logging_config import get_logger

router = APIRouter(prefix="/api/demo", tags=["demo"])
logger = get_logger(__name__)

@router.post("/seed")
def seed_demo_data(db: Session = Depends(get_db)):
    """Regenerate the three demo companies and train the shared base models."""
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
