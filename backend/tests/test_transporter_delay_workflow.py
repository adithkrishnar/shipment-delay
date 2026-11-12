import pytest
from datetime import date, datetime, timedelta
from app.models import Company, Shipment, Product, Supplier, User, Alert
from app.models.shipment_leg import ShipmentLeg
from app.models.shipment_delay import ShipmentDelay
from app.models.transporter_org import TransporterOrganization
from app.main import app
from app.auth.deps import get_current_user
from tests.conftest import mock_get_current_user


@pytest.fixture
def delay_setup(client):
    from app.database import SessionLocal
    db_session = SessionLocal()
    try:
        # Create Company A and Company B
        comp_a = Company(name="Company A Industrial", industry="Manufacturing")
        comp_b = Company(name="Company B Consumer", industry="Retail")
        db_session.add(comp_a)
        db_session.add(comp_b)
        db_session.commit()

        # Product
        prod_a = Product(company_id=comp_a.id, external_product_id="SKU-D1", name="Alternator", unit_price=150.0)
        db_session.add(prod_a)
        db_session.commit()

        # Transporter Orgs
        org_a = TransporterOrganization(name="Apex Carrier Group", code="APEX")
        org_b = TransporterOrganization(name="Titan Freight Systems", code="TITAN")
        db_session.add(org_a)
        db_session.add(org_b)
        db_session.commit()

        # Users
        carrier_a_user = User(
            email="driver@apex.com",
            hashed_password="pw",
            role="transporter",
            transporter_org_id=org_a.id,
            carrier_name=org_a.name
        )
        carrier_b_user = User(
            email="driver@titan.com",
            hashed_password="pw",
            role="transporter",
            transporter_org_id=org_b.id,
            carrier_name=org_b.name
        )
        company_admin_user = User(
            email="admin@compa.com",
            hashed_password="pw",
            role="company",
            company_id=comp_a.id
        )
        db_session.add(carrier_a_user)
        db_session.add(carrier_b_user)
        db_session.add(company_admin_user)
        db_session.commit()

        # Shipment assigned to Org A
        shipment_a = Shipment(
            company_id=comp_a.id,
            product_id=prod_a.id,
            external_shipment_id="SHP-DEL-100",
            origin="Chennai",
            destination="Pune",
            carrier=org_a.name,
            transporter_org_id=org_a.id,
            transport_mode="ROAD",
            planned_delivery=date.today() + timedelta(days=3),
            current_eta=date.today() + timedelta(days=3),
            assignment_status="ACCEPTED"
        )
        # Shipment assigned to Org B
        shipment_b = Shipment(
            company_id=comp_b.id,
            product_id=prod_a.id,
            external_shipment_id="SHP-DEL-200",
            origin="Delhi",
            destination="Jaipur",
            carrier=org_b.name,
            transporter_org_id=org_b.id,
            transport_mode="ROAD",
            planned_delivery=date.today() + timedelta(days=2),
            current_eta=date.today() + timedelta(days=2),
            assignment_status="ACCEPTED"
        )
        # Shipment with Revoked status
        shipment_revoked = Shipment(
            company_id=comp_a.id,
            product_id=prod_a.id,
            external_shipment_id="SHP-REV-300",
            origin="Mumbai",
            destination="Nagpur",
            carrier=org_a.name,
            transporter_org_id=org_a.id,
            transport_mode="ROAD",
            planned_delivery=date.today() + timedelta(days=4),
            assignment_status="REVOKED"
        )
        db_session.add(shipment_a)
        db_session.add(shipment_b)
        db_session.add(shipment_revoked)
        db_session.commit()

        context = {
            "comp_a_id": comp_a.id,
            "comp_b_id": comp_b.id,
            "org_a_id": org_a.id,
            "org_b_id": org_b.id,
            "carrier_a_user": carrier_a_user,
            "carrier_b_user": carrier_b_user,
            "company_admin_user": company_admin_user,
            "shipment_a_id": shipment_a.id,
            "shipment_b_id": shipment_b.id,
            "shipment_revoked_id": shipment_revoked.id,
            "planned_delivery_a": shipment_a.planned_delivery,
        }
        yield context
    finally:
        db_session.close()


def test_delay_reporting_success_and_eta_recalculation(client, delay_setup):
    """
    Test valid delay report returns 201 Created, recalculates ETA,
    updates assignment_status to DELAYED, preserves planned delivery,
    and publishes alert to Control Tower.
    """
    app.dependency_overrides[get_current_user] = lambda: delay_setup["carrier_a_user"]
    try:
        shipment_id = delay_setup["shipment_a_id"]
        payload = {
            "delay_hours": 6.5,
            "reason": "TRAFFIC_CONGESTION",
            "notes": "Accident on NH48; backup for 12km.",
            "idempotency_key": "delay-key-001"
        }

        res = client.post(f"/api/transporter/shipments/{shipment_id}/delay", json=payload)
        assert res.status_code == 201, res.text
        data = res.json()
        assert data["shipment_id"] == shipment_id
        assert data["delay_hours"] == 6.5
        assert data["reason"] == "TRAFFIC_CONGESTION"
        assert data["status"] == "DELAYED"
        assert data["control_tower_alert_id"] is not None

        # Verify DB persistence
        from app.database import SessionLocal
        db = SessionLocal()
        s = db.query(Shipment).filter(Shipment.id == shipment_id).first()
        assert s.assignment_status == "DELAYED"
        # Planned delivery preserved
        assert s.planned_delivery == delay_setup["planned_delivery_a"]
        # Delay record exists
        d_rec = db.query(ShipmentDelay).filter(ShipmentDelay.shipment_id == shipment_id).first()
        assert d_rec is not None
        assert d_rec.delay_hours == 6.5
        assert d_rec.reason == "TRAFFIC_CONGESTION"

        # Verify Control Tower Alert created
        alert = db.query(Alert).filter(Alert.id == data["control_tower_alert_id"]).first()
        assert alert is not None
        assert alert.company_id == delay_setup["comp_a_id"]
        assert alert.alert_type == "delay"
        assert alert.severity == "high"
        assert "SHP-DEL-100" in alert.message
        db.close()
    finally:
        app.dependency_overrides[get_current_user] = mock_get_current_user


def test_delay_reporting_idempotency_deduplication_and_conflict(client, delay_setup):
    """
    Test exact replaying of idempotency_key returns cached response without duplicate records.
    Test replaying same key with changed payload returns 409 Conflict.
    """
    app.dependency_overrides[get_current_user] = lambda: delay_setup["carrier_a_user"]
    try:
        shipment_id = delay_setup["shipment_a_id"]
        payload = {
            "delay_hours": 4.0,
            "reason": "WEATHER",
            "idempotency_key": "unique-idemp-1122"
        }

        # First request
        res1 = client.post(f"/api/transporter/shipments/{shipment_id}/delay", json=payload)
        assert res1.status_code == 201

        # Replay identical payload
        res2 = client.post(f"/api/transporter/shipments/{shipment_id}/delay", json=payload)
        assert res2.status_code == 201
        assert "Duplicate" in res2.json().get("message", "")

        # Verify only 1 delay record in database
        from app.database import SessionLocal
        db = SessionLocal()
        cnt = db.query(ShipmentDelay).filter(ShipmentDelay.idempotency_key == "unique-idemp-1122").count()
        assert cnt == 1

        # Replay same key with conflicting payload (different hours/reason)
        conflicting_payload = {
            "delay_hours": 12.0,
            "reason": "VEHICLE_BREAKDOWN",
            "idempotency_key": "unique-idemp-1122"
        }
        res3 = client.post(f"/api/transporter/shipments/{shipment_id}/delay", json=conflicting_payload)
        assert res3.status_code == 409, res3.text
        db.close()
    finally:
        app.dependency_overrides[get_current_user] = mock_get_current_user


def test_carrier_isolation_and_anti_spoofing(client, delay_setup):
    """
    Ensure carrier cannot report delay on another carrier's shipment (403 Forbidden).
    Ensure company user cannot call transporter delay endpoint (403 Forbidden).
    Ensure delay cannot be reported on REVOKED shipment (400 Bad Request).
    """
    try:
        # Carrier A attempts to report delay on Carrier B's shipment
        app.dependency_overrides[get_current_user] = lambda: delay_setup["carrier_a_user"]
        foreign_shipment_id = delay_setup["shipment_b_id"]

        res_foreign = client.post(
            f"/api/transporter/shipments/{foreign_shipment_id}/delay",
            json={"delay_hours": 2.0, "reason": "OTHER"}
        )
        assert res_foreign.status_code == 403, res_foreign.text

        # Carrier A attempts to report delay on a REVOKED shipment
        revoked_id = delay_setup["shipment_revoked_id"]
        res_revoked = client.post(
            f"/api/transporter/shipments/{revoked_id}/delay",
            json={"delay_hours": 3.0, "reason": "WEATHER"}
        )
        assert res_revoked.status_code == 400, res_revoked.text

        # Company Admin attempts to call transporter delay endpoint
        app.dependency_overrides[get_current_user] = lambda: delay_setup["company_admin_user"]
        res_admin = client.post(
            f"/api/transporter/shipments/{delay_setup['shipment_a_id']}/delay",
            json={"delay_hours": 2.0, "reason": "OTHER"}
        )
        assert res_admin.status_code == 403, res_admin.text

    finally:
        app.dependency_overrides[get_current_user] = mock_get_current_user


def test_company_control_tower_visibility(client, delay_setup):
    """
    Verify Company Admin can see the delayed shipment in /api/shipments/{company_id}.
    """
    # 1. Transporter reports delay
    app.dependency_overrides[get_current_user] = lambda: delay_setup["carrier_a_user"]
    res_delay = client.post(
        f"/api/transporter/shipments/{delay_setup['shipment_a_id']}/delay",
        json={"delay_hours": 8.0, "reason": "PORT_CONGESTION"}
    )
    assert res_delay.status_code == 201

    # 2. Company Admin retrieves shipments
    app.dependency_overrides[get_current_user] = lambda: delay_setup["company_admin_user"]
    try:
        comp_id = delay_setup["comp_a_id"]
        res = client.get(f"/api/shipments/{comp_id}")
        assert res.status_code == 200
        shipments = res.json().get("shipments", [])
        delayed_item = next((s for s in shipments if s["shipment_id"] == delay_setup["shipment_a_id"]), None)
        assert delayed_item is not None
        assert delayed_item["external_shipment_id"] == "SHP-DEL-100"
    finally:
        app.dependency_overrides[get_current_user] = mock_get_current_user
