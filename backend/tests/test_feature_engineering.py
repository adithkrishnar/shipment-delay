import numpy as np
import pandas as pd

from app.ml.feature_engineering import FEATURE_COLUMNS, build_feature_matrix


def _synthetic_sales(n_days=60, products=("P1", "P2")):
    dates = pd.date_range("2026-01-01", periods=n_days)
    rows = []
    for pid in products:
        for i, d in enumerate(dates):
            rows.append({
                "product_id": pid, "date": d,
                "quantity": max(0, 50 + 10 * np.sin(i / 7) + i * 0.2),
                "promotion": 0,
            })
    return pd.DataFrame(rows)


def test_row_count_after_warmup_drop():
    df = _synthetic_sales(n_days=60, products=("P1", "P2"))
    feat = build_feature_matrix(df)
    # max lag/rolling window is 14, so first 14 rows per product are dropped
    assert len(feat) == (60 - 14) * 2


def test_no_missing_values_in_feature_columns():
    df = _synthetic_sales()
    feat = build_feature_matrix(df)
    assert not feat[FEATURE_COLUMNS].isna().any().any()


def test_lag_1_matches_previous_day_actual():
    df = _synthetic_sales(n_days=30, products=("P1",))
    feat = build_feature_matrix(df).sort_values("date").reset_index(drop=True)
    # lag_1 on any row should equal the ACTUAL quantity of the day before, from the raw series
    raw = df.set_index("date")["quantity"]
    for _, row in feat.iterrows():
        prev_day = row["date"] - pd.Timedelta(days=1)
        assert abs(row["lag_1"] - raw.loc[prev_day]) < 1e-6


def test_rolling_features_never_include_current_day():
    """
    If rolling stats leaked the current day's value in, changing today's
    quantity would change today's own rollmean_7 feature. It must not.
    """
    df = _synthetic_sales(n_days=40, products=("P1",))
    feat_before = build_feature_matrix(df)

    df_leaked = df.copy()
    last_idx = df_leaked.index[-1]
    df_leaked.loc[last_idx, "quantity"] = 999999  # huge spike on the very last day
    feat_after = build_feature_matrix(df_leaked)

    last_row_before = feat_before.iloc[-1]
    last_row_after = feat_after.iloc[-1]
    assert last_row_before["rollmean_7"] == last_row_after["rollmean_7"]


def test_missing_days_filled_as_zero_demand():
    """A gap in the raw data (no row for that date) should be treated as 0 demand, not dropped."""
    dates = pd.date_range("2026-01-01", periods=30)
    dates_with_gap = dates.delete(15)  # remove day 16
    df = pd.DataFrame({
        "product_id": "P1", "date": dates_with_gap,
        "quantity": [50] * len(dates_with_gap), "promotion": 0,
    })
    from app.ml.feature_engineering import build_daily_demand_table
    daily = build_daily_demand_table(df)
    assert len(daily) == 30  # gap day re-inserted
    gap_day = dates[15]
    assert daily[daily["date"] == gap_day]["quantity"].iloc[0] == 0.0
