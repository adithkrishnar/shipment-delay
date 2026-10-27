"""
SupplyIQ Inventory Analytics & Segmentation Service.
Provides ABC classification (value contribution), XYZ classification (demand volatility),
inventory aging, turnover ratios, and warehouse comparisons.
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Any, Dict, List, Optional
import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Company, Product, InventoryRecord, Sale, Warehouse, Shipment


def get_abc_xyz_analysis(db: Session, company_id: int) -> Dict[str, Any]:
    """
    Computes ABC (revenue/consumption value) and XYZ (demand volatility) classification
    for all products belonging to the company.
    - ABC:
        A: Top 80% cumulative value
        B: Next 15% cumulative value (80% - 95%)
        C: Bottom 5% cumulative value (95% - 100%)
    - XYZ:
        X: Coefficient of variation (CV) < 0.5 (stable, predictable demand)
        Y: 0.5 <= CV <= 1.0 (moderate variability)
        Z: CV > 1.0 or intermittent/erratic demand
    """
    products = db.query(Product).filter(Product.company_id == company_id).all()
    if not products:
        return {
            "matrix": {},
            "summary": {"total_products": 0, "total_value": 0},
            "products": []
        }

    # Fetch total sales quantity in past 365 days
    cutoff_date = date.today() - timedelta(days=365)
    sales = (
        db.query(Sale.product_id, Sale.quantity, Sale.date)
        .filter(Sale.company_id == company_id, Sale.date >= cutoff_date)
        .all()
    )

    product_sales_map: Dict[int, List[float]] = {p.id: [] for p in products}
    for s in sales:
        if s.product_id in product_sales_map and s.quantity is not None:
            product_sales_map[s.product_id].append(float(s.quantity))

    # Compute latest stock per product
    latest_inv_rows = (
        db.query(InventoryRecord)
        .filter(InventoryRecord.company_id == company_id)
        .order_by(InventoryRecord.product_id, InventoryRecord.date.desc())
        .all()
    )
    stock_map: Dict[int, float] = {}
    for r in latest_inv_rows:
        if r.product_id not in stock_map:
            stock_map[r.product_id] = float(r.inventory_level or 0.0)

    # 1. Calculate Annual Consumption Value (ACV) and CV
    evaluated_products = []
    total_consumption_value = 0.0

    for p in products:
        sales_qtys = product_sales_map.get(p.id, [])
        annual_qty = sum(sales_qtys)
        unit_cost = float(p.unit_cost) if p.unit_cost is not None else float(p.unit_price or 25.0)
        acv = annual_qty * unit_cost
        total_consumption_value += acv

        # Coefficient of variation
        mean_demand = np.mean(sales_qtys) if sales_qtys else 0.0
        std_demand = np.std(sales_qtys, ddof=1) if len(sales_qtys) > 1 else 0.0
        cv = (std_demand / mean_demand) if mean_demand > 0 else 2.0

        current_stock = stock_map.get(p.id, 0.0)
        stock_value = current_stock * unit_cost

        evaluated_products.append({
            "id": p.id,
            "external_id": p.external_product_id,
            "name": p.name,
            "category": p.category or "General",
            "unit_cost": unit_cost,
            "unit_price": p.unit_price,
            "annual_qty_sold": round(annual_qty, 1),
            "annual_consumption_value": round(acv, 2),
            "current_stock": round(current_stock, 1),
            "stock_value": round(stock_value, 2),
            "mean_daily_demand": round(mean_demand, 2),
            "demand_std": round(std_demand, 2),
            "cv": round(cv, 3),
        })

    # 2. Sort descending by ACV for ABC classification
    evaluated_products.sort(key=lambda x: x["annual_consumption_value"], reverse=True)

    running_value = 0.0
    for item in evaluated_products:
        running_value += item["annual_consumption_value"]
        cumulative_share = (running_value / total_consumption_value) if total_consumption_value > 0 else 1.0

        # ABC
        if cumulative_share <= 0.80 or item == evaluated_products[0]:
            abc = "A"
        elif cumulative_share <= 0.95:
            abc = "B"
        else:
            abc = "C"

        # XYZ
        if item["cv"] < 0.5:
            xyz = "X"
        elif item["cv"] <= 1.0:
            xyz = "Y"
        else:
            xyz = "Z"

        item["abc_class"] = abc
        item["xyz_class"] = xyz
        item["segment"] = f"{abc}{xyz}"
        item["cumulative_value_share"] = round(cumulative_share * 100, 2)

    # 3. Construct 9-box matrix summary
    segments = ["AX", "AY", "AZ", "BX", "BY", "BZ", "CX", "CY", "CZ"]
    matrix = {s: {"count": 0, "total_value": 0.0, "total_stock": 0.0, "products": []} for s in segments}

    for item in evaluated_products:
        seg = item["segment"]
        if seg in matrix:
            matrix[seg]["count"] += 1
            matrix[seg]["total_value"] += item["stock_value"]
            matrix[seg]["total_stock"] += item["current_stock"]
            matrix[seg]["products"].append({
                "id": item["id"],
                "name": item["name"],
                "sku": item["external_id"],
                "stock": item["current_stock"],
                "stock_value": item["stock_value"],
            })

    for s in segments:
        matrix[s]["total_value"] = round(matrix[s]["total_value"], 2)
        matrix[s]["total_stock"] = round(matrix[s]["total_stock"], 1)

    return {
        "matrix": matrix,
        "summary": {
            "total_products": len(evaluated_products),
            "total_annual_consumption_value": round(total_consumption_value, 2),
            "total_stock_value": round(sum(p["stock_value"] for p in evaluated_products), 2),
            "a_count": sum(1 for p in evaluated_products if p["abc_class"] == "A"),
            "b_count": sum(1 for p in evaluated_products if p["abc_class"] == "B"),
            "c_count": sum(1 for p in evaluated_products if p["abc_class"] == "C"),
            "x_count": sum(1 for p in evaluated_products if p["xyz_class"] == "X"),
            "y_count": sum(1 for p in evaluated_products if p["xyz_class"] == "Y"),
            "z_count": sum(1 for p in evaluated_products if p["xyz_class"] == "Z"),
        },
        "products": evaluated_products,
    }


def get_inventory_aging_and_slow_moving(db: Session, company_id: int) -> Dict[str, Any]:
    """
    Identifies slow-moving, non-moving, and aging inventory.
    """
    products = db.query(Product).filter(Product.company_id == company_id).all()
    today = date.today()

    latest_sales = (
        db.query(Sale.product_id, func.max(Sale.date))
        .filter(Sale.company_id == company_id)
        .group_by(Sale.product_id)
        .all()
    )
    last_sale_map = {row[0]: row[1] for row in latest_sales}

    latest_inv_rows = (
        db.query(InventoryRecord)
        .filter(InventoryRecord.company_id == company_id)
        .order_by(InventoryRecord.product_id, InventoryRecord.date.desc())
        .all()
    )
    stock_map = {}
    for r in latest_inv_rows:
        if r.product_id not in stock_map:
            stock_map[r.product_id] = float(r.inventory_level or 0.0)

    aging_buckets = {
        "0-30 days": {"count": 0, "units": 0, "value": 0.0},
        "31-60 days": {"count": 0, "units": 0, "value": 0.0},
        "61-90 days": {"count": 0, "units": 0, "value": 0.0},
        "91-180 days (Slow Moving)": {"count": 0, "units": 0, "value": 0.0},
        "180+ days (Dead / Non-Moving)": {"count": 0, "units": 0, "value": 0.0},
    }

    slow_moving_list = []

    for p in products:
        stock = stock_map.get(p.id, 0.0)
        unit_cost = float(p.unit_cost) if p.unit_cost is not None else float(p.unit_price or 25.0)
        stock_value = stock * unit_cost

        last_date = last_sale_map.get(p.id)
        days_since_sale = (today - last_date).days if last_date else 120

        if days_since_sale <= 30:
            bucket = "0-30 days"
        elif days_since_sale <= 60:
            bucket = "31-60 days"
        elif days_since_sale <= 90:
            bucket = "61-90 days"
        elif days_since_sale <= 180:
            bucket = "91-180 days (Slow Moving)"
        else:
            bucket = "180+ days (Dead / Non-Moving)"

        aging_buckets[bucket]["count"] += 1
        aging_buckets[bucket]["units"] += stock
        aging_buckets[bucket]["value"] += stock_value

        if days_since_sale > 90 and stock > 0:
            slow_moving_list.append({
                "product_id": p.id,
                "name": p.name,
                "sku": p.external_product_id,
                "days_inactive": days_since_sale,
                "stock_on_hand": stock,
                "stock_value": round(stock_value, 2),
                "last_sale_date": str(last_date) if last_date else "Never",
                "risk_tier": "CRITICAL" if days_since_sale > 180 else "HIGH",
            })

    for k in aging_buckets:
        aging_buckets[k]["units"] = round(aging_buckets[k]["units"], 1)
        aging_buckets[k]["value"] = round(aging_buckets[k]["value"], 2)

    slow_moving_list.sort(key=lambda x: x["stock_value"], reverse=True)

    return {
        "aging_buckets": aging_buckets,
        "slow_moving_skus": slow_moving_list[:20],
        "total_at_risk_capital": round(
            aging_buckets["91-180 days (Slow Moving)"]["value"] +
            aging_buckets["180+ days (Dead / Non-Moving)"]["value"],
            2
        )
    }


def get_warehouses_analytics(db: Session, company_id: int) -> List[Dict[str, Any]]:
    """
    Summarizes stock levels, valuation, and SKU counts across all company warehouses.
    Utilization is reported only when explicit capacity metrics exist; otherwise None
    to avoid fabricating storage metrics.
    """
    warehouses = db.query(Warehouse).filter(Warehouse.company_id == company_id).all()
    if not warehouses:
        return []

    results = []
    for wh in warehouses:
        inv_records = (
            db.query(InventoryRecord)
            .filter(InventoryRecord.company_id == company_id, InventoryRecord.warehouse_id == wh.id)
            .all()
        )
        total_units = sum(float(r.inventory_level or 0) for r in inv_records)
        skus_in_wh = len(set(r.product_id for r in inv_records))

        # Check capacity: only report utilization if capacity is explicitly defined
        capacity = getattr(wh, "capacity", None)
        utilization_pct = round((total_units / capacity) * 100, 1) if (capacity and capacity > 0) else None

        # Determine status truthfully based on stock and SKU availability
        if total_units <= 0:
            status = "CRITICAL"
        elif total_units < 50:
            status = "ATTENTION"
        else:
            status = "HEALTHY"

        results.append({
            "id": wh.id,
            "name": wh.name,
            "location": wh.region or "Regional Hub",
            "total_skus": skus_in_wh,
            "total_units": round(total_units, 1),
            "capacity": capacity,
            "utilization_pct": utilization_pct,
            "status": status,
        })

    return results
