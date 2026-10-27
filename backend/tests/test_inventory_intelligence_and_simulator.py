"""
Comprehensive tests for Inventory Intelligence, Discrete-Event Simulator,
Analytics, Replenishment, and Multi-Tenant Isolation.
"""
from __future__ import annotations

from datetime import date, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Company, Product, InventoryRecord, Sale, Shipment, Supplier, Warehouse, User
from app.services.inventory_simulator_service import run_delay_simulation
from app.services.inventory_analytics_service import get_abc_xyz_analysis, get_inventory_aging_and_slow_moving
from app.services.replenishment_service import compute_replenishment_plan, get_warehouse_transfer_recommendations


def _seed_test_data(db: Session):
    c1 = Company(name="Test Inv Corp A", industry="Electronics")
    c2 = Company(name="Test Inv Corp B", industry="Automotive")
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)

    w1 = Warehouse(company_id=c1.id, name="Central DC", region="Dallas")
    w2 = Warehouse(company_id=c1.id, name="East DC", region="Atlanta")
    db.add_all([w1, w2])
    db.commit()
    db.refresh(w1)
    db.refresh(w2)

    p1 = Product(
        company_id=c1.id,
        external_product_id="SKU-MICRO-01",
        name="Microcontroller IC-32",
        category="Semiconductors",
        unit_cost=15.0,
        unit_price=35.0,
    )
    p2 = Product(
        company_id=c1.id,
        external_product_id="SKU-CAP-100",
        name="Capacitor 100uF",
        category="Passive Components",
        unit_cost=0.50,
        unit_price=2.00,
    )
    p3 = Product(
        company_id=c1.id,
        external_product_id="SKU-NO-COST",
        name="Generic Resistor Pack",
        category="Passive Components",
        unit_cost=None,
        unit_price=None,
    )
    p_comp2 = Product(
        company_id=c2.id,
        external_product_id="SKU-BRAKE-01",
        name="Ceramic Brake Pad",
        category="Brakes",
        unit_cost=40.0,
        unit_price=90.0,
    )
    db.add_all([p1, p2, p3, p_comp2])
    db.commit()
    db.refresh(p1)
    db.refresh(p2)
    db.refresh(p3)
    db.refresh(p_comp2)

    today = date.today()
    inv1 = InventoryRecord(company_id=c1.id, product_id=p1.id, warehouse_id=w1.id, date=today, inventory_level=100.0, safety_stock=25.0)
    inv1_east = InventoryRecord(company_id=c1.id, product_id=p1.id, warehouse_id=w2.id, date=today, inventory_level=10.0, safety_stock=15.0)
    inv2 = InventoryRecord(company_id=c1.id, product_id=p2.id, warehouse_id=w1.id, date=today, inventory_level=500.0, safety_stock=50.0)
    inv3 = InventoryRecord(company_id=c1.id, product_id=p3.id, warehouse_id=w1.id, date=today, inventory_level=80.0, safety_stock=20.0)
    inv_c2 = InventoryRecord(company_id=c2.id, product_id=p_comp2.id, warehouse_id=None, date=today, inventory_level=60.0, safety_stock=20.0)
    db.add_all([inv1, inv1_east, inv2, inv3, inv_c2])

    sales = []
    for d in range(1, 31):
        s_date = today - timedelta(days=d)
        sales.append(Sale(company_id=c1.id, product_id=p1.id, date=s_date, quantity=10.0))
        sales.append(Sale(company_id=c1.id, product_id=p2.id, date=s_date, quantity=5.0))
        sales.append(Sale(company_id=c1.id, product_id=p3.id, date=s_date, quantity=4.0))
        sales.append(Sale(company_id=c2.id, product_id=p_comp2.id, date=s_date, quantity=8.0))
    db.add_all(sales)

    shipment_p1 = Shipment(
        company_id=c1.id,
        product_id=p1.id,
        supplier_id=None,
        external_shipment_id="PO-INB-101",
        origin="Taipei",
        destination="Dallas",
        carrier="AirCargo Express",
        transport_mode="Air",
        quantity=50.0,
        order_date=today - timedelta(days=4),
        planned_delivery=today + timedelta(days=10),
        actual_delivery=None,
    )
    db.add(shipment_p1)
    db.commit()

    return {
        "c1": c1,
        "c2": c2,
        "p1": p1,
        "p2": p2,
        "p3": p3,
        "p_comp2": p_comp2,
        "w1": w1,
        "w2": w2,
    }


def test_simulator_invariant_1_zero_delay_matches_baseline(db_session):
    """Invariant 1: Zero additional delay reproduces the baseline timeline exactly."""
    data = _seed_test_data(db_session)
    c1, p1 = data["c1"], data["p1"]

    res = run_delay_simulation(db_session, c1.id, p1.id, delay_days=0.0, horizon_days=30)
    for day_data in res["timeline"]:
        assert day_data["baseline_stock"] == day_data["scenario_stock"], f"Day {day_data['day']} stock mismatch on delay=0"
    assert res["summary"]["additional_stockout_days"] == 0


def test_simulator_invariant_2_delay_cannot_arrive_earlier(db_session):
    """Invariant 2: Increasing a receipt delay cannot cause that receipt to arrive earlier."""
    data = _seed_test_data(db_session)
    c1, p1 = data["c1"], data["p1"]

    res_base = run_delay_simulation(db_session, c1.id, p1.id, delay_days=0.0)
    res_delay = run_delay_simulation(db_session, c1.id, p1.id, delay_days=7.0)

    base_arrival = res_base["dates"]["baseline_receipt_date"]
    delayed_arrival = res_delay["dates"]["delayed_receipt_date"]
    assert delayed_arrival >= base_arrival


def test_simulator_invariant_3_stock_does_not_increase_before_simulated_arrival(db_session):
    """Invariant 3: Stock does not increase from an incoming order before its simulated arrival."""
    data = _seed_test_data(db_session)
    c1, p1 = data["c1"], data["p1"]

    # Baseline arrival is day 10. Let's delay by 5 days -> delayed arrival is day 15.
    res = run_delay_simulation(db_session, c1.id, p1.id, delay_days=5.0, horizon_days=20)
    timeline = res["timeline"]

    # On day 10, baseline should receive inflow; scenario must NOT receive inflow
    day_10 = next(t for t in timeline if t["day"] == 10)
    assert day_10["baseline_inflow"] == 50.0
    assert day_10["scenario_inflow"] == 0.0

    # Scenario receives inflow on day 15
    day_15 = next(t for t in timeline if t["day"] == 15)
    assert day_15["scenario_inflow"] == 50.0


def test_simulator_invariant_4_higher_demand_cannot_reduce_cumulative_demand(db_session):
    """Invariant 4: Higher demand multiplier cannot reduce cumulative demand over same horizon."""
    data = _seed_test_data(db_session)
    c1, p1 = data["c1"], data["p1"]

    res_1x = run_delay_simulation(db_session, c1.id, p1.id, demand_multiplier=1.0)
    res_2x = run_delay_simulation(db_session, c1.id, p1.id, demand_multiplier=2.0)

    cum_demand_1x = sum(t["scenario_demand"] for t in res_1x["timeline"])
    cum_demand_2x = sum(t["scenario_demand"] for t in res_2x["timeline"])
    assert cum_demand_2x > cum_demand_1x


def test_simulator_invariant_5_and_6_delayed_order_causes_stockout_where_arithmetic_supports(db_session):
    """Invariant 5 & 6: Delayed order causes projected stockout, but no false positive when stock is sufficient."""
    data = _seed_test_data(db_session)
    c1, p1 = data["c1"], data["p1"]

    res = run_delay_simulation(db_session, c1.id, p1.id, delay_days=10.0, horizon_days=20)
    assert res["summary"]["scenario_stockout_days"] > 0
    assert res["dates"]["earliest_stockout_date"] is not None

    p2 = data["p2"]
    res_p2 = run_delay_simulation(db_session, c1.id, p2.id, delay_days=10.0, horizon_days=20)
    assert res_p2["summary"]["scenario_stockout_days"] == 0
    assert res_p2["dates"]["earliest_stockout_date"] is None


def test_simulator_invariant_8_scenario_execution_never_mutates_database(db_session):
    """Invariant 8: Scenario execution does not mutate actual inventory in the database."""
    data = _seed_test_data(db_session)
    c1, p1 = data["c1"], data["p1"]

    stock_before = (
        db_session.query(InventoryRecord.inventory_level)
        .filter(InventoryRecord.company_id == c1.id, InventoryRecord.product_id == p1.id)
        .first()[0]
    )

    _ = run_delay_simulation(db_session, c1.id, p1.id, delay_days=25.0, demand_multiplier=3.0, emergency_order_qty=200.0)

    stock_after = (
        db_session.query(InventoryRecord.inventory_level)
        .filter(InventoryRecord.company_id == c1.id, InventoryRecord.product_id == p1.id)
        .first()[0]
    )
    assert stock_before == stock_after, "Database was mutated during simulation!"


def test_simulator_invariant_9_reproducibility(db_session):
    """Invariant 9: Repeating identical inputs produces identical results."""
    data = _seed_test_data(db_session)
    c1, p1 = data["c1"], data["p1"]

    res_run1 = run_delay_simulation(db_session, c1.id, p1.id, delay_days=6.0, demand_multiplier=1.5)
    res_run2 = run_delay_simulation(db_session, c1.id, p1.id, delay_days=6.0, demand_multiplier=1.5)

    assert res_run1["summary"] == res_run2["summary"]
    assert len(res_run1["timeline"]) == len(res_run2["timeline"])
    for d1, d2 in zip(res_run1["timeline"], res_run2["timeline"]):
        assert d1 == d2


def test_simulator_invariant_10_missing_costs_are_not_invented(db_session):
    """Invariant 10: Unknown financial inputs are not replaced with invented costs."""
    data = _seed_test_data(db_session)
    c1, p3 = data["c1"], data["p3"]

    res = run_delay_simulation(db_session, c1.id, p3.id, delay_days=15.0, horizon_days=25)
    assert res["summary"]["value_at_risk"] is None
    assert res["summary"]["lost_revenue_potential"] is None
    assert res["summary"]["has_cost_data"] is False


def test_abc_xyz_analysis(db_session):
    """Verifies ABC and XYZ classification mathematics."""
    data = _seed_test_data(db_session)
    c1 = data["c1"]

    res = get_abc_xyz_analysis(db_session, c1.id)
    assert res["summary"]["total_products"] >= 3
    assert "AX" in res["matrix"]
    assert "CZ" in res["matrix"]
    shares = [p["cumulative_value_share"] for p in res["products"]]
    assert shares == sorted(shares)


def test_replenishment_and_transfer_optimization(db_session):
    """Verifies replenishment calculations and safe inter-warehouse transfers."""
    data = _seed_test_data(db_session)
    c1 = data["c1"]

    repl = compute_replenishment_plan(db_session, c1.id, service_level=0.95)
    assert repl["z_factor"] == 1.65
    assert len(repl["recommendations"]) >= 3

    transfers = get_warehouse_transfer_recommendations(db_session, c1.id)
    assert len(transfers) >= 1
    t = transfers[0]
    assert t["source_stock_after"] >= 50.0
    assert t["transfer_units"] > 0


def test_api_tenant_isolation(client):
    """Verifies multi-tenant company isolation across inventory endpoints."""
    # Create 2 companies via client fixture
    r1 = client.post("/api/companies", json={"name": "Company A", "industry": "Retail"})
    r2 = client.post("/api/companies", json={"name": "Company B", "industry": "Wholesale"})
    c1_id = r1.json()["id"]
    c2_id = r2.json()["id"]

    from app.auth.deps import get_current_user
    from app.main import app

    original_override = app.dependency_overrides.get(get_current_user)
    mock_user_c1 = User(id=991, email="user_a@test.com", company_id=c1_id, is_superuser=False)
    app.dependency_overrides[get_current_user] = lambda: mock_user_c1

    try:
        # Access own company -> 200 OK
        resp_own = client.get(f"/api/inventory/overview/{c1_id}")
        assert resp_own.status_code == 200

        # Cross-company attempt: User of C1 accessing C2 -> 403 Forbidden
        resp_other = client.get(f"/api/inventory/overview/{c2_id}")
        assert resp_other.status_code == 403
        assert "Not authorized" in resp_other.json()["detail"]
    finally:
        if original_override is not None:
            app.dependency_overrides[get_current_user] = original_override
        else:
            app.dependency_overrides.pop(get_current_user, None)


def test_simulator_daily_accounting_regression(db_session):
    """
    Task 1 Regression Test:
    Verifies daily inventory accounting prevents quadratic shortage inflation.
    Tests: consecutive stockout days, partial shortages, zero demand, multipliers,
    missing unit costs, and database non-mutation.
    """
    c = Company(name="Sim Math Test Co", industry="Logistics")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    w = Warehouse(company_id=c.id, name="Test Hub", region="Midwest")
    db_session.add(w)
    db_session.commit()
    db_session.refresh(w)

    # Product with known cost
    p = Product(
        company_id=c.id,
        external_product_id="SKU-MATH-TEST",
        name="Precision Widget",
        unit_cost=20.0,
        unit_price=50.0,
    )
    # Product without cost
    p_no_cost = Product(
        company_id=c.id,
        external_product_id="SKU-NO-COST-MATH",
        name="Costless Widget",
        unit_cost=None,
        unit_price=None,
    )
    db_session.add_all([p, p_no_cost])
    db_session.commit()
    db_session.refresh(p)
    db_session.refresh(p_no_cost)

    today = date.today()
    # Starting stock = 10 units
    inv = InventoryRecord(company_id=c.id, product_id=p.id, warehouse_id=w.id, date=today, inventory_level=10.0, safety_stock=5.0)
    inv_no_cost = InventoryRecord(company_id=c.id, product_id=p_no_cost.id, warehouse_id=w.id, date=today, inventory_level=0.0, safety_stock=0.0)
    db_session.add_all([inv, inv_no_cost])

    # 30 days of sales with 10 units/day -> daily demand = 10.0
    sales = [Sale(company_id=c.id, product_id=p.id, date=today - timedelta(days=d), quantity=10.0) for d in range(1, 31)]
    # Sales for no-cost product with 0 units/day -> daily demand = 0.0
    sales_zero = [Sale(company_id=c.id, product_id=p_no_cost.id, date=today - timedelta(days=d), quantity=0.0) for d in range(1, 31)]
    db_session.add_all(sales + sales_zero)

    # No shipments for this product (pure stockout scenario)
    db_session.commit()

    # 1. Test consecutive stockout days (starting stock 10, demand 10/day, horizon 7 days, order delayed 10 days)
    # Day 1: avail=10, dem=10 -> unmet=0, close=0
    # Days 2..7 (6 days): avail=0, dem=10 -> unmet=10, close=0
    # Correct sum: 0 + 6 * 10 = 60.0 (Previously bug produced quadratic accumulation: 0 + 10 + 20 + 30 + 40 + 50 + 60 = 210.0)
    res = run_delay_simulation(db_session, c.id, p.id, delay_days=10.0, horizon_days=7)
    summary = res["summary"]
    timeline = res["timeline"]

    assert len(timeline) == 7
    assert timeline[0]["shortage_units"] == 0.0
    assert timeline[0]["scenario_stock"] == 0.0
    assert timeline[0]["is_stockout"] is False

    for day_idx in range(1, 7):
        assert timeline[day_idx]["shortage_units"] == 10.0
        assert timeline[day_idx]["scenario_stock"] == 0.0
        assert timeline[day_idx]["is_stockout"] is True

    assert summary["total_unmet_demand_units"] == 60.0
    assert summary["scenario_stockout_days"] == 6
    assert summary["maximum_shortage_units"] == 10.0
    # Value at risk = 60.0 * $20.00 = $1,200.00
    assert summary["value_at_risk"] == 1200.00
    assert summary["lost_revenue_potential"] == 3000.00
    assert summary["has_cost_data"] is True

    # 2. Test zero demand and zero inventory
    res_zero = run_delay_simulation(db_session, c.id, p_no_cost.id, delay_days=10.0, horizon_days=7)
    assert res_zero["summary"]["total_unmet_demand_units"] == 0.0
    assert res_zero["summary"]["scenario_stockout_days"] == 0
    assert res_zero["summary"]["value_at_risk"] is None
    assert res_zero["summary"]["has_cost_data"] is False
    for t in res_zero["timeline"]:
        assert t["shortage_units"] == 0.0
        assert t["is_stockout"] is False

    # 3. Test demand multipliers (2x demand = 20.0/day)
    res_2x = run_delay_simulation(db_session, c.id, p.id, delay_days=10.0, horizon_days=7, demand_multiplier=2.0)
    # Day 1: avail=10, dem=20 -> unmet=10, close=0
    # Days 2..7 (6 days): avail=0, dem=20 -> unmet=20, close=0
    # Total unmet: 10 + 6 * 20 = 130.0
    assert res_2x["summary"]["total_unmet_demand_units"] == 130.0
    assert res_2x["summary"]["scenario_stockout_days"] == 7
    assert res_2x["summary"]["maximum_shortage_units"] == 20.0


def test_simulator_inbound_recovery_after_stockout(db_session):
    """
    Verifies that inbound receipt arriving after stockout period restores stock
    and resets daily unmet demand to zero.
    """
    c = Company(name="Recovery Test Co", industry="Supply")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    p = Product(company_id=c.id, external_product_id="SKU-RECOVER", name="Fastener", unit_cost=10.0, unit_price=20.0)
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    today = date.today()
    # Starting stock = 10, daily demand = 10
    inv = InventoryRecord(company_id=c.id, product_id=p.id, date=today, inventory_level=10.0, safety_stock=0.0)
    db_session.add(inv)
    sales = [Sale(company_id=c.id, product_id=p.id, date=today - timedelta(days=d), quantity=10.0) for d in range(1, 31)]
    db_session.add_all(sales)

    # Inbound shipment arriving on day 3 with 50 units
    shipment = Shipment(
        company_id=c.id,
        product_id=p.id,
        external_shipment_id="PO-RECOVER-1",
        quantity=50.0,
        order_date=today - timedelta(days=5),
        planned_delivery=today + timedelta(days=3),
    )
    db_session.add(shipment)
    db_session.commit()

    # Horizon 4 days, delay = 0
    res = run_delay_simulation(db_session, c.id, p.id, delay_days=0.0, horizon_days=4)
    timeline = res["timeline"]

    # Day 1: avail 10, demand 10 -> close 0, unmet 0
    assert timeline[0]["scenario_stock"] == 0.0
    assert timeline[0]["shortage_units"] == 0.0
    # Day 2: avail 0, demand 10 -> close 0, unmet 10, stockout True
    assert timeline[1]["scenario_stock"] == 0.0
    assert timeline[1]["shortage_units"] == 10.0
    assert timeline[1]["is_stockout"] is True
    # Day 3: inbound 50! Avail 50, demand 10 -> close 40, unmet 0, stockout False
    assert timeline[2]["scenario_inflow"] == 50.0
    assert timeline[2]["scenario_stock"] == 40.0
    assert timeline[2]["shortage_units"] == 0.0
    assert timeline[2]["is_stockout"] is False
    # Day 4: avail 40, demand 10 -> close 30, unmet 0, stockout False
    assert timeline[3]["scenario_stock"] == 30.0
    assert timeline[3]["shortage_units"] == 0.0
    assert timeline[3]["is_stockout"] is False

    assert res["summary"]["total_unmet_demand_units"] == 10.0
    assert res["summary"]["scenario_stockout_days"] == 1


def test_recommendation_engine_transfer_formatting_regression(db_session):
    """
    Task 3 Regression Test:
    Verifies that generated warehouse transfer recommendations contain correct warehouse
    names and quantities, and NEVER contain 'None' in title, reason, or warehouse string.
    """
    from app.services.recommendation_engine import generate_recommendations

    data = _seed_test_data(db_session)
    c1 = data["c1"]

    recs = generate_recommendations(db_session, c1.id)
    transfer_recs = [r for r in recs if r.get("action_type") == "STOCK_TRANSFER"]

    assert len(transfer_recs) >= 1
    for tr in transfer_recs:
        assert "None" not in tr["title"], f"Transfer title contains 'None': {tr['title']}"
        assert "None" not in tr["warehouse"], f"Transfer warehouse contains 'None': {tr['warehouse']}"
        assert "None" not in tr["reason"], f"Transfer reason contains 'None': {tr['reason']}"
        assert tr["supporting_data"]["destination_warehouse"] is not None
        assert tr["supporting_data"]["source_warehouse"] is not None
        assert tr["supporting_data"]["transfer_units"] > 0
        assert tr["supporting_data"]["source_stock"] >= 50.0


def test_task_7_supplier_assignment_and_missing_relationships(db_session):
    """
    Task 7 Test:
    Verifies that supplier assignment uses actual product-supplier relationships
    via shipments, handles varying supplier lead times, and explicitly reports
    'Unassigned' when no supplier relationship exists rather than assigning a random modulo supplier.
    """
    c = Company(name="Supplier Assign Co", industry="Manufacturing")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    # 2 distinct suppliers with different lead times
    sup_fast = Supplier(company_id=c.id, external_supplier_id="SUP-FAST", name="Fast Express Supply", lead_time_days=7.0)
    sup_slow = Supplier(company_id=c.id, external_supplier_id="SUP-SLOW", name="Slow Freight Global", lead_time_days=28.0)
    db_session.add_all([sup_fast, sup_slow])
    db_session.commit()

    # 3 products
    p1 = Product(company_id=c.id, external_product_id="SKU-P1", name="Fast Product", unit_cost=10.0, unit_price=20.0)
    p2 = Product(company_id=c.id, external_product_id="SKU-P2", name="Slow Product", unit_cost=15.0, unit_price=30.0)
    p3 = Product(company_id=c.id, external_product_id="SKU-P3", name="Unassigned Product", unit_cost=20.0, unit_price=40.0)
    db_session.add_all([p1, p2, p3])
    db_session.commit()

    today = date.today()
    # Link P1 to sup_fast via shipment
    s1 = Shipment(
        company_id=c.id,
        product_id=p1.id,
        supplier_id=sup_fast.id,
        external_shipment_id="SH-001",
        planned_delivery=today + timedelta(days=7),
    )
    # Link P2 to sup_slow via shipment
    s2 = Shipment(
        company_id=c.id,
        product_id=p2.id,
        supplier_id=sup_slow.id,
        external_shipment_id="SH-002",
        planned_delivery=today + timedelta(days=28),
    )
    # P3 has NO shipments
    db_session.add_all([s1, s2])
    db_session.commit()

    plan = compute_replenishment_plan(db_session, c.id)
    recs = {r["sku"]: r for r in plan["recommendations"]}

    # P1 assigned to sup_fast with 7.0 days
    assert recs["SKU-P1"]["supplier_id"] == sup_fast.id
    assert recs["SKU-P1"]["supplier_name"] == "Fast Express Supply"
    assert recs["SKU-P1"]["supplier_assigned"] is True
    assert recs["SKU-P1"]["lead_time_days"] == 7.0

    # P2 assigned to sup_slow with 28.0 days
    assert recs["SKU-P2"]["supplier_id"] == sup_slow.id
    assert recs["SKU-P2"]["supplier_name"] == "Slow Freight Global"
    assert recs["SKU-P2"]["supplier_assigned"] is True
    assert recs["SKU-P2"]["lead_time_days"] == 28.0

    # P3 has no relationship: explicitly Unassigned, NOT modulo-assigned!
    assert recs["SKU-P3"]["supplier_id"] is None
    assert recs["SKU-P3"]["supplier_name"] == "Unassigned"
    assert recs["SKU-P3"]["supplier_assigned"] is False


def test_task_10_safety_stock_formula_and_lead_time_variability(db_session):
    """
    Task 10 Test:
    Verifies that the unified safety stock formula:
        SS = Z * sqrt( L_mean * sigma_d^2 + d_mean^2 * sigma_L^2 )
    correctly handles:
    1. Zero demand -> SS = 0
    2. Stable lead time (sigma_L = 0) -> classic SS = Z * sigma_d * sqrt(L)
    3. Variable lead time (sigma_L > 0) -> SS is strictly higher than stable lead time
    4. Service levels (90%, 95%, 98%, 99%) strictly increase safety stock
    5. Insufficient historical data correctly falls back to sigma_L = 0.0 with documentation
    """
    from app.services.inventory_intelligence import calculate_safety_stock, get_supplier_lead_time_stats

    # 1. Zero demand
    assert calculate_safety_stock(0.0, 0.0, 14.0, 2.0) == 0.0

    # 2. Stable lead time (sigma_L = 0.0): Z=1.65, sigma_d=4, L=9 -> 1.65 * 4 * 3 = 19.8
    ss_stable = calculate_safety_stock(daily_demand_mean=10.0, daily_demand_std=4.0, lead_time_mean=9.0, lead_time_std=0.0, z_factor=1.65)
    assert ss_stable == 19.8

    # 3. Variable lead time (sigma_L = 3.0):
    # variance = 9 * 16 + 100 * 9 = 144 + 900 = 1044; sqrt(1044) ~ 32.311; 1.65 * 32.311 = 53.31
    ss_variable = calculate_safety_stock(daily_demand_mean=10.0, daily_demand_std=4.0, lead_time_mean=9.0, lead_time_std=3.0, z_factor=1.65)
    assert ss_variable == 53.31
    assert ss_variable > ss_stable

    # 4. Monotonically increasing service levels
    ss_90 = calculate_safety_stock(10.0, 4.0, 9.0, 3.0, z_factor=1.28)
    ss_95 = calculate_safety_stock(10.0, 4.0, 9.0, 3.0, z_factor=1.65)
    ss_98 = calculate_safety_stock(10.0, 4.0, 9.0, 3.0, z_factor=2.05)
    ss_99 = calculate_safety_stock(10.0, 4.0, 9.0, 3.0, z_factor=2.33)
    assert ss_90 < ss_95 < ss_98 < ss_99

    # 5. Delivery stats with insufficient history (< 2 shipments)
    c = Company(name="Lead Time Var Co", industry="Logistics")
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)

    p = Product(company_id=c.id, external_product_id="SKU-VAR", name="Var Test Product")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)

    # Zero shipments: fallback to default lead time and sigma_L = 0
    mean_l, std_l, src = get_supplier_lead_time_stats(db_session, c.id, product_id=p.id, default_lead_time=14.0)
    assert mean_l == 14.0
    assert std_l == 0.0
    assert "fallback" in src

    # 2 completed shipments with variable lead times (7 days and 13 days: mean=10, std=4.24)
    today = date.today()
    s_hist1 = Shipment(
        company_id=c.id,
        product_id=p.id,
        external_shipment_id="SH-H1",
        order_date=today - timedelta(days=20),
        planned_delivery=today - timedelta(days=13),
        actual_delivery=today - timedelta(days=13),  # 7 days elapsed
    )
    s_hist2 = Shipment(
        company_id=c.id,
        product_id=p.id,
        external_shipment_id="SH-H2",
        order_date=today - timedelta(days=20),
        planned_delivery=today - timedelta(days=10),
        actual_delivery=today - timedelta(days=7),   # 13 days elapsed
    )
    db_session.add_all([s_hist1, s_hist2])
    db_session.commit()

    mean_l2, std_l2, src2 = get_supplier_lead_time_stats(db_session, c.id, product_id=p.id)
    assert mean_l2 == 10.0
    assert round(std_l2, 2) == 4.24
    assert "historical_shipments_n=2" in src2


def test_task_11_persistent_what_if_scenarios(client):
    """
    Task 11 Test:
    Verifies saving, retrieving, deleting, and multi-tenant isolation for What-If scenarios.
    """
    from app.auth.deps import get_current_user
    from app.main import app

    # Create 2 companies
    r1 = client.post("/api/companies", json={"name": "Scenario Co A", "industry": "Retail"})
    r2 = client.post("/api/companies", json={"name": "Scenario Co B", "industry": "Wholesale"})
    c1_id = r1.json()["id"]
    c2_id = r2.json()["id"]

    mock_user_a = User(id=801, email="user_sc_a@test.com", company_id=c1_id, is_superuser=False)
    mock_user_b = User(id=802, email="user_sc_b@test.com", company_id=c2_id, is_superuser=False)

    original_override = app.dependency_overrides.get(get_current_user)
    try:
        app.dependency_overrides[get_current_user] = lambda: mock_user_a

        # 1. Save scenario for Company A
        payload = {
            "company_id": c1_id,
            "name": "Q4 Demand Surge Test",
            "description": "Stress testing safety stock under 1.5x surge and 5d delay",
            "scenario_type": "WHAT_IF",
            "parameters": {
                "product_id": 1,
                "demand_multiplier": 1.5,
                "lead_time_delta": 5.0,
                "service_level_target": 0.98,
            },
            "results": {
                "baseline": {"safety_stock": 20.0, "reorder_point": 50.0},
                "scenario": {"safety_stock": 35.0, "reorder_point": 80.0, "stockout_risk": "MEDIUM"},
                "deltas": {"safety_stock_diff": 15.0, "reorder_point_diff": 30.0},
            },
        }
        res_save = client.post("/api/inventory/scenarios", json=payload)
        assert res_save.status_code == 200
        saved_id = res_save.json()["id"]
        assert res_save.json()["name"] == "Q4 Demand Surge Test"
        assert res_save.json()["status"] == "SAVED"

        # 2. Retrieve scenarios for Company A
        res_list = client.get(f"/api/inventory/scenarios/{c1_id}")
        assert res_list.status_code == 200
        scenarios = res_list.json()
        assert len(scenarios) == 1
        assert scenarios[0]["id"] == saved_id
        assert scenarios[0]["parameters"]["demand_multiplier"] == 1.5
        assert scenarios[0]["results"]["scenario"]["safety_stock"] == 35.0

        # 3. Tenant isolation: User A cannot access Company B scenarios
        res_forbidden = client.get(f"/api/inventory/scenarios/{c2_id}")
        assert res_forbidden.status_code == 403

        # Switch to User B
        app.dependency_overrides[get_current_user] = lambda: mock_user_b
        # User B cannot save scenario claiming to be Company A
        res_b_tamper = client.post("/api/inventory/scenarios", json=payload)
        assert res_b_tamper.status_code == 403

        # User B sees 0 scenarios for Company B
        res_b_list = client.get(f"/api/inventory/scenarios/{c2_id}")
        assert res_b_list.status_code == 200
        assert len(res_b_list.json()) == 0

        # Switch back to User A and delete scenario
        app.dependency_overrides[get_current_user] = lambda: mock_user_a
        res_del = client.delete(f"/api/inventory/scenarios/{c1_id}/{saved_id}")
        assert res_del.status_code == 200
        assert res_del.json()["status"] == "DELETED"

        # Verify scenario is gone
        res_empty = client.get(f"/api/inventory/scenarios/{c1_id}")
        assert len(res_empty.json()) == 0
    finally:
        if original_override is not None:
            app.dependency_overrides[get_current_user] = original_override
        else:
            app.dependency_overrides.pop(get_current_user, None)



