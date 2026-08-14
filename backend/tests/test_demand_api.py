import datetime as dt

import numpy as np

from app.database import SessionLocal
from app.models import Product, Sale


def _seed_sales_via_db(company_id: int, n_days: int, n_products: int = 3, seed: int = 1):
    """Insert sales directly (fast) rather than going through the upload pipeline for every test."""
    rng = np.random.default_rng(seed)
    db = SessionLocal()
    try:
        start = dt.date.today() - dt.timedelta(days=n_days)
        for p in range(n_products):
            product = Product(company_id=company_id, external_product_id=f"P{p+1}", name=f"Product {p+1}")
            db.add(product)
            db.flush()
            base = rng.uniform(30, 100)
            for i in range(n_days):
                d = start + dt.timedelta(days=i)
                qty = max(0, base + 10 * np.sin(i / 7) + rng.normal(0, 5))
                db.add(Sale(company_id=company_id, product_id=product.id, date=d, quantity=qty, promotion=0))
        db.commit()
    finally:
        db.close()


def _create_company(client, name):
    r = client.post("/api/companies", json={"name": name, "industry": "Test"})
    assert r.status_code == 201
    return r.json()["id"]


def test_forecast_returns_404_before_any_model_exists(client):
    company_id = _create_company(client, "No Model Co")
    _seed_sales_via_db(company_id, n_days=50, n_products=2)
    r = client.get(f"/api/demand/forecast/{company_id}")
    assert r.status_code == 400  # no base model trained yet, no company model either


def test_retrain_then_forecast_end_to_end(client):
    company_id = _create_company(client, "Retrain Forecast Co")
    _seed_sales_via_db(company_id, n_days=400, n_products=10)  # 4000 records, clears the threshold

    r = client.post(f"/api/models/retrain/{company_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["demand"]["trained_company_specific"] is True
    assert body["demand"]["active_model_source"] == "company_specific"

    r = client.get(f"/api/demand/forecast/{company_id}?horizon=7")
    assert r.status_code == 200
    forecast = r.json()
    assert forecast["horizon_days"] == 7
    assert forecast["model_source"] == "company_specific"
    assert len(forecast["products"]) == 10
    for product in forecast["products"]:
        assert len(product["forecast"]) == 7


def test_forecast_rejects_invalid_horizon(client):
    company_id = _create_company(client, "Bad Horizon Co")
    _seed_sales_via_db(company_id, n_days=400, n_products=10)
    client.post(f"/api/models/retrain/{company_id}")

    r = client.get(f"/api/demand/forecast/{company_id}?horizon=13")
    assert r.status_code == 400


def test_small_company_falls_back_to_base_via_api(client):
    small_id = _create_company(client, "Tiny Co")
    _seed_sales_via_db(small_id, n_days=50, n_products=2, seed=11)

    big_id = _create_company(client, "Large Co")
    _seed_sales_via_db(big_id, n_days=400, n_products=10, seed=22)

    r = client.post("/api/models/train/base")
    assert r.status_code == 200

    r = client.post(f"/api/models/retrain/{small_id}")
    body = r.json()
    assert body["demand"]["trained_company_specific"] is False
    assert body["demand"]["active_model_source"] == "base"

    r = client.get(f"/api/demand/forecast/{small_id}")
    assert r.status_code == 200
    assert r.json()["model_source"] == "base"


def test_forecast_single_product_via_query_param(client):
    company_id = _create_company(client, "Single Product Co")
    _seed_sales_via_db(company_id, n_days=400, n_products=10)
    client.post(f"/api/models/retrain/{company_id}")

    r = client.get(f"/api/demand/forecast/{company_id}")
    all_products = r.json()["products"]
    one_id = all_products[0]["product_id"]

    r = client.get(f"/api/demand/forecast/{company_id}?product_id={one_id}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["products"]) == 1
    assert body["products"][0]["product_id"] == one_id


def test_model_registry_lists_entries_for_company(client):
    company_id = _create_company(client, "Registry Co")
    _seed_sales_via_db(company_id, n_days=400, n_products=10)
    client.post(f"/api/models/retrain/{company_id}")

    r = client.get(f"/api/models/{company_id}")
    assert r.status_code == 200
    entries = r.json()
    assert any(e["model_source"] == "company_specific" for e in entries)
