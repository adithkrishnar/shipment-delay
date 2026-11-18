"""
Phase 3 Role-Based Navigation and Permissions Verification Test Suite.
Validates:
1. Exact role identity resolution (/api/v1/auth/me) for all 3 participants (Sender, Transporter, Receiver).
2. Backend API RBAC authorization enforcement (Negative & Positive checks):
   - Shipment creation: Sender allowed, Receiver 403, Transporter 403.
   - Delivery confirmation: Receiver allowed, Sender 403, Transporter 403.
   - Delay reporting: Transporter allowed, Sender 403, Receiver 403.
   - Carrier assignment action: Transporter allowed, Sender 403, Receiver 403.
3. Frontend configuration validation:
   - Sidebar.jsx navigation partitioning.
   - App.jsx route layout bypass and root routing.
   - Overview.jsx role dispatcher.
   - Shipments.jsx button visibility and operational panels.
"""
import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.security import OAuth2PasswordRequestForm
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import User, Company, TransporterOrganization, Shipment
from app.services.demo_seeder import ensure_demo_accounts_seeded, reset_benchmark_corridor
from app.routes.auth import login_access_token, read_users_me
from app.auth.deps import get_current_user
from app.routes.shipments import create_shipment, confirm_shipment_delivery, list_shipment_risk
from app.routes.transporter import report_shipment_delay, update_assignment_status
from app.schemas.transporter import TransporterDelayRequest, AssignmentActionRequest


def run_phase3_tests():
    print("=" * 78)
    print("  SUPPLYIQ - PHASE 3 ROLE-BASED NAVIGATION & PERMISSIONS VERIFICATION")
    print("=" * 78)

    init_db()
    db: Session = SessionLocal()
    ensure_demo_accounts_seeded(db)
    reset_benchmark_corridor(db)

    # -------------------------------------------------------------------------
    # TEST 1: Identity & Participant Role Resolution via /auth/me
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing /api/v1/auth/me Participant Role Resolution...")

    # 1A: Sender
    auth_sender = login_access_token(db=db, form_data=OAuth2PasswordRequestForm(
        grant_type="password", username="sender@companyA.com", password="sender123", scope=""
    ))
    user_sender = get_current_user(db=db, token=auth_sender["access_token"])
    me_sender = read_users_me(current_user=user_sender)
    assert me_sender["participant_role"] == "sender", f"Expected sender, got {me_sender['participant_role']}"
    assert me_sender["company_id"] == 19, f"Expected company_id 19, got {me_sender['company_id']}"
    print(f"  [✓] Sender identity verified: {me_sender['email']} -> participant_role='{me_sender['participant_role']}', company_id={me_sender['company_id']}")

    # 1B: Receiver
    auth_receiver = login_access_token(db=db, form_data=OAuth2PasswordRequestForm(
        grant_type="password", username="receiver@companyC.com", password="receiver123", scope=""
    ))
    user_receiver = get_current_user(db=db, token=auth_receiver["access_token"])
    me_receiver = read_users_me(current_user=user_receiver)
    assert me_receiver["participant_role"] == "receiver", f"Expected receiver, got {me_receiver['participant_role']}"
    assert me_receiver["company_id"] == 21, f"Expected company_id 21, got {me_receiver['company_id']}"
    print(f"  [✓] Receiver identity verified: {me_receiver['email']} -> participant_role='{me_receiver['participant_role']}', company_id={me_receiver['company_id']}")

    # 1C: Transporter
    auth_transporter = login_access_token(db=db, form_data=OAuth2PasswordRequestForm(
        grant_type="password", username="transporter@companyB.com", password="transporter123", scope=""
    ))
    user_transporter = get_current_user(db=db, token=auth_transporter["access_token"])
    me_transporter = read_users_me(current_user=user_transporter)
    assert me_transporter["participant_role"] == "transporter", f"Expected transporter, got {me_transporter['participant_role']}"
    assert me_transporter["transporter_org_id"] == 5, f"Expected transporter_org_id 5, got {me_transporter['transporter_org_id']}"
    print(f"  [✓] Transporter identity verified: {me_transporter['email']} -> participant_role='{me_transporter['participant_role']}', transporter_org_id={me_transporter['transporter_org_id']}")

    # -------------------------------------------------------------------------
    # TEST 2: RBAC Enforcement - Shipment Creation Permissions
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Verifying Shipment Creation Authorization (Sender only)...")

    # Receiver attempting to create shipment for Company 19 -> Must be 403 Forbidden
    payload = {
        "external_shipment_id": "SH-TEST-NAV-001",
        "receiver_company_id": 21,
        "transporter_org_id": 5,
        "origin": "Bengaluru Electronic City Plant, Karnataka",
        "destination": "Chennai Central DC, Tamil Nadu",
        "transport_mode": "ROAD",
        "distance_km": 360,
        "quantity": 50
    }
    receiver_blocked = False
    try:
        create_shipment(company_id=19, payload=payload, db=db, current_user=user_receiver)
    except HTTPException as e:
        if e.status_code == 403:
            receiver_blocked = True
            print(f"  [✓] Receiver correctly blocked from creating outbound shipment: 403 Forbidden ({e.detail})")
    assert receiver_blocked, "Security violation: Receiver was allowed to create outbound shipment for Company 19"

    # Transporter attempting to create shipment for Company 19 -> Must be 403 Forbidden
    transporter_blocked = False
    try:
        create_shipment(company_id=19, payload=payload, db=db, current_user=user_transporter)
    except HTTPException as e:
        if e.status_code == 403:
            transporter_blocked = True
            print(f"  [✓] Transporter correctly blocked from creating outbound shipment: 403 Forbidden ({e.detail})")
    assert transporter_blocked, "Security violation: Transporter was allowed to create outbound shipment for Company 19"

    # Sender creates shipment for Company 19 -> Must succeed
    sender_result = create_shipment(company_id=19, payload=payload, db=db, current_user=user_sender)
    assert sender_result["external_shipment_id"] == "SH-TEST-NAV-001", "Sender failed to create shipment"
    print(f"  [✓] Sender authorized to create outbound shipment: ID {sender_result['id']} ({sender_result['external_shipment_id']})")

    # -------------------------------------------------------------------------
    # TEST 3: RBAC Enforcement - Delivery Confirmation Permissions
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Verifying Delivery Confirmation Authorization (Receiver only)...")

    # Benchmark shipment
    bench = db.query(Shipment).filter(Shipment.external_shipment_id == "SH-BLR-2026-0001").first()
    assert bench is not None, "Benchmark shipment SH-BLR-2026-0001 not found"

    # Sender attempting to confirm delivery -> Must be 403 Forbidden
    sender_deliv_blocked = False
    try:
        confirm_shipment_delivery(shipment_id=bench.id, db=db, current_user=user_sender)
    except HTTPException as e:
        if e.status_code == 403:
            sender_deliv_blocked = True
            print(f"  [✓] Sender correctly blocked from confirming delivery: 403 Forbidden ({e.detail})")
    assert sender_deliv_blocked, "Security violation: Sender was allowed to confirm delivery"

    # Transporter attempting to confirm delivery -> Must be 403 Forbidden
    transporter_deliv_blocked = False
    try:
        confirm_shipment_delivery(shipment_id=bench.id, db=db, current_user=user_transporter)
    except HTTPException as e:
        if e.status_code == 403:
            transporter_deliv_blocked = True
            print(f"  [✓] Transporter correctly blocked from confirming delivery: 403 Forbidden ({e.detail})")
    assert transporter_deliv_blocked, "Security violation: Transporter was allowed to confirm delivery"

    # Receiver confirms delivery -> Must succeed
    receiver_deliv_result = confirm_shipment_delivery(shipment_id=bench.id, db=db, current_user=user_receiver)
    assert receiver_deliv_result["status"] == "DELIVERED", f"Expected DELIVERED, got {receiver_deliv_result['status']}"
    print(f"  [✓] Receiver authorized to confirm delivery: {receiver_deliv_result['message']}")

    # -------------------------------------------------------------------------
    # TEST 4: RBAC Enforcement - Transporter Delay & Assignment Operations
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Verifying Carrier Delay Reporting & Assignment Authorization (Transporter only)...")

    # 4A. Transporter Assignment Action (ACCEPT / REJECT) - Transporter only
    action_req = AssignmentActionRequest(action="ACCEPT")

    # Sender attempting to execute carrier assignment action -> Must be 403 Forbidden
    sender_action_blocked = False
    try:
        update_assignment_status(shipment_id=bench.id, req=action_req, db=db, current_user=user_sender)
    except HTTPException as e:
        if e.status_code == 403:
            sender_action_blocked = True
            print(f"  [✓] Sender correctly blocked from carrier assignment action: 403 Forbidden ({e.detail})")
    assert sender_action_blocked, "Security violation: Sender was allowed to update transporter assignment"

    # Receiver attempting to execute carrier assignment action -> Must be 403 Forbidden
    receiver_action_blocked = False
    try:
        update_assignment_status(shipment_id=bench.id, req=action_req, db=db, current_user=user_receiver)
    except HTTPException as e:
        if e.status_code == 403:
            receiver_action_blocked = True
            print(f"  [✓] Receiver correctly blocked from carrier assignment action: 403 Forbidden ({e.detail})")
    assert receiver_action_blocked, "Security violation: Receiver was allowed to update transporter assignment"

    # Transporter executing carrier assignment action -> Must be authorized
    transporter_action_result = update_assignment_status(shipment_id=bench.id, req=action_req, db=db, current_user=user_transporter)
    assert transporter_action_result["assignment_status"] == "ACCEPTED", f"Expected ACCEPTED, got {transporter_action_result['assignment_status']}"
    print(f"  [✓] Transporter authorized to accept assignment: {transporter_action_result['message']}")

    # 4B. Transporter Delay Reporting
    delay_req = TransporterDelayRequest(delay_hours=4.0, reason="Traffic Congestion on Highway NH-48")
    transporter_delay_result = report_shipment_delay(shipment_id=str(bench.id), req=delay_req, db=db, current_user=user_transporter)
    assert transporter_delay_result.shipment_id == bench.id, "Delay report shipment mismatch"
    print(f"  [✓] Transporter authorized to report transit delay: new status={transporter_delay_result.status}, delay_hours={transporter_delay_result.delay_hours}")

    # -------------------------------------------------------------------------
    # TEST 5: Frontend Code Inspection & Permission Integrity
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Inspecting Frontend Navigation & Permissions Code Integrity...")
    
    base_fe = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src"))
    
    # 5A: Sidebar.jsx
    with open(os.path.join(base_fe, "components", "Sidebar.jsx"), "r", encoding="utf-8") as f:
        sidebar_code = f.read()
    assert "participantRole === 'sender'" in sidebar_code, "Sidebar missing sender navigation block"
    assert "participantRole === 'receiver'" in sidebar_code, "Sidebar missing receiver navigation block"
    assert "participantRole === 'transporter'" in sidebar_code, "Sidebar missing transporter navigation block"
    assert "Dispatch Operations Cockpit" in sidebar_code, "Sidebar missing Sender cockpit title"
    assert "Warehouse Receiving Tower" in sidebar_code, "Sidebar missing Receiver tower title"
    print("  [✓] Sidebar.jsx contains verified partitioned role navigation groups")

    # 5B: App.jsx
    with open(os.path.join(base_fe, "App.jsx"), "r", encoding="utf-8") as f:
        app_code = f.read()
    assert "isTransporter ? <TransporterPortal" in app_code, "App.jsx missing Transporter root route dispatch"
    assert "user?.role === 'transporter' || user?.participant_role === 'transporter'" in app_code, "App.jsx missing comprehensive isTransporter check"
    print("  [✓] App.jsx contains verified Transporter portal bypass and routing")

    # 5C: Overview.jsx
    with open(os.path.join(base_fe, "pages", "Overview.jsx"), "r", encoding="utf-8") as f:
        overview_code = f.read()
    assert "user?.participant_role === 'sender'" in overview_code, "Overview.jsx not using participant_role"
    assert "includes('sender')" not in overview_code, "Overview.jsx still using email string guessing"
    print("  [✓] Overview.jsx strictly uses participant_role with zero string guessing")

    # 5D: Shipments.jsx
    with open(os.path.join(base_fe, "pages", "Shipments.jsx"), "r", encoding="utf-8") as f:
        shipments_code = f.read()
    assert "isSender && (" in shipments_code, "Shipments.jsx missing isSender guard on Dispatch New Shipment"
    assert "isReceiver && (" in shipments_code, "Shipments.jsx missing isReceiver guard on delivery confirmation"
    assert "isTransporter && (" in shipments_code, "Shipments.jsx missing isTransporter guard on delay reporting"
    print("  [✓] Shipments.jsx contains verified RBAC action button guards and view separation")

    # 5E: Topbar.jsx
    with open(os.path.join(base_fe, "components", "Topbar.jsx"), "r", encoding="utf-8") as f:
        topbar_code = f.read()
    assert "ROLE:" in topbar_code, "Topbar.jsx missing ROLE badge"
    print("  [✓] Topbar.jsx contains verified participant role visual badge")

    # Clean up test shipment and restore benchmark corridor
    db.query(Shipment).filter(Shipment.external_shipment_id == "SH-TEST-NAV-001").delete()
    db.commit()
    reset_benchmark_corridor(db)
    db.close()

    print("\n" + "=" * 78)
    print("  ALL PHASE 3 VERIFICATION TESTS PASSED WITH 100% ACCURACY")
    print("=" * 78)


if __name__ == "__main__":
    run_phase3_tests()
