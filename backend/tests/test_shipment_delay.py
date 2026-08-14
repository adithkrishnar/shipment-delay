import numpy as np
import pandas as pd
import pytest

from app.ml.shipment_delay import (
    predict_shipment_risk,
    train_delay_classifier,
    train_delay_duration_model,
)


def _synthetic_shipments(n=300, seed=5):
    """
    Shipments across a few supplier/route combos with reliability-driven
    delay probability, so there's real signal for a classifier to learn
    (mirrors the logic in the demo data generator, but self-contained here).
    """
    rng = np.random.default_rng(seed)
    suppliers = [
        {"id": 1, "reliability": 0.95, "lead_time": 5},
        {"id": 2, "reliability": 0.75, "lead_time": 10},
        {"id": 3, "reliability": 0.55, "lead_time": 15},
    ]
    routes = [("Mumbai", "Delhi", 1400), ("Chennai", "Bengaluru", 350)]

    rows = []
    order_date = pd.Timestamp("2025-01-01")
    for i in range(n):
        supplier = suppliers[i % len(suppliers)]
        origin, destination, distance = routes[i % len(routes)]
        order_date = order_date + pd.Timedelta(days=rng.integers(1, 4))
        planned = order_date + pd.Timedelta(days=supplier["lead_time"])

        delay_prob = 1 - supplier["reliability"]
        is_delayed = rng.random() < delay_prob
        delay_days = int(rng.exponential(3)) + 1 if is_delayed else 0
        actual = planned + pd.Timedelta(days=delay_days)

        rows.append({
            "shipment_id": f"S{i}", "product_id": (i % 5) + 1, "supplier_id": supplier["id"],
            "origin": origin, "destination": destination,
            "carrier": f"Carrier{(i % 3) + 1}", "transport_mode": ["road", "air", "sea"][i % 3],
            "distance_km": distance, "weight_kg": float(rng.uniform(100, 2000)), "quantity": float(rng.uniform(50, 500)),
            "order_date": order_date, "planned_delivery": planned, "actual_delivery": actual,
            "supplier_lead_time_days": supplier["lead_time"], "supplier_reliability": supplier["reliability"],
            "supplier_cost_index": 1.0,
        })
    return pd.DataFrame(rows)


def test_train_delay_classifier_beats_majority_baseline_on_auc():
    df = _synthetic_shipments()
    clf = train_delay_classifier(df)
    comparison = clf.metrics["comparison"]
    selected_auc = comparison[clf.model_name]["roc_auc"]
    assert selected_auc is not None
    assert selected_auc > 0.55  # meaningfully better than random (0.5)


def test_train_delay_classifier_raises_on_too_little_data():
    tiny_df = _synthetic_shipments(n=10)
    with pytest.raises(ValueError):
        train_delay_classifier(tiny_df)


def test_train_delay_classifier_uses_time_based_split():
    df = _synthetic_shipments()
    clf = train_delay_classifier(df)
    train_rows = clf.metrics["train_rows"]
    test_rows = clf.metrics["test_rows"]
    fraction = test_rows / (train_rows + test_rows)
    assert 0.1 < fraction < 0.3


def test_confusion_matrix_totals_match_test_set_size():
    df = _synthetic_shipments()
    clf = train_delay_classifier(df)
    cm = clf.metrics["confusion_matrix_test"]
    total = cm["true_positive"] + cm["true_negative"] + cm["false_positive"] + cm["false_negative"]
    assert total == clf.metrics["test_rows"]


def test_train_delay_duration_model_only_uses_delayed_shipments():
    df = _synthetic_shipments()
    dur = train_delay_duration_model(df)
    assert dur.metrics["train_rows"] + dur.metrics["test_rows"] < len(df)  # strictly fewer than all shipments


def test_predict_shipment_risk_returns_valid_ranges():
    df = _synthetic_shipments()
    clf = train_delay_classifier(df)
    dur = train_delay_duration_model(df)

    pending = df.sort_values("order_date").iloc[[-1]].copy()
    pending["actual_delivery"] = pd.NaT

    result = predict_shipment_risk(clf, dur, pending)
    assert 0.0 <= result["delay_probability"] <= 1.0
    assert result["risk_tier"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert result["expected_delay_days"] is None or result["expected_delay_days"] >= 0
    assert isinstance(result["top_risk_factors"], list)
    assert len(result["top_risk_factors"]) > 0


def test_predict_shipment_risk_higher_for_unreliable_supplier():
    df = _synthetic_shipments()
    clf = train_delay_classifier(df)

    reliable = df[df.supplier_id == 1].sort_values("order_date").iloc[[-1]].copy()
    unreliable = df[df.supplier_id == 3].sort_values("order_date").iloc[[-1]].copy()
    reliable["actual_delivery"] = pd.NaT
    unreliable["actual_delivery"] = pd.NaT

    reliable_risk = predict_shipment_risk(clf, None, reliable)
    unreliable_risk = predict_shipment_risk(clf, None, unreliable)
    assert unreliable_risk["delay_probability"] > reliable_risk["delay_probability"]


def test_top_risk_factors_never_fabricated_beyond_known_features():
    df = _synthetic_shipments()
    clf = train_delay_classifier(df)
    pending = df.sort_values("order_date").iloc[[-1]].copy()
    pending["actual_delivery"] = pd.NaT
    result = predict_shipment_risk(clf, None, pending)
    for factor in result["top_risk_factors"]:
        assert factor["factor"] in clf.feature_columns
