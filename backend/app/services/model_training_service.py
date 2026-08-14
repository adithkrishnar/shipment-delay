"""
Orchestrates training, versioning, registration, and retrieval of demand
forecasting models.

Two kinds of model, per spec section "MODEL PERSONALIZATION":
  - BASE model: trained by pooling sales across ALL companies. Not tied to
    any single company_id (NULL in the registry). Exists so a brand-new
    company with little/no history still gets real forecasts on day one.
  - COMPANY-SPECIFIC model: trained only on one company's own sales, and
    only attempted once that company clears the data-sufficiency threshold
    (see services/model_selection.py).

At serving time (get_active_demand_model), a company-specific active model
is preferred; if none exists yet, the shared base model is used instead.
Every ModelRegistryEntry records which one was used, so this is never silent.
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
from sqlalchemy.orm import Session

from app.config import settings
from app.ml.demand_forecasting import TrainedDemandModel, load_model, save_model, train_demand_model
from app.ml.shipment_delay import (
    TrainedDelayClassifier,
    TrainedDelayDurationModel,
)
from app.ml.shipment_delay import load_model as load_shipment_model
from app.ml.shipment_delay import save_model as save_shipment_model
from app.ml.shipment_delay import train_delay_classifier, train_delay_duration_model
from app.models import Company, ModelRegistryEntry, Sale, Shipment, Supplier
from app.services.model_selection import check_demand_data_sufficiency, check_shipment_data_sufficiency
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

MODEL_TYPE_DEMAND = "demand_forecast"
MODEL_TYPE_DELAY_CLASSIFIER = "delay_classifier"
MODEL_TYPE_DELAY_DURATION = "delay_duration"


def _sales_dataframe(db: Session, company_id: int | None) -> pd.DataFrame:
    query = db.query(Sale.product_id, Sale.date, Sale.quantity, Sale.promotion)
    if company_id is not None:
        query = query.filter(Sale.company_id == company_id)
    rows = query.all()
    return pd.DataFrame(rows, columns=["product_id", "date", "quantity", "promotion"])


_SHIPMENT_COLS = [
    "shipment_id", "external_shipment_id", "product_id", "supplier_id", "origin", "destination",
    "carrier", "transport_mode", "distance_km", "weight_kg", "quantity",
    "order_date", "planned_delivery", "actual_delivery",
    "supplier_lead_time_days", "supplier_reliability", "supplier_cost_index",
]


def _shipments_dataframe(db: Session, company_id: int | None) -> pd.DataFrame:
    query = (
        db.query(
            Shipment.id, Shipment.external_shipment_id, Shipment.product_id, Shipment.supplier_id,
            Shipment.origin, Shipment.destination, Shipment.carrier, Shipment.transport_mode,
            Shipment.distance_km, Shipment.weight_kg, Shipment.quantity,
            Shipment.order_date, Shipment.planned_delivery, Shipment.actual_delivery,
            Supplier.lead_time_days, Supplier.reliability, Supplier.cost_index,
        )
        .join(Supplier, Shipment.supplier_id == Supplier.id)
    )
    if company_id is not None:
        query = query.filter(Shipment.company_id == company_id)
    rows = query.all()
    return pd.DataFrame(rows, columns=_SHIPMENT_COLS)


def _next_version(db: Session, company_id: int | None, model_type: str) -> str:
    count = (
        db.query(ModelRegistryEntry)
        .filter(ModelRegistryEntry.company_id == company_id, ModelRegistryEntry.model_type == model_type)
        .count()
    )
    return f"v{count + 1}"


def _archive_previous_active(db: Session, company_id: int | None, model_type: str) -> None:
    active_entries = (
        db.query(ModelRegistryEntry)
        .filter(
            ModelRegistryEntry.company_id == company_id,
            ModelRegistryEntry.model_type == model_type,
            ModelRegistryEntry.status == "active",
        )
        .all()
    )
    for entry in active_entries:
        entry.status = "archived"


def _register_model(
    db: Session,
    company_id: int | None,
    model_type: str,
    model_source: str,
    dataset_size: int,
    history_days: int,
    metrics: dict,
    model_path: str,
) -> ModelRegistryEntry:
    _archive_previous_active(db, company_id, model_type)
    entry = ModelRegistryEntry(
        company_id=company_id,
        model_type=model_type,
        model_source=model_source,
        version=_next_version(db, company_id, model_type),
        training_date=dt.datetime.utcnow(),
        dataset_size=dataset_size,
        history_days=history_days,
        metrics_json=json.dumps(metrics),
        model_path=model_path,
        status="active",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def train_base_demand_model(db: Session) -> ModelRegistryEntry:
    """Trains the shared base demand model by pooling sales across every company."""
    sales_df = _sales_dataframe(db, company_id=None)
    if sales_df.empty:
        raise ValueError("No sales data exists anywhere yet - cannot train the base model.")

    trained = train_demand_model(sales_df)

    model_dir = settings.TRAINED_MODELS_DIR / "base"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "demand_model.pkl"
    save_model(trained, model_path)

    history_days = (pd.to_datetime(sales_df["date"]).max() - pd.to_datetime(sales_df["date"]).min()).days
    entry = _register_model(
        db, company_id=None, model_type=MODEL_TYPE_DEMAND, model_source="base",
        dataset_size=len(sales_df), history_days=int(history_days),
        metrics=trained.metrics, model_path=str(model_path),
    )
    logger.info("Trained BASE demand model: %s rows, selected=%s", len(sales_df), trained.model_name)
    return entry


def train_company_demand_model(db: Session, company_id: int) -> tuple[ModelRegistryEntry | None, str]:
    """
    Attempts to train a company-specific demand model.

    Returns (entry, message). entry is None if the company doesn't yet have
    enough data - the caller should fall back to the base model in that case.
    """
    sufficiency = check_demand_data_sufficiency(db, company_id)
    if not sufficiency.is_sufficient:
        logger.info("Company %s insufficient for company-specific model: %s", company_id, sufficiency.reason)
        return None, sufficiency.reason

    sales_df = _sales_dataframe(db, company_id=company_id)
    trained = train_demand_model(sales_df)

    model_dir = settings.TRAINED_MODELS_DIR / f"company_{company_id}"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "demand_model.pkl"
    save_model(trained, model_path)

    entry = _register_model(
        db, company_id=company_id, model_type=MODEL_TYPE_DEMAND, model_source="company_specific",
        dataset_size=sufficiency.record_count, history_days=sufficiency.history_days,
        metrics=trained.metrics, model_path=str(model_path),
    )
    logger.info(
        "Trained COMPANY-SPECIFIC demand model for company_id=%s: %s rows, selected=%s",
        company_id, len(sales_df), trained.model_name,
    )
    return entry, sufficiency.reason


def get_active_demand_model(db: Session, company_id: int) -> tuple[TrainedDemandModel, ModelRegistryEntry]:
    """
    Returns the model that should actually serve forecasts for this company:
    its own active company-specific model if one exists, otherwise the
    shared base model.
    """
    company_entry = (
        db.query(ModelRegistryEntry)
        .filter(
            ModelRegistryEntry.company_id == company_id,
            ModelRegistryEntry.model_type == MODEL_TYPE_DEMAND,
            ModelRegistryEntry.status == "active",
        )
        .order_by(ModelRegistryEntry.training_date.desc())
        .first()
    )
    if company_entry:
        return load_model(company_entry.model_path), company_entry

    base_entry = (
        db.query(ModelRegistryEntry)
        .filter(
            ModelRegistryEntry.company_id.is_(None),
            ModelRegistryEntry.model_type == MODEL_TYPE_DEMAND,
            ModelRegistryEntry.status == "active",
        )
        .order_by(ModelRegistryEntry.training_date.desc())
        .first()
    )
    if base_entry:
        return load_model(base_entry.model_path), base_entry

    raise FileNotFoundError(
        "No demand forecasting model available for this company and no base model has been trained yet. "
        "Call POST /api/models/train/base first."
    )


def ensure_company_has_a_model(db: Session, company_id: int) -> ModelRegistryEntry:
    """
    Convenience used right after a data import: try a company-specific model;
    if data is still insufficient, make sure at least the base model exists
    so forecasts don't hard-fail.
    """
    entry, _ = train_company_demand_model(db, company_id)
    if entry:
        return entry

    base_entry = (
        db.query(ModelRegistryEntry)
        .filter(ModelRegistryEntry.company_id.is_(None), ModelRegistryEntry.model_type == MODEL_TYPE_DEMAND)
        .first()
    )
    if not base_entry:
        return train_base_demand_model(db)
    return base_entry


# ---------------------------------------------------------------------------
# Shipment delay classifier + delay duration regressor
# (mirrors the demand-forecasting base/company-specific pattern above)
# ---------------------------------------------------------------------------

def train_base_shipment_models(db: Session) -> tuple[ModelRegistryEntry, ModelRegistryEntry | None]:
    """Trains the shared base delay classifier (and duration model, if enough delayed shipments exist)."""
    shipments_df = _shipments_dataframe(db, company_id=None)
    if shipments_df.empty:
        raise ValueError("No shipment data exists anywhere yet - cannot train the base shipment models.")

    clf = train_delay_classifier(shipments_df)
    model_dir = settings.TRAINED_MODELS_DIR / "base"
    model_dir.mkdir(parents=True, exist_ok=True)
    clf_path = model_dir / "delay_classifier.pkl"
    save_shipment_model(clf, clf_path)

    completed = shipments_df[shipments_df["actual_delivery"].notna()]
    history_days = (pd.to_datetime(completed["order_date"]).max() - pd.to_datetime(completed["order_date"]).min()).days

    clf_entry = _register_model(
        db, company_id=None, model_type=MODEL_TYPE_DELAY_CLASSIFIER, model_source="base",
        dataset_size=len(completed), history_days=int(history_days),
        metrics=clf.metrics, model_path=str(clf_path),
    )

    dur_entry = None
    try:
        dur = train_delay_duration_model(shipments_df)
        dur_path = model_dir / "delay_duration.pkl"
        save_shipment_model(dur, dur_path)
        dur_entry = _register_model(
            db, company_id=None, model_type=MODEL_TYPE_DELAY_DURATION, model_source="base",
            dataset_size=len(completed), history_days=int(history_days),
            metrics=dur.metrics, model_path=str(dur_path),
        )
    except ValueError as exc:
        logger.info("Base delay-duration model skipped: %s", exc)

    logger.info("Trained BASE shipment models: %s completed shipments, classifier=%s", len(completed), clf.model_name)
    return clf_entry, dur_entry


def train_company_shipment_models(db: Session, company_id: int) -> tuple[ModelRegistryEntry | None, ModelRegistryEntry | None, str]:
    """Attempts company-specific delay classifier + duration model. Returns (clf_entry, dur_entry, reason)."""
    sufficiency = check_shipment_data_sufficiency(db, company_id)
    if not sufficiency.is_sufficient:
        logger.info("Company %s insufficient for company-specific shipment models: %s", company_id, sufficiency.reason)
        return None, None, sufficiency.reason

    shipments_df = _shipments_dataframe(db, company_id=company_id)
    model_dir = settings.TRAINED_MODELS_DIR / f"company_{company_id}"
    model_dir.mkdir(parents=True, exist_ok=True)

    try:
        clf = train_delay_classifier(shipments_df)
    except ValueError as exc:
        return None, None, f"Classifier training failed despite passing sufficiency check: {exc}"

    clf_path = model_dir / "delay_classifier.pkl"
    save_shipment_model(clf, clf_path)
    clf_entry = _register_model(
        db, company_id=company_id, model_type=MODEL_TYPE_DELAY_CLASSIFIER, model_source="company_specific",
        dataset_size=sufficiency.record_count, history_days=sufficiency.history_days,
        metrics=clf.metrics, model_path=str(clf_path),
    )

    dur_entry = None
    try:
        dur = train_delay_duration_model(shipments_df)
        dur_path = model_dir / "delay_duration.pkl"
        save_shipment_model(dur, dur_path)
        dur_entry = _register_model(
            db, company_id=company_id, model_type=MODEL_TYPE_DELAY_DURATION, model_source="company_specific",
            dataset_size=sufficiency.record_count, history_days=sufficiency.history_days,
            metrics=dur.metrics, model_path=str(dur_path),
        )
    except ValueError as exc:
        logger.info("Company %s delay-duration model skipped: %s", company_id, exc)

    logger.info("Trained COMPANY-SPECIFIC shipment models for company_id=%s: classifier=%s", company_id, clf.model_name)
    return clf_entry, dur_entry, sufficiency.reason


def get_active_shipment_models(db: Session, company_id: int) -> tuple[TrainedDelayClassifier, TrainedDelayDurationModel | None, ModelRegistryEntry]:
    """Returns (classifier, duration_model_or_None, classifier_registry_entry) - company-specific preferred, else base."""
    clf_entry = (
        db.query(ModelRegistryEntry)
        .filter(
            ModelRegistryEntry.company_id == company_id,
            ModelRegistryEntry.model_type == MODEL_TYPE_DELAY_CLASSIFIER,
            ModelRegistryEntry.status == "active",
        )
        .order_by(ModelRegistryEntry.training_date.desc())
        .first()
    )
    source_company_id = company_id
    if not clf_entry:
        clf_entry = (
            db.query(ModelRegistryEntry)
            .filter(
                ModelRegistryEntry.company_id.is_(None),
                ModelRegistryEntry.model_type == MODEL_TYPE_DELAY_CLASSIFIER,
                ModelRegistryEntry.status == "active",
            )
            .order_by(ModelRegistryEntry.training_date.desc())
            .first()
        )
        source_company_id = None

    if not clf_entry:
        raise FileNotFoundError(
            "No shipment delay classifier available for this company and no base model has been trained yet. "
            "Call POST /api/models/train/base first."
        )

    classifier = load_shipment_model(clf_entry.model_path)

    dur_entry = (
        db.query(ModelRegistryEntry)
        .filter(
            ModelRegistryEntry.company_id == source_company_id,
            ModelRegistryEntry.model_type == MODEL_TYPE_DELAY_DURATION,
            ModelRegistryEntry.status == "active",
        )
        .order_by(ModelRegistryEntry.training_date.desc())
        .first()
    )
    duration_model = load_shipment_model(dur_entry.model_path) if dur_entry else None

    return classifier, duration_model, clf_entry


def ensure_company_has_shipment_models(db: Session, company_id: int) -> ModelRegistryEntry:
    """Same convenience pattern as ensure_company_has_a_model, but for shipment models."""
    clf_entry, _dur_entry, _reason = train_company_shipment_models(db, company_id)
    if clf_entry:
        return clf_entry

    base_entry = (
        db.query(ModelRegistryEntry)
        .filter(ModelRegistryEntry.company_id.is_(None), ModelRegistryEntry.model_type == MODEL_TYPE_DELAY_CLASSIFIER)
        .first()
    )
    if not base_entry:
        clf_entry, _ = train_base_shipment_models(db)
        return clf_entry
    return base_entry
