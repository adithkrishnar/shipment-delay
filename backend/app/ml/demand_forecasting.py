"""
Demand forecasting model: training, evaluation, and recursive forecasting.

Follows the spec's ML rules strictly:
  - time-based train/test split (never random shuffle for forecasting)
  - a naive seasonal baseline is always trained and reported alongside the
    real models, so "the model beats a naive baseline" can actually be checked
  - preprocessing (product mean-encoding) is fit ONLY on the training split
  - a fixed random_state is used everywhere for reproducibility
  - real metrics (MAE, RMSE, MAPE) are computed on the held-out test split
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.ml.feature_engineering import FEATURE_COLUMNS, build_feature_matrix

TEST_FRACTION = 0.2
RANDOM_STATE = 42


@dataclass
class TrainedDemandModel:
    model_name: str
    model: object
    product_mean_encoding: dict
    global_mean_demand: float
    metrics: dict = field(default_factory=dict)
    feature_columns: list = field(default_factory=lambda: list(FEATURE_COLUMNS) + ["product_mean_demand"])


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """MAPE, safely ignoring near-zero actuals (which make MAPE explode/undefined)."""
    mask = y_true > 1e-6
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def _time_based_split(feature_df: pd.DataFrame, test_fraction: float = TEST_FRACTION) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits by a single global date cutoff (not per-product), so the test set
    is a genuine "future" period relative to train, with no leakage across
    the boundary in either direction.
    """
    cutoff = feature_df["date"].quantile(1 - test_fraction, interpolation="nearest")
    train = feature_df[feature_df["date"] < cutoff].copy()
    test = feature_df[feature_df["date"] >= cutoff].copy()
    return train, test


def _add_product_mean_encoding(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict, float]:
    """Mean-encode product_id using ONLY the training split, then apply to both splits."""
    product_means = train.groupby("product_id")["quantity"].mean().to_dict()
    global_mean = float(train["quantity"].mean())

    train = train.copy()
    test = test.copy()
    train["product_mean_demand"] = train["product_id"].map(product_means)
    test["product_mean_demand"] = test["product_id"].map(product_means).fillna(global_mean)
    return train, test, product_means, global_mean


def _naive_seasonal_baseline(test: pd.DataFrame) -> np.ndarray:
    """Naive baseline: predict this week's value as last week's same-weekday value (lag_7)."""
    return test["lag_7"].to_numpy()


def train_demand_model(sales_df: pd.DataFrame) -> TrainedDemandModel:
    """
    Trains and compares a naive baseline, Random Forest, and Gradient Boosting
    regressor on time-split data, and returns whichever REAL model (RF or GB)
    scored best on held-out MAE - while still reporting the baseline's score
    for comparison, per spec.
    """
    feature_df = build_feature_matrix(sales_df)
    if len(feature_df) < 50:
        raise ValueError("Not enough historical data to train a demand forecasting model (need >= 50 usable rows).")

    train_full, test = _time_based_split(feature_df)
    if len(train_full) < 20 or len(test) < 5:
        raise ValueError("Not enough data on one side of the time-based split to train/evaluate reliably.")

    # Internal split for hyperparameter/model selection (prevents test set leakage)
    train_sub, val = _time_based_split(train_full, test_fraction=0.25)
    
    train_sub, val, product_means_val, global_mean_val = _add_product_mean_encoding(train_sub, val)
    feature_cols = list(FEATURE_COLUMNS) + ["product_mean_demand"]

    X_train_sub, y_train_sub = train_sub[feature_cols], train_sub["quantity"]
    X_val, y_val = val[feature_cols], val["quantity"]

    candidates = {
        "random_forest": RandomForestRegressor(
            n_estimators=200, max_depth=10, min_samples_leaf=3, random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=200, max_depth=3, learning_rate=0.05, random_state=RANDOM_STATE,
        ),
    }

    # Model Selection using validation set
    val_maes = {}
    for name, model in candidates.items():
        model.fit(X_train_sub, y_train_sub)
        pred = np.clip(model.predict(X_val), 0, None)
        val_maes[name] = float(mean_absolute_error(y_val, pred))
        
    best_name = min(val_maes, key=val_maes.get)
    best_candidate = candidates[best_name]

    # Retrain on full train set
    train_full, test, product_means, global_mean = _add_product_mean_encoding(train_full, test)
    X_train_full, y_train_full = train_full[feature_cols], train_full["quantity"]
    X_test, y_test = test[feature_cols], test["quantity"]

    best_candidate.fit(X_train_full, y_train_full)

    baseline_pred = np.clip(_naive_seasonal_baseline(test), 0, None)
    results = {
        "naive_seasonal_baseline": {
            "mae": mean_absolute_error(y_test, baseline_pred),
            "rmse": float(np.sqrt(mean_squared_error(y_test, baseline_pred))),
            "mape": _mape(y_test.to_numpy(), baseline_pred),
        }
    }

    final_pred = np.clip(best_candidate.predict(X_test), 0, None)
    results[best_name] = {
        "mae": float(mean_absolute_error(y_test, final_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_test, final_pred))),
        "mape": _mape(y_test.to_numpy(), final_pred),
    }

    return TrainedDemandModel(
        model_name=best_name,
        model=best_candidate,
        product_mean_encoding=product_means,
        global_mean_demand=global_mean,
        metrics={
            "selected_model": best_name,
            "train_rows": len(train_full),
            "test_rows": len(test),
            "comparison": results,
            "validation_maes": val_maes,
        },
    )


def save_model(trained: TrainedDemandModel, path) -> None:
    joblib.dump(trained, path)


def load_model(path) -> TrainedDemandModel:
    return joblib.load(path)


def forecast_product_demand(
    trained: TrainedDemandModel,
    product_history: pd.DataFrame,
    horizon_days: int,
) -> pd.DataFrame:
    """
    Recursive multi-step forecast for ONE product: predicts day t+1, appends
    it to the working history, recomputes lag/rolling features, predicts
    t+2, and so on. This is the standard approach for tree-based models,
    which can't natively output a full future sequence in one shot.

    product_history must contain at least the last 14+ days of actual
    ('date', 'quantity', 'product_id', 'promotion') for lag/rolling features
    to be computable on the first forecasted day.
    """
    from app.ml.feature_engineering import add_lag_and_rolling_features, add_time_features

    history = product_history[["date", "product_id", "quantity", "promotion"]].copy()
    history["date"] = pd.to_datetime(history["date"])
    product_id = history["product_id"].iloc[0]
    product_mean = trained.product_mean_encoding.get(product_id, trained.global_mean_demand)

    last_date = history["date"].max()
    forecasts = []

    for step in range(1, horizon_days + 1):
        target_date = last_date + dt.timedelta(days=step)
        working = pd.concat([
            history,
            pd.DataFrame([{"date": target_date, "product_id": product_id, "quantity": np.nan, "promotion": 0}]),
        ], ignore_index=True)

        feat = add_time_features(working)
        feat = add_lag_and_rolling_features(feat)
        row = feat.iloc[[-1]].copy()
        row["product_mean_demand"] = product_mean

        X = row[trained.feature_columns]
        pred = float(np.clip(trained.model.predict(X)[0], 0, None))

        forecasts.append({"date": target_date.date().isoformat(), "predicted_quantity": round(pred, 1)})

        # feed the prediction back in so the next step's lags see it
        history = pd.concat([
            history,
            pd.DataFrame([{"date": target_date, "product_id": product_id, "quantity": pred, "promotion": 0}]),
        ], ignore_index=True)

    return pd.DataFrame(forecasts)
