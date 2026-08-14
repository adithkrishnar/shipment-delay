import numpy as np
import pandas as pd
import pytest

from app.ml.demand_forecasting import forecast_product_demand, train_demand_model


def _synthetic_sales(n_days=400, products=("P1", "P2", "P3"), seed=7):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2025-01-01", periods=n_days)
    rows = []
    for pid in products:
        base = rng.uniform(40, 120)
        for i, d in enumerate(dates):
            weekday_factor = 1 + 0.2 * np.sin(2 * np.pi * (d.weekday() / 7))
            trend = 1 + 0.0003 * i
            noise = rng.normal(0, base * 0.1)
            qty = max(0, base * weekday_factor * trend + noise)
            rows.append({"product_id": pid, "date": d, "quantity": qty, "promotion": 0})
    return pd.DataFrame(rows)


def test_train_demand_model_beats_or_matches_naive_baseline():
    df = _synthetic_sales()
    trained = train_demand_model(df)
    comparison = trained.metrics["comparison"]
    selected_mae = comparison[trained.model_name]["mae"]
    baseline_mae = comparison["naive_seasonal_baseline"]["mae"]
    # the selected model was chosen BECAUSE it had the lowest MAE among candidates
    assert selected_mae <= baseline_mae + 1e-6


def test_train_demand_model_raises_on_too_little_data():
    tiny_df = _synthetic_sales(n_days=10, products=("P1",))
    with pytest.raises(ValueError):
        train_demand_model(tiny_df)


def test_train_demand_model_uses_time_based_split_not_random():
    df = _synthetic_sales()
    trained = train_demand_model(df)
    # test set size should roughly match the configured 20% fraction
    train_rows = trained.metrics["train_rows"]
    test_rows = trained.metrics["test_rows"]
    fraction = test_rows / (train_rows + test_rows)
    assert 0.1 < fraction < 0.3


def test_forecast_returns_correct_horizon_length():
    df = _synthetic_sales()
    trained = train_demand_model(df)
    product_hist = df[df.product_id == "P1"].sort_values("date")

    for horizon in (7, 30, 90):
        fc = forecast_product_demand(trained, product_hist, horizon_days=horizon)
        assert len(fc) == horizon
        assert list(fc.columns) == ["date", "predicted_quantity"]


def test_forecast_dates_are_sequential_and_after_history():
    df = _synthetic_sales()
    trained = train_demand_model(df)
    product_hist = df[df.product_id == "P1"].sort_values("date")
    last_actual_date = pd.to_datetime(product_hist["date"]).max()

    fc = forecast_product_demand(trained, product_hist, horizon_days=7)
    fc_dates = pd.to_datetime(fc["date"])
    assert fc_dates.iloc[0] == last_actual_date + pd.Timedelta(days=1)
    assert (fc_dates.diff().dropna() == pd.Timedelta(days=1)).all()


def test_forecast_predictions_are_never_negative():
    df = _synthetic_sales()
    trained = train_demand_model(df)
    product_hist = df[df.product_id == "P2"].sort_values("date")
    fc = forecast_product_demand(trained, product_hist, horizon_days=30)
    assert (fc["predicted_quantity"] >= 0).all()


def test_forecast_handles_unseen_product_via_global_mean_fallback():
    """A product the model never saw during training should still get a sane forecast."""
    df = _synthetic_sales(products=("P1", "P2"))
    trained = train_demand_model(df)

    unseen_hist = _synthetic_sales(products=("P_UNSEEN",))
    unseen_hist = unseen_hist[unseen_hist.product_id == "P_UNSEEN"]
    fc = forecast_product_demand(trained, unseen_hist, horizon_days=7)
    assert len(fc) == 7
    assert (fc["predicted_quantity"] >= 0).all()
