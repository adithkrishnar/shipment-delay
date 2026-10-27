# SupplyIQ Discrete-Event Inventory Simulator Methodology

## 1. Engine Objective
The Inventory Delay Impact Simulator models daily discrete replenishment events under supply disruptions. Rather than applying static scalar rules or hardcoded coefficients, it runs a forward-looking day-by-day inventory simulation over a selectable horizon $T \in [7, 90]$ days.

## 2. Mathematical Formulation
Let $t \in \{1, 2, \dots, T\}$ index calendar days from simulation start $T_0$.
- Starting stock: $I_0 = \text{Current Physical On-Hand Stock}$.
- Daily demand: $D_t = \mu_d \cdot M$, where $\mu_d$ is the baseline daily demand and $M \ge 0$ is the demand multiplier.
- Inbound replenishment orders $\{O_k\}_{k=1}^K$, each with quantity $q_k$ and scheduled receipt day $t_k$.
- Under simulated disruption delay $\Delta \ge 0$ on target order $O_j$:
  $$t_j' = t_j + \Delta$$
- For all other orders $k \ne j$, $t_k' = t_k$.
- Inbound arrival on day $t$:
  $$A_t^{\text{scen}} = \sum_{k: t_k' = t} q_k + \delta(t, t_{\text{emerg}}) \cdot q_{\text{emerg}}$$
- Daily unconstrained inventory balance:
  $$I_t^* = I_{t-1} + A_t^{\text{scen}} - D_t$$
- Physical inventory on hand:
  $$I_t = \max(0, I_t^*)$$
- Daily unmet demand (shortage):
  $$U_t = \max(0, -I_t^*)$$

## 3. Simulator Core Invariants & Proofs

### Invariant 1: Identity at Zero Delay
When $\Delta = 0$ and $M = 1.0$:
$$t_j' = t_j \implies A_t^{\text{scen}} = A_t^{\text{base}} \implies I_t^{\text{scen}} = I_t^{\text{base}} \quad \forall t$$
Zero delay guarantees an exact match between baseline and scenario timelines.

### Invariant 2: Monotonic Arrival Shift
Since $\Delta \ge 0$:
$$t_j' = t_j + \Delta \ge t_j$$
Increasing a receipt delay cannot cause an inbound order to arrive earlier in time.

### Invariant 3: Event Timing Precedence
$$A_t^{\text{scen}} > 0 \iff \exists k \text{ s.t. } t_k' = t$$
Stock never increases before the order's simulated arrival date $t_j'$.

### Invariant 4: Demand Monotonicity
For $M_2 \ge M_1$:
$$\sum_{t=1}^T D_t(M_2) = M_2 \cdot T \cdot \mu_d \ge M_1 \cdot T \cdot \mu_d = \sum_{t=1}^T D_t(M_1)$$
Higher demand multipliers cannot decrease cumulative demand over the same horizon.

### Invariant 5 & 6: Deterministic Stockout Occurrence
A stockout occurs on day $t$ if and only if:
$$I_0 + \sum_{\tau=1}^t A_\tau^{\text{scen}} < \sum_{\tau=1}^t D_\tau$$
If initial stock $I_0$ exceeds cumulative horizon demand, no stockout is falsely triggered regardless of delay.

### Invariant 7: Multi-Order Event Processing
Each purchase order $O_k$ maintains an independent arrival event. Orders arriving on distinct days are evaluated at their respective calendar dates.

### Invariant 8: Read-Only Simulation Isolation
The simulation runs entirely in memory without executing SQL `UPDATE`, `INSERT`, or `DELETE` statements on `inventory_records`. Physical inventory is never mutated.

### Invariant 9: Determinism & Reproducibility
Given identical tuple $(\text{SKU}, \Delta, M, T)$, the function yields identical trajectories and summary metrics.

### Invariant 10: Strict Financial Truthfulness
If `unit_cost` or `unit_price` is missing (`None`), Value-at-Risk and Potential Lost Revenue return `None` with `has_cost_data: false`. Costs are never fabricated.

## 4. Mitigation Decision Alternatives
1. **Do Nothing**: Absorb disruption delay; projects stockout duration, unmet units, and financial impact.
2. **Expedite Inbound Order**: Models expedited air freight returning arrival to baseline $t_j$; evaluates user-provided expedite fee vs. stockout risk.
3. **Emergency Order Injection**: Simulates a rapid secondary batch of size $q_{\text{emerg}}$ arriving at day $t_{\text{emerg}} = 4$.
4. **Inter-Warehouse Transfer**: Reallocates buffer inventory from a surplus warehouse, provided the source facility retains its minimum safe threshold ($\ge 50$ units).
