"""
Demo / synthetic data generator.

Generates 3 demo companies (Electronics, Automotive Parts, FMCG) with
DELIBERATELY DIFFERENT data volumes and history lengths, so the platform's
"sufficient data -> company-specific model" vs "insufficient -> base model"
logic (see services/model_selection.py, built in a later phase) has a real
scenario to react to rather than an artificial toggle.

All values are clearly synthetic and are only ever used for demo companies
(Company.is_demo = 1). Relationships are deliberately realistic rather than
pure random noise:
  - demand has trend + weekly seasonality + occasional promotion bumps
  - each product is served by a supplier with its own reliability/lead time
  - shipment delay probability and duration are driven by that supplier's
    reliability and the shipment's distance (unreliable + long-distance =
    more/longer delays)
  - inventory is simulated day-by-day: it depletes with sales and is
    replenished only when a shipment's simulated actual_delivery date
    arrives - so stockout risk emerges from the data instead of being
    hard-coded.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import (
    Company,
    InventoryRecord,
    Product,
    Sale,
    Shipment,
    Supplier,
    Warehouse,
)

CATEGORY_POOL = {
    "Electronics": ["Laptops", "Audio", "Mobile Accessories", "Wearables", "Networking"],
    "Automotive Parts": ["Brakes", "Filters", "Batteries", "Lighting", "Suspension"],
    "FMCG": ["Snacks", "Beverages", "Personal Care", "Household", "Packaged Foods"],
}

TRANSPORT_MODES = ["road", "rail", "air", "sea"]
CITY_POOL = [
    ("Mumbai", "Delhi", 1400), ("Chennai", "Bengaluru", 350), ("Pune", "Hyderabad", 560),
    ("Kolkata", "Mumbai", 1960), ("Delhi", "Ahmedabad", 950), ("Bengaluru", "Chennai", 350),
    ("Hyderabad", "Delhi", 1580), ("Ahmedabad", "Pune", 660),
]

COMPANY_CONFIGS = [
    {
        "name": "Horizon Electronics",
        "industry": "Electronics",
        "n_products": 15,
        "n_suppliers": 5,
        "history_days": 365,    # 1 year -> enough for seasonality detection
        "seed": 101,
    },
    {
        "name": "TorqueParts Autoworks",
        "industry": "Automotive Parts",
        "n_products": 10,
        "n_suppliers": 3,
        "history_days": 120,    # 4 months -> sparse -> should fall back to base model
        "seed": 202,
    },
    {
        "name": "FreshMart FMCG",
        "industry": "FMCG",
        "n_products": 12,
        "n_suppliers": 4,
        "history_days": 270,    # 9 months -> borderline
        "seed": 303,
    },
]


def _reset_demo_data(db: Session) -> None:
    """Delete any existing demo companies and their data (cascades handle children)."""
    demo_ids = [c.id for c in db.query(Company).filter(Company.is_demo == 1).all()]
    for company_id in demo_ids:
        db.execute(delete(Shipment).where(Shipment.company_id == company_id))
        db.execute(delete(InventoryRecord).where(InventoryRecord.company_id == company_id))
        db.execute(delete(Sale).where(Sale.company_id == company_id))
        db.execute(delete(Supplier).where(Supplier.company_id == company_id))
        db.execute(delete(Product).where(Product.company_id == company_id))
        db.execute(delete(Warehouse).where(Warehouse.company_id == company_id))
    db.query(Company).filter(Company.is_demo == 1).delete()
    db.commit()


def _generate_company(db: Session, config: dict) -> dict:
    rng = np.random.default_rng(config["seed"])
    industry = config["industry"]
    categories = CATEGORY_POOL[industry]

    company = Company(name=config["name"], industry=industry, is_demo=1)
    db.add(company)
    db.flush()

    # --- Warehouses ---
    warehouses = [
        Warehouse(company_id=company.id, name=f"{config['name']} DC North", region="North"),
        Warehouse(company_id=company.id, name=f"{config['name']} DC South", region="South"),
    ]
    db.add_all(warehouses)
    db.flush()

    # --- Suppliers: each with its own reliability / lead time / cost profile ---
    suppliers = []
    for i in range(config["n_suppliers"]):
        reliability = float(np.clip(rng.normal(0.87, 0.09), 0.55, 0.99))
        supplier = Supplier(
            company_id=company.id,
            external_supplier_id=f"SUP-{i+1:03d}",
            name=f"{industry.split()[0]} Supply Co {i+1}",
            lead_time_days=float(rng.integers(4, 22)),
            reliability=round(reliability, 3),
            cost_index=round(float(rng.uniform(0.7, 1.3)), 3),
            defect_rate=round(float(np.clip(rng.normal(0.02, 0.015), 0, 0.15)), 4),
        )
        suppliers.append(supplier)
    db.add_all(suppliers)
    db.flush()

    # --- Products ---
    products, product_meta = [], []
    for i in range(config["n_products"]):
        category = categories[i % len(categories)]
        base_demand = float(rng.uniform(15, 220))
        product = Product(
            company_id=company.id,
            external_product_id=f"{industry[:3].upper()}-{i+1:04d}",
            name=f"{category} Item {i+1}",
            category=category,
            unit_cost=round(float(rng.uniform(50, 4000)), 2),
        )
        product.unit_price = round(product.unit_cost * float(rng.uniform(1.2, 1.8)), 2)
        products.append(product)
        product_meta.append({
            "base_demand": base_demand,
            "trend_per_day": float(rng.uniform(-0.0004, 0.0009)),          # slow drift, some declining
            "weekly_amplitude": float(rng.uniform(0.05, 0.3)),
            "noise_std_frac": float(rng.uniform(0.08, 0.2)),
            "supplier": suppliers[i % len(suppliers)],
            "warehouse": warehouses[i % len(warehouses)],
            "reorder_interval_days": int(rng.integers(10, 21)),
            "promo_day_prob": float(rng.uniform(0.02, 0.06)),
        })
    db.add_all(products)
    db.flush()

    start_date = dt.date.today() - dt.timedelta(days=config["history_days"])
    date_range = [start_date + dt.timedelta(days=d) for d in range(config["history_days"])]

    sale_rows: list[dict] = []
    shipment_rows: list[dict] = []
    inventory_rows: list[dict] = []

    for product, meta in zip(products, product_meta):
        supplier = meta["supplier"]
        # --- Demand series: trend + weekly seasonality + promo bumps + noise ---
        demand_series = np.zeros(len(date_range))
        promo_flags = rng.random(len(date_range)) < meta["promo_day_prob"]
        for t, d in enumerate(date_range):
            weekday_factor = 1 + meta["weekly_amplitude"] * np.sin(2 * np.pi * (d.weekday() / 7))
            trend_factor = 1 + meta["trend_per_day"] * t
            promo_factor = 1.6 if promo_flags[t] else 1.0
            mean_demand = meta["base_demand"] * weekday_factor * trend_factor * promo_factor
            noise = rng.normal(0, meta["noise_std_frac"] * meta["base_demand"])
            demand_series[t] = max(0, round(mean_demand + noise))

        for t, d in enumerate(date_range):
            sale_rows.append({
                "company_id": company.id,
                "product_id": product.id,
                "date": d,
                "quantity": float(demand_series[t]),
                "region": meta["warehouse"].region,
                "price": product.unit_price,
                "promotion": int(promo_flags[t]),
            })

        # --- Shipments: periodic replenishment orders from this product's supplier ---
        avg_daily_demand = float(np.mean(demand_series)) or 1.0
        interval = meta["reorder_interval_days"]
        order_days = list(range(0, len(date_range), interval))
        origin, destination, base_distance = CITY_POOL[hash(product.external_product_id) % len(CITY_POOL)]

        deliveries: list[tuple[dt.date, float]] = []  # (arrival_date, quantity)
        for si, order_t in enumerate(order_days):
            order_date = date_range[order_t]
            planned_delivery = order_date + dt.timedelta(days=supplier.lead_time_days)

            delay_prob = float(np.clip(1 - supplier.reliability, 0.02, 0.6))
            distance = base_distance * float(rng.uniform(0.9, 1.1))
            is_delayed = rng.random() < delay_prob
            if is_delayed:
                # longer distance & lower reliability -> longer delays
                delay_days = max(1, int(rng.exponential(2 + distance / 700 + (1 - supplier.reliability) * 6)))
            else:
                delay_days = 0
            actual_delivery = planned_delivery + dt.timedelta(days=delay_days)

            ship_qty = round(avg_daily_demand * interval * float(rng.uniform(1.05, 1.35)))
            shipment_rows.append({
                "company_id": company.id,
                "product_id": product.id,
                "supplier_id": supplier.id,
                "external_shipment_id": f"SHP-{product.external_product_id}-{si+1:04d}",
                "origin": origin,
                "destination": destination,
                "carrier": f"Carrier {(hash(supplier.external_supplier_id) % 4) + 1}",
                "transport_mode": TRANSPORT_MODES[(hash(supplier.external_supplier_id) + si) % len(TRANSPORT_MODES)],
                "distance_km": round(distance, 1),
                "weight_kg": round(ship_qty * float(rng.uniform(0.4, 2.2)), 1),
                "quantity": float(ship_qty),
                "order_date": order_date,
                "planned_delivery": planned_delivery,
                "actual_delivery": actual_delivery if actual_delivery <= date_range[-1] else None,
            })
            if actual_delivery <= date_range[-1]:
                deliveries.append((actual_delivery, ship_qty))

        # --- Simulate daily inventory: deplete with demand, replenish on delivery ---
        deliveries_by_date: dict[dt.date, float] = {}
        for delivery_date, qty in deliveries:
            deliveries_by_date[delivery_date] = deliveries_by_date.get(delivery_date, 0) + qty

        inventory_level = avg_daily_demand * float(rng.uniform(15, 25))  # initial stock buffer
        safety_stock = avg_daily_demand * supplier.lead_time_days * 0.5
        for t, d in enumerate(date_range):
            inventory_level += deliveries_by_date.get(d, 0)
            inventory_level -= demand_series[t]
            inventory_level = max(0.0, inventory_level)
            inventory_rows.append({
                "company_id": company.id,
                "product_id": product.id,
                "warehouse_id": meta["warehouse"].id,
                "date": d,
                "inventory_level": round(inventory_level, 1),
                "safety_stock": round(safety_stock, 1),
            })

    db.bulk_insert_mappings(Sale, sale_rows)
    db.bulk_insert_mappings(Shipment, shipment_rows)
    db.bulk_insert_mappings(InventoryRecord, inventory_rows)
    db.commit()

    return {
        "company_id": company.id,
        "name": company.name,
        "products": len(products),
        "suppliers": len(suppliers),
        "sales_rows": len(sale_rows),
        "shipment_rows": len(shipment_rows),
        "inventory_rows": len(inventory_rows),
        "history_days": config["history_days"],
    }


def generate_demo_companies(db: Session, reset: bool = True) -> list[dict]:
    """Generate all configured demo companies. Idempotent when reset=True."""
    if reset:
        _reset_demo_data(db)
    return [_generate_company(db, cfg) for cfg in COMPANY_CONFIGS]
