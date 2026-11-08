"""
Import DataCo Global Supply Chain dataset into SupplyIQ as a dedicated company.
Loads real products, pricing, daily sales demand, warehouses, suppliers, and shipments,
and trains a personalized demand-forecasting model.
"""
import os
import sys
from datetime import date, datetime, timedelta
import numpy as np
import pandas as pd

# Set paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.join(SCRIPT_DIR, "..")
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
DATASET_PATH = os.path.join(PROJECT_ROOT, "data", "raw", "dataco", "DataCoSupplyChainDataset.csv")

sys.path.insert(0, BACKEND_DIR)

from app.database import SessionLocal
from app.auth.security import get_password_hash
from app.models import (
    Company, User, Product, Warehouse, Supplier,
    InventoryRecord, Sale, Shipment, ModelRegistryEntry
)
from app.services.model_training_service import train_company_demand_model


def import_dataco():
    print(f"Loading DataCo dataset from {DATASET_PATH}...")
    if not os.path.exists(DATASET_PATH):
        print(f"Error: Dataset file not found at {DATASET_PATH}")
        return

    df = pd.read_csv(DATASET_PATH, encoding="latin1")
    print(f"Loaded {len(df):,} rows from DataCo dataset.")

    db = SessionLocal()
    try:
        # 1. Company
        company_name = "DataCo Global Supply Chain"
        existing_company = db.query(Company).filter(Company.name == company_name).first()
        if existing_company:
            print(f"Found existing company ID {existing_company.id}. Cleaning previous records...")
            cid = existing_company.id
            db.query(Shipment).filter(Shipment.company_id == cid).delete()
            db.query(InventoryRecord).filter(InventoryRecord.company_id == cid).delete()
            db.query(Sale).filter(Sale.company_id == cid).delete()
            db.query(Supplier).filter(Supplier.company_id == cid).delete()
            db.query(Product).filter(Product.company_id == cid).delete()
            db.query(Warehouse).filter(Warehouse.company_id == cid).delete()
            db.query(User).filter(User.company_id == cid).delete()
            db.query(ModelRegistryEntry).filter(ModelRegistryEntry.company_id == cid).delete()
            db.query(Company).filter(Company.id == cid).delete()
            db.commit()

        company = Company(
            name=company_name,
            industry="Omnichannel Retail & Logistics",
            is_demo=0,
            default_currency="USD",
            notes="Real-world multi-market commercial dataset imported from DataCo Global Supply Chain.",
        )
        db.add(company)
        db.flush()
        print(f"Created company '{company.name}' with ID={company.id}")

        # 2. Admin User
        user = User(
            email="admin@dataco.com",
            hashed_password=get_password_hash("password"),
            is_active=True,
            is_superuser=True,
            company_id=company.id,
        )
        db.add(user)
        db.flush()
        print(f"Created admin user: {user.email} / password")

        # 3. Warehouses mapped to DataCo Markets
        markets = ["Pacific Asia", "USCA", "Europe", "LATAM", "Africa"]
        warehouse_map = {}
        for m in markets:
            wh = Warehouse(
                company_id=company.id,
                name=f"DataCo {m} DC",
                region=m,
            )
            db.add(wh)
            db.flush()
            warehouse_map[m] = wh
        print(f"Created {len(warehouse_map)} regional distribution centers.")

        # 4. Suppliers mapped to Shipping Modes
        shipping_modes = df["Shipping Mode"].unique().tolist()
        supplier_map = {}
        for idx, sm in enumerate(shipping_modes):
            mode_sub = df[df["Shipping Mode"] == sm]
            avg_lead = float(mode_sub["Days for shipping (real)"].mean()) or 4.0
            late_rate = float(mode_sub["Late_delivery_risk"].mean()) or 0.2
            reliability = round(max(0.60, min(0.98, 1.0 - late_rate)), 3)

            supplier = Supplier(
                company_id=company.id,
                external_supplier_id=f"SUP-DC-{idx+1:02d}",
                name=f"{sm} Fleet Logistics",
                lead_time_days=round(avg_lead, 1),
                reliability=reliability,
                cost_index=round(1.0 + (5.0 - avg_lead) * 0.05, 3),
                defect_rate=0.015,
            )
            db.add(supplier)
            db.flush()
            supplier_map[sm] = supplier
        print(f"Created {len(supplier_map)} shipping fleet suppliers.")

        # 5. Products (Top 15 most frequent in DataCo)
        top_product_names = df["Product Name"].value_counts().head(15).index.tolist()
        product_map = {}
        for idx, pname in enumerate(top_product_names):
            p_sub = df[df["Product Name"] == pname].iloc[0]
            price = float(p_sub["Product Price"])
            category = str(p_sub["Category Name"])
            # Estimate realistic unit cost ~68% of selling price
            unit_cost = round(price * 0.68, 2)

            prod = Product(
                company_id=company.id,
                external_product_id=f"DC-SKU-{idx+1:04d}",
                name=pname,
                category=category,
                unit_cost=unit_cost,
                unit_price=price,
            )
            db.add(prod)
            db.flush()
            product_map[pname] = prod
        print(f"Created {len(product_map)} DataCo SKUs.")

        # 6. Dates calculation: shift DataCo timeline so max date aligns with yesterday
        df_sub = df[df["Product Name"].isin(top_product_names)].copy()
        df_sub["order_dt"] = pd.to_datetime(df_sub["order date (DateOrders)"])
        max_dt = df_sub["order_dt"].max()
        target_max_date = date.today() - timedelta(days=1)
        raw_diff_days = (target_max_date - max_dt.date()).days
        # Align to full weekly multiple (7 days) to preserve exact Monday-Sunday patterns
        shift_days = (raw_diff_days // 7) * 7
        shift_delta = timedelta(days=shift_days)
        print(f"Aligning timeline: Original max={max_dt.date()}, Target max={target_max_date}, Shift={shift_days} days.")

        df_sub["shifted_date"] = df_sub["order_dt"].apply(lambda d: d.date() + shift_delta)

        # 7. Aggregate Sales daily per product and warehouse region
        print("Aggregating daily sales...")
        agg_sales = (
            df_sub.groupby(["Product Name", "shifted_date", "Market"])
            .agg(
                quantity=("Order Item Quantity", "sum"),
                price=("Product Price", "mean"),
            )
            .reset_index()
        )

        sales_records = []
        for _, row in agg_sales.iterrows():
            prod = product_map.get(row["Product Name"])
            wh = warehouse_map.get(row["Market"])
            if not prod or not wh:
                continue
            sales_records.append({
                "company_id": company.id,
                "product_id": prod.id,
                "date": row["shifted_date"],
                "quantity": float(row["quantity"]),
                "region": wh.region,
                "price": float(row["price"]),
                "promotion": 0,
            })

        print(f"Inserting {len(sales_records):,} daily sales rows...")
        db.bulk_insert_mappings(Sale, sales_records)
        db.commit()

        # 8. Inbound Shipments / Purchase Orders (last 60 days + future scheduled)
        print("Generating realistic shipments from DataCo orders...")
        recent_cutoff = target_max_date - timedelta(days=60)
        recent_orders = df_sub[df_sub["shifted_date"] >= recent_cutoff].sample(min(300, len(df_sub)), random_state=42)

        shipment_records = []
        ship_counter = 1
        for _, row in recent_orders.iterrows():
            prod = product_map.get(row["Product Name"])
            supp = supplier_map.get(row["Shipping Mode"], list(supplier_map.values())[0])
            wh = warehouse_map.get(row["Market"], list(warehouse_map.values())[0])
            if not prod:
                continue

            order_date = row["shifted_date"]
            sched_days = int(row.get("Days for shipment (scheduled)", 4))
            real_days = int(row.get("Days for shipping (real)", 4))
            planned_date = order_date + timedelta(days=sched_days)
            actual_date = order_date + timedelta(days=real_days)

            # If actual arrival is in the future, mark as in-transit / open PO
            is_delivered = actual_date <= target_max_date
            qty = float(row["Order Item Quantity"]) * float(np.random.randint(15, 45))

            shipment_records.append({
                "company_id": company.id,
                "product_id": prod.id,
                "supplier_id": supp.id,
                "external_shipment_id": f"DC-PO-{ship_counter:05d}",
                "origin": f"Vendor Port ({supp.name.split()[0]})",
                "destination": wh.name,
                "carrier": supp.name,
                "transport_mode": "road" if "Standard" in supp.name else "air" if "First" in supp.name else "express",
                "distance_km": round(float(np.random.uniform(350, 1800)), 1),
                "weight_kg": round(qty * 0.85, 1),
                "quantity": qty,
                "order_date": order_date,
                "planned_delivery": planned_date,
                "actual_delivery": actual_date if is_delivered else None,
            })
            ship_counter += 1

        print(f"Inserting {len(shipment_records)} shipments (including open purchase orders)...")
        db.bulk_insert_mappings(Shipment, shipment_records)
        db.commit()

        # 9. Current Inventory Snapshot across warehouses
        print("Setting current inventory snapshot for all warehouses...")
        inventory_records = []
        today_date = date.today()

        for p_idx, (pname, prod) in enumerate(product_map.items()):
            # Calculate average daily sales for this product
            p_sales = [s["quantity"] for s in sales_records if s["product_id"] == prod.id]
            avg_daily = float(np.mean(p_sales)) if p_sales else 10.0
            safety_stock = round(avg_daily * 4.5, 1)

            for w_idx, (m, wh) in enumerate(warehouse_map.items()):
                # Create a diverse, realistic distribution:
                # - Warehouse 0 has healthy surplus (> 80)
                # - Warehouse 1 has low stock (< 25) to trigger transfer recommendation
                # - Other warehouses have balanced stock
                if w_idx == 0:
                    stock_level = round(avg_daily * 12.0 + 95.0, 1)
                elif w_idx == 1 and p_idx % 2 == 0:
                    stock_level = round(18.0, 1)  # Deficit to test transfer to WH 1
                else:
                    stock_level = round(avg_daily * 6.0 + 35.0, 1)

                inventory_records.append({
                    "company_id": company.id,
                    "product_id": prod.id,
                    "warehouse_id": wh.id,
                    "date": today_date,
                    "inventory_level": stock_level,
                    "safety_stock": safety_stock,
                })

        print(f"Inserting {len(inventory_records)} current inventory snapshot records...")
        db.bulk_insert_mappings(InventoryRecord, inventory_records)
        db.commit()

        # 10. Train Personalized Demand Forecasting Model
        print(f"Training personalized demand forecasting model for {company.name}...")
        entry, reason = train_company_demand_model(db, company.id)
        if entry:
            print(f"Successfully trained and registered model! ID={entry.id}, Status={entry.status}")
            print(f"Model Metrics: {entry.metrics_json}")
        else:
            print(f"Model training note: {reason}")

        print("\n" + "="*60)
        print("DataCo Global Supply Chain Successfully Imported!")
        print("="*60)
        print(f"Company ID: {company.id}")
        print(f"Company Name: {company.name}")
        print(f"Login Email: admin@dataco.com")
        print(f"Password: password")
        print(f"Total Products: {len(product_map)}")
        print(f"Total Warehouses: {len(warehouse_map)}")
        print(f"Total Daily Sales Rows: {len(sales_records):,}")
        print(f"Total Shipments / POs: {len(shipment_records)}")
        print(f"Total Inventory Records: {len(inventory_records)}")
        print("="*60)

    except Exception as e:
        db.rollback()
        print(f"Error during import: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    import_dataco()
