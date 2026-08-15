# SupplyIQ — Supply Chain Intelligence Platform

A multi-company supply-chain intelligence system: companies upload their own
historical sales, inventory, shipment, and supplier data; the platform predicts
demand, shipment delays, and inventory risk; propagates that risk into
financial impact; and recommends what to do about it.

**Build status:** Phases 1–5 are complete and tested (74 passing tests).
See "Roadmap status" below.

---

## Quick start

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Optional: copy the env template (the app runs fine with all defaults)
cp ../.env.example .env

# Generate the 3 built-in demo companies (Horizon Electronics, TorqueParts
# Autoworks, FreshMart FMCG) with realistic synthetic data
python ../scripts/generate_demo_data.py

# Run the API
python run.py
# -> http://127.0.0.1:8000
# -> interactive API docs at http://127.0.0.1:8000/docs
```

### Run tests

```bash
cd backend
./venv/bin/python -m pytest tests/ -v
```

74 tests currently cover: health check, demo data generation (including that
shipment delays correlate with supplier reliability and inventory never goes
negative), column-mapping fuzzy matching, data quality validation, the full
upload → validate → map → import API pipeline, feature-engineering leakage
checks (both demand and shipment), demand-model and shipment-delay-model
training/evaluation, recursive multi-horizon forecasting, and the
base-vs-company-specific model selection logic end to end via the API for
both demand and shipment models.

### Frontend

The React + Vite frontend is fully implemented and wired to the backend API. It includes dashboards for shipments, demand, inventory, anomaly detection, suppliers, what-if simulations, and recommendations.

---

## What's implemented so far

### Multi-company architecture
Every company's products, suppliers, warehouses, sales, inventory, and
shipments are scoped by `company_id`. Verified by test:
`test_companies_endpoint_isolates_data_per_company` — Company B can never see
Company A's uploads or data.

### Demo data generator
Generates 3 companies with **deliberately different** data volumes and
history lengths (3 years / 8 months / 18 months) so the future
company-specific-vs-base-model logic (Phase 14) has a real scenario, not an
artificial toggle. Relationships are simulated, not random:

- Demand has trend + weekly seasonality + occasional promotion bumps.
- Each product is served by a supplier with its own reliability/lead-time
  profile.
- Shipment delay probability and duration are driven by that supplier's
  reliability and the shipment's distance (verified by test:
  `test_shipment_delay_correlates_with_supplier_reliability`).
- Inventory is simulated day-by-day — it depletes with sales and is only
  replenished when a shipment's simulated `actual_delivery` date arrives, so
  stockout risk emerges from the data instead of being hard-coded.

Run `python scripts/generate_demo_data.py` or `POST /api/demo/seed`.

### Data upload, validation, and column mapping (Phase 2)
Companies (or the demo pipeline) upload CSV/Excel through:

1. `POST /api/upload` — parses the file, previews rows, and suggests a
   column mapping using exact-match → known-alias → fuzzy-string-similarity,
   in that order (`app/services/column_mapping.py`). Never assumes exact
   column names.
2. `POST /api/data/validate` — checks missing values, duplicates, invalid
   dates, negative quantities/inventory, impossible lead times, and
   out-of-range values; returns a 0–100 data quality score
   (`app/services/data_validation.py`).
3. `POST /api/data/map` — confirms the final mapping (after any manual
   correction) and reports any still-unmapped required fields.
4. `POST /api/data/import` — re-validates and writes accepted rows into the
   database, skipping and counting invalid rows rather than failing the
   whole import.

All four dataset types (sales, inventory, shipments, suppliers) are
supported, each with its own required/optional standard schema
(`app/services/schema_registry.py`).

### Demand forecasting (Phase 3)

`app/ml/feature_engineering.py` builds a leakage-safe feature matrix from raw
sales history:

- Continuous daily reindex per product (a day with no sale = a real 0, not a
  gap).
- Lag features (1/7/14 days), trailing rolling mean/std (7/14 days — the
  current day is excluded from its own rolling window), calendar features
  (day of week, month, weekend flag), a numeric trend index, and the
  promotion flag.
- Verified by test to never leak the future into a feature: changing the
  final day's actual demand does not change that same day's own rolling-mean
  feature (`test_rolling_features_never_include_current_day`).

`app/ml/demand_forecasting.py` trains and compares three approaches on a
**time-based** train/test split (never random shuffle, per the spec's ML
rules):

- A naive seasonal baseline (predict this week from last week's same
  weekday).
- Random Forest and Gradient Boosting regressors.
- Whichever real model beats the other on held-out MAE is selected — on the
  demo data, Random Forest beats the naive baseline by ~35% (MAE 16.0 vs
  24.7). All three scores are stored in the model registry so the comparison
  is inspectable, not just asserted.
- Product-level mean-encoding is fit **only on the training split** to avoid
  leakage, then applied to test/serving.
- Recursive multi-step forecasting produces real 7/30/90-day forecasts by
  feeding each prediction back in as the next step's lag feature.

**Model personalization** (`app/services/model_training_service.py`,
`app/services/model_selection.py`) implements the spec's base-vs-company-specific
logic for real, not as a toggle:

- A **base model** is trained by pooling sales across every company.
- A **company-specific model** is only attempted once a company clears a
  configurable data-sufficiency threshold (`MIN_RECORDS_FOR_COMPANY_MODEL`,
  `MIN_HISTORY_DAYS_FOR_COMPANY_MODEL` in `app/config.py`).
- At serving time, a company's own active model is preferred; otherwise it
  transparently falls back to the base model — every response reports which
  one actually answered.
- This is demonstrated with the demo data itself: Horizon Electronics
  (16,425 records) and FreshMart FMCG (6,480 records) clear the threshold
  and get their own models; TorqueParts Autoworks (2,400 records, just under
  the 3,000 threshold) automatically falls back to the base model.
- A sales import automatically triggers this training/fallback logic, so
  "upload → get a working forecast" happens without a manual step.

### Shipment delay classification & delay duration (Phases 4-5)

`app/ml/feature_engineering_shipment.py` engineers features from shipment +
supplier data, with the same leakage discipline as demand forecasting -
verified by test:

- `historical_route_delay_rate` and `supplier_recent_delay_rate` are
  **expanding** statistics (mean of prior outcomes only, via `shift(1)`
  before the expanding window) - a shipment's own outcome never leaks into
  its own feature. Traced by hand in
  `test_historical_route_delay_rate_excludes_current_shipment`.
- `previous_shipment_delayed` looks exactly one shipment back per supplier.
- Categorical features (carrier, transport mode) are one-hot encoded with a
  fixed column set saved alongside the model, so an unseen category at
  serving time produces all-zero dummies instead of crashing.

`app/ml/shipment_delay.py` trains:

- A **delay classifier** (LogisticRegression / RandomForest / GradientBoosting,
  compared against a majority-class baseline) predicting delay probability.
  With demo data's natural ~13% delay rate, the raw classifiers initially
  collapsed to always predicting "not delayed" (87% accuracy, 0% recall) -
  a classic imbalance trap. Fixed with `sklearn`'s balanced sample
  weighting; the selected model then reaches ROC-AUC ~0.71 with genuine
  recall, and this trade-off is documented rather than hidden.
- A **delay duration regressor**, trained only on shipments that were
  actually delayed, evaluated against a mean-baseline (beats it: R² 0.14 vs
  -0.03 on demo data).
- Lightweight, non-fabricated explainability: `top_risk_factors` comes from
  the trained model's own `feature_importances_` (tree models) or
  coefficient magnitude (logistic regression) combined with the specific
  shipment's feature values - never invented.

Same base-vs-company-specific serving pattern as demand forecasting, with
its own (lower) data threshold since shipment volumes are naturally smaller
than daily sales volumes (`MIN_SHIPMENT_RECORDS_FOR_COMPANY_MODEL` in
`app/config.py`). Demonstrated the same way: Horizon Electronics (1,211
completed shipments) and FreshMart FMCG (481) get their own models;
TorqueParts Autoworks (174, under the 300 threshold) falls back to base.

**Design note:** demand models and shipment models are trained and served
**independently**. `POST /api/models/retrain/{company_id}` reports a
separate outcome for each - a company with shipment history but no sales
history yet (or vice versa) still gets a working response for whichever
model type has data, instead of one all-or-nothing failure.

---

## Project structure

```
supply-chain-intelligence/
├── backend/
│   ├── app/
│   │   ├── models/        # SQLAlchemy ORM: Company, Product, Sale, InventoryRecord,
│   │   │                  # Shipment, Supplier, Warehouse, ModelRegistryEntry,
│   │   │                  # Recommendation, Alert, DatasetUpload
│   │   ├── schemas/        # Pydantic request/response models
│   │   ├── routes/         # health, companies, demo, upload, demand, models, shipments
│   │   ├── services/       # column_mapping, data_validation, data_import,
│   │   │                  # demo_data_generator, schema_registry, file_io,
│   │   │                  # model_selection, model_training_service
│   │   ├── ml/                # feature_engineering, demand_forecasting,
│   │   │                  # feature_engineering_shipment, shipment_delay
│   │   ├── analytics/       # (Phase 6+)
│   │   ├── config.py
│   │   ├── database.py
│   │   └── main.py
│   ├── tests/               # 74 tests, all passing
│   ├── trained_models/       # base/ and company_{id}/ model artifacts land here
│   ├── uploads/               # uploaded files, per company_id subfolder
│   ├── requirements.txt
│   └── run.py
├── frontend/                  # (Phase 13)
├── data/
├── scripts/
│   └── generate_demo_data.py
├── docs/
├── .env.example
└── README.md
```

## API reference (current)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/companies` | List companies with summary stats |
| POST | `/api/companies` | Create a company |
| GET | `/api/companies/{id}` | Get one company |
| POST | `/api/demo/seed` | (Re)generate the 3 demo companies |
| POST | `/api/upload` | Upload a CSV/Excel dataset |
| POST | `/api/data/validate` | Validate an upload against a proposed mapping |
| POST | `/api/data/map` | Confirm the final column mapping |
| POST | `/api/data/import` | Import validated, mapped rows into the DB |
| GET | `/api/data/uploads/{company_id}` | Upload history for a company |
| POST | `/api/models/train/base` | Train the shared base demand model (pools all companies) |
| POST | `/api/models/retrain/{company_id}` | Attempt a company-specific demand model; falls back to base if data is insufficient |
| GET | `/api/models/{company_id}` | List model registry entries relevant to a company |
| GET | `/api/demand/forecast/{company_id}` | Demand forecast (`?product_id=` optional, `?horizon=7\|30\|90`) |
| GET | `/api/shipments/{company_id}` | Shipment delay risk for all shipments (`?limit=`) |
| GET | `/api/shipments/{company_id}/{shipment_id}` | Single shipment risk detail with top risk factors |

Full interactive docs (request/response schemas, try-it-out) at `/docs` once
the server is running.

---

## Roadmap status

- [x] **Phase 1** — Project structure, backend setup, database, demo data generator
- [x] **Phase 2** — Data upload, validation, column mapping, cleaning
- [x] **Phase 3** — Demand forecasting (ML regression)
- [x] **Phase 4** — Shipment delay prediction (ML classification)
- [x] **Phase 5** — Delay duration prediction (ML regression)
- [x] **Phase 6** — Inventory intelligence (Operations analytics)
- [x] **Phase 7** — Supplier risk (Rule-based risk scoring)
- [x] **Phase 8** — Anomaly detection (Isolation Forest / Statistical Z-score)
- [x] **Phase 9** — Risk propagation (Deterministic risk analytics)
- [x] **Phase 10** — Financial impact
- [x] **Phase 11** — What-if simulator (Scenario simulation)
- [x] **Phase 12** — Recommendation engine (Rule-based decision engine)
- [x] **Phase 13** — Frontend integration (Vite + React)
- [x] **Phase 14** — Multi-company model management
- [x] **Phase 15** — Testing (expanded)
- [x] **Phase 16** — Optional live weather/news (External contextual intelligence)
- [x] **Phase 17** — Real-world Dataset Benchmark Integration
- [ ] Phase 18 — Final UI polish and deployment

## Design principles carried through every phase

- No paid APIs, no paid database, no paid hosting required for the core app.
- No mock data in application logic — the demo companies are clearly labeled
  synthetic (`Company.is_demo = 1`), but everything downstream (validation,
  mapping, import, and future ML models) treats them exactly like real
  uploaded data.
- No hard-coded predictions — every number in the future dashboard must come
  from the database or a model, not a fixture.

## Extended implementation status
The current build now includes inventory intelligence, stockout/overstock risk, supplier analytics, anomaly detection, risk propagation, a What-If simulator, deterministic recommendations, optional live weather/news endpoints, a FastAPI dashboard aggregation endpoint, and a React/Vite frontend wired to the backend. The frontend is designed to consume the existing APIs and can run in offline/demo mode when external live services are unavailable.

## Running the completed build locally

### Backend
```powershell
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python run.py
```
Open `http://127.0.0.1:8000/docs`.

### Seed demo data and base models
Use the Swagger UI endpoint `POST /api/demo/seed` or run `python scripts/generate_demo_data.py`. It creates three realistic fictional companies and trains the shared demand, delay-classifier and delay-duration base models. This is normally a one-time setup after starting the backend.

### Real Data Benchmark
The project supports evaluating the pipeline on the Brazilian E-Commerce Public Dataset by Olist.
1. Download from: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce (CC BY-NC-SA 4.0)
2. Extract and place `olist_orders_dataset.csv`, `olist_order_items_dataset.csv`, and `olist_products_dataset.csv` into `data/real/raw/`
3. Run `python scripts/prepare_real_dataset.py` to generate `processed_shipments.csv` and `processed_sales.csv`.
4. Upload these files via the dashboard to create a real-world benchmark company.

### Frontend
In a second terminal:
```powershell
cd frontend
npm install
npm run dev
```
Open `http://127.0.0.1:5173`.

The frontend includes the overview, shipment, demand, inventory, supplier, anomaly, What-If, recommendation, data-management, and model-center screens and connects to the FastAPI backend through `VITE_API_URL` (default `http://127.0.0.1:8000/api`).

### Core API additions in the extended build
- `GET /api/dashboard/{company_id}`
- `GET /api/intelligence/{company_id}/inventory`
- `GET /api/intelligence/{company_id}/inventory/{product_id}`
- `GET /api/intelligence/{company_id}/suppliers`
- `GET /api/intelligence/{company_id}/anomalies`
- `GET /api/intelligence/{company_id}/shipments/{shipment_id}/impact`
- `POST /api/simulator`
- `GET /api/recommendations/{company_id}`
- `GET /api/live/weather?port=Mumbai`
- `GET /api/live/news?query=port%20strike`

Live weather/news are optional. The core application remains functional without external API keys.
