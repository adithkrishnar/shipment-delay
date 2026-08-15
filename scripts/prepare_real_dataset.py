"""
Real-world Dataset Integration: Olist Brazilian E-Commerce Dataset

Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
License: CC BY-NC-SA 4.0

This script processes the raw Olist CSV files into the schema expected by the
SupplyIQ machine learning pipelines for benchmarking purposes.

Usage:
1. Download the dataset from the Kaggle link above.
2. Extract the archive.
3. Place the following files into the `data/real/raw/` directory:
   - olist_orders_dataset.csv
   - olist_order_items_dataset.csv
   - olist_products_dataset.csv
4. Run this script: `python scripts/prepare_real_dataset.py`

Output:
The script will generate `data/real/processed_shipments.csv` and 
`data/real/processed_sales.csv` which can be loaded for model evaluation.
"""
import os
import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "real"
RAW_DIR = DATA_DIR / "raw"

def process_olist_data():
    orders_path = RAW_DIR / "olist_orders_dataset.csv"
    items_path = RAW_DIR / "olist_order_items_dataset.csv"
    products_path = RAW_DIR / "olist_products_dataset.csv"

    if not all([orders_path.exists(), items_path.exists(), products_path.exists()]):
        print(f"Error: Missing raw Olist dataset files in {RAW_DIR}")
        print("Please download from https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")
        return

    print("Loading raw Olist data...")
    orders = pd.read_csv(orders_path)
    items = pd.read_csv(items_path)
    products = pd.read_csv(products_path)

    # 1. Prepare Shipments Data
    # Target definition: delay_days = order_delivered_customer_date - order_estimated_delivery_date
    print("Processing shipments...")
    shipments = orders[orders['order_status'] == 'delivered'].copy()
    shipments = shipments.dropna(subset=['order_delivered_customer_date', 'order_estimated_delivery_date', 'order_purchase_timestamp'])
    
    shipments_mapped = pd.DataFrame({
        "shipment_id": shipments["order_id"],
        "product_id": "mixed", # Olist orders can have multiple products
        "supplier_id": "mixed",
        "origin": "Olist Warehouse",
        "destination": "Customer",
        "carrier": "Correios", # Defaulting as most are shipped via Brazilian post
        "transport_mode": "road",
        "distance_km": 500.0, # Placeholder, would require geolocation dataset
        "weight_kg": 2.0,
        "quantity": 1.0,
        "order_date": pd.to_datetime(shipments["order_purchase_timestamp"]),
        "planned_delivery": pd.to_datetime(shipments["order_estimated_delivery_date"]),
        "actual_delivery": pd.to_datetime(shipments["order_delivered_customer_date"]),
        "supplier_lead_time_days": 2.0,
        "supplier_reliability": 0.9,
        "supplier_cost_index": 1.0
    })
    
    shipments_out_path = DATA_DIR / "processed_shipments.csv"
    shipments_mapped.to_csv(shipments_out_path, index=False)
    print(f"Saved {len(shipments_mapped)} shipments to {shipments_out_path}")

    # 2. Prepare Demand Data (Sales)
    print("Processing sales demand...")
    sales_merged = items.merge(orders[['order_id', 'order_purchase_timestamp', 'order_status']], on='order_id')
    sales_merged['date'] = pd.to_datetime(sales_merged['order_purchase_timestamp']).dt.date
    
    # Aggregate quantity sold per product per day
    daily_sales = sales_merged.groupby(['product_id', 'date']).size().reset_index(name='quantity')
    
    sales_mapped = pd.DataFrame({
        "product_id": daily_sales["product_id"],
        "date": pd.to_datetime(daily_sales["date"]),
        "quantity": daily_sales["quantity"].astype(float),
        "promotion": 0
    })
    
    sales_out_path = DATA_DIR / "processed_sales.csv"
    sales_mapped.to_csv(sales_out_path, index=False)
    print(f"Saved {len(sales_mapped)} daily sales records to {sales_out_path}")
    print("Done. You can now use these datasets to run the benchmark evaluation.")

if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    process_olist_data()
