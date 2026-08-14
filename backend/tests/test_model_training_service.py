import datetime as dt

import numpy as np
import pytest

from app.models import Company, Product, Sale
from app.services.model_training_service import (
    ensure_company_has_a_model,
    get_active_demand_model,
    train_base_demand_model,
    train_company_demand_model,
)


def _seed_company_sales(db, name: str, n_days: int, n_products: int = 3, seed: int = 1):
    rng = np.random.default_rng(seed)
    company = Company(name=name, industry="Test", is_demo=0)
    db.add(company)
    db.flush()

    start = dt.date.today() - dt.timedelta(days=n_days)
    for p in range(n_products):
        product = Product(company_id=company.id, external_product_id=f"P{p+1}", name=f"Product {p+1}")
        db.add(product)
        db.flush()
        base = rng.uniform(30, 100)
        for i in range(n_days):
            d = start + dt.timedelta(days=i)
            qty = max(0, base + 10 * np.sin(i / 7) + rng.normal(0, 5))
            db.add(Sale(company_id=company.id, product_id=product.id, date=d, quantity=qty, promotion=0))
    db.commit()
    return company


def test_train_company_model_skipped_when_below_threshold(db_session):
    # 50 days * 2 products = 100 records, well below MIN_RECORDS_FOR_COMPANY_MODEL (3000)
    company = _seed_company_sales(db_session, "Small Co", n_days=50, n_products=2)
    entry, reason = train_company_demand_model(db_session, company.id)
    assert entry is None
    assert "Insufficient" in reason


def test_train_company_model_succeeds_when_above_threshold(db_session):
    # 400 days * 10 products = 4000 records, above the 3000 threshold, and 400 days > 180
    company = _seed_company_sales(db_session, "Big Co", n_days=400, n_products=10)
    entry, reason = train_company_demand_model(db_session, company.id)
    assert entry is not None
    assert entry.model_source == "company_specific"
    assert entry.status == "active"


def test_get_active_model_falls_back_to_base_when_no_company_model(db_session):
    small_co = _seed_company_sales(db_session, "Fallback Co", n_days=50, n_products=2)
    big_co = _seed_company_sales(db_session, "Other Co", n_days=400, n_products=10, seed=2)

    train_base_demand_model(db_session)  # pools both companies

    trained, entry = get_active_demand_model(db_session, small_co.id)
    assert entry.model_source == "base"
    assert entry.company_id is None


def test_get_active_model_prefers_company_specific_when_available(db_session):
    company = _seed_company_sales(db_session, "Preferred Co", n_days=400, n_products=10)
    train_base_demand_model(db_session)
    train_company_demand_model(db_session, company.id)

    trained, entry = get_active_demand_model(db_session, company.id)
    assert entry.model_source == "company_specific"
    assert entry.company_id == company.id


def test_get_active_model_raises_when_nothing_trained_at_all(db_session):
    company = _seed_company_sales(db_session, "Untrained Co", n_days=50, n_products=1)
    with pytest.raises(FileNotFoundError):
        get_active_demand_model(db_session, company.id)


def test_ensure_company_has_a_model_trains_base_as_last_resort(db_session):
    company = _seed_company_sales(db_session, "Needs Fallback Co", n_days=50, n_products=2)
    entry = ensure_company_has_a_model(db_session, company.id)
    assert entry is not None
    assert entry.model_source == "base"


def test_retraining_archives_previous_version(db_session):
    company = _seed_company_sales(db_session, "Retrain Co", n_days=400, n_products=10)
    entry1, _ = train_company_demand_model(db_session, company.id)
    entry2, _ = train_company_demand_model(db_session, company.id)

    db_session.refresh(entry1)
    assert entry1.status == "archived"
    assert entry2.status == "active"
    assert entry2.version != entry1.version
