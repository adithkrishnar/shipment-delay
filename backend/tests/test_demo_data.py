import datetime as dt

from app.models import Company, InventoryRecord, Sale, Shipment, Supplier
from app.services.demo_data_generator import generate_demo_companies


def test_generate_demo_companies_creates_three_companies(db_session):
    results = generate_demo_companies(db_session, reset=True)
    assert len(results) == 3
    names = {r["name"] for r in results}
    assert names == {"Horizon Electronics", "TorqueParts Autoworks", "FreshMart FMCG"}

    companies = db_session.query(Company).filter(Company.is_demo == 1).all()
    assert len(companies) == 3


def test_generate_demo_companies_is_idempotent_on_reset(db_session):
    generate_demo_companies(db_session, reset=True)
    first_count = db_session.query(Company).count()
    generate_demo_companies(db_session, reset=True)
    second_count = db_session.query(Company).count()
    assert first_count == second_count == 3


def test_demo_companies_have_different_data_volumes(db_session):
    """Deliberately different scale, so model-selection logic has something real to react to."""
    generate_demo_companies(db_session, reset=True)
    companies = {c.name: c for c in db_session.query(Company).all()}

    horizon_sales = db_session.query(Sale).filter(Sale.company_id == companies["Horizon Electronics"].id).count()
    torque_sales = db_session.query(Sale).filter(Sale.company_id == companies["TorqueParts Autoworks"].id).count()

    assert horizon_sales > torque_sales  # 3 years of history vs 8 months


def test_shipment_delay_correlates_with_supplier_reliability(db_session):
    """Lower supplier reliability should produce more/longer shipment delays on average."""
    generate_demo_companies(db_session, reset=True)

    rows = (
        db_session.query(Shipment.planned_delivery, Shipment.actual_delivery, Supplier.reliability)
        .join(Supplier, Shipment.supplier_id == Supplier.id)
        .filter(Shipment.actual_delivery.isnot(None))
        .all()
    )
    assert len(rows) > 100

    low_reliability_delays = []
    high_reliability_delays = []
    for planned, actual, reliability in rows:
        delay_days = (actual - planned).days
        if reliability < 0.8:
            low_reliability_delays.append(delay_days)
        elif reliability > 0.93:
            high_reliability_delays.append(delay_days)

    assert low_reliability_delays and high_reliability_delays
    avg_low = sum(low_reliability_delays) / len(low_reliability_delays)
    avg_high = sum(high_reliability_delays) / len(high_reliability_delays)
    assert avg_low > avg_high


def test_inventory_never_negative(db_session):
    generate_demo_companies(db_session, reset=True)
    min_level = db_session.query(InventoryRecord.inventory_level).order_by(InventoryRecord.inventory_level.asc()).first()
    assert min_level[0] >= 0


def test_inventory_history_spans_expected_range(db_session):
    generate_demo_companies(db_session, reset=True)
    horizon = db_session.query(Company).filter(Company.name == "Horizon Electronics").first()
    dates = (
        db_session.query(InventoryRecord.date)
        .filter(InventoryRecord.company_id == horizon.id)
        .order_by(InventoryRecord.date.asc())
        .first()
    )
    latest = (
        db_session.query(InventoryRecord.date)
        .filter(InventoryRecord.company_id == horizon.id)
        .order_by(InventoryRecord.date.desc())
        .first()
    )
    span_days = (latest[0] - dates[0]).days
    assert span_days >= 1090  # ~3 years, allowing for date rounding
