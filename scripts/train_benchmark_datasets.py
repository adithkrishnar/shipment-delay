"""
Train Benchmark Models from Raw Datasets in data/raw/
- UCI Online Retail II (Demand Forecasting)
- BTS Air Flight Delay Reporting (Air Cargo / Aviation Delay Classification & Duration)
- BTS Road Freight Corridor Delay (Highway Transit Delay & Duration)
- Multimodal Logistics Congestion (NOAA Maritime AIS Port Congestion & Rail Transport)
"""
import os
import sys
import json
import zipfile
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score, recall_score,
    roc_auc_score, mean_absolute_error, mean_squared_error, r2_score
)
from sklearn.preprocessing import OrdinalEncoder

warnings.filterwarnings("ignore")

# Define base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
GEN_DIR = DATA_DIR / "generated"
MODELS_DIR = BASE_DIR / "trained_models"

GEN_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)


# =====================================================================
# 1. UCI Online Retail II - Demand Forecasting
# =====================================================================
def train_uci_demand_model(force=False):
    print("\n=======================================================")
    print(" 1. Training UCI Online Retail II Demand Forecasting Model")
    print("=======================================================")
    zip_path = RAW_DIR / "uci_demand" / "online+retail+ii.zip"
    if not zip_path.exists():
        print(f"Skipping UCI Demand: {zip_path} not found.")
        return None

    out_model_dir = MODELS_DIR / "uci_demand"
    out_model_dir.mkdir(parents=True, exist_ok=True)

    if not force and (out_model_dir / "demand_forecaster.pkl").exists() and (GEN_DIR / "uci_demand_metrics.json").exists():
        print(f"UCI Demand Model already trained. Loading cached metrics from {GEN_DIR / 'uci_demand_metrics.json'}...")
        with open(GEN_DIR / "uci_demand_metrics.json") as f:
            return json.load(f)

    import io
    print("Extracting and reading online_retail_II.xlsx...")
    with zipfile.ZipFile(zip_path) as z:
        excel_bytes = io.BytesIO(z.read("online_retail_II.xlsx"))
        df_sheet1 = pd.read_excel(excel_bytes, sheet_name="Year 2009-2010", engine="openpyxl")
        df_sheet2 = pd.read_excel(excel_bytes, sheet_name="Year 2010-2011", engine="openpyxl")

    df_raw = pd.concat([df_sheet1, df_sheet2], ignore_index=True)
    print(f"Loaded {len(df_raw):,} raw transaction records.")

    # Data cleaning: remove cancellations and non-positive quantities
    df = df_raw.dropna(subset=["InvoiceDate", "Quantity"]).copy()
    df = df[df["Quantity"] > 0]
    df["date"] = pd.to_datetime(df["InvoiceDate"]).dt.date
    
    # Aggregate daily demand
    daily_demand = df.groupby("date")["Quantity"].sum().reset_index()
    daily_demand.columns = ["date", "demand"]
    daily_demand["date"] = pd.to_datetime(daily_demand["date"])
    
    # Resample daily to ensure continuous timeline (fill 0 for quiet days)
    daily_demand = daily_demand.set_index("date").resample("D").sum().reset_index()
    daily_demand["demand"] = daily_demand["demand"].fillna(0)
    print(f"Aggregated into {len(daily_demand)} daily continuous records ({daily_demand['date'].min().date()} to {daily_demand['date'].max().date()}).")

    # Feature Engineering (leakage-safe)
    daily_demand["year"] = daily_demand["date"].dt.year
    daily_demand["month"] = daily_demand["date"].dt.month
    daily_demand["day"] = daily_demand["date"].dt.day
    daily_demand["dayofweek"] = daily_demand["date"].dt.dayofweek
    daily_demand["is_weekend"] = daily_demand["dayofweek"].isin([5, 6]).astype(int)

    # Lags
    for lag in [1, 7, 14, 28]:
        daily_demand[f"lag_{lag}"] = daily_demand["demand"].shift(lag)

    # Trailing rolling statistics (shifted by 1 day so today is never in its own window)
    daily_demand["rolling_mean_7"] = daily_demand["demand"].shift(1).rolling(7).mean()
    daily_demand["rolling_std_7"] = daily_demand["demand"].shift(1).rolling(7).std().fillna(0)
    daily_demand["rolling_mean_14"] = daily_demand["demand"].shift(1).rolling(14).mean()
    daily_demand["rolling_mean_28"] = daily_demand["demand"].shift(1).rolling(28).mean()

    # Drop warm-up window
    daily_clean = daily_demand.dropna().reset_index(drop=True)
    
    features = [
        "year", "month", "day", "dayofweek", "is_weekend",
        "lag_1", "lag_7", "lag_14", "lag_28",
        "rolling_mean_7", "rolling_std_7", "rolling_mean_14", "rolling_mean_28"
    ]
    target = "demand"

    # Time-based split (80% train, 20% test)
    split_idx = int(len(daily_clean) * 0.80)
    X_train = daily_clean.loc[:split_idx, features]
    y_train = daily_clean.loc[:split_idx, target]
    X_test = daily_clean.loc[split_idx + 1:, features]
    y_test = daily_clean.loc[split_idx + 1:, target]

    print(f"Training set: {len(X_train)} days, Test set: {len(X_test)} days.")

    # Train LightGBM Regressor
    model = LGBMRegressor(
        n_estimators=150,
        learning_rate=0.05,
        max_depth=5,
        random_state=42
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    preds = np.clip(preds, 0, None)  # Demand cannot be negative

    # Naive baseline: same day last week
    baseline_preds = X_test["lag_7"].values

    mae = float(mean_absolute_error(y_test, preds))
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    r2 = float(r2_score(y_test, preds))
    wape = float(np.sum(np.abs(y_test - preds)) / np.sum(y_test)) if np.sum(y_test) > 0 else 0.0

    base_mae = float(mean_absolute_error(y_test, baseline_preds))
    base_rmse = float(np.sqrt(mean_squared_error(y_test, baseline_preds)))

    print(f"Model Performance:")
    print(f"  MAE: {mae:.2f} (Baseline Naive MAE: {base_mae:.2f})")
    print(f"  RMSE: {rmse:.2f} (Baseline Naive RMSE: {base_rmse:.2f})")
    print(f"  WAPE: {wape:.2%}")
    print(f"  R2 Score: {r2:.4f}")

    # Feature importances
    importances = dict(zip(features, [float(x) for x in model.feature_importances_]))

    model_artifact = {
        "model": model,
        "features": features,
        "metrics": {
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "wape": wape,
            "baseline_mae": base_mae,
            "baseline_rmse": base_rmse,
            "total_raw_records": len(df_raw),
            "clean_days": len(daily_clean)
        },
        "feature_importances": importances
    }

    joblib.dump(model_artifact, out_model_dir / "demand_forecaster.pkl")
    with open(GEN_DIR / "uci_demand_metrics.json", "w") as f:
        json.dump(model_artifact["metrics"], f, indent=2)

    print(f"Saved UCI Demand Model to {out_model_dir / 'demand_forecaster.pkl'}")
    return model_artifact["metrics"]


# =====================================================================
# 2. BTS Air Cargo / Flight Delay Classification & Duration
# =====================================================================
def train_bts_air_models(force=False):
    print("\n=======================================================")
    print(" 2. Training BTS Air Delay Classifier & Duration Regressor")
    print("=======================================================")
    zip_path = RAW_DIR / "bts_air" / "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_2024_12.zip"
    if not zip_path.exists():
        print(f"Skipping BTS Air: {zip_path} not found.")
        return None

    out_model_dir = MODELS_DIR / "bts_air"
    out_model_dir.mkdir(parents=True, exist_ok=True)

    if not force and (out_model_dir / "air_delay_classifier.pkl").exists() and (GEN_DIR / "bts_air_metrics.json").exists():
        print(f"BTS Air Models already trained. Loading cached metrics from {GEN_DIR / 'bts_air_metrics.json'}...")
        with open(GEN_DIR / "bts_air_metrics.json") as f:
            return json.load(f)

    print("Extracting and reading BTS Air flight records...")
    usecols = [
        "FlightDate", "Reporting_Airline", "Origin", "Dest",
        "Distance", "CRSDepTime", "CRSArrTime", "DayOfWeek", "Month",
        "ArrDel15", "ArrDelayMinutes", "Cancelled", "Diverted"
    ]

    with zipfile.ZipFile(zip_path) as z:
        csv_name = [n for n in z.namelist() if n.endswith('.csv')][0]
        df = pd.read_csv(z.open(csv_name), usecols=usecols)

    print(f"Loaded {len(df):,} total flight records.")

    # Filter out cancelled or diverted flights for delay analysis
    df = df[(df["Cancelled"] == 0) & (df["Diverted"] == 0)].dropna(subset=["ArrDel15", "Distance"]).copy()
    df["FlightDate"] = pd.to_datetime(df["FlightDate"])
    df = df.sort_values("FlightDate").reset_index(drop=True)

    # Feature engineering
    df["DepHour"] = (df["CRSDepTime"] // 100).astype(int)
    df["ArrHour"] = (df["CRSArrTime"] // 100).astype(int)

    cat_cols = ["Reporting_Airline", "Origin", "Dest"]
    num_cols = ["Distance", "DepHour", "ArrHour", "DayOfWeek", "Month"]

    for col in cat_cols:
        df[col] = df[col].astype(str)

    # Ordinal encode categorical columns
    encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    df_cat_encoded = pd.DataFrame(
        encoder.fit_transform(df[cat_cols]),
        columns=cat_cols,
        index=df.index
    )

    features = cat_cols + num_cols
    X = pd.concat([df_cat_encoded, df[num_cols]], axis=1)
    y_clf = df["ArrDel15"].astype(int)

    # Time-based split (80/20)
    split_idx = int(len(df) * 0.80)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train_clf, y_test_clf = y_clf.iloc[:split_idx], y_clf.iloc[split_idx:]

    print(f"Training Air Delay Classifier on {len(X_train):,} rows, testing on {len(X_test):,} rows...")
    print(f"Delay Class distribution (Train): {y_train_clf.value_counts(normalize=True).to_dict()}")

    clf = LGBMClassifier(
        n_estimators=120,
        learning_rate=0.08,
        class_weight="balanced",
        random_state=42
    )
    clf.fit(X_train, y_train_clf)

    preds_clf = clf.predict(X_test)
    probs_clf = clf.predict_proba(X_test)[:, 1]

    roc_auc = float(roc_auc_score(y_test_clf, probs_clf))
    f1 = float(f1_score(y_test_clf, preds_clf))
    precision = float(precision_score(y_test_clf, preds_clf))
    recall = float(recall_score(y_test_clf, preds_clf))
    acc = float(accuracy_score(y_test_clf, preds_clf))

    print(f"Classifier Performance:")
    print(f"  ROC-AUC: {roc_auc:.4f}")
    print(f"  F1-Score: {f1:.4f}")
    print(f"  Precision: {precision:.4f}")
    print(f"  Recall: {recall:.4f}")
    print(f"  Accuracy: {acc:.4f}")

    # Delay Duration Regressor (conditioned on delayed flights)
    delayed_mask = (df["ArrDel15"] == 1) & (df["ArrDelayMinutes"] > 0)
    df_delayed = df[delayed_mask]
    X_reg = X.loc[df_delayed.index]
    y_reg = df_delayed["ArrDelayMinutes"]

    reg_split = int(len(X_reg) * 0.80)
    X_train_reg, X_test_reg = X_reg.iloc[:reg_split], X_reg.iloc[reg_split:]
    y_train_reg, y_test_reg = y_reg.iloc[:reg_split], y_reg.iloc[reg_split:]

    print(f"\nTraining Air Delay Duration Regressor on {len(X_train_reg):,} delayed records...")
    reg = LGBMRegressor(
        n_estimators=100,
        learning_rate=0.08,
        random_state=42
    )
    reg.fit(X_train_reg, y_train_reg)

    preds_reg = reg.predict(X_test_reg)
    preds_reg = np.clip(preds_reg, 0, None)

    mae_reg = float(mean_absolute_error(y_test_reg, preds_reg))
    rmse_reg = float(np.sqrt(mean_squared_error(y_test_reg, preds_reg)))
    print(f"Duration Regressor Performance:")
    print(f"  MAE: {mae_reg:.2f} minutes")
    print(f"  RMSE: {rmse_reg:.2f} minutes")

    metrics = {
        "classifier": {
            "roc_auc": roc_auc,
            "f1_score": f1,
            "precision": precision,
            "recall": recall,
            "accuracy": acc
        },
        "duration_regressor": {
            "mae_minutes": mae_reg,
            "rmse_minutes": rmse_reg
        },
        "sample_counts": {
            "total_flights": len(df),
            "delayed_flights": len(df_delayed)
        }
    }

    # Save artifacts
    joblib.dump({"model": clf, "encoder": encoder, "features": features}, out_model_dir / "air_delay_classifier.pkl")
    joblib.dump({"model": reg, "encoder": encoder, "features": features}, out_model_dir / "air_delay_regressor.pkl")
    with open(GEN_DIR / "bts_air_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Saved BTS Air Models to {out_model_dir}")
    return metrics


# =====================================================================
# 3. BTS Road Freight Corridor Transit Delay Model
# =====================================================================
def train_bts_road_model():
    print("\n=======================================================")
    print(" 3. Training BTS Road Freight Delay & Duration Model")
    print("=======================================================")
    csv_path = RAW_DIR / "bts_road" / "export.csv"
    if not csv_path.exists():
        print(f"Skipping BTS Road: {csv_path} not found.")
        return None

    out_model_dir = MODELS_DIR / "bts_road"
    out_model_dir.mkdir(parents=True, exist_ok=True)

    print("Loading BTS Road corridor data...")
    # Load 150,000 sample rows for efficiency and speed while maintaining full statistical power
    df = pd.read_csv(csv_path, nrows=150000)
    print(f"Loaded {len(df):,} road corridor movement observations.")

    # Clean numeric fields (strip commas if any)
    for col in ["25th Percentile (minutes)", "50th Percentile (minutes)", "75th Percentile (minutes)"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(",", "", regex=False)
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["50th Percentile (minutes)", "75th Percentile (minutes)"]).copy()
    df = df[df["50th Percentile (minutes)"] > 0]

    # Target: 75th percentile transit duration (congestion duration in hours)
    # Feature: corridor delay factor = (75th - 25th) / 50th percentile (variability)
    df["delay_variability"] = (df["75th Percentile (minutes)"] - df["25th Percentile (minutes)"]) / df["50th Percentile (minutes)"]
    df["transit_duration_hours"] = df["75th Percentile (minutes)"] / 60.0

    cat_cols = ["Origin State", "Destination State", "Movements"]
    num_cols = ["delay_variability"]

    for c in cat_cols:
        df[c] = df[c].fillna("Unknown").astype(str)

    encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    df_cat_enc = pd.DataFrame(
        encoder.fit_transform(df[cat_cols]),
        columns=cat_cols,
        index=df.index
    )

    features = cat_cols + num_cols
    X = pd.concat([df_cat_enc, df[num_cols]], axis=1)
    y = df["transit_duration_hours"]

    # Corridor train/test split
    split_idx = int(len(X) * 0.80)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    print(f"Training Road Transit Regressor on {len(X_train):,} corridors...")
    reg = LGBMRegressor(n_estimators=100, learning_rate=0.08, random_state=42)
    reg.fit(X_train, y_train)

    preds = reg.predict(X_test)
    preds = np.clip(preds, 0, None)

    mae = float(mean_absolute_error(y_test, preds))
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    r2 = float(r2_score(y_test, preds))

    print(f"Road Transit Model Performance:")
    print(f"  MAE: {mae:.2f} hours")
    print(f"  RMSE: {rmse:.2f} hours")
    print(f"  R2 Score: {r2:.4f}")

    metrics = {
        "mae_hours": mae,
        "rmse_hours": rmse,
        "r2_score": r2,
        "observations_evaluated": len(df)
    }

    joblib.dump({"model": reg, "encoder": encoder, "features": features}, out_model_dir / "road_transit_regressor.pkl")
    with open(GEN_DIR / "bts_road_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Saved BTS Road Model to {out_model_dir}")
    return metrics


# =====================================================================
# 4. Multimodal Congestion Risk Model (Maritime AIS + Rail Freight)
# =====================================================================
def train_multimodal_model():
    print("\n=======================================================")
    print(" 4. Training Multimodal Disruption & Congestion Model")
    print("=======================================================")
    maritime_file = GEN_DIR / "maritime_congestion.csv"
    rail_file = GEN_DIR / "rail_congestion.csv"

    if not maritime_file.exists() or not rail_file.exists():
        print("Running external data pipeline to ensure maritime & rail congestion series exist...")
        from app.ml.external_data_pipeline import process_maritime_data, process_rail_data
        process_maritime_data()
        process_rail_data()

    out_model_dir = MODELS_DIR / "multimodal"
    out_model_dir.mkdir(parents=True, exist_ok=True)

    df_maritime = pd.read_csv(maritime_file)
    df_rail = pd.read_csv(rail_file)

    print(f"Maritime congestion data: {len(df_maritime)} records.")
    print(f"Rail congestion data: {len(df_rail)} records.")

    # Train a maritime congestion forecasting model
    df_mar = df_maritime.copy()
    df_mar["date"] = pd.to_datetime(df_mar["date"])
    df_mar = df_mar.sort_values("date").reset_index(drop=True)

    for lag in [1, 2, 3]:
        df_mar[f"port_lag_{lag}"] = df_mar["port_congestion_index"].shift(lag)

    df_mar_clean = df_mar.dropna().reset_index(drop=True)
    if len(df_mar_clean) > 0:
        mar_features = [f"port_lag_{lag}" for lag in [1, 2, 3]]
        mar_model = LGBMRegressor(n_estimators=50, random_state=42)
        mar_model.fit(df_mar_clean[mar_features], df_mar_clean["port_congestion_index"])
        joblib.dump({"model": mar_model, "features": mar_features}, out_model_dir / "port_congestion_model.pkl")

    # Train rail freight congestion forecast model
    df_r = df_rail.copy()
    df_r["date"] = pd.to_datetime(df_r["date"])
    df_r = df_r.sort_values("date").reset_index(drop=True)

    for lag in [1, 2]:
        df_r[f"rail_lag_{lag}"] = df_r["rail_congestion_index"].shift(lag)

    df_r_clean = df_r.dropna().reset_index(drop=True)
    rail_features = [f"rail_lag_{lag}" for lag in [1, 2]]
    rail_model = LGBMRegressor(n_estimators=50, random_state=42)
    rail_model.fit(df_r_clean[rail_features], df_r_clean["rail_congestion_index"])
    joblib.dump({"model": rail_model, "features": rail_features}, out_model_dir / "rail_congestion_model.pkl")

    metrics = {
        "maritime_records": len(df_maritime),
        "rail_records": len(df_rail),
        "mean_port_congestion": float(df_maritime["port_congestion_index"].mean()),
        "mean_rail_congestion": float(df_rail["rail_congestion_index"].mean())
    }

    with open(GEN_DIR / "multimodal_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Saved Multimodal Models to {out_model_dir}")
    return metrics


if __name__ == "__main__":
    results = {}
    results["uci_demand"] = train_uci_demand_model()
    results["bts_air"] = train_bts_air_models()
    results["bts_road"] = train_bts_road_model()
    results["multimodal"] = train_multimodal_model()

    summary_file = GEN_DIR / "all_benchmark_models_summary.json"
    with open(summary_file, "w") as f:
        json.dump(results, f, indent=2)

    print("\n=======================================================")
    print(" ALL BENCHMARK DATASET TRAININGS COMPLETED SUCCESSFULLY!")
    print(f" Summary saved to: {summary_file}")
    print("=======================================================")
