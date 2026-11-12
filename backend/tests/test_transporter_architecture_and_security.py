import pytest
from datetime import date, datetime, timedelta
from app.models import Company, Shipment, Product, Supplier, User, Alert
from app.models.shipment_leg import ShipmentLeg, DisruptionReport
from app.models.transporter_org import TransporterOrganization, TransporterInvitation
from app.services.collaborative_disruption_service import ensure_shipment_legs, simulate_downstream_impact
from tests.conftest import mock_get_current_user


@pytest.fixture
def test_setup(client):
    from app.database import SessionLocal
    db_session = SessionLocal()
    try:
        # Company A & B
        comp_a = Company(name="Company A Industrial", industry="Manufacturing")
        comp_b = Company(name="Company B Electronics", industry="Electronics")
        db_session.add(comp_a)
        db_session.add(comp_b)
        db_session.commit()

        # Product for Company A
        prod_a = Product(company_id=comp_a.id, external_product_id="SKU-A1", name="Hydraulic Pump", unit_price=200.0)
        db_session.add(prod_a)
        db_session.commit()

        # Transporter Org A & B
        trans_org_a = TransporterOrganization(name="Transporter A Logistics", code="TRANS-A")
        trans_org_b = TransporterOrganization(name="Transporter B Express", code="TRANS-B")
        db_session.add(trans_org_a)
        db_session.add(trans_org_b)
        db_session.commit()

        # Users
        user_trans_a = User(
            email="driver@transporterA.com",
            hashed_password="pw",
            role="transporter",
            transporter_org_id=trans_org_a.id,
            carrier_name=trans_org_a.name
        )
        user_trans_b = User(
            email="driver@transporterB.com",
            hashed_password="pw",
            role="transporter",
            transporter_org_id=trans_org_b.id,
            carrier_name=trans_org_b.name
        )
        db_session.add(user_trans_a)
        db_session.add(user_trans_b)
        db_session.commit()

        # Shipments: Shipment 101 belongs to Comp A assigned to Transporter A
        shipment_101 = Shipment(
            company_id=comp_a.id,
            product_id=prod_a.id,
            external_shipment_id="SHP-101",
            origin="Chennai Plant",
            destination="Mumbai DC",
            carrier=trans_org_a.name,
            transporter_org_id=trans_org_a.id,
            transport_mode="ROAD",
            planned_delivery=date.today() + timedelta(days=2),
            assignment_status="ACCEPTED"
        )
        # Shipment 102 belongs to Comp B assigned to Transporter A as well (same transporter services both)
        shipment_102 = Shipment(
            company_id=comp_b.id,
            product_id=prod_a.id,
            external_shipment_id="SHP-102",
            origin="Bangalore Hub",
            destination="Delhi DC",
            carrier=trans_org_a.name,
            transporter_org_id=trans_org_a.id,
            transport_mode="AIR",
            planned_delivery=date.today() + timedelta(days=3),
            assignment_status="ACCEPTED"
        )
        db_session.add(shipment_101)
        db_session.add(shipment_102)
        db_session.commit()

        ensure_shipment_legs(db_session, shipment_101)
        ensure_shipment_legs(db_session, shipment_102)

        data = {
            "comp_a_id": comp_a.id,
            "comp_b_id": comp_b.id,
            "trans_org_a_id": trans_org_a.id,
            "trans_org_b_id": trans_org_b.id,
            "user_trans_a_id": user_trans_a.id,
            "user_trans_b_id": user_trans_b.id,
            "shipment_101_id": shipment_101.id,
            "shipment_102_id": shipment_102.id,
            "leg_101_id": shipment_101.legs[0].id,
            "leg_102_id": shipment_102.legs[0].id
        }
        return data
    finally:
        db_session.close()


def test_scenario_a_normal_workflow(test_setup):
    """Scenario A: Transporter reports delay -> event stored -> impact calculated -> alert created"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        s101 = db.query(Shipment).filter(Shipment.id == test_setup["shipment_101_id"]).first()
        legs = s101.legs
        assert len(legs) > 0

        target_leg = legs[0]
        result = simulate_downstream_impact(
            db=db,
            shipment=s101,
            leg_id=target_leg.id,
            reported_delay_hrs=12.0,
            reason="Vehicle breakdown",
            notes="Radiator leak",
            reporter_id=test_setup["user_trans_a_id"]
        )

        assert result["shipment_id"] == s101.id
        assert result["total_delay_hours"] >= 12.0
        report = db.query(DisruptionReport).filter(DisruptionReport.id == result["report_id"]).first()
        assert report is not None
        assert report.delay_hours == 12.0
    finally:
        db.close()


def test_scenario_b_cross_company_isolation(test_setup, client):
    """Scenario B: Disruption on Company A shipment notifies ONLY Company A, never Company B"""
    from app.auth.security import create_access_token
    from app.database import SessionLocal

    token_trans_a = create_access_token(test_setup["user_trans_a_id"])

    # Transporter reports delay on Shipment 101 (Company A)
    response = client.post(
        f"/api/v1/transporter/shipments/{test_setup['shipment_101_id']}/legs/{test_setup['leg_101_id']}/report-disruption",
        headers={"Authorization": f"Bearer {token_trans_a}"},
        json={"delay_hours": 12.0, "disruption_reason": "Severe weather", "notes": "Flooded expressway"}
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        # Company A MUST have received an alert
        alerts_a = db.query(Alert).filter(Alert.company_id == test_setup["comp_a_id"]).all()
        assert len(alerts_a) >= 1
        assert any("SHP-101" in a.message for a in alerts_a)

        # Company B MUST NOT have received any alert for Shipment 101
        alerts_b = db.query(Alert).filter(Alert.company_id == test_setup["comp_b_id"]).all()
        assert not any("SHP-101" in a.message for a in alerts_b)
    finally:
        db.close()


def test_scenario_c_unauthorized_transporter_rejection(test_setup, client):
    """Scenario C: Transporter B attempts to report disruption on Transporter A's shipment -> 403 Forbidden"""
    from app.main import app
    from app.auth.deps import get_current_user
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        user_b = db.query(User).filter(User.id == test_setup["user_trans_b_id"]).first()
        app.dependency_overrides[get_current_user] = lambda: user_b

        response = client.post(
            f"/api/v1/transporter/shipments/{test_setup['shipment_101_id']}/legs/{test_setup['leg_101_id']}/report-disruption",
            json={"delay_hours": 6.0, "disruption_reason": "Traffic congestion"}
        )
        assert response.status_code == 403
        assert "not assigned to your transporter organization" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides[get_current_user] = mock_get_current_user
        db.close()


def test_scenario_d_company_spoofing_resistance(test_setup, client):
    """Scenario D: Transporter cannot spoof or redirect alert to another company ID"""
    from app.auth.security import create_access_token
    from app.database import SessionLocal

    token_trans_a = create_access_token(test_setup["user_trans_a_id"])

    # Submit forged company_id: 99999 in payload
    response = client.post(
        f"/api/v1/transporter/shipments/{test_setup['shipment_101_id']}/legs/{test_setup['leg_101_id']}/report-disruption",
        headers={"Authorization": f"Bearer {token_trans_a}"},
        json={
            "delay_hours": 14.0,
            "disruption_reason": "Customs inspection",
            "company_id": 99999  # Forged input
        }
    )
    assert response.status_code == 200

    db = SessionLocal()
    try:
        # Verify alert was routed strictly to authentic owner Company A
        alert = db.query(Alert).filter(Alert.entity_id == test_setup["shipment_101_id"]).first()
        assert alert is not None
        assert alert.company_id == test_setup["comp_a_id"]
        assert alert.company_id != 99999
    finally:
        db.close()


def test_scenario_e_duplicate_submission_idempotency(test_setup, client):
    """Scenario E: Same request retried with idempotency key creates no duplicate report or duplicate alerts"""
    from app.auth.security import create_access_token
    from app.database import SessionLocal

    token_trans_a = create_access_token(test_setup["user_trans_a_id"])
    key = "idem-test-key-998811"

    # 1st attempt
    res1 = client.post(
        f"/api/v1/transporter/shipments/{test_setup['shipment_101_id']}/legs/{test_setup['leg_101_id']}/report-disruption",
        headers={"Authorization": f"Bearer {token_trans_a}"},
        json={"delay_hours": 8.0, "disruption_reason": "Mechanical fault", "idempotency_key": key}
    )
    assert res1.status_code == 200

    db = SessionLocal()
    try:
        reports_count1 = db.query(DisruptionReport).filter(DisruptionReport.idempotency_key == key).count()
        assert reports_count1 == 1

        # 2nd attempt with same key
        res2 = client.post(
            f"/api/v1/transporter/shipments/{test_setup['shipment_101_id']}/legs/{test_setup['leg_101_id']}/report-disruption",
            headers={"Authorization": f"Bearer {token_trans_a}"},
            json={"delay_hours": 8.0, "disruption_reason": "Mechanical fault", "idempotency_key": key}
        )
        assert res2.status_code == 200
        assert res2.json().get("status") == "DUPLICATE_IDEMPOTENT_IGNORED"

        reports_count2 = db.query(DisruptionReport).filter(DisruptionReport.idempotency_key == key).count()
        assert reports_count2 == 1, "Duplicate report must not be created"
    finally:
        db.close()


def test_scenario_f_assignment_lifecycle_and_revocation(test_setup, client):
    """Scenario F: Lifecycle transitions and access control on revocation"""
    from app.main import app
    from app.auth.deps import get_current_user
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        user_a = db.query(User).filter(User.id == test_setup["user_trans_a_id"]).first()
        app.dependency_overrides[get_current_user] = lambda: user_a

        # 1. Transporter starts transit
        res_start = client.post(
            f"/api/v1/transporter/shipments/{test_setup['shipment_101_id']}/assignment-action",
            json={"action": "START_TRANSIT"}
        )
        assert res_start.status_code == 200
        assert res_start.json()["assignment_status"] == "IN_TRANSIT"

        # 2. Company revokes assignment from Transporter A
        s101 = db.query(Shipment).filter(Shipment.id == test_setup["shipment_101_id"]).first()
        s101.transporter_org_id = None
        s101.carrier = "Other Carrier"
        db.commit()

        # 3. Transporter A attempts to report disruption on revoked shipment -> 403 Forbidden
        res_denied = client.post(
            f"/api/v1/transporter/shipments/{test_setup['shipment_101_id']}/legs/{test_setup['leg_101_id']}/report-disruption",
            json={"delay_hours": 5.0, "disruption_reason": "Puncture"}
        )
        assert res_denied.status_code == 403
    finally:
        app.dependency_overrides[get_current_user] = mock_get_current_user
        db.close()


def test_scenario_g_ai_data_limitations_integrity(db_session):
    """Scenario G: Missing inventory/sales records does NOT invent fake stockouts"""
    comp = Company(name="Data-Scarce Enterprise", industry="Aerospace")
    db_session.add(comp)
    db_session.commit()

    # Product with NO inventory records and NO sales history
    prod = Product(company_id=comp.id, external_product_id="SKU-NO-INV", name="Uninventoried Alloy", unit_price=500.0)
    db_session.add(prod)
    db_session.commit()

    shipment = Shipment(
        company_id=comp.id,
        product_id=prod.id,
        external_shipment_id="SHP-NO-DATA",
        origin="Forge",
        destination="Lab",
        planned_delivery=date.today(),
        transport_mode="ROAD"
    )
    db_session.add(shipment)
    db_session.commit()
    ensure_shipment_legs(db_session, shipment)

    result = simulate_downstream_impact(
        db=db_session,
        shipment=shipment,
        leg_id=shipment.legs[0].id,
        reported_delay_hrs=48.0,
        reason="Port congestion"
    )

    # Must explicitly show stockout is NOT predicted and data is insufficient
    inv_sim = result["inventory_simulation"]
    assert inv_sim["stockout_predicted"] is False
    assert inv_sim["stockout_risk"] == "DATA_UNAVAILABLE"
    assert result["financial_impact"]["total_cost_loss"] == 0.0
    assert result["prescriptive_mitigations"][0]["option_id"] == "INSUFFICIENT_INVENTORY_DATA"


# ─── PART 10: ADVERSARIAL PENETRATION & CONTROL TOWER AUDIT SCENARIOS ─────────

def test_adversarial_transporter_unauthorized_endpoints(test_setup, client):
    """
    Adversarial Audit 1: Transporter attempts to probe private company endpoints:
    - Company Dashboard (/api/dashboard/{comp_id})
    - Inventory intelligence (/api/intelligence/{comp_id}/inventory)
    - Recommendations & profit margins (/api/recommendations/{comp_id})
    - Shipment creation for another company (/api/shipments/{comp_id})
    All must strictly return 403 Forbidden.
    """
    from app.main import app
    from app.auth.deps import get_current_user
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        user_trans_a = db.query(User).filter(User.id == test_setup["user_trans_a_id"]).first()
        app.dependency_overrides[get_current_user] = lambda: user_trans_a

        # 1. Attacking Dashboard
        res_dash = client.get(f"/api/dashboard/{test_setup['comp_a_id']}")
        assert res_dash.status_code == 403, f"Dashboard leak: expected 403, got {res_dash.status_code}"

        # 2. Attacking Inventory
        res_inv = client.get(f"/api/intelligence/{test_setup['comp_a_id']}/inventory")
        assert res_inv.status_code == 403, f"Inventory leak: expected 403, got {res_inv.status_code}"

        # 3. Attacking Recommendations & Margin intelligence
        res_recs = client.get(f"/api/recommendations/{test_setup['comp_a_id']}")
        assert res_recs.status_code == 403, f"Recommendations leak: expected 403, got {res_recs.status_code}"

        # 4. Attacking Shipment creation
        res_create = client.post(
            f"/api/shipments/{test_setup['comp_a_id']}",
            json={"origin": "Hacked Plant", "destination": "Hacked Port"}
        )
        assert res_create.status_code == 403, f"Shipment creation exploit: expected 403, got {res_create.status_code}"
    finally:
        app.dependency_overrides[get_current_user] = mock_get_current_user
        db.close()


def test_adversarial_tampering_assignment_status_and_legs(test_setup, client):
    """
    Adversarial Audit 2:
    - Transporter B attempts to transition assignment status of Transporter A's shipment -> 403 Forbidden.
    - Transporter B attempts to fetch legs for Transporter A's shipment -> 403 Forbidden.
    """
    from app.main import app
    from app.auth.deps import get_current_user
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        user_trans_b = db.query(User).filter(User.id == test_setup["user_trans_b_id"]).first()
        app.dependency_overrides[get_current_user] = lambda: user_trans_b

        # Attacking assignment-action on shipment 101
        res_action = client.post(
            f"/api/v1/transporter/shipments/{test_setup['shipment_101_id']}/assignment-action",
            json={"action": "START_TRANSIT"}
        )
        assert res_action.status_code == 403
        assert "not assigned to your organization" in res_action.json()["detail"].lower()

        # Attacking legs listing on shipment 101
        res_legs = client.get(f"/api/v1/transporter/shipments/{test_setup['shipment_101_id']}/legs")
        assert res_legs.status_code == 403
        assert "not assigned to your transporter organization" in res_legs.json()["detail"].lower()
    finally:
        app.dependency_overrides[get_current_user] = mock_get_current_user
        db.close()


def test_adversarial_invitation_token_tampering(test_setup, client):
    """
    Adversarial Audit 3:
    - Transporter attempts to invite another transporter (privilege escalation) -> 403 Forbidden.
    - Attacker attempts registration with forged or non-existent token -> 400 Bad Request.
    """
    from app.main import app
    from app.auth.deps import get_current_user
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        user_trans_a = db.query(User).filter(User.id == test_setup["user_trans_a_id"]).first()
        app.dependency_overrides[get_current_user] = lambda: user_trans_a

        # Privilege escalation: Transporter trying to invite
        res_inv = client.post(
            "/api/v1/transporter/invite",
            json={"carrier_name": "Rogue Logistics", "email": "rogue@carrier.com"}
        )
        assert res_inv.status_code == 403
        assert "only company administrators can invite" in res_inv.json()["detail"].lower()

        # Registration with forged token
        app.dependency_overrides[get_current_user] = mock_get_current_user
        res_reg = client.post(
            "/api/v1/transporter/register",
            json={
                "email": "infiltrator@fake.com",
                "password": "Password123!",
                "carrier_name": "Fake Corp",
                "invite_token": "FORGED-TOKEN-12345"
            }
        )
        assert res_reg.status_code == 400
        assert "invalid or already used invite token" in res_reg.json()["detail"].lower()
    finally:
        app.dependency_overrides[get_current_user] = mock_get_current_user
        db.close()


def test_company_control_tower_disruption_visibility(test_setup, client):
    """
    Adversarial Audit 4: Verify end-to-end Control Tower integration:
    - Transporter A reports disruption on Company A shipment.
    - Company Admin A accesses /recent-disruptions -> Disruption event is visible with correct telemetry.
    - Company Admin B accesses /recent-disruptions -> Disruption event is NOT visible (zero leakage).
    """
    from app.main import app
    from app.auth.deps import get_current_user
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        # Create Company Admin A and Admin B users
        admin_a = User(email="adminA@companyA.com", hashed_password="pw", role="company", company_id=test_setup["comp_a_id"])
        admin_b = User(email="adminB@companyB.com", hashed_password="pw", role="company", company_id=test_setup["comp_b_id"])
        db.add(admin_a)
        db.add(admin_b)
        db.commit()

        # Step 1: Transporter A reports a disruption on Company A's shipment
        user_trans_a = db.query(User).filter(User.id == test_setup["user_trans_a_id"]).first()
        app.dependency_overrides[get_current_user] = lambda: user_trans_a

        res_report = client.post(
            f"/api/v1/transporter/shipments/{test_setup['shipment_101_id']}/legs/{test_setup['leg_101_id']}/report-disruption",
            json={
                "delay_hours": 16.0,
                "disruption_reason": "Severe weather",
                "incident_location": "Coimbatore Bypass",
                "notes": "Highway flooded, rerouting via Salem"
            }
        )
        assert res_report.status_code == 200

        # Step 2: Company Admin A inspects Control Tower feed
        app.dependency_overrides[get_current_user] = lambda: admin_a
        res_feed_a = client.get("/api/v1/transporter/recent-disruptions")
        assert res_feed_a.status_code == 200
        feed_a_data = res_feed_a.json()
        assert len(feed_a_data) >= 1
        assert any(item["external_shipment_id"] == "SHP-101" for item in feed_a_data)
        item_a = next(i for i in feed_a_data if i["external_shipment_id"] == "SHP-101")
        assert item_a["incident_location"] == "Coimbatore Bypass"
        assert item_a["delay_hours"] == 16.0

        # Step 3: Company Admin B inspects Control Tower feed -> MUST NOT see Company A's disruption
        app.dependency_overrides[get_current_user] = lambda: admin_b
        res_feed_b = client.get("/api/v1/transporter/recent-disruptions")
        assert res_feed_b.status_code == 200
        feed_b_data = res_feed_b.json()
        assert not any(item["external_shipment_id"] == "SHP-101" for item in feed_b_data)
    finally:
        app.dependency_overrides[get_current_user] = mock_get_current_user
        db.close()


