import pandas as pd
from app.database import SessionLocal
from app.models import Company, Product, InventoryRecord, Warehouse
from app.services.inventory_intelligence import _latest_inventory, company_inventory, inventory_summary
from app.services.inventory_analytics_service import get_warehouses_analytics, get_abc_xyz_analysis, get_inventory_aging_and_slow_moving
from app.services.replenishment_service import compute_replenishment_plan

def verify_inventory():
    db = SessionLocal()
    company_id = 5

    print("================ 1. UNDERLYING INVENTORY RECORDS AUDIT ================")
    records = db.query(InventoryRecord).filter(InventoryRecord.company_id == company_id).all()
    print(f"Total InventoryRecord rows for Company 5: {len(records)}")

    # Distinct dates
    dates = sorted(list({r.date for r in records}))
    print(f"Inventory record date(s): {dates}")

    # Warehouses
    warehouses = db.query(Warehouse).filter(Warehouse.company_id == company_id).all()
    print(f"Total Warehouses configured for Company 5: {len(warehouses)}")
    for w in warehouses:
        w_recs = [r for r in records if r.warehouse_id == w.id]
        total_w_units = sum(r.inventory_level for r in w_recs)
        print(f"  Warehouse {w.id}: {w.name} ({w.region}) -> {len(w_recs)} SKU records, total_units={total_w_units:.1f}")

    products = db.query(Product).filter(Product.company_id == company_id).all()
    print(f"\nTotal Products configured for Company 5: {len(products)}")
    for p in products:
        p_recs = [r for r in records if r.product_id == p.id]
        p_units = sum(r.inventory_level for r in p_recs)
        has_cost = p.unit_cost is not None
        cost_val = float(p.unit_cost) if has_cost else None
        price_val = float(p.unit_price) if p.unit_price is not None else None
        print(f"  SKU {p.id} ({p.name}, {p.external_product_id}): {len(p_recs)} facility records, sum_stock={p_units:.1f}, explicit_cost={cost_val}, unit_price={price_val}")

    print("\n================ 2. RECOMPUTED STOCK & VALUATION ================")
    total_canonical_units = sum(r.inventory_level for r in records)
    total_canonical_valuation = 0.0
    for p in products:
        p_recs = [r for r in records if r.product_id == p.id]
        p_stock = sum(r.inventory_level for r in p_recs)
        unit_val = float(p.unit_cost if p.unit_cost is not None else (p.unit_price or 0.0))
        p_val = p_stock * unit_val
        total_canonical_valuation += p_val

    print(f"Sum of underlying records: {total_canonical_units:.1f} units, ${total_canonical_valuation:,.2f}")

    print("\n================ 3. CROSS-PAGE CONSISTENCY VERIFICATION ================")
    # A. Overview
    items = company_inventory(db, company_id)
    summary = inventory_summary(items)
    overview_units = summary["inventory_units"]
    print(f"Overview: {overview_units:.1f} units across {summary['products']} SKUs")

    # B. Explorer
    explorer_units = sum(i["inventory_level"] for i in items)
    print(f"Inventory Explorer: {explorer_units:.1f} units")

    # C. Products & Warehouses
    wh_analytics = get_warehouses_analytics(db, company_id)
    wh_units = sum(w["total_units"] for w in wh_analytics)
    wh_val = sum(w["total_value"] for w in wh_analytics)
    print(f"Products & Warehouses: {wh_units:.1f} units, ${wh_val:,.2f} across {len(wh_analytics)} facilities")

    # D. Inventory Insights
    abc = get_abc_xyz_analysis(db, company_id)
    abc_val = abc["summary"]["total_stock_value"]
    aging = get_inventory_aging_and_slow_moving(db, company_id)
    aging_units = sum(b["units"] for b in aging["aging_buckets"].values())
    aging_val = sum(b["value"] for b in aging["aging_buckets"].values())
    print(f"Inventory Insights: ABC Valuation=${abc_val:,.2f}, Aging Units={aging_units:.1f}, Aging Valuation=${aging_val:,.2f}")

    # E. Replenishment
    replen = compute_replenishment_plan(db, company_id)
    replen_on_hand = sum(r["on_hand"] for r in replen["recommendations"])
    print(f"Replenishment: {replen_on_hand:.1f} on-hand units across {replen['summary']['total_skus']} SKUs")

    # Reconciled assertions
    assert abs(total_canonical_units - 2003.5) < 0.1, "Underlying records sum mismatch"
    assert abs(overview_units - 2003.5) < 0.1, "Overview units mismatch"
    assert abs(explorer_units - 2003.5) < 0.1, "Explorer units mismatch"
    assert abs(wh_units - 2003.5) < 0.1, "Warehouse units mismatch"
    assert abs(aging_units - 2003.5) < 0.1, "Aging units mismatch"
    assert abs(replen_on_hand - 2003.5) < 0.1, "Replenishment on-hand mismatch"

    assert abs(total_canonical_valuation - 337198.55) < 0.1, "Canonical valuation mismatch"
    assert abs(wh_val - 337198.55) < 0.1, "Warehouse valuation mismatch"
    assert abs(abc_val - 337198.55) < 0.1, "ABC valuation mismatch"
    assert abs(aging_val - 337198.55) < 0.1, "Aging valuation mismatch"

    print("\n[PASS] All 5 pages trace to identical underlying inventory records and exact $337,198.55 valuation!")

if __name__ == "__main__":
    verify_inventory()
