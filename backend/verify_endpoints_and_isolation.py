"""
Live API and Multi-Tenant Isolation Verification Script for SupplyIQ
"""
import requests
import json
from app.auth.security import create_access_token

BASE_URL = "http://127.0.0.1:8000"

def get_headers(user_id: int):
    token = create_access_token(subject=str(user_id))
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

def run_checks():
    headers_c5 = get_headers(5)  # User 5 belongs to Company 5 (non-superuser)
    headers_c7 = get_headers(7)  # User 7 belongs to Company 7 (non-superuser)

    print("=== LIVE API ENDPOINT VERIFICATION (COMPANY 5) ===")

    # 1. Overview endpoint
    r = requests.get(f"{BASE_URL}/api/inventory/overview/5", headers=headers_c5)
    assert r.status_code == 200, f"Overview returned {r.status_code}: {r.text}"
    d = r.json()
    print(f"[PASS] Overview 5: Total Units={d['total_inventory_units']}, Valuation=${d['total_valuation']:,.2f}, SKUs={d['total_skus']}")
    assert round(d["total_inventory_units"], 1) == 2003.5
    assert round(d["total_valuation"], 2) == 337198.55
    assert d["total_skus"] == 8

    # 2. Explorer endpoint
    r = requests.get(f"{BASE_URL}/api/inventory/explorer/5", headers=headers_c5)
    assert r.status_code == 200, f"Explorer returned {r.status_code}: {r.text}"
    d = r.json()
    ex_units = sum(i["inventory_level"] for i in d["items"])
    print(f"[PASS] Explorer 5: Total Catalog SKUs={d['total']}, Sum Units={ex_units:.1f}")
    assert d["total"] == 8
    assert round(ex_units, 1) == 2003.5

    # 3. Warehouses endpoint
    r = requests.get(f"{BASE_URL}/api/inventory/warehouses/5", headers=headers_c5)
    assert r.status_code == 200, f"Warehouses returned {r.status_code}: {r.text}"
    warehouses_list = r.json()
    wh_units = sum(w["total_units"] for w in warehouses_list)
    wh_val = sum(w["total_value"] for w in warehouses_list)
    print(f"[PASS] Warehouses 5: Warehouses={len(warehouses_list)}, Sum Units={wh_units:.1f}, Sum Valuation=${wh_val:,.2f}")
    assert len(warehouses_list) == 8
    assert round(wh_units, 1) == 2003.5
    assert abs(wh_val - 337198.55) <= 0.02

    # 4. Insights ABC/XYZ endpoint
    r = requests.get(f"{BASE_URL}/api/inventory/insights/abc-xyz/5", headers=headers_c5)
    assert r.status_code == 200, f"Insights returned {r.status_code}: {r.text}"
    d = r.json()
    insights_units = sum(p["current_stock"] for p in d["products"])
    insights_val = d["summary"]["total_stock_value"]
    print(f"[PASS] Insights 5: Products={len(d['products'])}, Sum Units={insights_units:.1f}, Total Stock Valuation=${insights_val:,.2f}")
    assert round(insights_units, 1) == 2003.5
    assert round(insights_val, 1) == 337198.6

    # 5. Replenishment endpoint
    r = requests.get(f"{BASE_URL}/api/inventory/replenishment/5", headers=headers_c5)
    assert r.status_code == 200, f"Replenishment returned {r.status_code}: {r.text}"
    d = r.json()
    recs = {r["name"]: r for r in d["recommendations"]}
    repl_units = sum(r["on_hand"] for r in d["recommendations"])
    repl_val = sum(r["on_hand"] * r["unit_cost"] for r in d["recommendations"])
    print(f"[PASS] Replenishment 5: Stock Units={repl_units:.1f}, Valuation=${repl_val:,.2f}, Total Reorder Qty={d['summary']['total_reorder_units']}, Total Cost=${d['summary']['total_reorder_cost']:,.2f}")
    assert round(repl_units, 1) == 2003.5
    assert round(repl_val, 2) == 337198.55
    assert "Laptops Item 1" in recs
    assert "Mouse Item 5" in recs
    assert recs["Laptops Item 1"]["suggested_order_qty"] == 200
    assert recs["Mouse Item 5"]["suggested_order_qty"] == 191
    assert d["summary"]["total_reorder_units"] == 391
    assert round(d["summary"]["total_reorder_cost"], 2) == 113603.75

    # 6. Action Center recommendations
    r = requests.get(f"{BASE_URL}/api/recommendations/5", headers=headers_c5)
    assert r.status_code == 200, f"Action Center returned {r.status_code}: {r.text}"
    d = r.json()
    recs_list = d["recommendations"]
    po_recs = [rec for rec in recs_list if rec.get("action_type") in ("PROACTIVE_REORDER", "PURCHASE_ORDER", "REORDER_POINT_BREACH", "EXPEDITE_REPLENISHMENT")]
    print(f"[PASS] Action Center 5: Total Recs={len(recs_list)}, PO Recs={len(po_recs)}")
    laptop_po = next(p for p in po_recs if "Laptops" in p["title"] or p["sku"] == "PROD-001" or p.get("product_name") == "Laptops Item 1")
    mouse_po = next(p for p in po_recs if "Mouse" in p["title"] or p["sku"] == "PROD-005" or p.get("product_name") == "Mouse Item 5")
    assert laptop_po["supporting_data"]["suggested_order_qty"] == 200
    assert mouse_po["supporting_data"]["suggested_order_qty"] == 191
    assert laptop_po["supporting_data"]["estimated_order_cost"] == 110500.00
    assert mouse_po["supporting_data"]["estimated_order_cost"] == 3103.75
    print(f"  Synchronized PO orders: Laptops=200 units (${laptop_po['supporting_data']['estimated_order_cost']:,.2f}), Mouse=191 units (${mouse_po['supporting_data']['estimated_order_cost']:,.2f})")

    # 7. Model Registry endpoint
    r = requests.get(f"{BASE_URL}/api/models/5", headers=headers_c5)
    assert r.status_code == 200, f"Models returned {r.status_code}: {r.text}"
    models_list = r.json()
    print(f"[PASS] Models 5: Registered Models count={len(models_list)}")
    demand_m = next(m for m in models_list if m["model_type"].lower() == "demand_forecast")
    m_json = demand_m["metrics"]
    print(f"  Demand Model {demand_m['id']}: MAE={m_json.get('mae'):.2f}, RMSE={m_json.get('rmse'):.2f}, MAPE={m_json.get('mape'):.2f}%, WAPE={m_json.get('wape'):.2f}%")
    print(f"  Data Leakage Guard: Train={m_json.get('train_rows')}, Test={m_json.get('test_rows')}, Dataset Size={demand_m.get('dataset_size')}")
    assert m_json.get("train_rows") == 19829
    assert m_json.get("test_rows") == 4958
    assert demand_m.get("dataset_size") == 25305
    assert "naive_seasonal_baseline" in m_json.get("comparison", {})

    # 8. Delay Simulator endpoint
    payload = {
        "company_id": 5,
        "product_id": 46,  # Laptops Item 1
        "delay_days": 7.0,
        "horizon_days": 30,
    }
    r = requests.post(f"{BASE_URL}/api/inventory/simulate/delay", json=payload, headers=headers_c5)
    assert r.status_code == 200, f"Simulator returned {r.status_code}: {r.text}"
    sim_data = r.json()
    print(f"[PASS] Simulator 5 SKU 46: Inflow Day 14={sim_data['timeline'][13]['scenario_inflow']}, Stockout Days={sim_data['summary']['scenario_stockout_days']}, Min Scenario Stock={sim_data['summary']['min_scenario_stock']}")
    assert sim_data["timeline"][13]["scenario_inflow"] == 171.0
    assert sim_data["summary"]["scenario_stockout_days"] == 0
    assert sim_data["parameters"]["is_assumed_order"] is True

    # 9. Multi-Tenant Isolation
    print("\n=== MULTI-TENANT ISOLATION SECURITY CHECKS ===")
    # User 5 (Company 5) attempting to access Company 7
    r_cross1 = requests.get(f"{BASE_URL}/api/inventory/overview/7", headers=headers_c5)
    print(f"[PASS] User 5 accessing Company 7 Overview: Status={r_cross1.status_code} ({r_cross1.json().get('detail')})")
    assert r_cross1.status_code == 403

    r_cross2 = requests.get(f"{BASE_URL}/api/inventory/replenishment/7", headers=headers_c5)
    print(f"[PASS] User 5 accessing Company 7 Replenishment: Status={r_cross2.status_code} ({r_cross2.json().get('detail')})")
    assert r_cross2.status_code == 403

    # User 7 (Company 7) attempting to access Company 5
    r_cross3 = requests.get(f"{BASE_URL}/api/inventory/overview/5", headers=headers_c7)
    print(f"[PASS] User 7 accessing Company 5 Overview: Status={r_cross3.status_code} ({r_cross3.json().get('detail')})")
    assert r_cross3.status_code == 403

    r_cross4 = requests.get(f"{BASE_URL}/api/recommendations/5", headers=headers_c7)
    print(f"[PASS] User 7 accessing Company 5 Recommendations: Status={r_cross4.status_code} ({r_cross4.json().get('detail')})")
    assert r_cross4.status_code == 403

    # Unauthenticated request
    r_unauth = requests.get(f"{BASE_URL}/api/inventory/overview/5")
    print(f"[PASS] Unauthenticated request to Overview: Status={r_unauth.status_code}")
    assert r_unauth.status_code == 401

    print("\n==================================================================")
    print("ALL LIVE ENDPOINTS AND MULTI-TENANT ISOLATION CHECKS PASSED 100%!")
    print("==================================================================")

if __name__ == "__main__":
    run_checks()
