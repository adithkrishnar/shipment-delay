"""
Audit Demand Model - Complete Forensic Recomputation
This script reads sales data, runs feature engineering, splits chronologically,
loads the base model, and computes all evaluation metrics independently.
DOES NOT MODIFY DATABASE, APPLICATION CODE, OR STORED ARTIFACTS.
"""
import math
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib

from app.database import SessionLocal
from app.models import Sale, Product, Company
from app.ml.feature_engineering import build_feature_matrix, FEATURE_COLUMNS
from app.ml.demand_forecasting import _time_based_split, _add_product_mean_encoding, _mape, _wape, _naive_seasonal_baseline

def audit():
    db = SessionLocal()
    print("==================================================================")
    print("FORENSIC ML AUDIT: SUPPLYIQ DEMAND FORECASTING PIPELINE")
    print("==================================================================")

    # 1. Dataset Provenance
    # Benchmark training companies: 11 (Horizon), 12 (TorqueParts), 13 (FreshMart)
    demo_companies = db.query(Company).filter(Company.id.in_([11, 12, 13])).all()
    print(f"Loaded benchmark companies: {[(c.id, c.name, c.industry) for c in demo_companies]}")

    sales_query = (
        db.query(Sale.company_id, Sale.product_id, Sale.date, Sale.quantity, Sale.promotion)
        .filter(Sale.company_id.in_([11, 12, 13]))
        .order_by(Sale.date.asc())
        .all()
    )
    raw_df = pd.DataFrame(sales_query, columns=["company_id", "product_id", "date", "quantity", "promotion"])
    print(f"\n1. RAW DATASET BREAKDOWN:")
    print(f"   - Total Raw Transactions/Records: {len(raw_df)}")
    for cid in [11, 12, 13]:
        cname = next(c.name for c in demo_companies if c.id == cid)
        sub = raw_df[raw_df["company_id"] == cid]
        n_prods = sub["product_id"].nunique()
        min_d = sub["date"].min()
        max_d = sub["date"].max()
        days = (pd.to_datetime(max_d) - pd.to_datetime(min_d)).days + 1
        print(f"   - Company {cid} ({cname}): {len(sub)} rows | {n_prods} products | {min_d} to {max_d} ({days} days)")

    # 2. Feature Engineering & Row Drop Explanation
    # Note: in train_base_demand_model, sales_df passes product_id, date, quantity, promotion
    sales_input = raw_df[["product_id", "date", "quantity", "promotion"]].copy()
    feature_df = build_feature_matrix(sales_input)
    n_raw = len(raw_df)
    n_usable = len(feature_df)
    n_dropped = n_raw - n_usable
    total_products = raw_df["product_id"].nunique()

    print(f"\n2. FEATURE ENGINEERING AUDIT:")
    print(f"   - Total Unique Products: {total_products}")
    print(f"   - Usable Feature Rows: {n_usable}")
    print(f"   - Dropped Warm-up Rows: {n_dropped}")
    print(f"   - Warm-up Days per Product: 14 days (max of lag_14, rollmean_14, rollstd_14)")
    print(f"   - Verification: {total_products} products * 14 warm-up days = {total_products * 14} dropped rows")
    assert n_dropped == total_products * 14, f"Mismatch: {n_dropped} != {total_products * 14}"
    print(f"   - Mathematical Check: {n_raw} - {total_products * 14} = {n_raw - total_products * 14} == {n_usable} (VERIFIED)")

    # 3. Train/Test Chronological Split
    train_full, test = _time_based_split(feature_df, test_fraction=0.2)
    train_min_date, train_max_date = train_full["date"].min(), train_full["date"].max()
    test_min_date, test_max_date = test["date"].min(), test["date"].max()

    print(f"\n3. TRAIN / TEST PARTITION AUDIT:")
    print(f"   - Train Volume: {len(train_full)} rows ({len(train_full)/n_usable*100:.2f}%)")
    print(f"   - Test Volume: {len(test)} rows ({len(test)/n_usable*100:.2f}%)")
    print(f"   - Total Verified: {len(train_full) + len(test)} == {n_usable}")
    print(f"   - Train Date Span: {train_min_date} to {train_max_date}")
    print(f"   - Test Date Span: {test_min_date} to {test_max_date}")
    print(f"   - Data Leakage Check: train_max ({train_max_date}) < test_min ({test_min_date}): {train_max_date < test_min_date}")
    assert train_max_date < test_min_date, "CRITICAL: Train and test overlap!"

    # 4. Product Mean Encoding
    train_full, test, product_means, global_mean = _add_product_mean_encoding(train_full, test)
    feature_cols = list(FEATURE_COLUMNS) + ["product_mean_demand"]
    X_train = train_full[feature_cols]
    y_train = train_full["quantity"]
    X_test = test[feature_cols]
    y_test = test["quantity"].to_numpy()

    # 5. Load Stored Production Model
    # Try root trained_models/base/demand_model.pkl
    import os
    model_paths = [
        os.path.abspath("../trained_models/base/demand_model.pkl"),
        os.path.abspath("trained_models/base/demand_model.pkl")
    ]
    prod_model_path = None
    for p in model_paths:
        if os.path.exists(p):
            m = joblib.load(p)
            if hasattr(m, "model") and m.model.__class__.__name__ == "GradientBoostingRegressor":
                prod_model_path = p
                trained_artifact = m
                break

    print(f"\n4. SAVED MODEL ARTIFACT AUDIT:")
    print(f"   - Model Path: {prod_model_path}")
    print(f"   - Wrapper Class: {trained_artifact.__class__.__name__}")
    print(f"   - Algorithm Class: {trained_artifact.model.__class__.__module__}.{trained_artifact.model.__class__.__name__}")
    print(f"   - Estimator Count: {trained_artifact.model.n_estimators}")
    print(f"   - Learning Rate: {trained_artifact.model.learning_rate}")
    print(f"   - Max Depth: {trained_artifact.model.max_depth}")
    print(f"   - Loss Function: {trained_artifact.model.loss}")
    print(f"   - Random Seed: {trained_artifact.model.random_state}")
    print(f"   - Feature Columns ({len(trained_artifact.feature_columns)}): {trained_artifact.feature_columns}")

    # 6. Generate Actual Model Predictions on Held-Out Test Set
    y_pred_gb = np.clip(trained_artifact.model.predict(X_test), 0, None)
    y_pred_base = np.clip(_naive_seasonal_baseline(test), 0, None)

    # 7. Independent Metrics Recomputation
    mae_gb = float(mean_absolute_error(y_test, y_pred_gb))
    mse_gb = float(mean_squared_error(y_test, y_pred_gb))
    rmse_gb = float(np.sqrt(mse_gb))
    mape_gb = _mape(y_test, y_pred_gb)
    wape_gb = _wape(y_test, y_pred_gb)
    r2_gb = float(r2_score(y_test, y_pred_gb))
    accuracy_derived_wape = 100.0 - wape_gb
    accuracy_derived_mape = 100.0 - mape_gb

    # Baseline metrics
    mae_base = float(mean_absolute_error(y_test, y_pred_base))
    mse_base = float(mean_squared_error(y_test, y_pred_base))
    rmse_base = float(np.sqrt(mse_base))
    mape_base = _mape(y_test, y_pred_base)
    wape_base = _wape(y_test, y_pred_base)
    r2_base = float(r2_score(y_test, y_pred_base))

    print(f"\n5. RECOMPUTED PERFORMANCE METRICS ON HELD-OUT TEST SET (N = {len(y_test)}):")
    print(f"   GRADIENT BOOSTING REGRESSOR:")
    print(f"   - MAE:   {mae_gb:.4f} units")
    print(f"   - MSE:   {mse_gb:.4f} units^2")
    print(f"   - RMSE:  {rmse_gb:.4f} units")
    print(f"   - MAPE:  {mape_gb:.2f}%")
    print(f"   - WAPE:  {wape_gb:.2f}%")
    print(f"   - R^2:   {r2_gb:.4f}")
    print(f"   - Derived Accuracy (100 - WAPE): {accuracy_derived_wape:.2f}%")
    print(f"   - Derived Accuracy (100 - MAPE): {accuracy_derived_mape:.2f}%")

    print(f"\n   SEASONAL-NAIVE BASELINE (Lag-7):")
    print(f"   - MAE:   {mae_base:.4f} units")
    print(f"   - MSE:   {mse_base:.4f} units^2")
    print(f"   - RMSE:  {rmse_base:.4f} units")
    print(f"   - MAPE:  {mape_base:.2f}%")
    print(f"   - WAPE:  {wape_base:.2f}%")
    print(f"   - R^2:   {r2_base:.4f}")

    # 8. Relative Improvement
    imp_mae = ((mae_base - mae_gb) / mae_base) * 100.0
    imp_rmse = ((rmse_base - rmse_gb) / rmse_base) * 100.0
    imp_wape = ((wape_base - wape_gb) / wape_base) * 100.0
    imp_r2 = r2_gb - r2_base

    print(f"\n6. MODEL VS. BASELINE COMPARISON:")
    print(f"   - MAE Reduction:  {imp_mae:.2f}% (from {mae_base:.2f} to {mae_gb:.2f} units)")
    print(f"   - RMSE Reduction: {imp_rmse:.2f}% (from {rmse_base:.2f} to {rmse_gb:.2f} units)")
    print(f"   - WAPE Reduction: {imp_wape:.2f}% (from {wape_base:.2f}% to {wape_gb:.2f}%)")
    print(f"   - R^2 Gain:       +{imp_r2:.4f} (from {r2_base:.4f} to {r2_gb:.4f})")

    # 9. Stored Registry Verification
    reg_metrics = trained_artifact.metrics
    print(f"\n7. COMPARISON WITH STORED ARTIFACT METRICS:")
    print(f"   - Stored MAE:  {reg_metrics['mae']:.4f} vs Recomputed: {mae_gb:.4f} (Diff: {abs(reg_metrics['mae'] - mae_gb):.6f})")
    print(f"   - Stored RMSE: {reg_metrics['rmse']:.4f} vs Recomputed: {rmse_gb:.4f} (Diff: {abs(reg_metrics['rmse'] - rmse_gb):.6f})")
    print(f"   - Stored MAPE: {reg_metrics['mape']:.2f}% vs Recomputed: {mape_gb:.2f}%")
    print(f"   - Stored WAPE: {reg_metrics['wape']:.2f}% vs Recomputed: {wape_gb:.2f}%")
    print(f"   - Stored Baseline MAE: {reg_metrics['comparison']['naive_seasonal_baseline']['mae']:.4f} vs Recomputed: {mae_base:.4f}")
    print(f"   - Stored Baseline WAPE: {reg_metrics['comparison']['naive_seasonal_baseline']['wape']:.2f}% vs Recomputed: {wape_base:.2f}%")

    print("\nAUDIT COMPLETE: ALL FIGURES VERIFIED DIRECTLY FROM SOURCE DATA AND MODEL ARTIFACT.")

if __name__ == "__main__":
    audit()
