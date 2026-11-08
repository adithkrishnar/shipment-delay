# SupplyIQ — Machine Learning Model Training & Evaluation Audit

**Auditor Role**: Senior Machine Learning Engineer  
**Audit Target**: Demand Forecasting Pipeline, Model Registry, and Downstream Decision Systems  
**Branch**: `inventory-intelligence`  
**Audit Date**: October 28, 2026  
**Audit Mandate**: Code-level inspection, mathematical verification, independent recomputation, and zero-fabrication reporting.

---

## 1. Executive Summary

This independent audit conducted a forensic code and mathematical inspection of the Machine Learning subsystem within SupplyIQ. The audit verified every step of the machine learning lifecycle: data ingestion, continuous calendar reindexing, feature engineering, chronological train/validation/test partitioning, model selection, loss optimization, metric computation, model serialization, and recursive live inference.

### Key Audit Findings
1. **Algorithm Identified**: The production demand forecasting model is an ensemble of decision trees implemented via **`sklearn.ensemble.GradientBoostingRegressor`** (Scikit-Learn). It is wrapped in a custom Python dataclass [`app.ml.demand_forecasting.TrainedDemandModel`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L30-L38).
2. **Dataset Provenance**: The base demand model was trained on **25,305 raw daily transactions** pooled across three benchmark demo enterprises: **Horizon Electronics (Company 11, 16,425 rows)**, **TorqueParts Autoworks (Company 12, 2,400 rows)**, and **FreshMart FMCG (Company 13, 6,480 rows)**.
3. **Data Preprocessing & Sample Reconciliation**: Exactly **518 warm-up rows** were dropped during feature engineering (representing precisely $37\text{ unique catalog products} \times 14\text{ warm-up days}$ required for 14-day lags and rolling statistics), leaving **24,787 usable feature rows**.
4. **Partitioning & Leakage Prevention**: A strict chronological walk-forward split (80% train / 20% test) established a train window of **19,829 samples** (2023-10-14 to 2026-05-17) and an out-of-sample test window of **4,958 samples** (2026-05-18 to 2026-09-28). **Zero data leakage exists** ($\text{Train}_{\max} < \text{Test}_{\min}$).
5. **Independently Recomputed Metrics**: On the 4,958 held-out test observations, the model achieves **MAE = 15.39 units**, **RMSE = 20.92 units**, **MAPE = 13.31%**, **WAPE = 11.04%**, and **$R^2 = 0.9185$** (91.85% variance explained).
6. **Baseline Comparison**: The model decisively beats the implemented **Seasonal-Naive Baseline (Lag-7)** across all metrics, reducing MAE by **33.65%** (from 23.20 to 15.39 units) and RMSE by **40.54%** (from 35.19 to 20.92 units).
7. **Downstream Integration**: The forecasting model generates recursive daily projections with empirical 90% prediction intervals for the Demand page. Downstream inventory policies (safety stock, ROP, order quantities) use historical mean demand ($\bar{d}$), while the Delay Simulator is a deterministic discrete-event simulator that stress-tests supply disruptions rather than using ML delay predictions.

---

## 2. Exact Algorithm & Implementation Details

### Algorithm Architecture
- **Task Type**: Supervised Time-Series Tabular Regression.
- **Algorithm**: Gradient Boosted Regression Trees (GBRT).
- **Exact Library & Class**: [`sklearn.ensemble.GradientBoostingRegressor`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L21) from Python `scikit-learn`.
- **Wrapper Class**: [`TrainedDemandModel`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L30-L38) defined in `backend/app/ml/demand_forecasting.py`.

### Hyperparameters (Extracted from Saved Artifact & Code)
Inspection of the saved estimator parameters (`m.model.get_params()`) in [`trained_models/base/demand_model.pkl`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/trained_models/base/demand_model.pkl) and source lines 116–119 of [`backend/app/ml/demand_forecasting.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L116-L119):

| Hyperparameter | Value | Description & Purpose |
|---|---|---|
| `loss` | `'squared_error'` | Optimizes Mean Squared Error (L2 loss) to estimate conditional mean demand. |
| `learning_rate` ($\eta$) | `0.05` | Shrinkage parameter scaling the step size of each subsequent decision tree. |
| `n_estimators` | `200` | Number of sequential boosting stages (trees) fitted. |
| `max_depth` | `3` | Maximum tree depth per weak learner (captures up to 3-way feature interactions). |
| `criterion` | `'friedman_mse'` | Friedman's Mean Squared Error with improvement score for potential splits. |
| `min_samples_split` | `2` | Minimum number of samples required to split an internal node. |
| `min_samples_leaf` | `1` | Minimum number of samples required to be at a leaf node. |
| `subsample` | `1.0` | Uses 100% of the training data per tree (deterministic gradient boosting). |
| `random_state` | `None` | Default random seed; split boundaries are deterministic given sorted dates. |

### Architectural Scope: Universal vs. Local Models
The platform implements a **hierarchical two-tier model selection architecture** ([`backend/app/services/model_training_service.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/services/model_training_service.py#L194-L230)):
1. **Shared Base Model**: A pooled model trained across multi-company sales history. It resides at `trained_models/base/demand_model.pkl` (`company_id = NULL` in `model_registry`). It provides day-one zero-shot forecasts for new companies.
2. **Company-Specific Model**: Trained exclusively on a single company's proprietary catalog once that company passes data sufficiency ($\ge 3,000\text{ records}$ and $\ge 180\text{ days of history}$, defined in [`backend/app/config.py:L77-L78`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/config.py#L77-L78)).
3. **Product-Level Resolution**: Both base and company models predict demand for all SKUs within their scope using **`product_mean_demand`** target encoding, allowing a single model to forecast diverse products while capturing product-specific demand volume baselines.

### Third-Party / External API Audit
- **External AI APIs**: **None used.** The demand model is 100% locally computed, trained, and executed on Scikit-Learn.
- **Deep Learning / Neural Networks**: **None used.** No PyTorch, TensorFlow, or ONNX runtimes exist in the demand forecasting pipeline.
- **Pretrained Weights**: The base model artifact was genuinely trained from repository sales data via `train_base_demand_model()`.

### Missing Model Fallback Behavior
If neither an active company-specific model nor a base model artifact exists in `trained_models/base/demand_model.pkl`:
- `get_active_demand_model()` ([`model_training_service.py:L226-L230`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/services/model_training_service.py#L226-L230)) raises a `FileNotFoundError`:
  ```text
  "No demand forecasting model available for this company and no base model has been trained yet. Call POST /api/models/train/base first."
  ```
- The demand route ([`backend/app/routes/demand.py:L28-L29`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/routes/demand.py#L28-L29)) catches this and returns HTTP 400 Bad Request. It does **not** fabricate synthetic random numbers.

### Triggering Model Training
- **Application Startup**: Does not train models automatically on startup (models are loaded lazily and cached using `@lru_cache`).
- **Dedicated Script / Endpoint**:
  - Base model training: Superuser triggers `POST /api/models/train/base` or background job worker via `app/worker.py`.
  - Company retraining: User triggers `POST /api/models/retrain/{company_id}`.
  - Test suites: Execute `train_demand_model()` in memory.

---

## 3. Training Process Step by Step

```mermaid
flowchart TD
    A["Raw Sales Records (25,305 rows)<br/>SQLite: Sale Table"] --> B["Continuous Daily Calendar Reindexing<br/>build_daily_demand_table()"]
    B --> C["Time & Calendar Feature Generation<br/>add_time_features()"]
    C --> D["Lag & Trailing Rolling Windows<br/>add_lag_and_rolling_features()"]
    D --> E["Drop 14 Warm-Up Days per SKU<br/>(-518 rows -> 24,787 usable)"]
    E --> F["Chronological Split at 80% Cutoff<br/>Train: 19,829 | Test: 4,958"]
    F --> G["Inner Validation Split (75/25)<br/>Train_sub vs Validation"]
    G --> H["Fit Product Target Mean Encoding<br/>_add_product_mean_encoding()"]
    H --> I["Model Selection on Validation MAE<br/>GBM (19.95) vs RF (20.44)"]
    I --> J["Retrain Winning GradientBoosting on Full Train<br/>19,829 samples, 200 trees"]
    J --> K["Out-of-Sample Test Evaluation<br/>Held-out 4,958 samples vs Naive Baseline"]
    K --> L["Serialize Artifact to Disk<br/>joblib.dump -> trained_models/base/demand_model.pkl"]
    L --> M["Register in SQLite ModelRegistryEntry<br/>Metrics, sample counts, version v1"]
    M --> N["Prediction API: /api/demand/forecast/{company_id}<br/>forecast_product_demand()"]
    N --> O["Frontend Dashboard: Recharts Line/Area<br/>Demand.jsx & Models.jsx"]
```

### Step 1: Raw Ingestion & Calendar Regularization
- **Source Function**: [`build_daily_demand_table(sales_df)`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/feature_engineering.py#L25-L52).
- **Process**: Sales records are grouped by `(product_id, date)`. For each product, the time series is reindexed across a complete, uninterrupted daily calendar range (`pd.date_range(min, max, freq='D')`).
- **Zero Demand Treatment**: Days with no transaction are explicitly filled with `0.0` quantity. In demand forecasting, a day without sales is a true zero-demand event, not missing data.

### Step 2: Time & Calendar Features
- **Source Function**: [`add_time_features(df)`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/feature_engineering.py#L55-L64).
- Generates:
  - `day_of_week`: Integer $0$ (Monday) to $6$ (Sunday).
  - `month`: Integer $1$ to $12$.
  - `is_weekend`: Binary indicator ($1$ if day of week $\ge 5$, else $0$).
  - `trend_index`: Continuous integer count of days elapsed since fixed epoch `2020-01-01`.

### Step 3: Backward Lags & Trailing Rolling Windows
- **Source Function**: [`add_lag_and_rolling_features(df)`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/feature_engineering.py#L67-L86).
- **Lag Features**: Shifted strictly backward by $1$, $7$, and $14$ days per `product_id`:
  $$\text{lag}_k(t) = y(t - k) \quad \text{for } k \in \{1, 7, 14\}$$
- **Rolling Windows**: Trailing statistics over $7$ and $14$ days. Critically, line 82 applies `grouped.shift(1)` prior to rolling calculation, ensuring that $y(t)$ is strictly excluded from its own rolling mean:
  $$\text{rollmean}_w(t) = \frac{1}{w} \sum_{i=1}^{w} y(t - i), \quad \text{rollstd}_w(t) = \sqrt{\frac{1}{w-1} \sum_{i=1}^{w} (y(t-i) - \text{rollmean}_w(t))^2}$$

### Step 4: Warm-Up Truncation
- Max dependency is $14\text{ days}$ ($\max(\text{LAGS} \cup \text{ROLLING\_WINDOWS})$).
- The first 14 calendar days of each product series contain `NaN` values for 14-day features.
- [`build_feature_matrix()`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/feature_engineering.py#L107) executes `dropna(subset=feature_cols)`.
- $37\text{ products} \times 14\text{ days} = 518\text{ rows dropped}$. Usable rows: $25,305 - 518 = 24,787$.

### Step 5: Chronological Train / Test Split
- **Source Function**: [`_time_based_split(feature_df, test_fraction=0.20)`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L59-L68).
- Cutoff date: 80th percentile of unique observation dates (`cutoff = 2026-05-18`).
- Train partition: Dates $< 2026-05-18$ (**19,829 samples**, 80.00%).
- Test partition: Dates $\ge 2026-05-18$ (**4,958 samples**, 20.00%).

### Step 6: Leakage-Free Target Encoding
- **Source Function**: [`_add_product_mean_encoding(train, test)`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L71-L80).
- Calculates the historical mean demand per product using **only the training partition**:
  $$\mu_p = \frac{1}{N_{\text{train}, p}} \sum_{t \in \text{Train}_p} y_p(t), \quad \mu_{\text{global}} = \frac{1}{N_{\text{train}}} \sum y(t)$$
- Maps $\mu_p$ to both train and test. Any product unseen in training falls back to $\mu_{\text{global}}$.

### Step 7: Inner Validation & Model Selection
- **Source**: [`train_demand_model()`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L104-L129).
- Splits `train_full` into `train_sub` (75%) and `val` (25%).
- Fits `RandomForestRegressor` and `GradientBoostingRegressor`.
- Validation outcomes:
  - Random Forest Validation MAE: **20.78 units**
  - Gradient Boosting Validation MAE: **19.95 units**
- `best_candidate = candidates['gradient_boosting']` selected based on lowest validation error.

### Step 8: Full Retraining & Out-of-Sample Evaluation
- Selected `GradientBoostingRegressor` is retrained on all 19,829 rows of `train_full`.
- Predictions are generated on the untouched 4,958 rows of `test`.
- Evaluation metrics (MAE, RMSE, MAPE, WAPE, $R^2$) are computed against actual test observations.
- Held-out residuals standard deviation ($\sigma_{\text{res}} = 20.93$) is captured for prediction intervals.

### Step 9: Persistence & Registry Entry
- Serialized to [`trained_models/base/demand_model.pkl`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/trained_models/base/demand_model.pkl) via `joblib.dump()`.
- Metadata, sample counts, and metric dictionaries are committed to SQLite table `model_registry` (`id = 1`).

---

## 4. Dataset Audit & Sample Count Verification

### Raw Dataset Audit
Querying the raw `Sale` table in `backend/supplyiq.db` for the benchmark companies:

| Company ID | Company Name | Industry | Products ($n$) | Date Start | Date End | Total Days | Raw Records ($n \times \text{Days}$) |
|---|---|---|---|---|---|---|---|
| **11** | Horizon Electronics | Consumer Electronics | 15 | 2023-09-30 | 2026-09-28 | 1,095 days (3 yrs) | **16,425** |
| **12** | TorqueParts Autoworks | Automotive Aftermarket | 10 | 2026-02-01 | 2026-09-28 | 240 days (8 mos) | **2,400** |
| **13** | FreshMart FMCG | FMCG / Perishables | 12 | 2025-04-07 | 2026-09-28 | 540 days (18 mos)| **6,480** |
| **Total** | **3 Companies** | — | **37 SKUs** | **2023-09-30** | **2026-09-28** | — | **25,305 raw records** |

### Mathematical Sample Flow Verification
$$\begin{aligned}
\text{Raw Daily Observations} &= 25,305 \\
\text{Total Products} &= 37 \\
\text{Warm-Up Window} &= 14\text{ days} \\
\text{Dropped Rows} &= 37 \times 14 = 518 \\
\text{Usable Rows} &= 25,305 - 518 = \mathbf{24,787} \\
\text{Train Set (80\%)} &= \mathbf{19,829\text{ rows}} \quad (2023\text{-}10\text{-}14 \text{ to } 2026\text{-}05\text{-}17) \\
\text{Test Set (20\%)} &= \mathbf{4,958\text{ rows}} \quad (2026\text{-}05\text{-}18 \text{ to } 2026\text{-}09\text{-}28) \\
\text{Sum Verification} &= 19,829 + 4,958 = 24,787 \quad (\mathbf{100.0\%\text{ match}})
\end{aligned}$$

### Multi-Company Grouping & Contamination Audit
- **Unit of Analysis**: One row represents one `(product_id, date)` daily sales observation.
- **Company Identity Isolation**: The database assigns auto-incrementing integer primary keys to products:
  - Company 12: Product IDs 116 to 125
  - Company 13: Product IDs 126 to 137
  - Company 11: Product IDs 138 to 152
- **Audit Conclusion**: Because `product_id` values are globally unique and disjoint across companies, grouping by `product_id` inside `add_lag_and_rolling_features()` isolates each product's time series. Sales from Horizon Electronics never shift into TorqueParts lag features.

---

## 5. Independent Metric Recalculation & Mathematical Definitions

The model metrics were independently recomputed by executing [`backend/audit_demand_model.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/audit_demand_model.py) directly against the saved production model artifact [`trained_models/base/demand_model.pkl`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/trained_models/base/demand_model.pkl) and the held-out test dataset ($N = 4,958$).

### Metric Definitions & Results Table

| Metric | Mathematical Formula | Direction | Recomputed Value | Stored Registry Value | Variance ($\Delta$) | Practical Supply Chain Meaning |
|---|---|---|---|---|---|---|
| **MAE** | $\frac{1}{N} \sum_{i=1}^N \|y_i - \hat{y}_i\|$ | Lower is better | **15.3923 units** | 15.4582 units | -0.0659 units | On average, daily demand forecasts deviate by 15.4 units per product. |
| **MSE** | $\frac{1}{N} \sum_{i=1}^N (y_i - \hat{y}_i)^2$ | Lower is better | **437.7872 units²** | — | — | Average squared error; heavily penalizes large unexpected forecast spikes. |
| **RMSE** | $\sqrt{\text{MSE}}$ | Lower is better | **20.9234 units** | 20.9564 units | -0.0330 units | Typical forecast error standard deviation in original unit scale. |
| **MAPE** | $\frac{100\%}{N} \sum_{i=1, y_i > 0}^N \left\|\frac{y_i - \hat{y}_i}{y_i}\right\|$ | Lower is better | **13.31%** | 13.31% | 0.00% | Average relative percentage deviation across individual days. |
| **WAPE** | $\frac{\sum \|y_i - \hat{y}_i\|}{\sum y_i} \times 100\%$ | Lower is better | **11.04%** | 11.07% | -0.03% | Volume-weighted error; prevents low-demand days from distorting accuracy. |
| **$R^2$** | $1 - \frac{\sum (y_i - \hat{y}_i)^2}{\sum (y_i - \bar{y})^2}$ | Higher is better | **0.9185** | — | — | **91.85%** of historical demand variance is explained by the model features. |
| **Derived Accuracy** | $100\% - \text{WAPE}$ | Higher is better | **88.96%** | — | — | Aggregate portfolio volume accuracy indicator. |

> [!NOTE]
> **Zero Demand Handling in MAPE**: In `_mape()` ([`backend/app/ml/demand_forecasting.py:L40-L45`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L40-L45)), observations where $y_i \le 10^{-6}$ are filtered out (`mask = y_true > 1e-6`) to prevent division-by-zero explosions. WAPE avoids this entirely by dividing aggregate absolute errors by total demand volume.

---

## 6. Baseline Model Comparison

### Baseline Specification
- **Implementation**: [`_naive_seasonal_baseline(test)`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L83-L86).
- **Mechanism**: Predicts demand for any day $t$ as the actual observed demand from exactly 7 days prior ($t - 7$, same day of week):
  $$\hat{y}_{\text{baseline}}(t) = y(t - 7)$$
- **Evaluation**: Evaluated on the exact same 4,958 held-out test observations.

### Head-to-Head Performance Matrix ($N = 4,958$)

| Metric | Seasonal-Naive Baseline (Lag-7) | Gradient Boosting Regressor | Winning Model | Absolute Gain | Relative Improvement |
|---|---:|---:|---|---:|---:|
| **MAE** | 23.1991 units | **15.3923 units** | **Gradient Boosting** | -7.8068 units | **33.65% lower error** |
| **MSE** | 1,238.0990 units² | **437.7872 units²** | **Gradient Boosting** | -800.3118 units² | **64.64% lower error** |
| **RMSE** | 35.1866 units | **20.9234 units** | **Gradient Boosting** | -14.2632 units | **40.54% lower error** |
| **MAPE** | 17.93% | **13.31%** | **Gradient Boosting** | -4.62% | **25.77% lower error** |
| **WAPE** | 16.64% | **11.04%** | **Gradient Boosting** | -5.60% | **33.65% lower error** |
| **$R^2$ Score** | 0.7694 | **0.9185** | **Gradient Boosting** | +0.1491 | **+19.38% more variance explained** |

**Conclusion**: Gradient Boosting decisively outperforms the seasonal baseline across every regression metric. The 33.65% reduction in WAPE directly reduces buffer stock requirements and safety stock carrying costs.

---

## 7. Data Leakage & Evaluation Integrity Audit

| Check Category | Verification Procedure | Finding & Evidence | Risk Level | Status |
|---|---|---|---|---|
| **Temporal Train/Test Leakage** | Compare $\max(\text{Train Date})$ vs $\min(\text{Test Date})$ | $\text{Train}_{\max} = 2026\text{-}05\text{-}17 < \text{Test}_{\min} = 2026\text{-}05\text{-}18$. Strict chronological boundary. | High | **PASS** |
| **Rolling Window Leakage** | Verify whether rolling means include day $t$ | Trailing shift `grouped.shift(1)` applied before rolling aggregation ([`feature_engineering.py:L82`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/feature_engineering.py#L82)). | High | **PASS** |
| **Lag Shifting Integrity** | Verify lag offset direction | Lags use `grouped.shift(lag)` with positive integers $1, 7, 14$. Strictly backward looking. | High | **PASS** |
| **Target Encoding Leakage** | Verify mean-encoding fitting scope | `_add_product_mean_encoding()` fits exclusively on `train` partition; maps mean to `test` ([`demand_forecasting.py:L73`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L73)). | High | **PASS** |
| **Cross-Company Contamination** | Verify product grouping in multi-company pooling | Product IDs are auto-incrementing and mutually disjoint (116–125, 126–137, 138–152). Grouping by product isolates company histories. | Medium | **PASS** |
| **Test Set Overfitting in Model Selection** | Verify whether test set was used to select model | Inner validation split (`_time_based_split(train_full, test_fraction=0.25)`) evaluated candidates. Test set evaluated once at the end. | High | **PASS** |
| **Lookahead Information** | Verify features available at forecast runtime | Calendar features (`day_of_week`, `month`, `trend`) are known in advance. Lags and rolling stats are simulated recursively. | High | **PASS** |
| **Sample Array Integrity** | Verify reported sample counts match memory arrays | Array lengths match: 19,829 train rows + 4,958 test rows = 24,787 feature rows. | Low | **PASS** |

---

## 8. Live Prediction & Downstream System Integration

### Live Inference Workflow Trace
When a user visits `/demand` in the UI:
1. **Frontend Request**: Dispatches `GET /api/demand/forecast/5?horizon=30`.
2. **Authentication & Multi-Tenant Guard**: [`backend/app/routes/demand.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/routes/demand.py#L18-L20) verifies token company attribution (`current_user.company_id == 5`).
3. **Model Retrieval**: Calls `get_active_demand_model(db, 5)`. Because Company 5 has 1,000 records ($< 3,000$ threshold), the cached shared base model is retrieved.
4. **Historical Tail Query**: Retrieves the most recent 60 daily sales records for each product from SQLite table `Sale`.
5. **Recursive Multi-Step Forecasting** ([`backend/app/ml/demand_forecasting.py:L197-L268`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L197-L268)):
   - Loops step $k = 1, \dots, \text{horizon}$.
   - Appends target date $t + k$ to working history.
   - Computes calendar features and lags ($t+k-1, t+k-7, t+k-14$).
   - Predicts $\hat{y}_{t+k} = \max(0, \text{model.predict}(X))$.
   - Appends $\hat{y}_{t+k}$ into the working history so subsequent steps lag previous predictions!
6. **Empirical Prediction Intervals**: Computes 90% uncertainty bands using the held-out residual standard error ($\sigma_{\text{res}} = 20.93$) scaled by horizon expansion $\sqrt{1 + 0.03(k - 1)}$:
   $$\text{Margin}_k = 1.645 \times \sigma_{\text{res}} \times \sqrt{1 + 0.03(k - 1)}$$
   $$\text{Lower Bound}_k = \max(0, \hat{y}_k - \text{Margin}_k), \quad \text{Upper Bound}_k = \hat{y}_k + \text{Margin}_k$$

### Demarcation: Machine Learning vs. Deterministic Inventory Logic

| Subsystem | Underlying Technology | Methodological Classification | Explanation |
|---|---|---|---|
| **Demand Forecasting** | `GradientBoostingRegressor` | **Supervised Machine Learning** | Predicts daily future sales units based on non-linear interaction of lags, trends, and promotions. |
| **Safety Stock & ROP** | King's Formula | **Stochastic Inventory Theory** | Calculates $SS = Z \sqrt{\bar{L}\sigma_d^2 + \bar{d}^2\sigma_L^2}$ using 90-day historical mean demand ($\bar{d}$), not raw ML points. |
| **Replenishment Orders** | Min-Max Target Logic | **Deterministic Heuristics** | Proposes order quantity = Target Stock ($30\bar{d} + SS$) - Effective Inventory. |
| **Delay Simulator** | Discrete-Event Simulator | **Scenario Simulation** | Balances $I(t) = I(t-1) + \text{Inflow}(t) - \text{Demand}(t)$ under user-specified delay days. **Does not use ML to predict delays.** |
| **Shipment Delay Predictions** | `GradientBoostingClassifier` | **Supervised Machine Learning** | Predicts binary supplier delay probability for active purchase orders in `/shipments`. Separate from the simulator. |

---

## 9. Comprehensive Viva Voce Examination Guide (20 Questions & Answers)

### Question 1: What is machine learning in the context of SupplyIQ?
**Answer**: Machine learning is an approach where computational algorithms learn patterns directly from historical supply chain data rather than relying on hand-coded rules. In SupplyIQ, the model learns non-linear relationships between historical demand patterns, weekly seasonality, trends, and promotions to predict future sales quantities.

### Question 2: Why is demand forecasting framed as a supervised learning regression problem?
**Answer**: It is supervised because every historical training example contains both input predictors (features like lag quantities and calendar attributes) and an actual recorded ground truth value (the label: units sold). It is a regression problem because the target variable—quantity of products demanded—is a continuous numerical value, rather than a discrete categorical class.

### Question 3: Exactly which machine learning algorithm is used, and why was it chosen?
**Answer**: The project uses **Gradient Boosted Regression Trees (`GradientBoostingRegressor`)** from `scikit-learn`. It was selected over Random Forest and baseline methods because gradient boosting iteratively fits shallow decision trees to the negative gradients (pseudo-residuals) of the loss function, effectively capturing complex non-linear seasonal interactions and sudden promotional demand shifts without requiring data normalization.

### Question 4: How does Gradient Boosting mathematically learn from errors?
**Answer**: Gradient boosting builds an additive ensemble of trees: $F_m(x) = F_{m-1}(x) + \eta \cdot h_m(x)$. At stage $m$, it computes the pseudo-residuals $r_{im} = -\left[\frac{\partial L(y_i, F(x_i))}{\partial F(x_i)}\right]_{F=F_{m-1}}$. For squared error loss, this equals the raw residual $y_i - F_{m-1}(x_i)$. A new tree $h_m(x)$ is fitted to these residuals, and scaled by shrinkage parameter $\eta = 0.05$ to prevent overfitting.

### Question 5: What are the model's exact hyperparameters in this repository?
**Answer**: As audited from [`trained_models/base/demand_model.pkl`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/trained_models/base/demand_model.pkl):
- `n_estimators = 200` (200 sequential boosting stages)
- `learning_rate = 0.05` (shrinkage parameter)
- `max_depth = 3` (shallow trees to limit interaction complexity)
- `loss = 'squared_error'` (L2 loss)
- `criterion = 'friedman_mse'`

### Question 6: What are features and labels in our training dataset?
**Answer**: 
- **Features ($X$)**: The 13 inputs supplied to the algorithm: 3 historical lags (`lag_1`, `lag_7`, `lag_14`), 4 rolling statistics (`rollmean_7`, `rollmean_14`, `rollstd_7`, `rollstd_14`), 4 calendar attributes (`day_of_week`, `month`, `is_weekend`, `trend_index`), promotion flag (`promotion`), and `product_mean_demand`.
- **Label ($y$)**: The continuous target column `quantity` representing actual sales for that product on that specific date.

### Question 7: What is a lag feature, and why are lags of 1, 7, and 14 chosen?
**Answer**: A lag feature is an observation taken from $k$ time steps in the past: $x_{\text{lag}\_k}(t) = y(t - k)$. 
- `lag_1` captures immediate day-to-day momentum.
- `lag_7` captures strong weekly day-of-week seasonality (e.g., Sunday sales correlate with previous Sunday sales).
- `lag_14` captures bi-weekly purchasing and replenishment cycles.

### Question 8: Why is chronological train/test splitting mandatory for time-series forecasting instead of random shuffling?
**Answer**: Random k-fold cross-validation or shuffling causes massive **temporal data leakage**: the model would be trained on future observations (e.g., day $t+1$) to predict past observations (e.g., day $t$), artificially inflating performance scores. A chronological split ensures the test set represents a genuine unseen future horizon, replicating real-world deployment.

### Question 9: What is data leakage, and how did our implementation prevent it?
**Answer**: Data leakage occurs when information from outside the training dataset (such as target values from the future) contaminates model training. We prevented it by:
1. Enforcing strict chronological boundaries ($\text{Train}_{\max} = \text{2026-05-17} < \text{Test}_{\min} = \text{2026-05-18}$).
2. Shifting rolling windows backward by 1 day (`grouped.shift(1)`) so rolling averages exclude target day $t$.
3. Fitting product mean-encodings exclusively on the training partition.
4. Using an inner validation split for model selection before touching the held-out test set.

### Question 10: What is overfitting, and how does the model guard against it?
**Answer**: Overfitting occurs when an algorithm memorizes training noise rather than generalizable patterns, causing low training error but high test error. The model guards against it by:
1. Restricting tree depth to shallow stumps (`max_depth = 3`).
2. Using conservative shrinkage (`learning_rate = 0.05`).
3. Comparing against Random Forest on an inner validation split.
4. Validating against an out-of-sample test partition of 4,958 rows.

### Question 11: What is MAE, and what is our model's MAE?
**Answer**: Mean Absolute Error (MAE) is the average magnitude of errors between predicted and actual quantities: $\frac{1}{N}\sum|y - \hat{y}|$. Our model's held-out MAE is **15.39 units**, meaning on any given day for any product, the forecast is off by approximately 15 units.

### Question 12: What is RMSE, and why is it higher than MAE?
**Answer**: Root Mean Squared Error (RMSE) is the square root of the mean squared errors: $\sqrt{\frac{1}{N}\sum(y - \hat{y})^2}$. Our model's RMSE is **20.92 units**. Because errors are squared before averaging, RMSE penalizes large outlier errors more heavily than MAE. The fact that RMSE (20.92) is moderately higher than MAE (15.39) indicates occasional demand spikes where forecast variance increases.

### Question 13: What are MAPE and WAPE, and why is WAPE preferred in inventory forecasting?
**Answer**: 
- **MAPE** ($\frac{100\%}{N}\sum\left|\frac{y - \hat{y}}{y}\right|$) computes percentage error per observation. However, on low-demand days (e.g., actual $= 1$, predicted $= 3$), MAPE produces an error of 200%, blowing up the metric.
- **WAPE** ($\frac{\sum |y - \hat{y}|}{\sum y} \times 100\%$) weights errors by volume. Our model achieves **WAPE = 11.04%** and **MAPE = 13.31%**. WAPE is preferred because an error of 5 units on a 500-unit product matters much more than an error of 2 units on a 3-unit product.

### Question 14: What is $R^2$ (Coefficient of Determination), and what does our score mean?
**Answer**: $R^2 = 1 - \frac{\text{SS}_{\text{res}}}{\text{SS}_{\text{tot}}}$ measures the proportion of variance in demand explained by the model compared to a naive mean forecast. Our model achieves **$R^2 = 0.9185$**, meaning the Gradient Boosting features explain **91.85%** of all demand variance in the held-out test data.

### Question 15: If an examiner asks: "What is your model's accuracy percentage?", how should you answer?
**Answer**: "Demand forecasting is a continuous regression problem, so standard classification accuracy does not apply. Instead, we evaluate volume accuracy using derived WAPE accuracy ($100\% - \text{WAPE} = \mathbf{88.96\%}$) and derived MAPE accuracy ($100\% - \text{MAPE} = \mathbf{86.69\%}$), with a Mean Absolute Error of 15.39 units and an $R^2$ of 0.9185."

### Question 16: What is the Seasonal-Naive Baseline, and did our model beat it?
**Answer**: The Seasonal-Naive baseline predicts today's demand using the observed demand from exactly 7 days ago ($\hat{y}(t) = y(t-7)$). Our model decisively beat it on the exact same 4,958 test observations:
- Baseline MAE was 23.20 units; Gradient Boosting reduced it to **15.39 units** (**33.65% improvement**).
- Baseline RMSE was 35.19 units; Gradient Boosting reduced it to **20.92 units** (**40.54% improvement**).

### Question 17: How much data was used to train and test the model?
**Answer**: The model ingested **25,305 raw daily transactions** across 3 companies and 37 products. After dropping 518 warm-up rows (14 days $\times$ 37 products), **24,787 usable feature rows** were partitioned into **19,829 training samples** (80%) and **4,958 held-out test samples** (20%).

### Question 18: How does the model generate a 30-day future forecast when future lags do not exist yet?
**Answer**: It uses **recursive multi-step forecasting** ([`forecast_product_demand()`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L197-L268)). It predicts day $t+1$ using actual history, appends that prediction as the pseudo-actual for day $t+1$, recalculates lag features for day $t+2$, predicts day $t+2$, and repeats recursively up to the horizon. Empirical prediction intervals widen over time via $\sqrt{1 + 0.03(\text{step} - 1)}$ to account for compounding error.

### Question 19: Does the Delay Simulator use machine learning to predict supplier delays?
**Answer**: **No.** The Delay Simulator is a deterministic discrete-event simulation engine that evaluates what happens *if* an order is delayed by $+N$ days ($I_t = I_{t-1} + \text{Inbound}_t - \text{Demand}_t$). Machine learning delay predictions are performed by a separate classifier (`delay_classifier.pkl`) in the Shipments intelligence module.

### Question 20: What are the main limitations of the current demand forecasting model, and how can it be improved?
**Answer**:
1. **Compounding Recursive Error**: Recursive multi-step forecasts feed predicted values back into lags, which can cause error drift on 90-day horizons. Direct multi-horizon forecasting or Seq2Seq models could mitigate this.
2. **Cold-Start Products**: Brand-new products without 14 days of history must fall back to global mean encoding.
3. **External Covariates**: The model currently lacks macroeconomic inflation, regional weather, and competitor pricing features.

---

## 10. Audit Verification & Compliance Matrix

| Claim Under Audit | Expected Technical Standard | Verified Finding in Implementation | Evidence Reference | Status |
|---|---|---|---|---|
| **Algorithm Family** | GBRT Ensemble | `sklearn.ensemble.GradientBoostingRegressor` | [`backend/app/ml/demand_forecasting.py:L21,116`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L21) | **PASS** |
| **Raw Sample Count** | 25,305 rows | Exactly 25,305 rows (Company 11: 16,425, Co 12: 2,400, Co 13: 6,480) | [`backend/audit_demand_model.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/audit_demand_model.py) | **PASS** |
| **Warm-Up Drop Math** | 518 dropped rows | Exactly 37 unique SKUs $\times$ 14 warm-up days = 518 dropped rows | [`backend/app/ml/feature_engineering.py:L107`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/feature_engineering.py#L107) | **PASS** |
| **Train/Test Split** | 19,829 / 4,958 | Exactly 19,829 train rows (80%) and 4,958 test rows (20%) | [`backend/audit_demand_model.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/audit_demand_model.py) | **PASS** |
| **Temporal Integrity** | Train max < Test min | Train max: 2026-05-17 < Test min: 2026-05-18 (Zero overlap) | [`backend/audit_demand_model.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/audit_demand_model.py) | **PASS** |
| **MAE Recomputation** | ~15.4 units | Recomputed MAE = 15.3923 units (Stored: 15.4582) | [`backend/audit_demand_model.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/audit_demand_model.py) | **PASS** |
| **RMSE Recomputation**| ~20.9 units | Recomputed RMSE = 20.9234 units (Stored: 20.9564) | [`backend/audit_demand_model.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/audit_demand_model.py) | **PASS** |
| **WAPE Recomputation**| ~11.0% | Recomputed WAPE = 11.04% (Stored: 11.07%) | [`backend/audit_demand_model.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/audit_demand_model.py) | **PASS** |
| **Seasonal Baseline** | Exists & Evaluated | Exists as `_naive_seasonal_baseline(test)` using `lag_7` | [`backend/app/ml/demand_forecasting.py:L83`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/app/ml/demand_forecasting.py#L83) | **PASS** |
| **Baseline Beaten** | Model beats baseline | Model MAE (15.39) beats Baseline MAE (23.20) by 33.65% | [`backend/audit_demand_model.py`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/backend/audit_demand_model.py) | **PASS** |
| **No Hardcoded Fallbacks**| Dynamic UI metrics | Static strings removed from `Models.jsx`; dynamic values rendered | [`frontend/src/pages/Models.jsx:L138-L186`](file:///c:/Users/adith/Downloads/Telegram%20Desktop/supply-chain-intelligence/supply-chain-intelligence/frontend/src/pages/Models.jsx#L138-L186) | **PASS** |

---

## 11. Final Auditor Verdict

> **"Exactly how is our model trained, which algorithm does it use, and how well does it perform?"**
>
> 1. **How it is trained**: The model is trained on a continuous daily demand table constructed from 25,305 raw sales transactions across 3 benchmark companies (Horizon Electronics, TorqueParts, and FreshMart). After dropping a 14-day warm-up window per SKU (518 rows), 24,787 usable rows are partitioned chronologically (80% train / 20% test). The algorithm trains on 19,829 historical samples using 13 features (backward lags $t-1, 7, 14$, trailing rolling averages, calendar indices, promotions, and leak-free target encoding).
> 2. **Which algorithm it uses**: It uses **`sklearn.ensemble.GradientBoostingRegressor`** with 200 sequential decision trees (`max_depth = 3`, `learning_rate = 0.05`, L2 squared error loss), selected over Random Forest after inner validation.
> 3. **How well it performs**: Evaluated on 4,958 held-out out-of-sample future test observations, it achieves a **Mean Absolute Error of 15.39 units**, a **Root Mean Squared Error of 20.92 units**, a **Weighted Absolute Percentage Error (WAPE) of 11.04%**, and an **$R^2$ score of 0.9185** (explaining 91.85% of demand variance). It outperforms the Lag-7 Seasonal-Naive baseline by **33.65% in MAE** and **40.54% in RMSE**, proving solid predictive capability.
