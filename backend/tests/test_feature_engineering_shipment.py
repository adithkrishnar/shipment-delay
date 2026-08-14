import pandas as pd

from app.ml.feature_engineering_shipment import build_shipment_feature_matrix


def _synthetic_shipments(n=10, delayed_every=3):
    rows = []
    for i in range(n):
        order_date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=i * 10)
        planned = order_date + pd.Timedelta(days=7)
        delayed = (i % delayed_every == 0)
        actual = planned + pd.Timedelta(days=5 if delayed else 0)
        rows.append({
            "shipment_id": f"S{i}", "product_id": 1, "supplier_id": 1,
            "origin": "Mumbai", "destination": "Delhi", "carrier": "CarrierX", "transport_mode": "road",
            "distance_km": 1400, "weight_kg": 500, "quantity": 100,
            "order_date": order_date, "planned_delivery": planned, "actual_delivery": actual,
            "supplier_lead_time_days": 7, "supplier_reliability": 0.8, "supplier_cost_index": 1.0,
        })
    return pd.DataFrame(rows)


def test_is_delayed_and_delay_days_computed_correctly():
    df = _synthetic_shipments()
    feat = build_shipment_feature_matrix(df)
    s0 = feat[feat.shipment_id == "S0"].iloc[0]  # i=0, 0%3==0 -> delayed
    s1 = feat[feat.shipment_id == "S1"].iloc[0]  # i=1, not delayed
    assert s0["is_delayed"] == 1.0
    assert s0["delay_days"] == 5
    assert s1["is_delayed"] == 0.0
    assert s1["delay_days"] == 0


def test_historical_route_delay_rate_excludes_current_shipment():
    """S3 is itself delayed, but its OWN feature must reflect only S0,S1,S2."""
    df = _synthetic_shipments()
    feat = build_shipment_feature_matrix(df)
    s3 = feat[feat.shipment_id == "S3"].iloc[0]
    # S0 delayed, S1 not, S2 not -> 1/3
    assert abs(s3["historical_route_delay_rate"] - (1 / 3)) < 1e-6


def test_previous_shipment_delayed_looks_exactly_one_back():
    df = _synthetic_shipments()
    feat = build_shipment_feature_matrix(df)
    s1 = feat[feat.shipment_id == "S1"].iloc[0]  # previous is S0, which WAS delayed
    s2 = feat[feat.shipment_id == "S2"].iloc[0]  # previous is S1, which was NOT delayed
    assert s1["previous_shipment_delayed"] == 1.0
    assert s2["previous_shipment_delayed"] == 0.0


def test_first_shipment_has_no_prior_history_defaults_sanely():
    df = _synthetic_shipments()
    feat = build_shipment_feature_matrix(df)
    s0 = feat[feat.shipment_id == "S0"].iloc[0]
    assert s0["previous_shipment_delayed"] == 0.0
    assert 0 <= s0["historical_route_delay_rate"] <= 1


def test_incomplete_shipments_excluded_by_default():
    df = _synthetic_shipments()
    df.loc[df.index[-1], "actual_delivery"] = pd.NaT  # last shipment still in transit
    feat = build_shipment_feature_matrix(df, completed_only=True)
    assert len(feat) == len(df) - 1

    feat_all = build_shipment_feature_matrix(df, completed_only=False)
    assert len(feat_all) == len(df)


def test_changing_a_later_shipment_outcome_does_not_change_earlier_features():
    """Leakage check: a later shipment's outcome must not affect an earlier shipment's features."""
    df = _synthetic_shipments()
    feat_before = build_shipment_feature_matrix(df)
    s2_before = feat_before[feat_before.shipment_id == "S2"].iloc[0]["historical_route_delay_rate"]

    df_modified = df.copy()
    last_idx = df_modified.index[-1]
    df_modified.loc[last_idx, "actual_delivery"] = df_modified.loc[last_idx, "planned_delivery"] + pd.Timedelta(days=99)
    feat_after = build_shipment_feature_matrix(df_modified)
    s2_after = feat_after[feat_after.shipment_id == "S2"].iloc[0]["historical_route_delay_rate"]

    assert s2_before == s2_after
