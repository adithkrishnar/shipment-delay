# SupplyIQ Inventory Intelligence — Branch Baseline Record

## 1. Baseline Metadata
- **Creation Date**: 2026-10-26
- **Original Branch**: `main`
- **Original Commit HEAD**: `7e7fc930f029eb20d8cb896c2f685b6011722e55` ("Final verification and blueprint completion")
- **Dedicated Branch**: `inventory-intelligence`
- **Safety Backup Branch**: `backup/pre-inventory-baseline`
- **Working-Tree Stash**: `stash@{0}: On main: backup-uncommitted-before-branching` (contains benchmark model scripts and generated metrics)

## 2. Protected Artifacts & System State
- **Pre-existing Model Artifacts Preserved**:
  - `trained_models/shipment_delay_classifier.pkl` (DataCo baseline classifier)
  - `trained_models/delay_duration_regressor.pkl` (DataCo baseline regressor)
  - `trained_models/demand_forecasting_model.pkl` (Baseline pooled demand regressor)
  - `trained_models/classifier_encoder.pkl`
  - `trained_models/regressor_encoder.pkl`
  - Company-specific models: `trained_models/company_1/`, `trained_models/company_10/`, `trained_models/company_11/`
  - External benchmark models: `trained_models/uci_demand/`, `trained_models/bts_air/`, `trained_models/bts_road/`, `trained_models/multimodal/`
- **Backend Framework**:
  - FastAPI 0.115.0
  - SQLAlchemy ORM with SQLite database (`supplyiq.db`)
  - Pydantic 2.9.2
  - LightGBM 4.7.0, Scikit-learn 1.5.1, Pandas 2.2.2, Numpy 2.0.0
  - Pytest 7.4.3 (74 passing tests at baseline)
- **Frontend Framework**:
  - React (v18/v19) + Vite (v8.2.1)
  - Recharts for analytical data visualizations
  - Lucide React for consistent UI iconography
  - Axios for typed backend client requests
- **Multi-Tenant Security Architecture**:
  - Company-scoped tenancy enforced via `company_id` filter across all database models and routes.
  - JWT Bearer authentication with hashed passwords (`bcrypt`/`passlib`).

## 3. Mission Scope for Branch `inventory-intelligence`
- Refocus the primary user journey from general multi-modal shipment tracking to **Inventory Intelligence, Stockout Prevention, Optimization, and Simulation**.
- Preserve all existing core models and codebase without destructive deletions on the main branch.
- Retain ability to safely switch back to `main` at any time with complete data and feature integrity.
