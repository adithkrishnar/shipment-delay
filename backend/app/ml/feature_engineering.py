"""
Feature engineering for demand forecasting.

Given raw per-(product, date) sales rows, builds a supervised-learning
feature matrix with lag features, rolling statistics, trend, seasonality
(calendar features), and promotion flags - as required by the spec's
"DEMAND FORECASTING" section.

IMPORTANT (leakage prevention): every feature here is computable using only
information available strictly BEFORE the target date (lags look backward,
rolling windows are trailing). Nothing here looks at the future. Product-level
mean-encoding (which WOULD leak if computed on the full dataset) is
deliberately left out of this module and is instead computed only on the
training split inside ml/demand_forecasting.py.
"""
from __future__ import annotations

import pandas as pd

LAGS = (1, 7, 14)
ROLLING_WINDOWS = (7, 14)
MIN_HISTORY_FOR_FEATURES = max(LAGS + ROLLING_WINDOWS)  # warm-up period that must be dropped


def build_daily_demand_table(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Reindexes each product's sales onto a continuous daily calendar (filling
    days with no recorded sale as 0 demand - a day with no sale is a real
    zero, not missing data, for demand-forecasting purposes).
    """
    sales_df = sales_df.copy()
    sales_df["date"] = pd.to_datetime(sales_df["date"])

    frames = []
    for product_id, group in sales_df.groupby("product_id"):
        group = group.sort_values("date")
        full_range = pd.date_range(group["date"].min(), group["date"].max(), freq="D")
        g = group.set_index("date").reindex(full_range)
        g["product_id"] = product_id
        g["quantity"] = g["quantity"].fillna(0.0)
        if "promotion" in g.columns:
            g["promotion"] = g["promotion"].fillna(0).astype(int)
        else:
            g["promotion"] = 0
        g.index.name = "date"
        frames.append(g.reset_index())

    return pd.concat(frames, ignore_index=True)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["day_of_week"] = df["date"].dt.dayofweek
    df["month"] = df["date"].dt.month
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    min_date = df["date"].min()
    df["trend_index"] = (df["date"] - min_date).dt.days
    return df


def add_lag_and_rolling_features(
    df: pd.DataFrame,
    group_col: str = "product_id",
    target_col: str = "quantity",
    lags: tuple[int, ...] = LAGS,
    rolling_windows: tuple[int, ...] = ROLLING_WINDOWS,
) -> pd.DataFrame:
    df = df.sort_values([group_col, "date"]).copy()
    grouped = df.groupby(group_col)[target_col]

    for lag in lags:
        df[f"lag_{lag}"] = grouped.shift(lag)

    for window in rolling_windows:
        # shift(1) first so the rolling window is strictly historical (excludes the target day itself)
        shifted = grouped.shift(1)
        df[f"rollmean_{window}"] = shifted.groupby(df[group_col]).rolling(window).mean().reset_index(level=0, drop=True)
        df[f"rollstd_{window}"] = shifted.groupby(df[group_col]).rolling(window).std().reset_index(level=0, drop=True)

    return df


def build_feature_matrix(sales_df: pd.DataFrame) -> pd.DataFrame:
    """
    Full pipeline: continuous daily reindex -> calendar features -> lag/rolling
    features -> drop the warm-up rows that don't have full lag history yet.

    Returns a DataFrame with one row per (product_id, date) ready to be split
    into train/test and fed to a model, still containing 'date' and
    'product_id' for later reference (drop them from X right before fit/predict).
    """
    daily = build_daily_demand_table(sales_df)
    daily = add_time_features(daily)
    daily = add_lag_and_rolling_features(daily)

    feature_cols = (
        [f"lag_{lag}" for lag in LAGS]
        + [f"rollmean_{w}" for w in ROLLING_WINDOWS]
        + [f"rollstd_{w}" for w in ROLLING_WINDOWS]
    )
    daily = daily.dropna(subset=feature_cols).reset_index(drop=True)
    return daily


FEATURE_COLUMNS = (
    [f"lag_{lag}" for lag in LAGS]
    + [f"rollmean_{w}" for w in ROLLING_WINDOWS]
    + [f"rollstd_{w}" for w in ROLLING_WINDOWS]
    + ["day_of_week", "month", "is_weekend", "trend_index", "promotion"]
)
