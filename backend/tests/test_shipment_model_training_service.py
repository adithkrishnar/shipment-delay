import datetime as dt

import numpy as np
import pytest

from app.models import Company, Product, Shipment, Supplier
from app.services.model_training_service import (
    ensure_company_has_shipment_models,
    get_active_shipment_models,
    train_base_shipment_models,
    train_company_shipment_models,
)


def _seed_company_shipments(db, name: str, n_shipments: int, history_days: int, seed: int = 1):
    rng = np.random.default_rng(seed)
    company = Company(name=name, industry="Test", is_demo=0)
    db.add(company)
    db.flush()

    product = Product(company_id=company.id, external_product_id="P1", name="Product 1")
    db.add(product)
    supplier = Supplier(
        company_id=company.id, external_supplier_id="SUP-1", name="Supplier 1",
        lead_time_days=10, reliability=0.7, cost_index=1.0,
    )
    db.add(supplier)
    db.flush()

    start = dt.date.today() - dt.timedelta(days=history_days)
    step = max(1, history_days // max(n_shipments, 1))
    for i in range(n_shipments):
        order_date = start + dt.timedelta(days=(i * step) % history_days)
        planned = order_date + dt.timedelta(days=10)
        is_delayed = rng.random() < 0.3
        actual = planned + dt.timedelta(days=int(rng.exponential(3)) + 1 if is_delayed else 0)
        db.add(Shipment(
            company_id=company.id, product_id=product.id, supplier_id=supplier.id,
            external_shipment_id=f"SHP-{i}", origin="Mumbai", destination="Delhi",
            carrier="CarrierX", transport_mode="road", distance_km=1400, weight_kg=500, quantity=100,
            order_date=order_date, planned_delivery=planned, actual_delivery=actual,
        ))
    db.commit()
    return company


def test_train_company_shipment_models_skipped_when_below_threshold(db_session):
    company = _seed_company_shipments(db_session, "Small Shipper", n_shipments=50, history_days=100)
    clf_entry, dur_entry, reason = train_company_shipment_models(db_session, company.id)
    assert clf_entry is None
    assert "Insufficient" in reason


def test_train_company_shipment_models_succeeds_above_threshold(db_session):
    company = _seed_company_shipments(db_session, "Big Shipper", n_shipments=400, history_days=400)
    clf_entry, dur_entry, reason = train_company_shipment_models(db_session, company.id)
    assert clf_entry is not None
    assert clf_entry.model_source == "company_specific"
    assert clf_entry.model_type == "delay_classifier"


def test_get_active_shipment_models_falls_back_to_base(db_session):
    small = _seed_company_shipments(db_session, "Fallback Shipper", n_shipments=50, history_days=100, seed=1)
    _seed_company_shipments(db_session, "Big Shipper Co", n_shipments=400, history_days=400, seed=2)

    train_base_shipment_models(db_session)

    classifier, duration_model, entry = get_active_shipment_models(db_session, small.id)
    assert entry.model_source == "base"
    assert entry.company_id is None


def test_get_active_shipment_models_prefers_company_specific(db_session):
    company = _seed_company_shipments(db_session, "Preferred Shipper", n_shipments=400, history_days=400)
    train_base_shipment_models(db_session)
    train_company_shipment_models(db_session, company.id)

    classifier, duration_model, entry = get_active_shipment_models(db_session, company.id)
    assert entry.model_source == "company_specific"
    assert entry.company_id == company.id


def test_get_active_shipment_models_raises_when_nothing_trained(db_session):
    company = _seed_company_shipments(db_session, "Untrained Shipper", n_shipments=50, history_days=100)
    with pytest.raises(FileNotFoundError):
        get_active_shipment_models(db_session, company.id)


def test_ensure_company_has_shipment_models_trains_base_as_last_resort(db_session):
    company = _seed_company_shipments(db_session, "Needs Fallback Shipper", n_shipments=50, history_days=100)
    entry = ensure_company_has_shipment_models(db_session, company.id)
    assert entry is not None
    assert entry.model_source == "base"
