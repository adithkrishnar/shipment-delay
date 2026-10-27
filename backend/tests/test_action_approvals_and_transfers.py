"""
Tests for Task 4: Real Action Approvals and Transactional Warehouse Transfers.
Verifies persistence, authorization, stock movements, and tenant isolation.
"""
from datetime import date
import pytest
from app.models import Company, Product, InventoryRecord, Warehouse, User, ActionApproval, WarehouseTransfer
from app.auth.deps import get_current_user
from app.main import app


def test_action_approval_lifecycle_and_persistence(client, db_session):
    """Verifies that action approvals are persisted in database and returned in recommendations."""
    c = Company(name="Approval Test Co", industry="Retail")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    user = User(id=8801, email="mgr@approval.com", company_id=c.id, is_superuser=False)

    original_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        # 1. Approve an action
        resp = client.post(
            f"/api/recommendations/{c.id}/approve",
            json={
                "action_id": "ACTION-TEST-001",
                "action_type": "STOCK_TRANSFER",
                "title": "Transfer 50 units to Atlanta DC",
                "notes": "Approved by Operations Lead",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "APPROVED"
        assert data["action_id"] == "ACTION-TEST-001"
        assert data["approved_by_user_id"] == user.id

        # 2. Duplicate approval request should be idempotent
        resp_dup = client.post(
            f"/api/recommendations/{c.id}/approve",
            json={
                "action_id": "ACTION-TEST-001",
                "action_type": "STOCK_TRANSFER",
                "title": "Transfer 50 units to Atlanta DC",
            },
        )
        assert resp_dup.status_code == 200
        assert resp_dup.json()["message"] == "Action was already approved"

        # 3. Verify approvals list endpoint
        resp_list = client.get(f"/api/recommendations/{c.id}/approvals")
        assert resp_list.status_code == 200
        approvals = resp_list.json()
        assert len(approvals) >= 1
        assert any(a["action_id"] == "ACTION-TEST-001" for a in approvals)

        # 4. Cross-company approval attempt -> 403 Forbidden
        c_other = Company(name="Other Co", industry="Wholesale")
        db_session.add(c_other)
        db_session.commit()
        db_session.refresh(c_other)

        resp_forbidden = client.post(
            f"/api/recommendations/{c_other.id}/approve",
            json={"action_id": "HACK-001"},
        )
        assert resp_forbidden.status_code == 403

    finally:
        if original_override is not None:
            app.dependency_overrides[get_current_user] = original_override
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_warehouse_transfer_transactional_stock_movement(client, db_session):
    """
    Verifies transactional execution of inter-warehouse transfers:
    - Decrements source warehouse stock
    - Increments destination warehouse stock
    - Prevents negative inventory
    - Records transfer history
    """
    c = Company(name="Transfer Test Co", industry="Logistics")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    w_source = Warehouse(company_id=c.id, name="Dallas Hub", region="South")
    w_dest = Warehouse(company_id=c.id, name="Atlanta Hub", region="East")
    p = Product(company_id=c.id, external_product_id="SKU-TR-100", name="Transfer Widget", unit_cost=25.0)
    db_session.add_all([w_source, w_dest, p])
    db_session.commit()
    db_session.refresh(w_source)
    db_session.refresh(w_dest)
    db_session.refresh(p)

    today = date.today()
    # Source starting stock: 120 units
    inv_source = InventoryRecord(company_id=c.id, product_id=p.id, warehouse_id=w_source.id, date=today, inventory_level=120.0, safety_stock=20.0)
    # Destination starting stock: 10 units
    inv_dest = InventoryRecord(company_id=c.id, product_id=p.id, warehouse_id=w_dest.id, date=today, inventory_level=10.0, safety_stock=20.0)
    db_session.add_all([inv_source, inv_dest])
    db_session.commit()

    user = User(id=8802, email="ops@transfer.com", company_id=c.id, is_superuser=False)
    original_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        # 1. Execute valid transfer of 40 units from Dallas to Atlanta
        resp = client.post(
            "/api/inventory/transfers/execute",
            json={
                "company_id": c.id,
                "product_id": p.id,
                "sku": p.external_product_id,
                "source_warehouse_id": w_source.id,
                "destination_warehouse_id": w_dest.id,
                "quantity": 40.0,
                "notes": "Seasonal rebalancing",
            },
        )
        assert resp.status_code == 200
        res = resp.json()
        assert res["status"] == "COMPLETED"
        assert res["quantity"] == 40.0
        assert res["source_stock_before"] == 120.0
        assert res["source_stock_after"] == 80.0
        assert res["destination_stock_before"] == 10.0
        assert res["destination_stock_after"] == 50.0

        # Verify database state after transfer
        db_session.expire_all()
        refreshed_source = (
            db_session.query(InventoryRecord)
            .filter(InventoryRecord.warehouse_id == w_source.id, InventoryRecord.product_id == p.id)
            .first()
        )
        refreshed_dest = (
            db_session.query(InventoryRecord)
            .filter(InventoryRecord.warehouse_id == w_dest.id, InventoryRecord.product_id == p.id)
            .first()
        )
        assert refreshed_source.inventory_level == 80.0
        assert refreshed_dest.inventory_level == 50.0

        # 2. Check transfer history endpoint
        resp_hist = client.get(f"/api/inventory/transfers/history/{c.id}")
        assert resp_hist.status_code == 200
        hist = resp_hist.json()
        assert len(hist) >= 1
        assert hist[0]["quantity"] == 40.0
        assert hist[0]["source_warehouse_id"] == w_source.id
        assert hist[0]["destination_warehouse_id"] == w_dest.id

        # 3. Attempt transfer exceeding available stock (80 available, request 150) -> 400 Bad Request
        resp_excess = client.post(
            "/api/inventory/transfers/execute",
            json={
                "company_id": c.id,
                "product_id": p.id,
                "source_warehouse_id": w_source.id,
                "destination_warehouse_id": w_dest.id,
                "quantity": 150.0,
            },
        )
        assert resp_excess.status_code == 400
        assert "Insufficient stock" in resp_excess.json()["detail"]

        # 4. Attempt transfer to identical warehouse -> 400 Bad Request
        resp_same = client.post(
            "/api/inventory/transfers/execute",
            json={
                "company_id": c.id,
                "product_id": p.id,
                "source_warehouse_id": w_source.id,
                "destination_warehouse_id": w_source.id,
                "quantity": 10.0,
            },
        )
        assert resp_same.status_code == 400
        assert "must be different" in resp_same.json()["detail"]

    finally:
        if original_override is not None:
            app.dependency_overrides[get_current_user] = original_override
        else:
            app.dependency_overrides.pop(get_current_user, None)
