# SupplyIQ Inventory Intelligence — Model & Forecasting Methodology

## 1. Overview
The SupplyIQ demand forecasting engine produces forward-looking demand estimates across multiple horizons ($H \in \{7, 30, 60, 90\}$ days) to drive safety stock calculations, reorder points, and simulation trajectories.

## 2. Leakage-Free Feature Engineering
To avoid target leakage, all time-series features are generated chronologically:
1. **Daily Continuous Reindexing**: Any date missing sales is explicitly assigned a demand of `0.0`. Gaps are never dropped or silently omitted.
2. **Lag Features**: $S_{t-1}, S_{t-7}, S_{t-14}$ (prior day, same weekday last week, two weeks prior).
3. **Rolling Trailing Windows**:
   - 7-day trailing mean: $\frac{1}{7} \sum_{k=1}^7 S_{t-k}$ (current day $t$ is strictly excluded via `shift(1)`).
   - 14-day trailing mean & standard deviation.
4. **Calendar Features**: Day-of-week (0-6), Month (1-12), Weekend indicator (binary).
5. **Known Future Features**: Planned promotional indicators for day $t$.

## 3. Training & Validation Strategy
1. **Chronological Splitting**: Shuffling is strictly disallowed. The dataset is split into chronological Train (earlier 80%) and Test (latest 20%) partitions.
2. **Preprocessing Fit**: Categorical encoders and scalers are fitted exclusively on the Train partition and applied to the Test partition.
3. **Candidate Models Evaluated**:
   - **Seasonal Naive Baseline**: Predicts $S_t = S_{t-7}$ (last week's same weekday).
   - **Random Forest Regressor**: 100 estimators, max depth 12.
   - **LightGBM Regressor**: Gradient boosting with histogram-based split finding.
4. **Model Selection**: The model that achieves the lowest out-of-sample Mean Absolute Error (MAE) is registered as the active model.

## 4. Evaluation Metrics
- **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{N} \sum_{t=1}^N |y_t - \hat{y}_t|$$
- **Root Mean Squared Error (RMSE)**:
  $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{t=1}^N (y_t - \hat{y}_t)^2}$$
- **Weighted Absolute Percentage Error (WAPE)**:
  $$\text{WAPE} = \frac{\sum_{t=1}^N |y_t - \hat{y}_t|}{\sum_{t=1}^N y_t}$$
  Avoids division-by-zero errors inherent in MAPE when daily sales are zero.

## 5. Company Personalization & Thresholds
- **Data Sufficiency Threshold**:
  - `MIN_RECORDS_FOR_COMPANY_MODEL`: 3,000 historical sales transactions.
  - `MIN_HISTORY_DAYS_FOR_COMPANY_MODEL`: 180 continuous calendar days.
- **Serving Fallback**: If a company has insufficient records, the platform serves forecasts using the pooled Base Model and returns an explicit `model_source: "BASE"` tag, informing the user that personalized retraining will unlock once volume targets are met.
