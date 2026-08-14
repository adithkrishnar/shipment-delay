"""
Shipment delay classification (will it be delayed?) and delay duration
regression (how long?), per spec sections "SHIPMENT DELAY CLASSIFICATION"
and "DELAY DURATION REGRESSION".

Same ML discipline as demand forecasting: time-based split, a naive baseline
reported alongside real models, fixed random_state, real held-out metrics.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    mean_absolute_error,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.utils.class_weight import compute_sample_weight

from app.ml.feature_engineering_shipment import build_shipment_feature_matrix, encode_categoricals

TEST_FRACTION = 0.2
RANDOM_STATE = 42


@dataclass
class TrainedDelayClassifier:
    model_name: str
    model: object
    feature_columns: list
    metrics: dict = field(default_factory=dict)


@dataclass
class TrainedDelayDurationModel:
    model_name: str
    model: object
    feature_columns: list
    metrics: dict = field(default_factory=dict)


def _time_split(df: pd.DataFrame, test_fraction: float = TEST_FRACTION) -> tuple[pd.DataFrame, pd.DataFrame]:
    cutoff = df["order_date"].quantile(1 - test_fraction, interpolation="nearest")
    return df[df["order_date"] < cutoff].copy(), df[df["order_date"] >= cutoff].copy()


def train_delay_classifier(shipments_df: pd.DataFrame) -> TrainedDelayClassifier:
    feat = build_shipment_feature_matrix(shipments_df, completed_only=True)
    if len(feat) < 40:
        raise ValueError("Not enough completed shipments to train a delay classifier (need >= 40).")

    train, test = _time_split(feat)
    if len(train) < 20 or len(test) < 5:
        raise ValueError("Not enough data on one side of the time-based split to train/evaluate reliably.")
    if train["is_delayed"].nunique() < 2:
        raise ValueError("Training split has only one class (all delayed or all on-time) - cannot train a classifier.")

    train_enc, feature_cols = encode_categoricals(train)
    test_enc, _ = encode_categoricals(test, fit_columns=feature_cols)

    X_train, y_train = train_enc[feature_cols], train_enc["is_delayed"].astype(int)
    X_test, y_test = test_enc[feature_cols], test_enc["is_delayed"].astype(int)

    majority_class = int(y_train.mode()[0])
    majority_pred = np.full(len(y_test), majority_class)
    baseline_metrics = {
        "accuracy": float(accuracy_score(y_test, majority_pred)),
        "precision": float(precision_score(y_test, majority_pred, zero_division=0)),
        "recall": float(recall_score(y_test, majority_pred, zero_division=0)),
        "f1": float(f1_score(y_test, majority_pred, zero_division=0)),
        "roc_auc": None,
    }
    results = {"majority_class_baseline": baseline_metrics}

    candidates = {
        "logistic_regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=3, random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.05, random_state=RANDOM_STATE,
        ),
    }

    fitted = {}
    sample_weight = compute_sample_weight(class_weight="balanced", y=y_train)
    for name, model in candidates.items():
        fit_kwargs = {"clf__sample_weight": sample_weight} if isinstance(model, Pipeline) else {"sample_weight": sample_weight}
        model.fit(X_train, y_train, **fit_kwargs)
        pred = model.predict(X_test)
        proba = model.predict_proba(X_test)[:, 1]
        try:
            auc = float(roc_auc_score(y_test, proba)) if y_test.nunique() > 1 else None
        except ValueError:
            auc = None
        results[name] = {
            "accuracy": float(accuracy_score(y_test, pred)),
            "precision": float(precision_score(y_test, pred, zero_division=0)),
            "recall": float(recall_score(y_test, pred, zero_division=0)),
            "f1": float(f1_score(y_test, pred, zero_division=0)),
            "roc_auc": auc,
        }
        fitted[name] = model

    def _score(name):
        auc = results[name]["roc_auc"]
        return auc if auc is not None else results[name]["f1"]

    best_name = max(fitted, key=_score)
    best_model = fitted[best_name]

    return TrainedDelayClassifier(
        model_name=best_name,
        model=best_model,
        feature_columns=feature_cols,
        metrics={
            "selected_model": best_name,
            "train_rows": len(train),
            "test_rows": len(test),
            "positive_rate_train": float(y_train.mean()),
            "confusion_matrix_test": _confusion_matrix(y_test, fitted[best_name].predict(X_test)),
            "comparison": results,
        },
    )


def _confusion_matrix(y_true, y_pred) -> dict:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    return {"true_positive": tp, "true_negative": tn, "false_positive": fp, "false_negative": fn}


def train_delay_duration_model(shipments_df: pd.DataFrame) -> TrainedDelayDurationModel:
    """Regresses delay DURATION in days, trained only on shipments that were actually delayed."""
    feat = build_shipment_feature_matrix(shipments_df, completed_only=True)
    delayed = feat[feat["is_delayed"] == 1].copy()
    if len(delayed) < 30:
        raise ValueError("Not enough delayed shipments to train a delay-duration regressor (need >= 30).")

    train, test = _time_split(delayed)
    if len(train) < 15 or len(test) < 5:
        raise ValueError("Not enough delayed shipments on one side of the time-based split.")

    train_enc, feature_cols = encode_categoricals(train)
    test_enc, _ = encode_categoricals(test, fit_columns=feature_cols)

    X_train, y_train = train_enc[feature_cols], train_enc["delay_days"]
    X_test, y_test = test_enc[feature_cols], test_enc["delay_days"]

    naive_pred = np.full(len(y_test), float(y_train.mean()))
    results = {
        "mean_baseline": {
            "mae": float(mean_absolute_error(y_test, naive_pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, naive_pred))),
            "r2": float(r2_score(y_test, naive_pred)) if y_test.nunique() > 1 else None,
        }
    }

    candidates = {
        "random_forest": RandomForestRegressor(
            n_estimators=200, max_depth=8, min_samples_leaf=2, random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "gradient_boosting": GradientBoostingRegressor(
            n_estimators=150, max_depth=3, learning_rate=0.05, random_state=RANDOM_STATE,
        ),
    }
    fitted = {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        pred = np.clip(model.predict(X_test), 0, None)
        results[name] = {
            "mae": float(mean_absolute_error(y_test, pred)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, pred))),
            "r2": float(r2_score(y_test, pred)) if y_test.nunique() > 1 else None,
        }
        fitted[name] = model

    best_name = min(fitted, key=lambda n: results[n]["mae"])

    return TrainedDelayDurationModel(
        model_name=best_name,
        model=fitted[best_name],
        feature_columns=feature_cols,
        metrics={
            "selected_model": best_name,
            "train_rows": len(train),
            "test_rows": len(test),
            "comparison": results,
        },
    )


def save_model(trained, path) -> None:
    joblib.dump(trained, path)


def load_model(path):
    return joblib.load(path)


def predict_shipment_risk(
    classifier: TrainedDelayClassifier,
    duration_model: TrainedDelayDurationModel | None,
    shipment_row: pd.DataFrame,
) -> dict:
    """
    shipment_row: a single-row DataFrame in the same raw shape accepted by
    build_shipment_feature_matrix (completed_only=False, since this is for
    a shipment that may not have an actual_delivery yet).
    """
    feat = build_shipment_feature_matrix(shipment_row, completed_only=False)
    encoded, _ = encode_categoricals(feat, fit_columns=classifier.feature_columns)
    X = encoded[classifier.feature_columns]

    delay_probability = float(classifier.model.predict_proba(X)[0, 1])

    if delay_probability >= 0.7:
        risk_tier = "CRITICAL" if delay_probability >= 0.85 else "HIGH"
    elif delay_probability >= 0.4:
        risk_tier = "MEDIUM"
    else:
        risk_tier = "LOW"

    expected_delay_days = None
    if duration_model is not None:
        encoded_dur, _ = encode_categoricals(feat, fit_columns=duration_model.feature_columns)
        X_dur = encoded_dur[duration_model.feature_columns]
        expected_delay_days = float(np.clip(duration_model.model.predict(X_dur)[0], 0, None))

    top_factors = _top_risk_factors(classifier, X.iloc[0])

    return {
        "delay_probability": round(delay_probability, 4),
        "risk_tier": risk_tier,
        "expected_delay_days": round(expected_delay_days, 1) if expected_delay_days is not None else None,
        "top_risk_factors": top_factors,
    }


def predict_shipment_risk_batch(
    classifier: TrainedDelayClassifier,
    duration_model: TrainedDelayDurationModel | None,
    shipments_df: pd.DataFrame,
) -> list[str]:
    """Returns a list of risk tiers for a batch of shipments."""
    if shipments_df.empty:
        return []
    feat = build_shipment_feature_matrix(shipments_df, completed_only=False)
    encoded, _ = encode_categoricals(feat, fit_columns=classifier.feature_columns)
    X = encoded[classifier.feature_columns]

    delay_probabilities = classifier.model.predict_proba(X)[:, 1]
    
    risk_tiers = []
    for p in delay_probabilities:
        if p >= 0.7:
            risk_tiers.append("CRITICAL" if p >= 0.85 else "HIGH")
        elif p >= 0.4:
            risk_tiers.append("MEDIUM")
        else:
            risk_tiers.append("LOW")
            
    return risk_tiers


def _top_risk_factors(classifier: TrainedDelayClassifier, feature_row: pd.Series, top_n: int = 5) -> list[dict]:
    """
    Lightweight explainability: for tree-based models, use global
    feature_importances_; for linear models (e.g. logistic regression,
    possibly wrapped in a scaling Pipeline), use absolute coefficient
    magnitude instead. Combined with this shipment's own feature values to
    surface which factors are driving THIS prediction. (Full SHAP-based
    per-instance attribution can be layered on later; this gives a real,
    non-fabricated signal in the meantime.)
    """
    model = classifier.model

    if hasattr(model, "feature_importances_"):
        importances = pd.Series(model.feature_importances_, index=classifier.feature_columns)
    elif hasattr(model, "coef_"):
        importances = pd.Series(np.abs(model.coef_[0]), index=classifier.feature_columns)
    elif hasattr(model, "named_steps"):  # sklearn Pipeline, e.g. StandardScaler + LogisticRegression
        final_step = model.named_steps[list(model.named_steps.keys())[-1]]
        if hasattr(final_step, "coef_"):
            importances = pd.Series(np.abs(final_step.coef_[0]), index=classifier.feature_columns)
        else:
            return []
    else:
        return []

    top = importances.sort_values(ascending=False).head(top_n)
    factors = []
    for feature_name, importance in top.items():
        if importance <= 0:
            continue
        factors.append({
            "factor": feature_name,
            "importance": round(float(importance), 4),
            "value": round(float(feature_row[feature_name]), 3),
        })
    return factors
