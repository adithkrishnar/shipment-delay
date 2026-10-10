from __future__ import annotations
import uuid
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy.orm import Session
from app.models import Product, Sale, InventoryRecord, Shipment, Supplier


def detect_anomalies(db: Session, company_id: int, limit: int = 100) -> list[dict]:
    anomalies = []
    
    # 1. Demand / Sales Anomalies
    sales = db.query(Sale).join(Product).filter(Sale.company_id == company_id).all()
    if sales:
        df = pd.DataFrame([{"id": s.id, "product_id": s.product.id, "product_name": s.product.name, "date": s.date, "quantity": s.quantity} for s in sales])
        df["quantity"] = df["quantity"].astype(float)
        
        # Calculate Rolling Mean (Expected)
        df = df.sort_values(by=["product_id", "date"])
        df["expected_value"] = df.groupby("product_id")["quantity"].transform(lambda x: x.rolling(window=7, min_periods=1).mean())
        df["std"] = df.groupby("product_id")["quantity"].transform("std").fillna(1.0)
        
        df["z_score"] = (df["quantity"] - df["expected_value"]) / (df["std"] + 1e-9)
        df["abs_z"] = df["z_score"].abs()
        
        anomalous_sales = df[df["abs_z"] > 2.5]
        for _, row in anomalous_sales.iterrows():
            dev = ((row.quantity - row.expected_value) / max(row.expected_value, 1)) * 100
            score = min(1.0, float(row.abs_z) / 5.0)
            severity = "CRITICAL" if score > 0.8 else "HIGH" if score > 0.6 else "MEDIUM"
            anomalies.append({
                "anomaly_id": str(uuid.uuid4()),
                "category": "Demand",
                "entity_type": "Product",
                "entity_id": int(row.product_id),
                "product": row.product_name,
                "supplier": None,
                "date": str(row.date),
                "metric": "Sales Quantity",
                "observed_value": round(float(row.quantity), 2),
                "expected_value": round(float(row.expected_value), 2),
                "deviation_percent": round(dev, 1),
                "anomaly_score": round(score, 4),
                "severity": severity,
                "reason": "Demand spiked significantly above recent moving average." if dev > 0 else "Demand dropped significantly below recent moving average.",
                "potential_business_impact": "Stockout risk." if dev > 0 else "Excess inventory risk.",
                "recommended_action": "Review inventory allocation." if dev > 0 else "Consider promotions."
            })

    # 2. Inventory Anomalies
    inventory = db.query(InventoryRecord).join(Product).filter(InventoryRecord.company_id == company_id).all()
    if inventory:
        df = pd.DataFrame([{"id": i.id, "product_id": i.product.id, "product_name": i.product.name, "date": i.date, "inventory_level": i.inventory_level, "safety_stock": i.safety_stock} for i in inventory])
        df["inventory_level"] = df["inventory_level"].astype(float)
        df["expected_value"] = df.groupby("product_id")["inventory_level"].transform("median")
        
        # Anomaly if current inventory is far below safety stock OR expected
        for _, row in df.iterrows():
            safety = row.safety_stock if pd.notna(row.safety_stock) and row.safety_stock else row.expected_value * 0.2
            if row.inventory_level < safety:
                dev = ((row.inventory_level - row.expected_value) / max(row.expected_value, 1)) * 100
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "category": "Inventory",
                    "entity_type": "Product",
                    "entity_id": int(row.product_id),
                    "product": row.product_name,
                    "supplier": None,
                    "date": str(row.date),
                    "metric": "Inventory Level",
                    "observed_value": round(float(row.inventory_level), 2),
                    "expected_value": round(float(row.expected_value), 2),
                    "deviation_percent": round(dev, 1),
                    "anomaly_score": 0.85,
                    "severity": "CRITICAL" if row.inventory_level == 0 else "HIGH",
                    "reason": "Inventory is significantly below its historical normal range and safety stock.",
                    "potential_business_impact": "Higher stockout risk.",
                    "recommended_action": "Review replenishment requirement immediately."
                })
            elif row.inventory_level > row.expected_value * 3 and row.expected_value > 0:
                dev = ((row.inventory_level - row.expected_value) / max(row.expected_value, 1)) * 100
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "category": "Inventory",
                    "entity_type": "Product",
                    "entity_id": int(row.product_id),
                    "product": row.product_name,
                    "supplier": None,
                    "date": str(row.date),
                    "metric": "Inventory Level",
                    "observed_value": round(float(row.inventory_level), 2),
                    "expected_value": round(float(row.expected_value), 2),
                    "deviation_percent": round(dev, 1),
                    "anomaly_score": 0.6,
                    "severity": "MEDIUM",
                    "reason": "Inventory is significantly above its historical normal range.",
                    "potential_business_impact": "High holding costs and capital tied up.",
                    "recommended_action": "Pause procurement and analyze demand."
                })
                
    # 3. Shipment Anomalies
    shipments = db.query(Shipment).filter(Shipment.company_id == company_id).all()
    if len(shipments) >= 15:
        df = pd.DataFrame([{"id":s.id, "shipment_id": s.external_shipment_id, "distance":s.distance_km or 0,"weight":s.weight_kg or 0,"quantity":s.quantity or 0,"date":s.actual_delivery or s.planned_delivery} for s in shipments])
        for col in ["distance", "weight", "quantity"]:
            df[col] = df[col].astype(float)
            
        features = df[["distance", "weight", "quantity"]]
        model = IsolationForest(n_estimators=100, contamination=0.05, random_state=None)
        model.fit(features)
        
        df["anomaly_score"] = model.decision_function(features)
        df["is_anomaly"] = model.predict(features)
        
        # Calculate Medians for explanation
        median_dist = df["distance"].median()
        median_weight = df["weight"].median()
        
        anomalous_shipments = df[df["is_anomaly"] == -1]
        
        for _, row in anomalous_shipments.iterrows():
            score = min(1.0, abs(float(row.anomaly_score)) * 2) 
            severity = "CRITICAL" if score > 0.8 else "HIGH" if score > 0.5 else "MEDIUM"
            anomalies.append({
                "anomaly_id": str(uuid.uuid4()),
                "category": "Shipment",
                "entity_type": "Shipment",
                "entity_id": int(row.id),
                "product": None,
                "supplier": None,
                "date": str(row.date) if pd.notna(row.date) else None,
                "metric": "Shipment Profile",
                "observed_value": round(float(row.quantity), 2),
                "expected_value": round(float(df["quantity"].median()), 2),
                "deviation_percent": round(((row.quantity - df["quantity"].median()) / max(df["quantity"].median(), 1)) * 100, 1),
                "anomaly_score": round(score, 4),
                "severity": severity,
                "reason": f"Shipment profile is unusual. Distance {row.distance} vs Expected {median_dist}, Weight {row.weight} vs Expected {median_weight}.",
                "potential_business_impact": "Unexpected logistics costs or delays.",
                "recommended_action": "Investigate routing and loading for this shipment."
            })
            
    # 4. Supplier Anomalies
    suppliers = db.query(Supplier).filter(Supplier.company_id == company_id).all()
    if suppliers:
        df = pd.DataFrame([{"id": s.id, "name": s.name, "reliability": s.reliability, "defect_rate": s.defect_rate} for s in suppliers])
        median_rel = df["reliability"].median() if df["reliability"].notna().any() else 0.95
        median_def = df["defect_rate"].median() if df["defect_rate"].notna().any() else 0.01
        
        for _, row in df.iterrows():
            if pd.notna(row.reliability) and row.reliability < median_rel * 0.8:
                dev = ((row.reliability - median_rel) / max(median_rel, 0.01)) * 100
                anomalies.append({
                    "anomaly_id": str(uuid.uuid4()),
                    "category": "Supplier",
                    "entity_type": "Supplier",
                    "entity_id": int(row.id),
                    "product": None,
                    "supplier": row["name"],
                    "date": None,
                    "metric": "Reliability",
                    "observed_value": round(float(row.reliability), 2),
                    "expected_value": round(float(median_rel), 2),
                    "deviation_percent": round(dev, 1),
                    "anomaly_score": 0.8,
                    "severity": "HIGH",
                    "reason": "Supplier reliability has fallen significantly below company average.",
                    "potential_business_impact": "Production stops due to missing raw materials.",
                    "recommended_action": "Engage alternative suppliers or renegotiate SLAs."
                })
            
    return sorted(anomalies, key=lambda x:x["anomaly_score"], reverse=True)[:limit]
