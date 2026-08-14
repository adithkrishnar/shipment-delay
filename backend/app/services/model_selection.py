"""
Data sufficiency check used to decide whether a company has enough
historical data to justify training its OWN model, or whether it should
fall back to the shared base model.

See spec section "MODEL PERSONALIZATION". Thresholds are configurable via
app.config.settings so they can be tuned without touching this logic.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Sale, Shipment


@dataclass
class DataSufficiency:
    record_count: int
    history_days: int
    is_sufficient: bool
    reason: str


def check_demand_data_sufficiency(db: Session, company_id: int) -> DataSufficiency:
    record_count = db.query(func.count(Sale.id)).filter(Sale.company_id == company_id).scalar() or 0
    date_bounds = (
        db.query(func.min(Sale.date), func.max(Sale.date)).filter(Sale.company_id == company_id).first()
    )
    if not date_bounds or not date_bounds[0]:
        return DataSufficiency(0, 0, False, "No sales history uploaded yet.")

    history_days = (date_bounds[1] - date_bounds[0]).days

    enough_records = record_count >= settings.MIN_RECORDS_FOR_COMPANY_MODEL
    enough_history = history_days >= settings.MIN_HISTORY_DAYS_FOR_COMPANY_MODEL

    is_sufficient = enough_records and enough_history
    if is_sufficient:
        reason = f"{record_count} records over {history_days} days meets the threshold for a company-specific model."
    else:
        missing = []
        if not enough_records:
            missing.append(f"needs >= {settings.MIN_RECORDS_FOR_COMPANY_MODEL} records (has {record_count})")
        if not enough_history:
            missing.append(f"needs >= {settings.MIN_HISTORY_DAYS_FOR_COMPANY_MODEL} days of history (has {history_days})")
        reason = "Insufficient data for a company-specific model: " + "; ".join(missing) + ". Using base model."

    return DataSufficiency(record_count, history_days, is_sufficient, reason)


def check_shipment_data_sufficiency(db: Session, company_id: int) -> DataSufficiency:
    """Same idea as check_demand_data_sufficiency, but counting COMPLETED shipments (have an actual_delivery)."""
    completed = (
        db.query(Shipment)
        .filter(Shipment.company_id == company_id, Shipment.actual_delivery.isnot(None))
        .all()
    )
    record_count = len(completed)
    if record_count == 0:
        return DataSufficiency(0, 0, False, "No completed shipment history uploaded yet.")

    order_dates = [s.order_date for s in completed if s.order_date is not None]
    if not order_dates:
        return DataSufficiency(record_count, 0, False, "Shipments have no order_date to measure history span.")

    history_days = (max(order_dates) - min(order_dates)).days

    enough_records = record_count >= settings.MIN_SHIPMENT_RECORDS_FOR_COMPANY_MODEL
    enough_history = history_days >= settings.MIN_HISTORY_DAYS_FOR_COMPANY_MODEL

    is_sufficient = enough_records and enough_history
    if is_sufficient:
        reason = f"{record_count} completed shipments over {history_days} days meets the threshold for a company-specific model."
    else:
        missing = []
        if not enough_records:
            missing.append(f"needs >= {settings.MIN_SHIPMENT_RECORDS_FOR_COMPANY_MODEL} completed shipments (has {record_count})")
        if not enough_history:
            missing.append(f"needs >= {settings.MIN_HISTORY_DAYS_FOR_COMPANY_MODEL} days of history (has {history_days})")
        reason = "Insufficient data for a company-specific model: " + "; ".join(missing) + ". Using base model."

    return DataSufficiency(record_count, history_days, is_sufficient, reason)
