import time
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Company, Shipment, Supplier
from app.services.model_training_service import get_active_shipment_models
from app.ml.shipment_delay import predict_shipment_risk
import pandas as pd
from app.routes.shipments import _row_to_single_df
from app.services.inventory_intelligence import company_inventory
from app.services.supplier_intelligence import analyze_suppliers
from app.services.anomaly_detection import detect_anomalies

def profile_shipments(db, company_id):
    print("--- PROFILING SHIPMENTS ---")
    limit = 100
    
    t0 = time.perf_counter()
    classifier, duration_model, clf_entry = get_active_shipment_models(db, company_id)
    t1 = time.perf_counter()
    print(f"Model Load Time: {t1 - t0:.4f}s")
    
    t2 = time.perf_counter()
    shipments = (
        db.query(Shipment)
        .filter(Shipment.company_id == company_id)
        .order_by(Shipment.order_date.desc())
        .limit(limit)
        .all()
    )
    t3 = time.perf_counter()
    print(f"Shipment DB Query Time: {t3 - t2:.4f}s")
    
    print(f"Looping over {len(shipments)} shipments...")
    t4 = time.perf_counter()
    db_query_time = 0
    inference_time = 0
    for shipment in shipments:
        s0 = time.perf_counter()
        supplier = db.query(Supplier).filter(Supplier.id == shipment.supplier_id).first()
        s1 = time.perf_counter()
        db_query_time += (s1 - s0)
        
        row_df = _row_to_single_df(shipment, supplier)
        s2 = time.perf_counter()
        try:
            risk = predict_shipment_risk(classifier, duration_model, row_df)
        except Exception:
            pass
        s3 = time.perf_counter()
        inference_time += (s3 - s2)
        
    t5 = time.perf_counter()
    print(f"Total Loop Time: {t5 - t4:.4f}s")
    print(f"  - Supplier DB N+1 Queries: {db_query_time:.4f}s")
    print(f"  - Prediction/Inference (unbatched): {inference_time:.4f}s")
    

def profile_recommendations(db, company_id):
    print("\n--- PROFILING RECOMMENDATIONS ---")
    
    t0 = time.perf_counter()
    inv = company_inventory(db, company_id)
    t1 = time.perf_counter()
    print(f"company_inventory Time: {t1 - t0:.4f}s")
    
    t2 = time.perf_counter()
    analyze_suppliers(db, company_id)
    t3 = time.perf_counter()
    print(f"analyze_suppliers Time: {t3 - t2:.4f}s")
    
    t4 = time.perf_counter()
    detect_anomalies(db, company_id, 20)
    t5 = time.perf_counter()
    print(f"detect_anomalies Time: {t5 - t4:.4f}s")

if __name__ == "__main__":
    db = SessionLocal()
    # Find a demo company
    company = db.query(Company).filter(Company.is_demo == 1).first()
    if company:
        profile_shipments(db, company.id)
        profile_recommendations(db, company.id)
    else:
        print("No demo company found!")
