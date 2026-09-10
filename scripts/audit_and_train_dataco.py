import os
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, average_precision_score, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder, StandardScaler
from sklearn.utils.class_weight import compute_sample_weight

warnings.filterwarnings("ignore")

DATASET_PATH  = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "data", "raw", "dataco", "DataCoSupplyChainDataset.csv")
OUTPUT_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "trained_models")
RANDOM_STATE  = 42
TEST_FRACTION = 0.20
VAL_FRACTION  = 0.15
TARGET        = "Late_delivery_risk"

# ── Leakage columns removed from features ─────────────────────────────────
# Delivery Status     -> text encoding of target (Late delivery = delayed=1)
# Late_delivery_risk  -> IS the target itself
# Days for shipping (real)   -> actual duration, only known after delivery
# shipping date (DateOrders) -> actual ship date, only known after dispatch
# Order Status        -> COMPLETE/CLOSED/CANCELED reflect post-fulfilment state
LEAKAGE_COLUMNS = [
    "Delivery Status",
    "Late_delivery_risk",
    "Days for shipping (real)",
    "shipping date (DateOrders)",
    "Order Status",
]

# ── Pre-shipment features (all known at order placement time) ──────────────
CAT_FEATURES = [
    "Type", "Category Name", "Customer City", "Customer Country",
    "Customer Segment", "Customer State", "Department Name",
    "Market", "Order City", "Order Country", "Order Region",
    "Order State", "Product Name", "Shipping Mode",
]
NUM_FEATURES = [
    "Days for shipment (scheduled)",
    "Order Item Discount", "Order Item Discount Rate",
    "Order Item Product Price", "Order Item Profit Ratio",
    "Order Item Quantity", "Sales", "Order Item Total", "Product Price",
    "order_year", "order_month", "order_day", "order_dayofweek",
]
ALL_FEATURES = CAT_FEATURES + NUM_FEATURES


def load_data():
    print("Loading DataCo dataset...")
    df = pd.read_csv(DATASET_PATH, encoding="latin1")
    print(f"  Loaded {len(df):,} rows x {len(df.columns)} columns")
    pii = ["Customer Email", "Customer Fname", "Customer Lname", "Customer Password",
           "Customer Street", "Product Description", "Product Image",
           "Order Zipcode", "Customer Zipcode"]
    df.drop(columns=[c for c in pii if c in df.columns], inplace=True)
    df["order date (DateOrders)"] = pd.to_datetime(df["order date (DateOrders)"])
    df.sort_values("order date (DateOrders)", inplace=True)
    df.reset_index(drop=True, inplace=True)
    before = len(df)
    df = df[df["Delivery Status"] != "Shipping canceled"].reset_index(drop=True)
    print(f"  Dropped {before - len(df):,} Shipping canceled rows -> {len(df):,} usable rows")
    return df


def engineer(df):
    df = df.copy()
    df["order_year"]      = df["order date (DateOrders)"].dt.year
    df["order_month"]     = df["order date (DateOrders)"].dt.month
    df["order_day"]       = df["order date (DateOrders)"].dt.day
    df["order_dayofweek"] = df["order date (DateOrders)"].dt.dayofweek
    return df


def prepare(df, enc=None):
    df = df.copy()
    for c in CAT_FEATURES:
        if c in df.columns:
            df[c] = df[c].fillna("unknown").astype(str)
    for c in NUM_FEATURES:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    X = df[ALL_FEATURES].copy()
    y = df[TARGET].astype(int)
    if enc is None:
        enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
        X[CAT_FEATURES] = enc.fit_transform(X[CAT_FEATURES])
    else:
        X[CAT_FEATURES] = enc.transform(X[CAT_FEATURES])
    return X, y, enc


def chron_split(df, frac=TEST_FRACTION):
    n = int(len(df) * (1 - frac))
    return df.iloc[:n].copy(), df.iloc[n:].copy()


def eval_model(model, X_test, y_test, name):
    pred  = model.predict(X_test)
    proba = model.predict_proba(X_test)[:, 1]
    acc   = accuracy_score(y_test, pred)
    prec  = precision_score(y_test, pred, zero_division=0)
    rec   = recall_score(y_test, pred, zero_division=0)
    f1    = f1_score(y_test, pred, zero_division=0)
    auc   = roc_auc_score(y_test, proba)
    pr    = average_precision_score(y_test, proba)
    cm    = confusion_matrix(y_test, pred)
    print(f"\n  -- {name} TEST METRICS --")
    print(f"    Accuracy  : {acc:.4f}")
    print(f"    Precision : {prec:.4f}")
    print(f"    Recall    : {rec:.4f}")
    print(f"    F1-Score  : {f1:.4f}")
    print(f"    ROC-AUC   : {auc:.4f}")
    print(f"    PR-AUC    : {pr:.4f}")
    tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
    print(f"    ConfMatrix: TN={tn:,} FP={fp:,} FN={fn:,} TP={tp:,}")
    return dict(
        accuracy=round(acc, 4), precision=round(prec, 4),
        recall=round(rec, 4), f1=round(f1, 4),
        roc_auc=round(auc, 4), pr_auc=round(pr, 4),
        confusion_matrix=dict(tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp)),
    )


def main():
    print("=" * 65)
    print("  SUPPLYIQ - DataCo Shipment Delay Audit & Training")
    print("=" * 65)

    df_raw = load_data()
    vc = df_raw[TARGET].value_counts()
    on_time = int(vc.get(0, 0))
    delayed = int(vc.get(1, 0))
    rate    = delayed / len(df_raw) * 100
    print(f"\n  TARGET: {TARGET}")
    print(f"    On-time(0): {on_time:,}  Delayed(1): {delayed:,}  Rate: {rate:.1f}%")

    print(f"\n  LEAKAGE AUDIT - columns removed from features:")
    for c in LEAKAGE_COLUMNS:
        print(f"    - {c}")

    df = engineer(df_raw)
    df_tv, df_test = chron_split(df, TEST_FRACTION)
    vi = int(len(df_tv) * (1 - VAL_FRACTION))
    df_tr  = df_tv.iloc[:vi]
    df_val = df_tv.iloc[vi:]

    date_col = "order date (DateOrders)"
    print(f"\n  CHRONOLOGICAL SPLIT:")
    print(f"    Train : {len(df_tr):,}  ({df_tr[date_col].min().date()} to {df_tr[date_col].max().date()})")
    print(f"    Val   : {len(df_val):,}  ({df_val[date_col].min().date()} to {df_val[date_col].max().date()})")
    print(f"    Test  : {len(df_test):,}  ({df_test[date_col].min().date()} to {df_test[date_col].max().date()})")

    # Fit encoder on train only to prevent leakage
    X_tr, y_tr, enc = prepare(df_tr)
    X_val, y_val, _ = prepare(df_val, enc)
    X_te,  y_te,  _ = prepare(df_test, enc)

    n_feat = len(X_tr.columns)
    print(f"\n  FEATURES: {n_feat} total ({len(NUM_FEATURES)} numeric + {len(CAT_FEATURES)} ordinal-encoded)")
    print(f"  CLASS BALANCE (train): on-time={(y_tr==0).sum():,}  delayed={(y_tr==1).sum():,}")
    print(f"  -> class_weight=balanced / sample_weight used in all models")
    print()

    sw_tr = compute_sample_weight("balanced", y_tr)

    candidates = {
        "logistic_regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE, C=1.0)),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=12, min_samples_leaf=3,
            class_weight="balanced", random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=150, max_depth=4, learning_rate=0.1,
            subsample=0.8, random_state=RANDOM_STATE,
        ),
    }

    print("  TRAINING ALL THREE MODELS (selecting by validation AUC):")
    val_scores = {}
    for name, model in candidates.items():
        t0 = time.time()
        if isinstance(model, Pipeline):
            model.fit(X_tr, y_tr, clf__sample_weight=sw_tr)
        else:
            model.fit(X_tr, y_tr, sample_weight=sw_tr)
        proba = model.predict_proba(X_val)[:, 1]
        auc_v = roc_auc_score(y_val, proba)
        f1_v  = f1_score(y_val, model.predict(X_val), zero_division=0)
        val_scores[name] = auc_v
        print(f"    {name:<22}  val_AUC={auc_v:.4f}  val_F1={f1_v:.4f}  ({time.time()-t0:.1f}s)")

    best_name = max(val_scores, key=val_scores.get)
    print(f"\n  BEST MODEL by val AUC: {best_name}")

    # Retrain all on full train+val for honest test evaluation
    X_tv2, y_tv2, _ = prepare(df_tv, enc)
    sw_tv = compute_sample_weight("balanced", y_tv2)
    print(f"\n  RETRAINING ALL on train+val ({len(df_tv):,} rows), evaluating on test...")
    all_metrics = {}
    for name, model in candidates.items():
        if isinstance(model, Pipeline):
            model.fit(X_tv2, y_tv2, clf__sample_weight=sw_tv)
        else:
            model.fit(X_tv2, y_tv2, sample_weight=sw_tv)
        all_metrics[name] = eval_model(model, X_te, y_te, name)

    best_model = candidates[best_name]

    # Sample predictions
    print(f"\n  SAMPLE PREDICTIONS on first 5 test rows ({best_name}):")
    sx = X_te.iloc[:5]
    sy = y_te.iloc[:5].values
    pp = best_model.predict_proba(sx)[:, 1]
    pr_pred = best_model.predict(sx)
    print(f"    {'Actual':<10} {'Predicted':<10} {'Delay Prob'}")
    for a, p, prob in zip(sy, pr_pred, pp):
        print(f"    {a:<10} {p:<10} {prob:.4f}")

    # Feature importances
    print(f"\n  TOP 15 FEATURES ({best_name}):")
    fm = best_model
    if isinstance(fm, Pipeline):
        fs = list(fm.named_steps.values())[-1]
        if hasattr(fs, "coef_"):
            imp = pd.Series(np.abs(fs.coef_[0]), index=ALL_FEATURES).sort_values(ascending=False)
        else:
            imp = pd.Series(dtype=float)
    elif hasattr(fm, "feature_importances_"):
        imp = pd.Series(fm.feature_importances_, index=ALL_FEATURES).sort_values(ascending=False)
    else:
        imp = pd.Series(dtype=float)
    for feat, v in imp.head(15).items():
        print(f"    {feat:<45} {v:.4f}")

    # Save best model
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    clf_path = os.path.join(OUTPUT_DIR, "shipment_delay_classifier.pkl")
    enc_path = os.path.join(OUTPUT_DIR, "classifier_encoder.pkl")
    artifact = dict(
        model=best_model, model_name=best_name,
        feature_columns=ALL_FEATURES, encoder=enc,
        cat_features=CAT_FEATURES, num_features=NUM_FEATURES,
        leakage_removed=LEAKAGE_COLUMNS,
        metrics=all_metrics[best_name], all_metrics=all_metrics,
        dataset_rows=len(df_raw), target=TARGET,
        time_based_split=True, trained_on_dataco=True,
    )
    joblib.dump(artifact, clf_path)
    joblib.dump(dict(encoder=enc, feature_columns=ALL_FEATURES), enc_path)
    print(f"\n  Saved -> {clf_path}")

    # ── FINAL AUDIT REPORT ────────────────────────────────────────────────
    bm = all_metrics[best_name]
    lr = all_metrics["logistic_regression"]
    rf = all_metrics["random_forest"]
    gb = all_metrics["gradient_boosting"]

    print()
    print("=" * 65)
    print("  AUDIT REPORT")
    print("=" * 65)
    print()
    print("DATASET:")
    print(f"  Dataset used : DataCoSupplyChainDataset.csv")
    print(f"  Rows         : {len(df_raw):,}  (Shipping canceled excluded)")
    print(f"  Columns      : {len(df_raw.columns)}")
    print()
    print("TARGET:")
    print(f"  Target       : {TARGET}")
    print(f"  Delayed (1)  : {delayed:,}  ({rate:.1f}%)")
    print(f"  On-time (0)  : {on_time:,}  ({100-rate:.1f}%)")
    print()
    print("LEAKAGE:")
    print(f"  Leakage found : YES")
    print(f"  Columns removed from features:")
    for c in LEAKAGE_COLUMNS:
        print(f"    - {c}")
    print()
    print("MODELS (test set):")
    lr_line = (f"  Logistic Regression : Acc={lr['accuracy']}  Prec={lr['precision']}"
               f"  Rec={lr['recall']}  F1={lr['f1']}  AUC={lr['roc_auc']}")
    rf_line = (f"  Random Forest       : Acc={rf['accuracy']}  Prec={rf['precision']}"
               f"  Rec={rf['recall']}  F1={rf['f1']}  AUC={rf['roc_auc']}")
    gb_line = (f"  Gradient Boosting   : Acc={gb['accuracy']}  Prec={gb['precision']}"
               f"  Rec={gb['recall']}  F1={gb['f1']}  AUC={gb['roc_auc']}")
    print(lr_line)
    print(rf_line)
    print(gb_line)
    print()
    print("BEST MODEL:")
    print(f"  Model     : {best_name}")
    print(f"  Accuracy  : {bm['accuracy']}")
    print(f"  Precision : {bm['precision']}")
    print(f"  Recall    : {bm['recall']}")
    print(f"  F1        : {bm['f1']}")
    print(f"  ROC-AUC   : {bm['roc_auc']}")
    print()
    print("TRAINING:")
    print(f"  Time-based split : YES (80/20 chronological)")
    print(f"  Model saved      : YES -> {clf_path}")
    print(f"  API test         : Call /api/shipments/<company_id> with backend running")
    print("=" * 65)


if __name__ == "__main__":
    main()
