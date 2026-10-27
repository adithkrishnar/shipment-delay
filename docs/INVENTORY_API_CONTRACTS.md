# SupplyIQ Inventory Intelligence — API Contracts

All endpoints enforce multi-tenant authorization. Non-superusers attempting to access a `company_id` different from their JWT session receive `403 Forbidden`.

---

## 1. Inventory Control Tower Overview
- **Method**: `GET`
- **Route**: `/api/inventory/overview/{company_id}`
- **Response Schema** (`200 OK`):
```json
{
  "company_id": 1,
  "health_score": 88,
  "total_skus": 24,
  "total_inventory_units": 15420.0,
  "total_valuation": 385500.0,
  "critical_stockouts": 2,
  "overstock_skus": 1,
  "avg_stockout_probability": 0.1245,
  "items": [
    {
      "product_id": 101,
      "external_product_id": "SKU-001",
      "product_name": "High Voltage Relay",
      "inventory_level": 45.0,
      "daily_demand": 12.0,
      "inventory_coverage_days": 3.8,
      "stockout_risk": "CRITICAL"
    }
  ]
}
```

---

## 2. Inventory Explorer
- **Method**: `GET`
- **Route**: `/api/inventory/explorer/{company_id}`
- **Query Parameters**:
  - `search` (string, optional): Search query for SKU or product name.
  - `category` (string, optional): Filter by category.
  - `risk_tier` (string, optional): Filter by `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- **Response Schema** (`200 OK`):
```json
{
  "total": 24,
  "items": [
    {
      "product_id": 1,
      "external_product_id": "SKU-101",
      "product_name": "Microcontroller",
      "category": "Electronics",
      "inventory_level": 120.0,
      "daily_demand": 14.2,
      "inventory_coverage_days": 8.5,
      "safety_stock": 28.5,
      "reorder_point": 170.5,
      "stockout_risk": "MEDIUM",
      "lead_time_days": 10.0,
      "supplier_name": "Apex Micro"
    }
  ]
}
```

---

## 3. Discrete-Event Delay Simulation
- **Method**: `POST`
- **Route**: `/api/inventory/simulate/delay`
- **Request Body**:
```json
{
  "company_id": 1,
  "product_id": 101,
  "warehouse_id": null,
  "delay_days": 10.0,
  "demand_multiplier": 1.0,
  "horizon_days": 30,
  "target_order_id": null,
  "emergency_order_qty": 0.0,
  "emergency_order_day": 5,
  "user_expedite_cost": null
}
```
- **Response Schema** (`200 OK`):
```json
{
  "product_id": 101,
  "product_name": "High Voltage Relay",
  "external_product_id": "SKU-001",
  "sim_start_date": "2026-10-26",
  "horizon_days": 30,
  "parameters": {
    "delay_days": 10.0,
    "demand_multiplier": 1.0,
    "starting_stock": 45.0,
    "safety_stock": 25.0,
    "reorder_point": 145.0
  },
  "dates": {
    "baseline_receipt_date": "2026-11-05",
    "delayed_receipt_date": "2026-11-15",
    "earliest_stockout_date": "2026-10-30"
  },
  "summary": {
    "starting_stock": 45.0,
    "ending_baseline_stock": 85.0,
    "ending_scenario_stock": 0.0,
    "baseline_stockout_days": 0,
    "scenario_stockout_days": 6,
    "additional_stockout_days": 6,
    "total_unmet_demand_units": 72.0,
    "maximum_shortage_units": 72.0,
    "value_at_risk": 1080.0,
    "lost_revenue_potential": 2520.0,
    "has_cost_data": true
  },
  "timeline": [
    {
      "day": 1,
      "date": "2026-10-27",
      "baseline_stock": 33.0,
      "scenario_stock": 33.0,
      "baseline_demand": 12.0,
      "scenario_demand": 12.0,
      "is_stockout": false,
      "shortage_units": 0.0,
      "events": null
    }
  ],
  "alternatives": [
    {
      "action": "Do Nothing (Absorb Delay)",
      "projected_stockout_days": 6,
      "unmet_demand_units": 72.0,
      "financial_impact": "$1,080.00",
      "risk_tier": "CRITICAL"
    }
  ]
}
```

---

## 4. ABC/XYZ Portfolio Insights
- **Method**: `GET`
- **Route**: `/api/inventory/insights/abc-xyz/{company_id}`
- **Response Schema** (`200 OK`):
```json
{
  "matrix": {
    "AX": { "count": 4, "total_value": 185000.0, "total_stock": 4200.0, "products": [] },
    "AY": { "count": 2, "total_value": 95000.0, "total_stock": 1800.0, "products": [] }
  },
  "summary": {
    "total_products": 24,
    "total_annual_consumption_value": 450000.0,
    "total_stock_value": 385500.0,
    "a_count": 6,
    "b_count": 8,
    "c_count": 10,
    "x_count": 12,
    "y_count": 8,
    "z_count": 4
  },
  "products": []
}
```

---

## 5. Replenishment & Reorder Planning
- **Method**: `GET`
- **Route**: `/api/inventory/replenishment/{company_id}?service_level=0.95&horizon_days=30`
- **Response Schema** (`200 OK`):
```json
{
  "service_level": 0.95,
  "z_factor": 1.65,
  "summary": {
    "total_skus": 24,
    "skus_needing_reorder": 5,
    "critical_stockouts": 2,
    "total_reorder_units": 1250,
    "total_reorder_cost": 31250.0
  },
  "recommendations": []
}
```

---

## 6. Multi-Warehouse Transfers
- **Method**: `GET`
- **Route**: `/api/inventory/transfers/{company_id}`
- **Response Schema** (`200 OK`): Returns array of valid surplus-to-shortage transfer proposals preserving source safety stock ($\ge 50$ units).
