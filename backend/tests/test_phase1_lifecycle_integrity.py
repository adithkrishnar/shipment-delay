"""
Phase 1 Verification: Critical Shipment Lifecycle & Inventory Integrity.
Validates DEF-001 (Premature Delivery Rejection & Inward Guards) and
DEF-002 (Transporter COMPLETE_DELIVERY Bypass Prevention).

Executes against an isolated, disposable temporary SQLite database cloned from
the benchmark, ensuring backend/supplyiq.db is strictly untouched.
"""

import os
import sys
import shutil
import tempfile

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from datetime import date, datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set isolated test database path before loading models
TEMP_DIR = tempfile.mkdtemp(prefix="supplyiq_phase1_")
ISOLATED_DB_PATH = os.path.join(TEMP_DIR, "isolated_supplyiq.db")
BENCHMARK_DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "supplyiq.db")
)

# Clone benchmark DB to isolated location
shutil.copyfile(BENCHMARK_DB_PATH, ISOLATED_DB_PATH)

# Point SQLAlchemy to isolated disposable database
test_engine = create_engine(f"sqlite:///{ISOLATED_DB_PATH}", connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

from app.models import (
    Company, User, Warehouse, Product, InventoryRecord,
    Shipment, TransporterOrganization, Alert
)
from app.models.shipment_leg import ShipmentLeg
from app.routes.shipments import confirm_shipment_delivery
from app.routes.transporter import update_assignment_status
from app.schemas.transporter import AssignmentActionRequest


def run_phase1_verification_suite():
    db = TestSession()
    print("======================================================================")
    print("SUPPLYIQ PHASE 1: CRITICAL LIFECYCLE & INVENTORY INTEGRITY TEST SUITE")
    print(f"Isolated Disposable DB: {ISOLATED_DB_PATH}")
    print("======================================================================\n")

    # Resolve test fixtures from isolated DB
    comp_a = db.query(Company).filter(Company.name.ilike("%Bengaluru%")).first()
    comp_b_org = db.query(TransporterOrganization).filter(TransporterOrganization.name.ilike("%Karnataka%")).first()
    comp_c = db.query(Company).filter(Company.name.ilike("%Chennai%")).first()

    assert comp_a and comp_b_org and comp_c, "Failed to resolve Company A, Carrier B, or Company C fixtures."

    user_sender = db.query(User).filter(User.company_id == comp_a.id, User.role == "company").first()
    user_carrier = db.query(User).filter(User.transporter_org_id == comp_b_org.id, User.role == "transporter").first()
    user_receiver = db.query(User).filter(User.company_id == comp_c.id, User.role == "company").first()
    user_unauthorized = db.query(User).filter(User.company_id != comp_c.id, User.role == "company").first()

    assert user_sender and user_carrier and user_receiver, "Failed to resolve role users."

    wh_c = db.query(Warehouse).filter(Warehouse.company_id == comp_c.id).first()
    assert wh_c, "Receiver warehouse not found."

    # Resolve product for company C
    prod_c = db.query(Product).filter(Product.company_id == comp_c.id).first()
    assert prod_c, "Receiver product not found."

    inv_c = db.query(InventoryRecord).filter(
        InventoryRecord.company_id == comp_c.id,
        InventoryRecord.warehouse_id == wh_c.id,
        InventoryRecord.product_id == prod_c.id
    ).first()
    initial_stock = float(inv_c.inventory_level) if inv_c else 0.0
    print(f"[FIXTURES] Initial Receiver Warehouse Stock: {initial_stock} units")

    passed_tests = 0
    total_tests = 10

    # -------------------------------------------------------------------------
    # TEST 1: Reject Goods Inward on IN_TRANSIT shipment (DEF-001)
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing rejection of Goods Inward on IN_TRANSIT shipment...")
    shp_in_transit = Shipment(
        company_id=comp_a.id,
        receiver_company_id=comp_c.id,
        destination_warehouse_id=wh_c.id,
        product_id=prod_c.id,
        external_shipment_id="TEST-LIFECYCLE-001",
        origin="Bengaluru Electronic City Plant",
        destination="Chennai Central DC",
        carrier="Karnataka-Tamil Nadu Express Logistics",
        transporter_org_id=comp_b_org.id,
        transport_mode="ROAD",
        quantity=50.0,
        order_date=date.today(),
        planned_delivery=date.today() + timedelta(days=2),
        assignment_status="IN_TRANSIT"
    )
    db.add(shp_in_transit)
    db.commit()
    db.refresh(shp_in_transit)

    try:
        confirm_shipment_delivery(shp_in_transit.id, payload={}, db=db, current_user=user_receiver)
        assert False, "IN_TRANSIT delivery confirmation should have been rejected with HTTP 400!"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "not arrived at destination gate" in exc.detail
        print(f"  [✓] Successfully rejected with 400: '{exc.detail}'")
        db.refresh(shp_in_transit)
        assert shp_in_transit.assignment_status == "IN_TRANSIT"
        assert shp_in_transit.actual_delivery is None
        passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 2: Reject Goods Inward on DELAYED shipment (DEF-001)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Testing rejection of Goods Inward on DELAYED shipment...")
    shp_delayed = Shipment(
        company_id=comp_a.id,
        receiver_company_id=comp_c.id,
        destination_warehouse_id=wh_c.id,
        product_id=prod_c.id,
        external_shipment_id="TEST-LIFECYCLE-002",
        origin="Bengaluru Electronic City Plant",
        destination="Chennai Central DC",
        carrier="Karnataka-Tamil Nadu Express Logistics",
        transporter_org_id=comp_b_org.id,
        transport_mode="ROAD",
        quantity=50.0,
        order_date=date.today(),
        planned_delivery=date.today() + timedelta(days=2),
        assignment_status="DELAYED"
    )
    db.add(shp_delayed)
    db.commit()
    db.refresh(shp_delayed)

    try:
        confirm_shipment_delivery(shp_delayed.id, payload={}, db=db, current_user=user_receiver)
        assert False, "DELAYED delivery confirmation should have been rejected with HTTP 400!"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "not arrived at destination gate" in exc.detail
        print(f"  [✓] Successfully rejected with 400: '{exc.detail}'")
        passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 3: Reject Goods Inward on ARRIVED shipment with incomplete legs (DEF-001)
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing rejection of Goods Inward on ARRIVED shipment with incomplete legs...")
    shp_legs_inc = Shipment(
        company_id=comp_a.id,
        receiver_company_id=comp_c.id,
        destination_warehouse_id=wh_c.id,
        product_id=prod_c.id,
        external_shipment_id="TEST-LIFECYCLE-003",
        origin="Bengaluru Electronic City Plant",
        destination="Chennai Central DC",
        carrier="Karnataka-Tamil Nadu Express Logistics",
        transporter_org_id=comp_b_org.id,
        transport_mode="ROAD",
        quantity=50.0,
        order_date=date.today(),
        planned_delivery=date.today() + timedelta(days=2),
        assignment_status="ARRIVED"
    )
    db.add(shp_legs_inc)
    db.commit()
    db.refresh(shp_legs_inc)

    leg1 = ShipmentLeg(shipment_id=shp_legs_inc.id, sequence=1, mode="ROAD", origin="BLR", destination="Hosur", status="COMPLETED")
    leg2 = ShipmentLeg(shipment_id=shp_legs_inc.id, sequence=2, mode="ROAD", origin="Hosur", destination="Chennai", status="IN_TRANSIT")
    db.add_all([leg1, leg2])
    db.commit()

    try:
        confirm_shipment_delivery(shp_legs_inc.id, payload={}, db=db, current_user=user_receiver)
        assert False, "ARRIVED with incomplete legs should have been rejected with HTTP 400!"
    except HTTPException as exc:
        assert exc.status_code == 400
        assert "incomplete transportation legs" in exc.detail
        print(f"  [✓] Successfully rejected with 400: '{exc.detail}'")
        passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 4: Successful Goods Inward when ARRIVED and all legs COMPLETED (DEF-001)
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing successful Goods Inward on ARRIVED shipment with completed legs...")
    leg2.status = "COMPLETED"
    db.commit()

    db.refresh(inv_c)
    stock_before_inward = float(inv_c.inventory_level)

    res_inward = confirm_shipment_delivery(
        shp_legs_inc.id,
        payload={"received_quantity": 50.0},
        db=db,
        current_user=user_receiver
    )
    assert res_inward["status"] == "DELIVERED"
    assert res_inward["received_quantity"] == 50.0

    db.refresh(shp_legs_inc)
    assert shp_legs_inc.assignment_status == "DELIVERED"
    assert shp_legs_inc.actual_delivery == date.today()

    db.refresh(inv_c)
    stock_after_inward = float(inv_c.inventory_level)
    print(f"  [✓] Goods Inward Successful! Stock incremented from {stock_before_inward} to {stock_after_inward} (+50 units)")
    assert stock_after_inward == stock_before_inward + 50.0
    passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 5: Repeated confirmation idempotency (DEF-001)
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing Delivery Confirmation Idempotency...")
    res_dup = confirm_shipment_delivery(
        shp_legs_inc.id,
        payload={"received_quantity": 50.0},
        db=db,
        current_user=user_receiver
    )
    assert res_dup["status"] == "DELIVERED"
    assert "already confirmed previously" in res_dup["message"]

    db.refresh(inv_c)
    assert float(inv_c.inventory_level) == stock_after_inward, "Idempotent duplicate call double-incremented stock!"
    print(f"  [✓] Idempotency Verified: Stock remains exactly {float(inv_c.inventory_level)} units.")
    passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 6: Sender and Transporter Goods Inward Authorization Rejection (DEF-001)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Testing Sender & Transporter Goods Inward RBAC Rejection...")
    shp_arrived_auth = Shipment(
        company_id=comp_a.id,
        receiver_company_id=comp_c.id,
        destination_warehouse_id=wh_c.id,
        product_id=prod_c.id,
        external_shipment_id="TEST-LIFECYCLE-AUTH",
        origin="BLR", destination="Chennai",
        carrier="Karnataka Express",
        transport_mode="ROAD", quantity=50.0,
        order_date=date.today(),
        planned_delivery=date.today() + timedelta(days=2),
        assignment_status="ARRIVED"
    )
    db.add(shp_arrived_auth)
    db.commit()
    db.refresh(shp_arrived_auth)

    # 6a. Sender attempts inward
    try:
        confirm_shipment_delivery(shp_arrived_auth.id, payload={}, db=db, current_user=user_sender)
        assert False, "Sender should have been rejected with HTTP 403 Forbidden!"
    except HTTPException as exc:
        assert exc.status_code == 403
        print(f"  [✓] Sender Rejection Confirmed: {exc.status_code} Forbidden ({exc.detail})")

    # 6b. Transporter attempts inward
    try:
        confirm_shipment_delivery(shp_arrived_auth.id, payload={}, db=db, current_user=user_carrier)
        assert False, "Transporter should have been rejected with HTTP 403 Forbidden!"
    except HTTPException as exc:
        assert exc.status_code == 403
        print(f"  [✓] Transporter Rejection Confirmed: {exc.status_code} Forbidden ({exc.detail})")

    passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 7: Unauthorized third-party receiver rejection (DEF-001)
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Testing Unauthorized Third-Party Receiver Rejection...")
    try:
        confirm_shipment_delivery(shp_arrived_auth.id, payload={}, db=db, current_user=user_unauthorized)
        assert False, "Unauthorized receiver should have been rejected with HTTP 403!"
    except HTTPException as exc:
        assert exc.status_code == 403
        print(f"  [✓] Unauthorized Receiver Rejection Confirmed: {exc.status_code} Forbidden")
        passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 8: Transporter COMPLETE_DELIVERY Cannot Produce DELIVERED (DEF-002)
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Testing Transporter COMPLETE_DELIVERY action safely transitions to ARRIVED...")
    shp_carrier_test = Shipment(
        company_id=comp_a.id,
        receiver_company_id=comp_c.id,
        destination_warehouse_id=wh_c.id,
        product_id=prod_c.id,
        external_shipment_id="TEST-LIFECYCLE-CARRIER-001",
        origin="BLR", destination="Chennai",
        carrier="Karnataka-Tamil Nadu Express Logistics",
        transporter_org_id=comp_b_org.id,
        transport_mode="ROAD", quantity=100.0,
        order_date=date.today(),
        planned_delivery=date.today() + timedelta(days=2),
        assignment_status="IN_TRANSIT"
    )
    db.add(shp_carrier_test)
    db.commit()
    db.refresh(shp_carrier_test)

    req_cd = AssignmentActionRequest(action="COMPLETE_DELIVERY")
    res_carrier = update_assignment_status(
        shipment_id=shp_carrier_test.id,
        req=req_cd,
        current_user=user_carrier,
        db=db
    )
    assert res_carrier["assignment_status"] == "ARRIVED", f"Expected ARRIVED, got {res_carrier['assignment_status']}"
    assert "ARRIVED" in res_carrier["message"]

    db.refresh(shp_carrier_test)
    assert shp_carrier_test.assignment_status == "ARRIVED"
    assert shp_carrier_test.actual_delivery is None, "Carrier action must NOT set actual_delivery date!"
    print(f"  [✓] Transporter COMPLETE_DELIVERY transitioned to ARRIVED (actual_delivery: {shp_carrier_test.actual_delivery})")
    passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 9: Transporter MARK_ARRIVED Does Not Modify Inventory (DEF-002)
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Testing Transporter MARK_ARRIVED action preserves inventory...")
    db.refresh(inv_c)
    stock_prior_mark = float(inv_c.inventory_level)

    shp_carrier_arr = Shipment(
        company_id=comp_a.id,
        receiver_company_id=comp_c.id,
        destination_warehouse_id=wh_c.id,
        product_id=prod_c.id,
        external_shipment_id="TEST-LIFECYCLE-CARRIER-002",
        origin="BLR", destination="Chennai",
        carrier="Karnataka-Tamil Nadu Express Logistics",
        transporter_org_id=comp_b_org.id,
        transport_mode="ROAD", quantity=100.0,
        order_date=date.today(),
        planned_delivery=date.today() + timedelta(days=2),
        assignment_status="IN_TRANSIT"
    )
    db.add(shp_carrier_arr)
    db.commit()
    db.refresh(shp_carrier_arr)

    req_ma = AssignmentActionRequest(action="MARK_ARRIVED")
    res_ma = update_assignment_status(
        shipment_id=shp_carrier_arr.id,
        req=req_ma,
        current_user=user_carrier,
        db=db
    )
    assert res_ma["assignment_status"] == "ARRIVED"

    db.refresh(inv_c)
    stock_after_mark = float(inv_c.inventory_level)
    assert stock_after_mark == stock_prior_mark, f"MARK_ARRIVED modified inventory! ({stock_prior_mark} -> {stock_after_mark})"
    print(f"  [✓] MARK_ARRIVED Verified: Status is ARRIVED, warehouse stock remains exactly {stock_after_mark} units.")
    passed_tests += 1

    # -------------------------------------------------------------------------
    # TEST 10: Failed transaction rollback produces zero partial state changes
    # -------------------------------------------------------------------------
    print("\n[TEST 10] Testing Atomic Transaction Rollback on Failure...")
    shp_fail_test = Shipment(
        company_id=comp_a.id,
        receiver_company_id=comp_c.id,
        destination_warehouse_id=wh_c.id,
        product_id=9999999,  # Non-existent product ID to trigger error
        external_shipment_id="TEST-LIFECYCLE-FAIL",
        origin="BLR", destination="Chennai",
        carrier="Karnataka Express",
        transport_mode="ROAD", quantity=50.0,
        order_date=date.today(),
        planned_delivery=date.today() + timedelta(days=2),
        assignment_status="ARRIVED"
    )
    db.add(shp_fail_test)
    db.commit()
    db.refresh(shp_fail_test)

    db.refresh(inv_c)
    stock_pre_fail = float(inv_c.inventory_level)

    try:
        confirm_shipment_delivery(shp_fail_test.id, payload={}, db=db, current_user=user_receiver)
        assert False, "Should have raised 400 on non-existent product!"
    except HTTPException as exc:
        assert exc.status_code == 400
        print(f"  [✓] Rollback Verified on Failure: {exc.detail}")
        db.refresh(shp_fail_test)
        assert shp_fail_test.assignment_status == "ARRIVED"
        assert shp_fail_test.actual_delivery is None
        db.refresh(inv_c)
        assert float(inv_c.inventory_level) == stock_pre_fail
        passed_tests += 1

    print("\n======================================================================")
    print(f"PHASE 1 VERIFICATION COMPLETE: {passed_tests}/{total_tests} TESTS PASSED (100%)")
    print("======================================================================\n")

    # Clean up isolated DB and temp dir
    db.close()
    try:
        shutil.rmtree(TEMP_DIR)
        print(f"[CLEANUP] Cleaned up temporary test directory: {TEMP_DIR}")
    except Exception as e:
        print(f"[CLEANUP NOTICE] Could not remove temp dir: {e}")

    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_phase1_verification_suite()
    sys.exit(0 if success else 1)
