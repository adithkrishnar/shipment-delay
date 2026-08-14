from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sqlalchemy.orm import Session
from app.models import Product, Sale, InventoryRecord, Shipment


def detect_anomalies(db: Session, company_id: int, limit: int = 100) -> list[dict]:
    anomalies = []
    # Fast Demand anomalies by product/day (using Z-Score instead of IsolationForest)
    sales = db.query(Sale).filter(Sale.company_id == company_id).all()
    if sales:
        df = pd.DataFrame([{"id": s.id, "product_id": s.product_id, "date": s.date, "quantity": s.quantity} for s in sales])
        
        # Vectorized Z-Score calculation across all products
        df["quantity"] = df["quantity"].astype(float)
        mean = df.groupby("product_id")["quantity"].transform("mean")
        std = df.groupby("product_id")["quantity"].transform("std")
        
        # Add small epsilon to std to prevent division by zero
        df["z_score"] = (df["quantity"] - mean) / (std + 1e-9)
        df["abs_z"] = df["z_score"].abs()
        
        anomalous_sales = df[df["abs_z"] > 3.0]
        for _, row in anomalous_sales.iterrows():
            score = float(row.abs_z) / 10.0 # Normalize roughly to 0-1 range for consistency
            severity = "CRITICAL" if score > 0.4 else "HIGH" if score > 0.35 else "MEDIUM"
            anomalies.append({
                "entity_type": "product", "entity_id": int(row.product_id), "record_id": int(row.id), 
                "date": str(row.date), "metric": "demand", "value": round(float(row.quantity), 2), 
                "score": round(score, 4), "severity": severity, 
                "explanation": "Daily demand is materially different from the product's recent distribution (Z-score > 3)."
            })

    # Fast Shipment anomalies using Z-Score on distance/weight/quantity
    shipments = db.query(Shipment).filter(Shipment.company_id == company_id).all()
    if len(shipments) >= 15:
        df = pd.DataFrame([{"id":s.id,"product_id":s.product_id,"distance":s.distance_km or 0,"weight":s.weight_kg or 0,"quantity":s.quantity or 0,"date":s.order_date} for s in shipments])
        for col in ["distance", "weight", "quantity"]:
            df[col] = df[col].astype(float)
            mean = df[col].mean()
            std = df[col].std() + 1e-9
            df[f"{col}_z"] = ((df[col] - mean) / std).abs()
        
        df["max_z"] = df[["distance_z", "weight_z", "quantity_z"]].max(axis=1)
        anomalous_shipments = df[df["max_z"] > 3.0]
        
        for _, row in anomalous_shipments.iterrows():
            score = float(row.max_z) / 10.0
            severity = "HIGH" if score > 0.35 else "MEDIUM"
            anomalies.append({
                "entity_type": "shipment", "entity_id": int(row.id), "record_id": int(row.id), 
                "date": str(row.date) if pd.notna(row.date) else None, "metric": "shipment_profile", 
                "value": round(float(row.quantity), 2), "score": round(score, 4), "severity": severity, 
                "explanation": "Shipment profile is unusual relative to this company's average (Z-score > 3)."
            })
            
    return sorted(anomalies, key=lambda x:x["score"], reverse=True)[:limit]
