import datetime as dt

import numpy as np

from app.database import SessionLocal
from app.models import Product, Shipment, Supplier


def _seed_shipments_via_db(company_id: int, n_shipments: int, history_days: int, seed: int = 1):
    rng = np.random.default_rng(seed)
    db = SessionLocal()
    try:
        product = Product(company_id=company_id, external_product_id="P1", name="Product 1")
        db.add(product)
        supplier = Supplier(
            company_id=company_id, external_supplier_id="SUP-1", name="Supplier 1",
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
                company_id=company_id, product_id=product.id, supplier_id=supplier.id,
                external_shipment_id=f"SHP-{i}", origin="Mumbai", destination="Delhi",
                carrier="CarrierX", transport_mode="road", distance_km=1400, weight_kg=500, quantity=100,
                order_date=order_date, planned_delivery=planned, actual_delivery=actual,
            ))
        db.commit()
    finally:
        db.close()


def _create_company(client, name):
    r = client.post("/api/companies", json={"name": name, "industry": "Test"})
    assert r.status_code == 201
    return r.json()["id"]


def test_shipment_risk_list_before_any_model_returns_400(client):
    company_id = _create_company(client, "No Shipment Model Co")
    _seed_shipments_via_db(company_id, n_shipments=50, history_days=100)
    r = client.get(f"/api/shipments/{company_id}")
    assert r.status_code == 400


def test_retrain_then_shipment_risk_list(client):
    company_id = _create_company(client, "Shipment Retrain Co")
    _seed_shipments_via_db(company_id, n_shipments=400, history_days=400)

    r = client.post(f"/api/models/retrain/{company_id}")
    assert r.status_code == 200

    r = client.get(f"/api/shipments/{company_id}?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert body["model_source"] == "company_specific"
    assert len(body["shipments"]) == 10
    for s in body["shipments"]:
        assert 0.0 <= s["delay_probability"] <= 1.0
        assert s["risk_tier"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def test_single_shipment_detail_endpoint(client):
    company_id = _create_company(client, "Single Shipment Co")
    _seed_shipments_via_db(company_id, n_shipments=400, history_days=400)
    client.post(f"/api/models/retrain/{company_id}")

    r = client.get(f"/api/shipments/{company_id}?limit=1")
    shipment_id = r.json()["shipments"][0]["shipment_id"]

    r = client.get(f"/api/shipments/{company_id}/{shipment_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["shipment_id"] == shipment_id
    assert len(body["top_risk_factors"]) > 0


def test_completed_shipment_shows_actual_outcome(client):
    company_id = _create_company(client, "Completed Outcome Co")
    _seed_shipments_via_db(company_id, n_shipments=400, history_days=400)
    client.post(f"/api/models/retrain/{company_id}")

    r = client.get(f"/api/shipments/{company_id}?limit=400")
    shipments = r.json()["shipments"]
    completed = [s for s in shipments if s["is_completed"]]
    assert len(completed) > 0
    for s in completed:
        assert s["actual_was_delayed"] is not None
        assert s["actual_delay_days"] is not None


def test_small_shipper_falls_back_to_base_via_api(client):
    small_id = _create_company(client, "Tiny Shipper Co")
    _seed_shipments_via_db(small_id, n_shipments=50, history_days=100, seed=11)

    big_id = _create_company(client, "Large Shipper Co")
    _seed_shipments_via_db(big_id, n_shipments=400, history_days=400, seed=22)

    r = client.post("/api/models/train/base")
    assert r.status_code == 200
    body = r.json()
    trained_types = [e["model_type"] for e in body["trained"]]
    assert "delay_classifier" in trained_types
    # No sales data was seeded in this test, so the demand model should show up as an error, not crash the whole call
    assert any(e["model_type"] == "demand_forecast" for e in body["errors"])

    r = client.post(f"/api/models/retrain/{small_id}")
    assert "Insufficient" in r.json()["shipments"]["reason"]

    r = client.get(f"/api/shipments/{small_id}")
    assert r.status_code == 200
    assert r.json()["model_source"] == "base"


def test_shipments_isolated_per_company(client):
    company_a = _create_company(client, "Shipper A")
    company_b = _create_company(client, "Shipper B")
    _seed_shipments_via_db(company_a, n_shipments=400, history_days=400, seed=1)
    client.post(f"/api/models/retrain/{company_a}")

    r = client.get(f"/api/shipments/{company_b}")
    assert r.status_code in (400, 404)  # no shipments and/or no model for company B
