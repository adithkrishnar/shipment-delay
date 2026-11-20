"""
Test Suite: Phase 3 Medium-Severity Decision Logic, Inventory Accuracy, and Navigation Defects
Covers:
  - DEF-012: What-If service-level Z-factor calculation (0.90->1.28, 0.95->1.65, 0.98->2.05, 0.99->2.33)
  - DEF-013: Multi-SKU Receiver Inventory data integrity, zero/null honesty, and cross-SKU isolation
  - DEF-014: Enterprise Superuser tenant switching and strict non-superuser cross-tenant rejection
  - DEF-015: Prescriptive action approval infrastructure verification and execution safeguards
Runs against an isolated temporary clone of the SQLite database.
"""
import os
import shutil
import tempfile
import pytest
from datetime import date, datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from fastapi.exceptions import HTTPException
from app.models import Company, Product, Warehouse, InventoryRecord, User, ActionApproval
from app.models.warehouse_transfer import WarehouseTransfer
from app.services.inventory_intelligence import (
    SERVICE_LEVEL_Z_FACTORS,
    get_z_factor,
    calculate_safety_stock,
    company_inventory,
)
from app.routes.inventory import simulate_what_if, WhatIfRequest, get_inventory_overview, get_inventory_explorer
from app.routes.recommendations import approve_action, ActionApprovalRequest


@pytest.fixture(scope="module")
def isolated_db():
    temp_dir = tempfile.mkdtemp()
    src_db = os.path.join(backend_dir, "supplyiq.db")
    isolated_db_path = os.path.join(temp_dir, "isolated_phase3_supplyiq.db")
    shutil.copy2(src_db, isolated_db_path)

    engine = create_engine(f"sqlite:///{isolated_db_path}", connect_args={"check_same_thread": False})
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    yield session

    session.close()
    engine.dispose()
    shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# DEF-012: What-If Service-Level Z-Factor Calculations
# ==============================================================================

def test_def_012_z_factor_mapping_and_monotonicity():
    """
    DEF-012: Verify that get_z_factor accurately maps service levels and
    produces monotonically strictly increasing safety stock values.
    """
    assert get_z_factor(0.90) == 1.28
    assert get_z_factor(0.95) == 1.65
    assert get_z_factor(0.98) == 2.05
    assert get_z_factor(0.99) == 2.33

    # Statistical parameter inputs
    d_mean = 20.0
    d_std = 5.0
    l_mean = 10.0
    l_std = 2.0

    ss_90 = calculate_safety_stock(d_mean, d_std, l_mean, l_std, z_factor=get_z_factor(0.90))
    ss_95 = calculate_safety_stock(d_mean, d_std, l_mean, l_std, z_factor=get_z_factor(0.95))
    ss_98 = calculate_safety_stock(d_mean, d_std, l_mean, l_std, z_factor=get_z_factor(0.98))
    ss_99 = calculate_safety_stock(d_mean, d_std, l_mean, l_std, z_factor=get_z_factor(0.99))

    # Verify strict monotonic increase
    assert ss_90 < ss_95 < ss_98 < ss_99, f"Safety stock must strictly increase: {ss_90} < {ss_95} < {ss_98} < {ss_99}"


def test_def_012_simulate_what_if_98_percent_branch(isolated_db):
    """
    DEF-012: Verify simulate_what_if endpoint applies z_factor=2.05 for service_level_target=0.98,
    eliminating the previous bug where 0.98 fell back to 1.28.
    """
    db = isolated_db
    # Use Company 21 and its primary product
    product = db.query(Product).filter(Product.company_id == 21).first()
    assert product is not None

    user = User(id=7701, email="superuser@dataco.com", is_superuser=True)

    res_95 = simulate_what_if(
        req=WhatIfRequest(
            company_id=21,
            product_id=product.id,
            demand_multiplier=1.0,
            lead_time_delta=0.0,
            service_level_target=0.95,
        ),
        db=db,
        current_user=user,
    )

    res_98 = simulate_what_if(
        req=WhatIfRequest(
            company_id=21,
            product_id=product.id,
            demand_multiplier=1.0,
            lead_time_delta=0.0,
            service_level_target=0.98,
        ),
        db=db,
        current_user=user,
    )

    res_99 = simulate_what_if(
        req=WhatIfRequest(
            company_id=21,
            product_id=product.id,
            demand_multiplier=1.0,
            lead_time_delta=0.0,
            service_level_target=0.99,
        ),
        db=db,
        current_user=user,
    )

    ss_95 = res_95["scenario"]["safety_stock"]
    ss_98 = res_98["scenario"]["safety_stock"]
    ss_99 = res_99["scenario"]["safety_stock"]

    # 98% must be strictly greater than 95% and strictly less than or equal to 99%
    assert ss_98 > ss_95, f"98% safety stock ({ss_98}) must be greater than 95% ({ss_95})"
    assert ss_99 >= ss_98, f"99% safety stock ({ss_99}) must be >= 98% ({ss_98})"


# ==============================================================================
# DEF-013: Multi-SKU Receiver Inventory Accuracy & Zero/Null Honesty
# ==============================================================================

def test_def_013_multi_sku_receiver_inventory_isolation(isolated_db):
    """
    DEF-013: Verify that company_inventory accurately calculates metrics per SKU
    without data leakage between SKUs, and correctly handles 0.0 without falling back to 85.0.
    """
    db = isolated_db
    # Create test company with 2 distinct SKUs: one with zero stock and zero demand, one with active stock
    test_co = Company(name="DEF-013 Multi-SKU Test Co", industry="Electronics")
    db.add(test_co)
    db.commit()
    db.refresh(test_co)

    wh = Warehouse(company_id=test_co.id, name="Test Hub", region="South")
    p_zero = Product(company_id=test_co.id, external_product_id="SKU-ZERO-001", name="Zero Stock Item", unit_cost=10.0)
    p_active = Product(company_id=test_co.id, external_product_id="SKU-ACTIVE-002", name="Active Stock Item", unit_cost=50.0)
    db.add_all([wh, p_zero, p_active])
    db.commit()
    db.refresh(wh)
    db.refresh(p_zero)
    db.refresh(p_active)

    today = date.today()
    # Zero stock item has an explicit 0.0 inventory record
    inv_zero = InventoryRecord(company_id=test_co.id, product_id=p_zero.id, warehouse_id=wh.id, date=today, inventory_level=0.0, safety_stock=0.0)
    # Active stock item has 250.0 units
    inv_active = InventoryRecord(company_id=test_co.id, product_id=p_active.id, warehouse_id=wh.id, date=today, inventory_level=250.0, safety_stock=30.0)
    db.add_all([inv_zero, inv_active])
    db.commit()

    inventory = company_inventory(db, test_co.id)
    assert len(inventory) == 2

    zero_item = next(i for i in inventory if i["product_id"] == p_zero.id)
    active_item = next(i for i in inventory if i["product_id"] == p_active.id)

    # Verify zero-stock item is honest 0.0, NOT 85.0 or any arbitrary fallback
    assert zero_item["inventory_level"] == 0.0
    assert zero_item["external_product_id"] == "SKU-ZERO-001"

    # Verify active-stock item has its own 250.0 units
    assert active_item["inventory_level"] == 250.0
    assert active_item["external_product_id"] == "SKU-ACTIVE-002"

    # Cross-SKU isolation: zero item's zero stock didn't affect active item
    assert active_item["inventory_level"] != zero_item["inventory_level"]


# ==============================================================================
# DEF-014: Enterprise Superuser Tenant Switching & Cross-Tenant Rejection
# ==============================================================================

def test_def_014_superuser_tenant_switching_and_non_superuser_rejection(isolated_db):
    """
    DEF-014: Verify that enterprise superusers can access multiple authorized tenants
    while non-superuser tenant boundaries remain strictly enforced with 403 Forbidden.
    """
    db = isolated_db
    superuser = User(id=8801, email="admin@dataco.com", company_id=16, is_superuser=True)
    chennai_user = User(id=8802, email="receiver@chennai.com", company_id=21, is_superuser=False)
    bengaluru_user = User(id=8803, email="sender@bengaluru.com", company_id=19, is_superuser=False)

    # 1. Superuser can access all 3 primary companies: DataCo (16), Bengaluru (19), Chennai (21)
    ov_16 = get_inventory_overview(company_id=16, db=db, current_user=superuser)
    assert ov_16["company_id"] == 16

    ov_19 = get_inventory_overview(company_id=19, db=db, current_user=superuser)
    assert ov_19["company_id"] == 19

    ov_21 = get_inventory_overview(company_id=21, db=db, current_user=superuser)
    assert ov_21["company_id"] == 21

    # 2. Chennai user can access Company 21
    ov_chennai = get_inventory_overview(company_id=21, db=db, current_user=chennai_user)
    assert ov_chennai["company_id"] == 21

    # 3. Chennai user attempting to access Company 19 is strictly rejected with 403 Forbidden
    with pytest.raises(HTTPException) as exc_19:
        get_inventory_overview(company_id=19, db=db, current_user=chennai_user)
    assert exc_19.value.status_code == 403
    assert "Not authorized" in exc_19.value.detail

    # 4. Bengaluru user attempting to access Company 21 is strictly rejected with 403 Forbidden
    with pytest.raises(HTTPException) as exc_21:
        get_inventory_overview(company_id=21, db=db, current_user=bengaluru_user)
    assert exc_21.value.status_code == 403
    assert "Not authorized" in exc_21.value.detail


# ==============================================================================
# DEF-015: Warehouse Transfer Approval Infrastructure Verification & Execution
# ==============================================================================

def test_def_015_single_warehouse_mitigation_approval_guidance(isolated_db):
    """
    DEF-015: For a single-warehouse tenant (e.g. Chennai Central DC Company 21),
    approving a disruption mitigation / stock transfer must set status to PENDING_EXTERNAL_DISPATCH,
    include operational guidance that internal facility transfer is not applicable,
    and NOT claim that an internal transfer was completed.
    """
    db = isolated_db
    user_chennai = User(id=8804, email="ops@chennai.com", company_id=21, is_superuser=False)

    # Verify Company 21 has exactly 1 warehouse
    wh_count = db.query(Warehouse).filter(Warehouse.company_id == 21).count()
    assert wh_count == 1

    # Approve stock transfer mitigation
    resp = approve_action(
        company_id=21,
        payload=ActionApprovalRequest(
            action_id="MITIGATE-DISRUPTION-SH-001",
            action_type="DISRUPTION_MITIGATION",
            title="Fix Transit Delay: Shipment SH-BLR-2026-0001",
            notes="Emergency Stock Transfer approved via Consignee Control Tower",
        ),
        db=db,
        current_user=user_chennai,
    )

    assert resp["status"] == "PENDING_EXTERNAL_DISPATCH"
    assert "Internal facility transfer not possible" in resp["message"] or "Internal facility transfer not applicable" in resp["message"]
    assert resp["action_id"] == "MITIGATE-DISRUPTION-SH-001"

    # Verify ActionApproval record in database
    approval_rec = (
        db.query(ActionApproval)
        .filter(ActionApproval.company_id == 21, ActionApproval.action_id == "MITIGATE-DISRUPTION-SH-001")
        .first()
    )
    assert approval_rec is not None
    assert approval_rec.status == "PENDING_EXTERNAL_DISPATCH"
    assert "Operational Guidance: Company has only 1 facility" in approval_rec.notes


def test_def_015_multi_warehouse_transfer_execution(isolated_db):
    """
    DEF-015: For a multi-warehouse tenant, approving a transfer with parameters
    atomically executes the transfer, updates inventory records, logs the transfer,
    and returns EXECUTED status.
    """
    db = isolated_db
    multi_co = Company(name="DEF-015 Multi-Hub Logistics Co", industry="Logistics")
    db.add(multi_co)
    db.commit()
    db.refresh(multi_co)

    w_source = Warehouse(company_id=multi_co.id, name="Hub Alpha", region="North")
    w_dest = Warehouse(company_id=multi_co.id, name="Hub Beta", region="South")
    prod = Product(company_id=multi_co.id, external_product_id="SKU-TR-505", name="Precision Valve", unit_cost=100.0)
    db.add_all([w_source, w_dest, prod])
    db.commit()
    db.refresh(w_source)
    db.refresh(w_dest)
    db.refresh(prod)

    today = date.today()
    inv_source = InventoryRecord(company_id=multi_co.id, product_id=prod.id, warehouse_id=w_source.id, date=today, inventory_level=100.0, safety_stock=10.0)
    inv_dest = InventoryRecord(company_id=multi_co.id, product_id=prod.id, warehouse_id=w_dest.id, date=today, inventory_level=20.0, safety_stock=10.0)
    db.add_all([inv_source, inv_dest])
    db.commit()

    user_multi = User(id=8805, email="manager@multihub.com", company_id=multi_co.id, is_superuser=False)

    # 1. Execute transfer via action approval
    resp = approve_action(
        company_id=multi_co.id,
        payload=ActionApprovalRequest(
            action_id="TRANSFER-ACT-001",
            action_type="STOCK_TRANSFER",
            title="Rebalance 35 units from Hub Alpha to Hub Beta",
            notes="Operations directive",
            source_warehouse_id=w_source.id,
            destination_warehouse_id=w_dest.id,
            product_id=prod.id,
            quantity=35.0,
        ),
        db=db,
        current_user=user_multi,
    )

    assert resp["status"] == "EXECUTED"
    assert "transfer of 35.0 units executed successfully" in resp["message"]

    # Verify inventory was updated transactionally
    db.expire_all()
    source_after = db.query(InventoryRecord).filter(InventoryRecord.warehouse_id == w_source.id, InventoryRecord.product_id == prod.id).first()
    dest_after = db.query(InventoryRecord).filter(InventoryRecord.warehouse_id == w_dest.id, InventoryRecord.product_id == prod.id).first()
    assert source_after.inventory_level == 65.0   # 100 - 35
    assert dest_after.inventory_level == 55.0     # 20 + 35

    # Verify WarehouseTransfer log was created
    transfer_log = (
        db.query(WarehouseTransfer)
        .filter(WarehouseTransfer.company_id == multi_co.id, WarehouseTransfer.product_id == prod.id)
        .first()
    )
    assert transfer_log is not None
    assert transfer_log.quantity == 35.0
    assert transfer_log.status == "COMPLETED"
    assert transfer_log.source_warehouse_id == w_source.id
    assert transfer_log.destination_warehouse_id == w_dest.id

    # 2. Reject transfer exceeding available stock (65 available, requesting 90)
    with pytest.raises(HTTPException) as exc_excess:
        approve_action(
            company_id=multi_co.id,
            payload=ActionApprovalRequest(
                action_id="TRANSFER-EXCESS-002",
                action_type="STOCK_TRANSFER",
                title="Overdraw stock transfer",
                source_warehouse_id=w_source.id,
                destination_warehouse_id=w_dest.id,
                product_id=prod.id,
                quantity=90.0,
            ),
            db=db,
            current_user=user_multi,
        )
    assert exc_excess.value.status_code == 400
    assert "Insufficient stock" in exc_excess.value.detail
