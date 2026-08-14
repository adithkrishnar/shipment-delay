import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Company, ModelRegistryEntry
from app.schemas.ml import BaseModelTrainError, ModelRegistryOut, ModelTrainOutcome, RetrainResponse, TrainBaseModelsResponse
from app.services.model_training_service import (
    get_active_demand_model,
    get_active_shipment_models,
    train_base_demand_model,
    train_base_shipment_models,
    train_company_demand_model,
    train_company_shipment_models,
)
from app.utils.logging_config import get_logger

router = APIRouter(prefix="/api/models", tags=["models"])
logger = get_logger(__name__)


def _to_registry_out(entry: ModelRegistryEntry) -> ModelRegistryOut:
    return ModelRegistryOut(
        id=entry.id, company_id=entry.company_id, model_type=entry.model_type,
        model_source=entry.model_source, version=entry.version, training_date=entry.training_date,
        dataset_size=entry.dataset_size, history_days=entry.history_days, status=entry.status,
        metrics=json.loads(entry.metrics_json) if entry.metrics_json else None,
    )


@router.post("/train/base", response_model=TrainBaseModelsResponse)
def train_base_model(db: Session = Depends(get_db)):
    """
    Trains every base model that currently has enough pooled data: the
    demand model (needs sales history somewhere) and the shipment delay
    classifier + duration model (needs shipment history somewhere). These
    are independent - if one has no data yet, the other still trains.
    """
    trained: list[ModelRegistryOut] = []
    errors: list[BaseModelTrainError] = []

    try:
        trained.append(_to_registry_out(train_base_demand_model(db)))
    except ValueError as exc:
        errors.append(BaseModelTrainError(model_type="demand_forecast", error=str(exc)))

    try:
        clf_entry, dur_entry = train_base_shipment_models(db)
        trained.append(_to_registry_out(clf_entry))
        if dur_entry:
            trained.append(_to_registry_out(dur_entry))
    except ValueError as exc:
        errors.append(BaseModelTrainError(model_type="delay_classifier", error=str(exc)))

    if not trained:
        raise HTTPException(status_code=400, detail="No base model could be trained: " + "; ".join(e.error for e in errors))

    return TrainBaseModelsResponse(trained=trained, errors=errors)


def _demand_outcome(db: Session, company_id: int) -> ModelTrainOutcome:
    entry, reason = train_company_demand_model(db, company_id)
    try:
        _, active = get_active_demand_model(db, company_id)
        return ModelTrainOutcome(
            trained_company_specific=entry is not None, reason=reason,
            active_model_source=active.model_source, registry_entry=_to_registry_out(active),
        )
    except FileNotFoundError as exc:
        return ModelTrainOutcome(
            trained_company_specific=False, reason=f"{reason} | {exc}",
            active_model_source=None, registry_entry=None,
        )


def _shipment_outcome(db: Session, company_id: int) -> ModelTrainOutcome:
    entry, _dur_entry, reason = train_company_shipment_models(db, company_id)
    try:
        _, _dur, active = get_active_shipment_models(db, company_id)
        return ModelTrainOutcome(
            trained_company_specific=entry is not None, reason=reason,
            active_model_source=active.model_source, registry_entry=_to_registry_out(active),
        )
    except FileNotFoundError as exc:
        return ModelTrainOutcome(
            trained_company_specific=False, reason=f"{reason} | {exc}",
            active_model_source=None, registry_entry=None,
        )


@router.post("/retrain/{company_id}", response_model=RetrainResponse)
def retrain_company_model(company_id: int, db: Session = Depends(get_db)):
    """
    Attempts to (re)train company-specific demand AND shipment models.
    These are INDEPENDENT: a company with shipment history but no sales
    history yet (or vice versa) still gets a successful response for
    whichever model type has data, rather than a single all-or-nothing
    failure.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    return RetrainResponse(
        company_id=company_id,
        demand=_demand_outcome(db, company_id),
        shipments=_shipment_outcome(db, company_id),
    )


@router.get("/{company_id}", response_model=list[ModelRegistryOut])
def list_models_for_company(company_id: int, db: Session = Depends(get_db)):
    """
    Lists every model relevant to a company: its own company-specific
    registry entries plus the current base model (which may be what's
    actually serving it).
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    own_entries = (
        db.query(ModelRegistryEntry)
        .filter(ModelRegistryEntry.company_id == company_id)
        .order_by(ModelRegistryEntry.training_date.desc())
        .all()
    )
    base_entries = (
        db.query(ModelRegistryEntry)
        .filter(ModelRegistryEntry.company_id.is_(None))
        .order_by(ModelRegistryEntry.training_date.desc())
        .all()
    )
    return [_to_registry_out(e) for e in (own_entries + base_entries)]
