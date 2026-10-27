# SupplyIQ — Inventory Intelligence Platform Implementation Plan

## 1. Executive Summary & Architecture Audit
The SupplyIQ platform is being transitioned on branch `inventory-intelligence` from a general multi-modal logistics tracker to an **Inventory Intelligence, Optimization, and Simulation Platform**.

### 1.1 Existing Reusable Assets
- **Authentication & Security**: JWT bearer authentication (`app/auth/`), user models (`app/models/user.py`), company context scoping (`company_id`), password hashing via Passlib/Bcrypt.
- **Database & Persistence**: SQLAlchemy ORM with SQLite engine (`supplyiq.db`), foreign keys (`companies`, `products`, `warehouses`, `suppliers`, `sales`, `inventory_records`, `shipments`, `model_registry`).
- **Data Ingestion Infrastructure**: CSV/XLSX file ingestion, deterministic and fuzzy column mapping (`app/services/column_mapping.py`), schema registry (`app/services/schema_registry.py`), data validation engine (`app/services/data_validation.py`).
- **Core Inventory Intelligence**: Baseline calculations for daily demand, demand standard deviation, safety stock ($1.65 \cdot \sigma_d \cdot \sqrt{L}$), reorder point, coverage days, stockout probability heuristic (`app/services/inventory_intelligence.py`).
- **Frontend Architecture**: React 18 + Vite, Recharts visualization library, Lucide React icons, Axios API client, custom design system tokenized in `global.css`.

### 1.2 Identified Gaps & Required Enhancements
1. **Discrete-Event Delay Simulation**:
   - Current simulator in `risk_engine.py` only computes a single scalar point without daily time-series trajectory.
   - Required: A true daily discrete-event timeline engine that projects day-by-day inventory balances, processes purchase order receipts strictly on their scheduled/delayed arrival date, calculates unmet demand, stockout duration, and compares baseline vs. scenario trajectories.
2. **Inventory Optimization & Replenishment**:
   - Configurable service levels ($Z$-scores for 90%, 95%, 99%), economic order quantity / suggested reorder quantities, minimum order quantities (MOQ), and multi-warehouse transfer feasibility.
3. **Inventory Segmentation & Analytics**:
   - ABC analysis (by cumulative revenue/value contribution: 80/15/5%).
   - XYZ analysis (by coefficient of variation $CV = \sigma / \mu$: $CV < 0.5$, $0.5 \le CV \le 1.0$, $CV > 1.0$).
   - Slow-moving and non-moving inventory detection, inventory aging, and turnover rates.
4. **Enhanced Data Ingestion**:
   - Support for purchase orders and receipts (PO ID, SKU, supplier, warehouse, order date, expected arrival, actual arrival, quantity).
   - Direct inventory snapshot updates and deterministic aliases for stock levels.
5. **Modern, High-Density Graphical UI**:
   - Dedicated views for Overview (Control Tower), Inventory Explorer, Products & Warehouses, Demand Forecasts, Replenishment, Delay Simulator, What-If Lab, Action Center (Recommendations), Inventory Insights (ABC/XYZ & Aging), Data & Imports, and Models.
   - Interactive charts with Recharts (ReferenceLines for safety stock and reorder point, shaded shortage areas, responsive tooltips).

---

## 2. Technical Design & Mathematical Formulations

### 2.1 Inventory Mathematics & Replenishment
1. **Average Daily Demand ($\mu_d$)**:
   $$\mu_d = \frac{1}{N} \sum_{t=1}^N S_t$$
   Computed over continuous daily reindexed sales (days with 0 sales counted as 0, not omitted).
2. **Demand Standard Deviation ($\sigma_d$)**:
   $$\sigma_d = \sqrt{\frac{1}{N-1} \sum_{t=1}^N (S_t - \mu_d)^2}$$
3. **Safety Stock ($SS$)**:
   $$SS = Z_{\alpha} \cdot \sqrt{L \cdot \sigma_d^2 + \mu_d^2 \cdot \sigma_L^2}$$
   Where $Z_{\alpha} = 1.65$ (for 95% cycle service level) or $2.33$ (for 99%), $L$ is lead time in days. When lead time variance $\sigma_L = 0$, $SS = Z_{\alpha} \cdot \sigma_d \cdot \sqrt{L}$.
4. **Reorder Point ($ROP$)**:
   $$ROP = (\mu_d \cdot L) + SS$$
5. **Days of Inventory Remaining (Coverage)**:
   $$\text{Coverage} = \frac{I_{\text{current}}}{\mu_d} \quad (\text{for } \mu_d > 0)$$
6. **Suggested Order Quantity ($Q$)**:
   $$Q = \max(0, \lceil \mu_d \cdot T_{\text{target}} + SS - I_{\text{current}} - I_{\text{inbound}} \rceil)$$

### 2.2 Discrete-Event Delay Simulation Engine
For a selected product, warehouse, and forecast horizon $T \in [1, 90]$ days:
- Starting stock: $I_0 = \text{Current On-Hand}$.
- Incoming orders $\{O_k\}$ with quantity $q_k$ and scheduled baseline arrival $t_k$.
- Under simulated delay $\Delta$ on order $O_j$:
  $$t_j' = t_j + \Delta$$
- For each day $t = 1, \dots, T$:
  - Daily demand $D_t \sim \text{Forecast}(t) \cdot \text{Multiplier}$.
  - Inbound arrivals: $A_t = \sum_{k: t_k' = t} q_k$.
  - End-of-day projected stock before stockout clipping:
    $$I_t^* = I_{t-1} + A_t - D_t$$
  - Unmet demand (shortage) on day $t$:
    $$U_t = \max(0, -I_t^*)$$
  - Physical non-negative stock balance:
    $$I_t = \max(0, I_t^*)$$
- **Key Invariants**:
  1. $I_t$ increases from order $O_j$ *if and only if* $t \ge t_j'$.
  2. If $\Delta = 0$, the delayed trajectory matches the baseline trajectory exactly.
  3. Cumulative unmet demand $\sum U_t$ is non-decreasing with respect to delay $\Delta \ge 0$.
  4. Earliest stockout date: $t_{\text{stockout}} = \min \{t \mid I_t^* \le 0\}$, if any.

### 2.3 Inventory Segmentation
- **ABC Classification**: Sort SKUs by Annual Consumption Value ($\text{ACV} = \text{Annual Units Sold} \times \text{Unit Cost}$).
  - Class A: Top 80% of value (highest priority).
  - Class B: Next 15% of value.
  - Class C: Remaining 5% of value.
- **XYZ Classification**: Demand volatility based on coefficient of variation $CV = \frac{\sigma_d}{\mu_d}$.
  - Class X: $CV < 0.5$ (very steady, high forecast confidence).
  - Class Y: $0.5 \le CV \le 1.0$ (moderate variability).
  - Class Z: $CV > 1.0$ (erratic demand, low forecast confidence).

---

## 3. Database & API Architecture

### 3.1 Extended Models
- Keep existing models intact.
- Add support for Purchase Orders and Warehouse Transfers either as specialized models or rich service extensions backed by the database.
- Provide clean endpoints for:
  - `GET /api/inventory/overview`: High-level inventory KPIs, total valuation, low/critical stock counts, warehouse distributions.
  - `GET /api/inventory/explorer`: Comprehensive list of SKUs with stock level, daily demand, safety stock, ROP, coverage days, stockout tier.
  - `GET /api/inventory/product/{id}`: Detailed product profile, historical demand, projected inventory trajectory, inbound receipts.
  - `GET /api/inventory/warehouses`: Warehouse stock breakdowns, storage utilization, cross-warehouse inventory positions.
  - `GET /api/inventory/insights/abc-xyz`: ABC/XYZ matrix and aging stock distributions.
  - `POST /api/inventory/replenishment/calculate`: Reorder recommendations and safety stock optimization.
  - `POST /api/inventory/simulate/delay`: Full discrete-event daily timeline simulation for baseline vs. delayed orders.
  - `POST /api/inventory/simulate/what-if`: Multi-parameter what-if simulation (demand, lead time, buffer stock).
  - `POST /api/inventory/transfers/recommend`: Surplus-to-shortage transfer recommendations between warehouses.

### 3.2 Tenant Isolation
- Every query executes with `WHERE company_id = :company_id`.
- `current_user.company_id` is verified against requested company parameter; 403 returned on mismatch for non-superusers.

---

## 4. UI Architecture & Navigation
- **Theme**: Dark enterprise control tower (`#0B0F14` background, `#151C24` surface, `#26313D` border, `#4F8CFF` primary blue, `#2DD4A7` healthy teal, `#F5B942` warning amber, `#FF4D5F` critical coral, `#A78BFA` forecast purple).
- **Navigation Groups**:
  - **Operations**: Overview, Inventory Explorer, Products & Warehouses, Demand Forecasts, Replenishment.
  - **Decision Support**: Delay Simulator, What-If Lab, Action Center (Recommendations), Inventory Insights.
  - **System**: Data & Imports, Models & Forecast Quality.
- **Visualizations (Recharts)**:
  - Interactive Delay Simulator Workspace: Area/Line stock trajectory with ReferenceLines for Safety Stock and ROP, shaded shortage regions, animated KPI cards, day-by-day schedule table.
  - ABC/XYZ 9-box matrix visualization with interactive SKU filtering.
  - Warehouse comparison grouped bar charts.
  - Demand actual vs. forecast multi-horizon area charts with uncertainty bands.

---

## 5. Verification & Testing Strategy
- Unit & integration tests for:
  1. Inventory calculation metrics (daily demand, safety stock, ROP, coverage).
  2. All 10 Delay Simulator invariants (Phase 11.4).
  3. Multi-warehouse transfer logic (no creating shortages at source).
  4. ABC/XYZ classification correctness.
  5. API endpoint contracts and tenant isolation tests (cross-company 403 checks).
- Full backend `pytest` suite execution.
- Frontend production bundle build (`npm run build`).
