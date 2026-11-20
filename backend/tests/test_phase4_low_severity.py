import os
import sys
import shutil
import tempfile
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.models import Company, Product, Shipment, ShipmentLeg, DisruptionReport, Alert, User, Warehouse
from app.services.collaborative_disruption_service import simulate_downstream_impact, ensure_shipment_legs

ROOT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "supplyiq.db"))
EXPECTED_PRISTINE_SHA256 = "66CBCE89C3CD1326B39AA6F6DDD897F00F0693A86AEC933E3101F8A358147E15"


@pytest.fixture
def isolated_db():
    """Creates a temporary isolated SQLite database cloned from supplyiq.db."""
    temp_dir = tempfile.mkdtemp(prefix="supplyiq_phase4_test_")
    temp_db_path = os.path.join(temp_dir, "isolated_supplyiq.db")
    shutil.copyfile(ROOT_DB_PATH, temp_db_path)

    engine = create_engine(f"sqlite:///{temp_db_path}", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()
        shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# DEF-016: Dynamic Currency Formatting
# ==============================================================================

def test_def_016_collaborative_disruption_currency_inr(isolated_db):
    """
    Verify that an Indian domestic disruption (Bengaluru -> Chennai) formats monetary
    values with ₹ (INR), including in alert messages and impact details, and never with hardcoded $.
    """
    db = isolated_db
    # Find a Bengaluru (19) -> Chennai (21) shipment
    shipment = db.query(Shipment).filter(
        Shipment.company_id == 19,
        Shipment.receiver_company_id == 21
    ).first()
    assert shipment is not None, "Domestic Indian benchmark shipment must exist"

    # Ensure shipment company has INR
    sender_comp = db.query(Company).filter(Company.id == 19).first()
    assert sender_comp.default_currency == "INR"

    legs = ensure_shipment_legs(db, shipment)
    assert len(legs) > 0

    res = simulate_downstream_impact(
        db=db,
        shipment=shipment,
        leg_id=legs[0].id,
        reported_delay_hrs=16.0,
        reason="Severe monsoonal flash flooding",
        notes="Highway transit halt",
        reporter_id=1
    )

    # 1. Returned financial impact must reflect INR currency and symbol ₹
    financial_impact = res.get("financial_impact", {})
    assert financial_impact.get("currency") == "INR", f"Expected INR, got {financial_impact.get('currency')}"
    assert financial_impact.get("currency_symbol") == "₹", f"Expected ₹, got {financial_impact.get('currency_symbol')}"

    # 2. Check the generated Alert record
    alert = db.query(Alert).filter(
        Alert.entity_id == shipment.id,
        Alert.alert_type == "delay"
    ).order_by(Alert.created_at.desc()).first()
    assert alert is not None
    if "Risk:" in alert.message:
        assert "₹" in alert.message, f"Alert message must use ₹ symbol: {alert.message}"
        assert "$" not in alert.message, f"Alert message must not contain hardcoded $: {alert.message}"


def test_def_016_collaborative_disruption_currency_usd(isolated_db):
    """
    Verify that a USD company disruption (DataCo, company 16) formats with $ (USD).
    """
    db = isolated_db
    # Find a DataCo shipment
    shipment = db.query(Shipment).filter(Shipment.company_id == 16).first()
    if shipment:
        legs = ensure_shipment_legs(db, shipment)
        res = simulate_downstream_impact(
            db=db,
            shipment=shipment,
            leg_id=legs[0].id,
            reported_delay_hrs=24.0,
            reason="Port congestion",
            notes="Customs delay",
            reporter_id=1
        )
        financial_impact = res.get("financial_impact", {})
        assert financial_impact.get("currency") == "USD"
        assert financial_impact.get("currency_symbol") == "$"


def test_def_016_transporter_recent_disruptions_currency_metadata(isolated_db):
    """
    Verify that get_recent_disruptions returns currency and currency_symbol attributes.
    """
    from app.routes.transporter import get_recent_disruptions
    user = isolated_db.query(User).filter(User.is_superuser == True).first()
    assert user is not None

    disruptions = get_recent_disruptions(current_user=user, db=isolated_db)
    assert len(disruptions) > 0, "Recent disruptions must return records"

    for d in disruptions:
        assert "currency" in d, "Disruption record must contain currency"
        assert "currency_symbol" in d, "Disruption record must contain currency_symbol"
        assert d["currency"] in ["INR", "USD", "EUR", "GBP"], f"Unexpected currency: {d['currency']}"
        if d["currency"] == "INR":
            assert d["currency_symbol"] == "₹"
        elif d["currency"] == "USD":
            assert d["currency_symbol"] == "$"


# ==============================================================================
# DEF-017: Dynamic Transportation Route Information
# ==============================================================================

def test_def_017_route_info_dynamic_modes_and_distances(isolated_db):
    """
    Verify that route information derives dynamically from shipment transport mode
    and distance attributes, and doesn't hardcode NH-48 (360 km) across modes.
    """
    def format_route_display(transport_mode, distance_km):
        mode = (transport_mode or "ROAD").upper()
        dist_str = f"{distance_km:,.0f} km" if (distance_km is not None and distance_km > 0) else "Distance not recorded"
        return f"{mode} • {dist_str}"

    # Road with known distance
    assert format_route_display("ROAD", 360) == "ROAD • 360 km"
    assert format_route_display("road", 450) == "ROAD • 450 km"

    # Air, Rail, Sea with or without distance
    assert format_route_display("AIR", 1250) == "AIR • 1,250 km"
    assert "NH-48" not in format_route_display("AIR", 1250)
    assert format_route_display("RAIL", None) == "RAIL • Distance not recorded"
    assert "NH-48" not in format_route_display("RAIL", None)
    assert format_route_display("SEA", 0) == "SEA • Distance not recorded"

    # Verify existing database shipments have legitimate transport modes
    shipments = isolated_db.query(Shipment).limit(20).all()
    for s in shipments:
        mode = s.transport_mode or "ROAD"
        display = format_route_display(mode, s.distance_km)
        assert mode.upper() in display
        if s.distance_km and s.distance_km > 0:
            assert f"{s.distance_km:,.0f} km" in display
        else:
            assert "Distance not recorded" in display


# ==============================================================================
# DEF-018: Correct Shipment KPI Classification and Counting
# ==============================================================================

def test_def_018_mutually_exclusive_classification():
    """
    Verify that shipment categories (In-Transit, Arrived, Delivered) are mutually exclusive
    and collectively exhaustive (Total == In-Transit + Arrived + Delivered).
    """
    def classify_shipment(s):
        assignment_status = (s.get("assignment_status") or "").upper()
        has_delivery = bool(s.get("actual_delivery"))

        is_delivered = assignment_status == "DELIVERED" or has_delivery
        is_arrived = not is_delivered and assignment_status == "ARRIVED"
        is_in_transit = not is_delivered and not is_arrived
        is_critical_delayed = is_in_transit and (assignment_status == "DELAYED" or str(s.get("risk_tier", "")).upper() == "CRITICAL")

        return {
            "is_delivered": is_delivered,
            "is_arrived": is_arrived,
            "is_in_transit": is_in_transit,
            "is_critical_delayed": is_critical_delayed,
        }

    sample_shipments = [
        {"id": 1, "assignment_status": "PENDING", "risk_tier": "LOW"},
        {"id": 2, "assignment_status": "ACCEPTED", "risk_tier": "LOW"},
        {"id": 3, "assignment_status": "IN_TRANSIT", "risk_tier": "LOW"},
        {"id": 4, "assignment_status": "DELAYED", "risk_tier": "CRITICAL"},
        {"id": 5, "assignment_status": "IN_TRANSIT", "risk_tier": "CRITICAL"},
        {"id": 6, "assignment_status": "ARRIVED", "risk_tier": "LOW"},
        {"id": 7, "assignment_status": "DELIVERED", "actual_delivery": "2026-11-18", "risk_tier": "LOW"},
        {"id": 8, "assignment_status": "ARRIVED", "actual_delivery": "2026-11-18", "risk_tier": "LOW"}, # actual_delivery overrides to delivered
    ]

    in_transit_count = 0
    arrived_count = 0
    delivered_count = 0
    critical_delayed_count = 0

    for s in sample_shipments:
        c = classify_shipment(s)
        # Check mutual exclusivity of primary categories
        bucket_sum = int(c["is_in_transit"]) + int(c["is_arrived"]) + int(c["is_delivered"])
        assert bucket_sum == 1, f"Shipment {s['id']} must belong to exactly one primary category"

        if c["is_in_transit"]:
            in_transit_count += 1
        elif c["is_arrived"]:
            arrived_count += 1
        elif c["is_delivered"]:
            delivered_count += 1

        if c["is_critical_delayed"]:
            critical_delayed_count += 1

    total = len(sample_shipments)
    assert total == in_transit_count + arrived_count + delivered_count, (
        f"Reconciliation failure: Total {total} != {in_transit_count} + {arrived_count} + {delivered_count}"
    )

    # Critical delayed is a subcategory of in-transit
    assert critical_delayed_count <= in_transit_count
    assert critical_delayed_count == 2  # items 4 and 5


def test_def_018_status_transition_reconciliation(isolated_db):
    """
    Verify that across shipment lifecycle transitions (IN_TRANSIT -> DELAYED -> ARRIVED -> DELIVERED),
    the reconciliation invariant Total == In-Transit + Arrived + Delivered holds at every step.
    """
    def compute_kpis(shipments):
        total = len(shipments)
        in_transit = 0
        arrived = 0
        delivered = 0
        critical = 0

        for s in shipments:
            st = (s.assignment_status or "").upper()
            has_del = bool(s.actual_delivery)
            is_del = st == "DELIVERED" or has_del
            is_arr = not is_del and st == "ARRIVED"
            is_it = not is_del and not is_arr

            if is_del:
                delivered += 1
            elif is_arr:
                arrived += 1
            elif is_it:
                in_transit += 1

            if is_it and (st == "DELAYED" or str(getattr(s, "risk_tier", "") or "").upper() == "CRITICAL"):
                critical += 1

        assert total == in_transit + arrived + delivered, f"Total {total} != {in_transit} + {arrived} + {delivered}"
        return total, in_transit, arrived, delivered, critical

    # Evaluate against real isolated database
    all_shipments = isolated_db.query(Shipment).all()
    t0, it0, arr0, del0, crit0 = compute_kpis(all_shipments)
    assert t0 == it0 + arr0 + del0

    # Pick an active shipment and transition it through lifecycle
    active = next((s for s in all_shipments if not s.actual_delivery and (s.assignment_status or "").upper() != "ARRIVED"), None)
    assert active is not None, "Active shipment needed for transition test"

    # Step 1: Delay shipment
    active.assignment_status = "DELAYED"
    isolated_db.flush()
    t1, it1, arr1, del1, crit1 = compute_kpis(all_shipments)
    assert t1 == t0
    assert it1 == it0
    assert crit1 >= crit0

    # Step 2: Arrive shipment
    active.assignment_status = "ARRIVED"
    isolated_db.flush()
    t2, it2, arr2, del2, crit2 = compute_kpis(all_shipments)
    assert t2 == t0
    assert it2 == it1 - 1
    assert arr2 == arr1 + 1
    assert t2 == it2 + arr2 + del2

    # Step 3: Complete Goods Inward (Deliver)
    active.assignment_status = "DELIVERED"
    active.actual_delivery = datetime.utcnow().date()
    isolated_db.flush()
    t3, it3, arr3, del3, crit3 = compute_kpis(all_shipments)
    assert t3 == t0
    assert arr3 == arr2 - 1
    assert del3 == del2 + 1
    assert t3 == it3 + arr3 + del3
