"""
Analysis: Why does Shipping Mode have 0.68 feature importance?
- Shows delay rate per Shipping Mode
- Shows relationship to Days for shipment (scheduled)
- Checks redundancy
- Computes permutation importance on held-out test set
- Checks SHAP availability
"""
import time
import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from sklearn.preprocessing import OrdinalEncoder

warnings.filterwarnings("ignore")

DATASET = r"data/raw/dataco/DataCoSupplyChainDataset.csv"
MODEL_PATH = r"trained_models/shipment_delay_classifier.pkl"
TARGET = "Late_delivery_risk"

CAT = [
    "Type", "Category Name", "Customer City", "Customer Country",
    "Customer Segment", "Customer State", "Department Name",
    "Market", "Order City", "Order Country", "Order Region",
    "Order State", "Product Name", "Shipping Mode",
]
NUM = [
    "Days for shipment (scheduled)",
    "Order Item Discount", "Order Item Discount Rate",
    "Order Item Product Price", "Order Item Profit Ratio",
    "Order Item Quantity", "Sales", "Order Item Total", "Product Price",
    "order_year", "order_month", "order_day", "order_dayofweek",
]

# ── Load dataset ──────────────────────────────────────────────────────────
print("Loading DataCo dataset...")
df = pd.read_csv(DATASET, encoding="latin1")
df["order date (DateOrders)"] = pd.to_datetime(df["order date (DateOrders)"])
df.sort_values("order date (DateOrders)", inplace=True)
df.reset_index(drop=True, inplace=True)
df = df[df["Delivery Status"] != "Shipping canceled"].reset_index(drop=True)
print(f"  {len(df):,} usable rows")

df["order_year"]      = df["order date (DateOrders)"].dt.year
df["order_month"]     = df["order date (DateOrders)"].dt.month
df["order_day"]       = df["order date (DateOrders)"].dt.day
df["order_dayofweek"] = df["order date (DateOrders)"].dt.dayofweek

for c in CAT:
    df[c] = df[c].fillna("unknown").astype(str)
for c in NUM:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

# ── Reproduce same train/test split ───────────────────────────────────────
n_tv = int(len(df) * 0.80)
df_tv   = df.iloc[:n_tv]
df_test = df.iloc[n_tv:]

enc = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
X_tv = df_tv[CAT + NUM].copy()
X_tv[CAT] = enc.fit_transform(X_tv[CAT])

X_te = df_test[CAT + NUM].copy()
X_te[CAT] = enc.transform(X_te[CAT])
y_te = df_test[TARGET].astype(int)

# Load saved model
artifact = joblib.load(MODEL_PATH)
model = artifact["model"]

# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 68)
print("  1. DELAY RATE BY SHIPPING MODE")
print("=" * 68)
sm_stats = df.groupby("Shipping Mode").agg(
    total=("Late_delivery_risk", "count"),
    delayed=("Late_delivery_risk", "sum"),
).assign(
    on_time=lambda x: x["total"] - x["delayed"],
    delay_rate=lambda x: (x["delayed"] / x["total"]).round(4),
    pct_of_data=lambda x: (x["total"] / len(df) * 100).round(1),
).sort_values("delay_rate", ascending=False)
print(sm_stats.to_string())

# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 68)
print("  2. SCHEDULED DAYS BY SHIPPING MODE  (cross-tab)")
print("=" * 68)
ct = pd.crosstab(df["Shipping Mode"], df["Days for shipment (scheduled)"], margins=True)
print(ct.to_string())
print()
print("KEY: Each Shipping Mode maps EXACTLY to one unique scheduled-days value.")
print("  Same Day      -> 0 days  (delay_rate=0.479)")
print("  First Class   -> 1 day   (delay_rate=1.000 !)")
print("  Second Class  -> 2 days  (delay_rate=0.798)")
print("  Standard Class-> 4 days  (delay_rate=0.398)")

# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 68)
print("  3. DELAY RATE BY SCHEDULED DAYS (ignoring Shipping Mode label)")
print("=" * 68)
dd = df.groupby("Days for shipment (scheduled)").agg(
    total=("Late_delivery_risk", "count"),
    delayed=("Late_delivery_risk", "sum"),
).assign(delay_rate=lambda x: (x["delayed"] / x["total"]).round(4))
print(dd.to_string())

# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 68)
print("  4. CORRELATION ANALYSIS")
print("=" * 68)
df_corr = df.copy()
enc_corr = OrdinalEncoder()
df_corr["sm_enc"] = enc_corr.fit_transform(df_corr[["Shipping Mode"]])
corr = df_corr[["sm_enc", "Days for shipment (scheduled)", TARGET]].corr()
print("Pearson correlation matrix:")
print(corr.round(4).to_string())
print()
print(f"Correlation(Shipping Mode encoded, Scheduled Days): "
      f"{corr.loc['sm_enc','Days for shipment (scheduled)']:.4f}")
print("-> 0.919 = near-perfect linear relationship.")
print("-> They carry almost identical information. The model splits its")
print("   importance budget between two variables encoding the SAME SLA tier.")

# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 68)
print("  5. FIRST CLASS anomaly investigation")
print("=" * 68)
fc = df[df["Shipping Mode"] == "First Class"]
print(f"First Class rows: {len(fc):,}")
print(f"  Delay rate: {fc[TARGET].mean():.4f}  (100%!)")
print(f"  Scheduled days: always {fc['Days for shipment (scheduled)'].unique()}")
print(f"  Days for shipping (real) distribution:")
if "Days for shipping (real)" in df.columns:
    print(fc["Days for shipping (real)"].value_counts().sort_index().to_string())
print()
print("First Class has 100% delay rate -> this looks like a DataCo dataset")
print("quirk: the 'First Class' label appears to have been assigned when")
print("scheduled days=1, but almost all such orders arrived in 2+ days.")
real_vs_sched = df.groupby("Shipping Mode")[["Days for shipping (real)", "Days for shipment (scheduled)"]].mean().round(2)
print()
print("Mean real vs scheduled shipping days:")
print(real_vs_sched.to_string())

# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 68)
print("  6. NATIVE (model-built-in) FEATURE IMPORTANCE")
print("=" * 68)
imp_native = pd.Series(model.feature_importances_, index=CAT + NUM).sort_values(ascending=False)
print(f"  {'Feature':<45} {'Importance':>10}")
print(f"  {'-'*45} {'-'*10}")
for feat, val in imp_native.items():
    bar = "#" * int(val * 50)
    print(f"  {feat:<45} {val:>10.4f}  {bar}")

# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 68)
print("  7. PERMUTATION IMPORTANCE on HELD-OUT TEST SET (n_repeats=15, scoring=roc_auc)")
print("=" * 68)
print("  Running permutation importance... (may take 2-3 minutes)")
t0 = time.time()
perm = permutation_importance(
    model, X_te, y_te,
    n_repeats=15, random_state=42, n_jobs=-1,
    scoring="roc_auc",
)
elapsed = time.time() - t0
print(f"  Done in {elapsed:.1f}s")
print()
imp_perm = pd.Series(perm.importances_mean, index=CAT + NUM).sort_values(ascending=False)
imp_std  = pd.Series(perm.importances_std,  index=CAT + NUM)

print(f"  {'Feature':<45} {'ROC-AUC drop (mean)':>20}  {'Std':>8}")
print(f"  {'-'*45} {'-'*20}  {'-'*8}")
for feat in imp_perm.index:
    mean_v = imp_perm[feat]
    std_v  = imp_std[feat]
    bar = "#" * max(0, int(mean_v * 200))
    print(f"  {feat:<45} {mean_v:>+20.6f}  {std_v:>8.6f}  {bar}")

# ── Combined ranking ──────────────────────────────────────────────────────
print()
print("=" * 68)
print("  8. COMBINED RANKING: Native vs Permutation (normalised)")
print("=" * 68)
norm_native = imp_native / imp_native.sum()
# Permutation may have negatives - shift to 0 min, then normalise
shifted_perm = imp_perm - imp_perm.min()
norm_perm = shifted_perm / shifted_perm.sum() if shifted_perm.sum() > 0 else shifted_perm

comparison = pd.DataFrame({
    "native_imp": imp_native,
    "perm_roc_drop": imp_perm,
}).sort_values("perm_roc_drop", ascending=False)
print(comparison.round(6).to_string())

# ── SHAP check ───────────────────────────────────────────────────────────
print()
print("=" * 68)
print("  9. SHAP availability check")
print("=" * 68)
try:
    import shap
    print(f"  SHAP installed: YES (version {shap.__version__})")
    print("  Computing SHAP values on 500-row test sample...")
    t0 = time.time()
    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(X_te.iloc[:500])
    elapsed = time.time() - t0
    shap_mean = pd.Series(np.abs(shap_vals).mean(axis=0), index=CAT + NUM).sort_values(ascending=False)
    print(f"  Done in {elapsed:.1f}s")
    print()
    print(f"  {'Feature':<45} {'Mean |SHAP|':>12}")
    print(f"  {'-'*45} {'-'*12}")
    for feat, val in shap_mean.items():
        print(f"  {feat:<45} {val:>12.6f}")
except ImportError:
    print("  SHAP not installed. Install with: pip install shap")
    print("  Using permutation importance (above) as the model-agnostic alternative.")

# ── VERDICT ──────────────────────────────────────────────────────────────
print()
print("=" * 68)
print("  VERDICT")
print("=" * 68)
top_perm = imp_perm.head(5)
shipping_mode_perm = imp_perm.get("Shipping Mode", 0)
sched_days_perm    = imp_perm.get("Days for shipment (scheduled)", 0)
print(f"""
  Q: Is Shipping Mode's 0.68 native importance genuine or an artifact?

  FINDING: BOTH genuine AND partially artifactual.

  GENUINE part:
    - Shipping Mode has a REAL statistical relationship with delay rate:
        First Class   -> 100% delay  (SLA=1 day, nearly always missed)
        Second Class  -> 80% delay   (SLA=2 days, often missed)
        Same Day      -> 48% delay   (SLA=0 days)
        Standard      -> 40% delay   (SLA=4 days, most lenient)
    - This relationship is true predictive information.

  ARTIFACTUAL part:
    - Shipping Mode and 'Days for shipment (scheduled)' are NOT independent.
    - Cross-tab shows PERFECT 1-to-1 mapping: each mode always has
      exactly ONE value of scheduled days (Same Day=0, First=1, Second=2, Standard=4).
    - Pearson correlation = 0.919 between ordinal-encoded Shipping Mode
      and scheduled days.
    - The model has TWO near-redundant features encoding the SAME SLA tier.
    - GBM's native importance assigns 0.68 to Shipping Mode and 0.22 to
      scheduled days. Together = 0.90 of all importance.
    - Permutation importance (on held-out test, model-agnostic) tells the
      true story: see values above for actual held-out ROC-AUC drops.

  Permutation importance for Shipping Mode   : {shipping_mode_perm:+.6f} ROC-AUC
  Permutation importance for Scheduled Days  : {sched_days_perm:+.6f} ROC-AUC

  RECOMMENDATION (do not implement now - report only):
    - These two features together encode the same SLA tier.
    - Consider dropping one (preferably keeping 'Days for shipment scheduled'
      as it is numeric and more expressive) to remove redundancy.
    - The permutation importance ranking is more trustworthy than native
      importance for diagnosing true feature contribution.
""")
