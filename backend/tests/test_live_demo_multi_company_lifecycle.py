"""
SUPPLYIQ - End-to-End Multi-Company Live Demonstration Integration Test.
Validates the complete 20-step lifecycle across:
- Manufacturer: Company A (Bengaluru Manufacturing Ltd)
- Transporter: Company B (Karnataka-Tamil Nadu Express Logistics)
- Receiver: Company C (Chennai Central Distribution)

Executes all 10 core FastAPI route functions, verifying authentication,
tenant isolation, shipment dispatch, assignment acceptance, sequential leg handover,
mid-transit delay reporting, downstream stockout simulation, Action Center mitigation approval,
and final delivery receipt with warehouse inventory replenishment.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime, timedelta
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app.models import (
    Company, User, Warehouse, Product, InventoryRecord, 
    Shipment, TransporterOrganization, Alert
)
from app.models.shipment_leg import ShipmentLeg, DisruptionReport
from app.models.action_approval import ActionApproval
from app.services.demo_seeder import ensure_demo_accounts_seeded, reset_benchmark_corridor
from app.auth.deps import get_current_user
from fastapi import HTTPException
from app.routes.auth import login_access_token
from app.routes.shipments import (
    create_shipment, 
    complete_shipment_leg, 
    confirm_shipment_delivery, 
    list_shipment_risk
)
from app.routes.transporter import (
    update_assignment_status, 
    report_shipment_delay
)
from app.routes.recommendations import (
    recommendations as get_recommendations,
    approve_action,
    ActionApprovalRequest
)
from app.schemas.transporter import (
    AssignmentActionRequest, 
    TransporterDelayRequest
)


def run_e2e_lifecycle_test():
    print("=" * 75)
    print("  SUPPLYIQ - END-TO-END MULTI-COMPANY TRANSPORTATION & INVENTORY LIFECYCLE")
    print("=" * 75)

    import tempfile, shutil
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    temp_dir = tempfile.mkdtemp(prefix="supplyiq_e2e_")
    src_db = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "supplyiq.db")
    isolated_db_path = os.path.join(temp_dir, "isolated_supplyiq.db")
    shutil.copy2(src_db, isolated_db_path)

    engine = create_engine(f"sqlite:///{isolated_db_path}", connect_args={"check_same_thread": False})
    IsolatedSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db: Session = IsolatedSession()

    seed_res = ensure_demo_accounts_seeded(db)
    reset_res = reset_benchmark_corridor(db)
    print(f"[INIT] Master database & demo entities seeded: {seed_res['status']}")
    print(f"[INIT] Benchmark corridor reset: {reset_res['shipment_id']} (Baseline On-Hand: {reset_res['initial_inventory']} units)")

    # 2. Phase 1: Authentication & Role Verification for 3 Companies
    print("\n[PHASE 1] Authenticating 3 Independent Enterprise Roles...")
    
    # 2a. Manufacturer (Company A)
    auth_a = login_access_token(db=db, form_data=OAuth2PasswordRequestForm(
        grant_type="password", username="sender@companyA.com", password="sender123", scope=""
    ))
    user_a = get_current_user(db=db, token=auth_a["access_token"])
    assert user_a.role == "company", "User A should have 'company' role"
    print(f"  [✓] Company A (Manufacturer): Authenticated as {user_a.email} (Tenant ID: {user_a.company_id})")

    # 2b. Transporter / Carrier (Company B)
    auth_b = login_access_token(db=db, form_data=OAuth2PasswordRequestForm(
        grant_type="password", username="transporter@companyB.com", password="transporter123", scope=""
    ))
    user_b = get_current_user(db=db, token=auth_b["access_token"])
    assert user_b.role == "transporter", "User B should have 'transporter' role"
    print(f"  [✓] Company B (Transporter Fleet): Authenticated as {user_b.email} (Carrier: {user_b.carrier_name})")

    # 2c. Receiver / Consignee (Company C)
    auth_c = login_access_token(db=db, form_data=OAuth2PasswordRequestForm(
        grant_type="password", username="receiver@companyC.com", password="receiver123", scope=""
    ))
    user_c = get_current_user(db=db, token=auth_c["access_token"])
    assert user_c.role == "company", "User C should have 'company' role"
    print(f"  [✓] Company C (Receiver DC): Authenticated as {user_c.email} (Tenant ID: {user_c.company_id})")

    # Resolve core company models
    comp_a = db.query(Company).filter(Company.name == "Bengaluru Manufacturing Ltd").first()
    comp_c = db.query(Company).filter(Company.name == "Chennai Central Distribution").first()
    carrier_b = db.query(TransporterOrganization).filter(TransporterOrganization.name == "Karnataka-Tamil Nadu Express Logistics").first()
    wh_c = db.query(Warehouse).filter(Warehouse.company_id == comp_c.id, Warehouse.name == "Chennai Central DC").first()
    prod_a = db.query(Product).filter(Product.company_id == comp_a.id, Product.external_product_id == "SKU-BLR-101").first()

    assert comp_a and comp_c and carrier_b and wh_c and prod_a, "Required entities missing from database"

    # 3. Phase 2: Manufacturer Dispatches New Multi-Company Shipment
    print("\n[PHASE 2] Manufacturer (Company A) Creates & Dispatches New Shipment...")
    dispatch_payload = {
        "product_id": prod_a.id,
        "receiver_company_id": comp_c.id,
        "destination_warehouse_id": wh_c.id,
        "transporter_org_id": carrier_b.id,
        "carrier": carrier_b.name,
        "origin": "Bengaluru Electronic City Plant, Karnataka",
        "destination": "Chennai Central DC, Tamil Nadu",
        "transport_mode": "ROAD",
        "quantity": 120.0,
        "distance_km": 360.0,
        "planned_delivery": str(date.today() + timedelta(days=2))
    }
    new_shipment_res = create_shipment(company_id=comp_a.id, payload=dispatch_payload, db=db, current_user=user_a)
    new_id = new_shipment_res["id"]
    new_ref = new_shipment_res["external_shipment_id"]
    print(f"  [✓] Shipment Generated: {new_ref} (DB ID: {new_id})")
    print(f"  [✓] Assignment Status: {new_shipment_res['assignment_status']}, Multimodal Legs: {new_shipment_res['legs_count']}")
    assert new_shipment_res["assignment_status"] == "PENDING", "Initial carrier status should be PENDING"

    # 4. Phase 3: Transporter Accepts Shipment Assignment
    print("\n[PHASE 3] Transporter (Company B) Accepts Assigned Shipment...")
    accept_res = update_assignment_status(
        shipment_id=new_id,
        req=AssignmentActionRequest(action="ACCEPT"),
        current_user=user_b,
        db=db
    )
    print(f"  [✓] Transporter Accepted: Status = {accept_res['assignment_status']}")
    assert accept_res["assignment_status"] == "ACCEPTED"

    # 5. Phase 4: Inspect Benchmark Corridor SH-BLR-2026-0001
    print("\n[PHASE 4] Inspecting Pre-Seeded Benchmark Corridor: SH-BLR-2026-0001...")
    s_blr = db.query(Shipment).filter(Shipment.external_shipment_id == "SH-BLR-2026-0001").first()
    assert s_blr is not None, "Benchmark shipment SH-BLR-2026-0001 missing"
    legs = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == s_blr.id).order_by(ShipmentLeg.sequence).all()
    assert len(legs) == 3, f"Expected 3 legs, got {len(legs)}"

    # Reset benchmark shipment to fresh initial transit state
    s_blr.assignment_status = "IN_TRANSIT"
    legs[0].status = "COMPLETED"
    legs[1].status = "IN_TRANSIT"
    legs[1].delay_hours = 0.0
    legs[2].status = "SCHEDULED"
    db.commit()

    print(f"  [✓] Benchmark Shipment ID: {s_blr.external_shipment_id} (Status: {s_blr.assignment_status})")
    print(f"  [✓] Leg Sequence: Leg #1 ({legs[0].status}) → Leg #2 ({legs[1].status}) → Leg #3 ({legs[2].status})")
    assert legs[0].status == "COMPLETED"
    assert legs[1].status == "IN_TRANSIT"
    assert legs[2].status == "SCHEDULED"

    # 6. Phase 5: Mid-Transit Delay Reporting by Carrier on Leg #2
    print("\n[PHASE 5] Transporter Reports Mid-Transit Highway Delay on Leg #2 (+16 Hours)...")
    delay_res = report_shipment_delay(
        shipment_id=s_blr.id,
        req=TransporterDelayRequest(
            delay_hours=16.0,
            reason="Severe Weather / Landslide",
            notes="Highway 48 closed near Vellore due to rockslide.",
            leg_id=legs[1].id
        ),
        current_user=user_b,
        db=db
    )
    print(f"  [✓] Operational Delay Broadcasted: +{delay_res.delay_hours}h due to {delay_res.reason}")
    print(f"  [✓] Revised Destination ETA: {delay_res.new_eta}, Status: {delay_res.status}")
    assert delay_res.status == "DELAYED"
    assert delay_res.delay_hours == 16.0

    # 7. Phase 6: Downstream Stockout Impact & Action Center Evaluation
    print("\n[PHASE 6] Evaluating Destination Stockout Exposure at Chennai DC (Company C)...")
    recs_res = get_recommendations(company_id=comp_c.id, db=db, current_user=user_c)
    recs = recs_res.get("recommendations", [])
    disruption_recs = [r for r in recs if r.get("action_type") == "DISRUPTION_MITIGATION"]
    assert len(disruption_recs) > 0, "Disruption mitigation recommendation not found for Company C"
    top_rec = disruption_recs[0]
    print(f"  [✓] Prescriptive Mitigation: {top_rec['action']} (Priority: {top_rec['priority']})")
    print(f"  [✓] Quantified Stockout Penalty: {top_rec['financial_impact']}")
    print(f"  [✓] Mitigation Cost: ₹{top_rec['estimated_cost']}, Net ROI Savings: ₹{top_rec['net_savings']:,.2f}")
    print(f"  [✓] Decision Reasoning: {top_rec['why_best']}")
    assert top_rec["priority"] == "CRITICAL"
    assert top_rec["financial_impact"] == "₹171,600.00", f"Expected ₹171,600.00 financial impact, got {top_rec['financial_impact']}"
    assert top_rec["net_savings"] == 171150.0, f"Expected 171150.0 net savings, got {top_rec['net_savings']}"
    assert "₹" in top_rec["financial_impact"], "Currency should be formatted in Indian Rupees (₹)"

    # 8. Phase 7: Authorized Manager Approves Mitigation Action
    print("\n[PHASE 7] Company C Manager Approves Action in Control Tower...")
    action_id = top_rec["target_id"]
    approval_res = approve_action(
        company_id=comp_c.id,
        payload=ActionApprovalRequest(action_id=action_id, notes="Approved for immediate inter-hub dispatch to prevent stockout."),
        db=db,
        current_user=user_c
    )
    print(f"  [✓] Action Approval Status: {approval_res['status']} (Action ID: {approval_res['action_id']})")
    assert approval_res["status"] == "APPROVED"

    # Verify persistent DB record
    approval_rec = db.query(ActionApproval).filter(
        ActionApproval.action_id == action_id, 
        ActionApproval.company_id == comp_c.id
    ).first()
    assert approval_rec is not None, "Action approval was not written to action_approvals table"
    print(f"  [✓] Auditable DB Persistence Verified: Approved by User ID {approval_rec.user_id}")

    # 9. Phase 8: Complete Leg #2 -> Handover Activates Leg #3
    print("\n[PHASE 8] Carrier Completes Leg #2 (Hosur → Sriperumbudur Depot)...")
    adv2_res = complete_shipment_leg(
        shipment_id=s_blr.id,
        leg_id=legs[1].id,
        db=db,
        current_user=user_b
    )
    print(f"  [✓] Handover Completed: {adv2_res['message']}")
    assert adv2_res["completed_leg"]["status"] == "COMPLETED"
    assert adv2_res["next_leg"]["sequence"] == 3
    assert adv2_res["next_leg"]["status"] == "IN_TRANSIT"

    # 10. Phase 9: Complete Leg #3 -> Cargo Arrives at Destination
    print("\n[PHASE 9] Carrier Completes Final Mile Leg #3 (Sriperumbudur → Chennai DC)...")
    adv3_res = complete_shipment_leg(
        shipment_id=s_blr.id,
        leg_id=legs[2].id,
        db=db,
        current_user=user_b
    )
    print(f"  [✓] Arrival Confirmed: {adv3_res['message']}")
    assert adv3_res["assignment_status"] == "ARRIVED"

    # 11. Phase 10: Receiver Confirms Delivery & Accepts Stock into Warehouse
    print("\n[PHASE 10] Receiver Confirms Delivery & Accepts Stock into Chennai Central DC...")
    inv_before = db.query(InventoryRecord).filter(
        InventoryRecord.company_id == comp_c.id,
        InventoryRecord.warehouse_id == wh_c.id
    ).order_by(InventoryRecord.date.desc()).first()
    stock_before = inv_before.inventory_level if inv_before else 0.0
    assert stock_before == 85.0, f"Expected deterministic initial inventory 85.0 units, got {stock_before}"

    deliv_res = confirm_shipment_delivery(
        shipment_id=s_blr.id,
        payload={"received_quantity": 100.0},
        db=db,
        current_user=user_c
    )
    print(f"  [✓] Delivery Status: {deliv_res['status']} at {deliv_res['warehouse_name']}")
    print(f"  [✓] Accepted Stock: +{deliv_res['received_quantity']} units")
    print(f"  [✓] Updated On-Hand Inventory: {deliv_res['new_inventory_level']} units (was {stock_before} units)")
    assert deliv_res["status"] == "DELIVERED"
    assert deliv_res["new_inventory_level"] == 185.0, f"Expected exactly 185.0 units (85 + 100), got {deliv_res['new_inventory_level']}"

    # Verify Idempotency: Duplicate delivery call must NOT double-increment inventory
    print("  [✓] Verifying Delivery Idempotency...")
    dup_res = confirm_shipment_delivery(
        shipment_id=s_blr.id,
        payload={"received_quantity": 100.0},
        db=db,
        current_user=user_c
    )
    assert dup_res["status"] == "DELIVERED"
    inv_after = db.query(InventoryRecord).filter(
        InventoryRecord.company_id == comp_c.id,
        InventoryRecord.warehouse_id == wh_c.id
    ).order_by(InventoryRecord.date.desc()).first()
    assert inv_after.inventory_level == 185.0, "Duplicate delivery call incorrectly added double inventory!"
    print("  [✓] Delivery Idempotency Verified: Inventory level remains 185.0 units.")

    # 12. Phase 11: Verify Cross-Company Visibility Across Both Tenant Dashboards
    print("\n[PHASE 11] Verifying Real-Time Cross-Company Visibility...")
    # Sender Dashboard
    sender_view = list_shipment_risk(company_id=comp_a.id, db=db, current_user=user_a)
    s_in_sender = next((s for s in sender_view.shipments if s.external_shipment_id == "SH-BLR-2026-0001"), None)
    assert s_in_sender is not None, "Shipment not visible in Sender Control Tower"
    assert s_in_sender.assignment_status == "DELIVERED"
    print(f"  [✓] Sender Control Tower (Company A): {s_in_sender.external_shipment_id} → {s_in_sender.assignment_status}")

    # Receiver Dashboard
    receiver_view = list_shipment_risk(company_id=comp_c.id, db=db, current_user=user_c)
    s_in_receiver = next((s for s in receiver_view.shipments if s.external_shipment_id == "SH-BLR-2026-0001"), None)
    assert s_in_receiver is not None, "Shipment not visible in Receiver Control Tower"
    assert s_in_receiver.assignment_status == "DELIVERED"
    print(f"  [✓] Receiver Control Tower (Company C): {s_in_receiver.external_shipment_id} → {s_in_receiver.assignment_status}")

    # 13. Phase 12: Negative Security & RBAC Isolation Verification
    print("\n[PHASE 12] Testing Strict RBAC, Tenant Isolation & Negative Permissions...")

    # 13a. Carrier attempts to create a shipment directly -> 403 Forbidden
    try:
        create_shipment(company_id=comp_a.id, payload=dispatch_payload, db=db, current_user=user_b)
        assert False, "Security violation: Carrier should NOT be permitted to create shipments!"
    except HTTPException as e:
        assert e.status_code == 403
        print(f"  [✓] RBAC Rejection: Carrier cannot create shipments ({e.detail})")

    # 13b. Carrier attempts to confirm delivery & replenish warehouse -> 403 Forbidden
    try:
        confirm_shipment_delivery(shipment_id=s_blr.id, payload={"received_quantity": 100.0}, db=db, current_user=user_b)
        assert False, "Security violation: Carrier should NOT be permitted to confirm delivery on receiver warehouse!"
    except HTTPException as e:
        assert e.status_code == 403
        print(f"  [✓] RBAC Rejection: Carrier cannot confirm final delivery on receiver DC ({e.detail})")

    # 13c. Cross-Tenant Isolation: Company A user attempts to list Company C's private shipments -> 403 Forbidden
    try:
        list_shipment_risk(company_id=comp_c.id, db=db, current_user=user_a)
        assert False, "Tenant isolation violation: Company A should NOT access Company C's shipment endpoint!"
    except HTTPException as e:
        assert e.status_code == 403
        print(f"  [✓] Tenant Isolation Enforced: Cross-company access rejected ({e.detail})")

    # 13d. Sequential Integrity: Attempt to complete Leg 3 on a new shipment when Leg 1 is incomplete -> 400 Bad Request
    new_legs = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == new_id).order_by(ShipmentLeg.sequence).all()
    if len(new_legs) >= 3:
        try:
            complete_shipment_leg(shipment_id=new_id, leg_id=new_legs[2].id, db=db, current_user=user_b)
            assert False, "Sequential violation: Out-of-order leg completion should be rejected!"
        except HTTPException as e:
            assert e.status_code == 400
            print(f"  [✓] Sequential Integrity Enforced: Leg 3 blocked until preceding legs complete ({e.detail})")

    # 13e. Cannot advance legs on an already DELIVERED shipment -> 400 Bad Request
    try:
        complete_shipment_leg(shipment_id=s_blr.id, leg_id=legs[1].id, db=db, current_user=user_b)
        assert False, "Should not be able to advance legs on a DELIVERED shipment!"
    except HTTPException as e:
        assert e.status_code == 400
        print(f"  [✓] Delivered Shipment Guard: {e.detail}")

    # 13f. Leg Completion Idempotency on in-progress shipment:
    # First complete Leg 1 on the newly dispatched shipment
    adv_new_1 = complete_shipment_leg(shipment_id=new_id, leg_id=new_legs[0].id, db=db, current_user=user_b)
    assert adv_new_1["completed_leg"]["status"] == "COMPLETED"
    # Call complete Leg 1 again -> must return cleanly with idempotent notice
    adv_new_dup = complete_shipment_leg(shipment_id=new_id, leg_id=new_legs[0].id, db=db, current_user=user_b)
    assert "already marked COMPLETED" in adv_new_dup["message"]
    print(f"  [✓] Leg Completion Idempotency Enforced: {adv_new_dup['message']}")

    db.close()
    engine.dispose()
    shutil.rmtree(temp_dir, ignore_errors=True)
    print("\n" + "=" * 75)
    print("  ALL 12 END-TO-END VERIFICATION PHASES PASSED WITH 100% SUCCESS!")
    print("=" * 75)


if __name__ == "__main__":
    run_e2e_lifecycle_test()
