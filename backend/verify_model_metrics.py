import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.config import settings
from app.database import SessionLocal
from app.models import ModelRegistryEntry
from app.services.model_training_service import _sales_dataframe
from app.ml.demand_forecasting import (
    build_feature_matrix,
    _time_based_split,
    _add_product_mean_encoding,
    _naive_seasonal_baseline,
    _mape,
    _wape,
    FEATURE_COLUMNS,
)

def run_verification():
    db = SessionLocal()
    from app.models import Sale
    rows = db.query(Sale).filter(Sale.company_id.in_([11, 12, 13])).all()
    print(f"Total raw benchmark sales rows in DB: {len(rows)}")

    sales_df = pd.DataFrame([{
        "date": pd.to_datetime(r.date),
        "product_id": int(r.product_id),
        "quantity": float(r.quantity),
        "promotion": int(r.promotion or 0),
    } for r in rows])

    # Check date range of pooled sales
    min_date = sales_df["date"].min()
    max_date = sales_df["date"].max()
    print(f"Sales date span: {min_date} to {max_date}")

    feature_df = build_feature_matrix(sales_df)
    print(f"Feature matrix usable rows (after lag burn-in): {len(feature_df)}")

    train_full, test = _time_based_split(feature_df)
    train_max = train_full["date"].max()
    test_min = test["date"].min()
    print(f"Train date span: {train_full['date'].min()} to {train_max} (count={len(train_full)})")
    print(f"Test date span: {test_min} to {test['date'].max()} (count={len(test)})")
    
    assert train_max < test_min, f"Data leakage error: train_max {train_max} >= test_min {test_min}"
    print("Verification: ZERO OVERLAP between train and test datasets. Time-series split verified.")

    model_path = settings.TRAINED_MODELS_DIR / "base" / "demand_model.pkl"
    assert model_path.exists(), f"Model artifact not found at {model_path}"
    trained = joblib.load(model_path)
    print(f"Loaded model artifact from {model_path}, model_name={trained.model_name}")

    # Re-apply mean encoding derived from train_full as done during training
    train_full_enc, test_enc, _, _ = _add_product_mean_encoding(train_full, test)
    feature_cols = list(FEATURE_COLUMNS) + ["product_mean_demand"]
    X_test = test_enc[feature_cols]
    y_test = test_enc["quantity"].to_numpy()

    final_pred = np.clip(trained.model.predict(X_test), 0, None)
    model_mae = float(mean_absolute_error(y_test, final_pred))
    model_rmse = float(np.sqrt(mean_squared_error(y_test, final_pred)))
    model_mape = _mape(y_test, final_pred)
    model_wape = _wape(y_test, final_pred)

    baseline_pred = np.clip(_naive_seasonal_baseline(test), 0, None)
    base_mae = float(mean_absolute_error(y_test, baseline_pred))
    base_rmse = float(np.sqrt(mean_squared_error(y_test, baseline_pred)))
    base_mape = _mape(y_test, baseline_pred)
    base_wape = _wape(y_test, baseline_pred)

    print("\n================ RECOMPUTED METRICS FROM HELD-OUT TEST DATA ================")
    print(f"Model ({trained.model_name}):")
    print(f"  MAE  = {model_mae:.4f} units")
    print(f"  RMSE = {model_rmse:.4f}")
    print(f"  MAPE = {model_mape:.2f}%")
    print(f"  WAPE = {model_wape:.2f}%")
    print(f"Naive Seasonal Baseline (Lag-7):")
    print(f"  MAE  = {base_mae:.4f} units")
    print(f"  RMSE = {base_rmse:.4f}")
    print(f"  MAPE = {base_mape:.2f}%")
    print(f"  WAPE = {base_wape:.2f}%")

    e = db.query(ModelRegistryEntry).filter(
        ModelRegistryEntry.company_id.is_(None),
        ModelRegistryEntry.model_type == "demand_forecast",
    ).first()
    db_metrics = json.loads(e.metrics_json)

    print("\n================ DATABASE STORED METRICS ================")
    print(f"DB Model ({db_metrics.get('selected_model')}):")
    print(f"  MAE  = {db_metrics.get('mae'):.4f} units")
    print(f"  RMSE = {db_metrics.get('rmse'):.4f}")
    print(f"  MAPE = {db_metrics.get('mape'):.2f}%")
    print(f"  WAPE = {db_metrics.get('wape'):.2f}%")

    # Match check within 0.1 delta tolerance
    assert abs(model_mae - db_metrics["mae"]) < 0.1, f"MAE deviation {abs(model_mae - db_metrics['mae'])} > 0.1"
    assert abs(model_rmse - db_metrics["rmse"]) < 0.1, f"RMSE deviation {abs(model_rmse - db_metrics['rmse'])} > 0.1"
    assert abs(model_mape - db_metrics["mape"]) < 0.1, f"MAPE deviation {abs(model_mape - db_metrics['mape'])} > 0.1"
    assert abs(model_wape - db_metrics["wape"]) < 0.1, f"WAPE deviation {abs(model_wape - db_metrics['wape'])} > 0.1"
    print("\n[PASS] Recomputed evaluation metrics verified against model artifact and database records!")

if __name__ == "__main__":
    run_verification()
