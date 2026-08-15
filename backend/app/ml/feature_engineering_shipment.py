"""
Feature engineering for shipment delay classification and delay-duration
regression.

LEAKAGE PREVENTION: 'historical route delay rate' and 'supplier recent delay
rate' are EXPANDING statistics computed per (route / supplier), sorted by
order_date, using shift(1) before the expanding window so a shipment's own
outcome is never used to compute its own feature - only shipments that were
ORDERED STRICTLY BEFORE it. This mirrors the lag/rolling approach used for
demand forecasting.

Only shipments with a known actual_delivery date can be used for TRAINING
(they have a label). Shipments still in transit are fine for the historical
expanding stats leading up to them, but they themselves cannot be a training
row until they're delivered.
"""
from __future__ import annotations

import pandas as pd

CATEGORICAL_COLUMNS = ["transport_mode", "carrier"]
NUMERIC_FEATURE_COLUMNS = [
    "distance_km", "weight_kg", "quantity",
    "supplier_lead_time_days", "supplier_reliability", "supplier_cost_index",
    "historical_route_delay_rate", "supplier_recent_delay_rate", "previous_shipment_delayed",
    "order_day_of_week", "order_month",
]


def _expanding_prior_mean(df: pd.DataFrame, group_col: str, value_col: str, order_col: str) -> pd.Series:
    """
    For each row, the mean of value_col over all PRIOR rows (by order_col)
    within the same group - i.e. strictly excluding the row itself.
    """
    df = df.sort_values(order_col)
    shifted = df.groupby(group_col)[value_col].shift(1)
    expanding_mean = shifted.groupby(df[group_col]).expanding().mean().reset_index(level=0, drop=True)
    return expanding_mean.reindex(df.index)


def build_shipment_feature_matrix(shipments_df: pd.DataFrame, completed_only: bool = True, train_end_date=None) -> pd.DataFrame:
    """
    shipments_df must contain: shipment_id, product_id, supplier_id, origin,
    destination, carrier, transport_mode, distance_km, weight_kg, quantity,
    order_date, planned_delivery, actual_delivery, supplier_lead_time_days,
    supplier_reliability, supplier_cost_index.

    Returns one row per shipment with engineered features plus target
    columns 'is_delayed' and 'delay_days' (both NaN for undelivered shipments
    unless completed_only=False, in which case they're included for
    feature-only / serving use with target columns left NaN).
    """
    df = shipments_df.copy()
    for col in ("order_date", "planned_delivery", "actual_delivery"):
        df[col] = pd.to_datetime(df[col])
    df = df.sort_values("order_date").reset_index(drop=True)

    df["delay_days"] = (df["actual_delivery"] - df["planned_delivery"]).dt.days
    df["target_is_delayed"] = (df["delay_days"] > 0).astype("float")
    df.loc[df["actual_delivery"].isna(), ["delay_days", "target_is_delayed"]] = pd.NA
    
    df["is_delayed"] = df["target_is_delayed"].copy()
    if train_end_date is not None:
        df.loc[df["order_date"] >= pd.to_datetime(train_end_date), "is_delayed"] = pd.NA

    # route key for expanding stats
    df["route"] = df["origin"].astype(str) + " -> " + df["destination"].astype(str)

    df["historical_route_delay_rate"] = _expanding_prior_mean(df, "route", "is_delayed", "order_date")
    df["supplier_recent_delay_rate"] = _expanding_prior_mean(df, "supplier_id", "is_delayed", "order_date")

    df = df.sort_values(["supplier_id", "order_date"])
    df["previous_shipment_delayed"] = df.groupby("supplier_id")["is_delayed"].shift(1)
    df = df.sort_values("order_date").reset_index(drop=True)

    global_delay_rate = df["is_delayed"].mean(skipna=True)
    if pd.isna(global_delay_rate):
        global_delay_rate = 0.1
    df["historical_route_delay_rate"] = df["historical_route_delay_rate"].fillna(global_delay_rate)
    df["supplier_recent_delay_rate"] = df["supplier_recent_delay_rate"].fillna(global_delay_rate)
    df["previous_shipment_delayed"] = df["previous_shipment_delayed"].fillna(0)

    df["order_day_of_week"] = df["order_date"].dt.dayofweek
    df["order_month"] = df["order_date"].dt.month

    for col in CATEGORICAL_COLUMNS:
        if col not in df.columns:
            df[col] = "unknown"
        df[col] = df[col].fillna("unknown").astype(str)

    for col in NUMERIC_FEATURE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df[NUMERIC_FEATURE_COLUMNS] = df[NUMERIC_FEATURE_COLUMNS].fillna(0)
    
    # Restore actual target labels for evaluation
    df["is_delayed"] = df["target_is_delayed"]
    df = df.drop(columns=["target_is_delayed"])

    if completed_only:
        df = df[df["actual_delivery"].notna()].reset_index(drop=True)

    return df


def encode_categoricals(df: pd.DataFrame, fit_columns: list[str] | None = None) -> tuple[pd.DataFrame, list[str]]:
    """
    One-hot encodes CATEGORICAL_COLUMNS. If fit_columns is given (from a
    previously trained model), the output is reindexed to exactly those
    columns - unseen categories at serving time simply produce all-zero
    dummies rather than crashing or shifting the feature space.
    """
    encoded = pd.get_dummies(df, columns=CATEGORICAL_COLUMNS, prefix=CATEGORICAL_COLUMNS)
    dummy_cols = [c for c in encoded.columns if any(c.startswith(f"{p}_") for p in CATEGORICAL_COLUMNS)]

    if fit_columns is None:
        all_feature_cols = NUMERIC_FEATURE_COLUMNS + sorted(dummy_cols)
        return encoded, all_feature_cols

    for col in fit_columns:
        if col not in encoded.columns:
            encoded[col] = 0
    return encoded, fit_columns
