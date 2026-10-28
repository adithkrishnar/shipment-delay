import React, { useState, useEffect } from 'react';
import {
  SlidersHorizontal, AlertTriangle, ShieldCheck, Clock, DollarSign,
  TrendingDown, ArrowRight, RefreshCw, CheckCircle2, Package
} from 'lucide-react';
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, ReferenceLine, Legend, Area, ComposedChart
} from 'recharts';
import { getInventoryExplorer, simulateDelay } from '../services/api';

export default function Simulator({ company }) {
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState(null);
  const [delayDays, setDelayDays] = useState(7);
  const [demandMultiplier, setDemandMultiplier] = useState(1.0);
  const [horizonDays, setHorizonDays] = useState(30);
  const [emergencyQty, setEmergencyQty] = useState(0);
  const [emergencyDay, setEmergencyDay] = useState(5);

  const [loadingProducts, setLoadingProducts] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [simData, setSimData] = useState(null);
  const [error, setError] = useState(null);

  // Load products for dropdown
  useEffect(() => {
    if (!company?.id) return;
    setLoadingProducts(true);
    getInventoryExplorer(company.id)
      .then(res => {
        const items = res.items || [];
        setProducts(items);
        if (items.length > 0) {
          setSelectedProductId(items[0].product_id);
        }
      })
      .catch(err => setError(err.response?.data?.detail || err.message))
      .finally(() => setLoadingProducts(false));
  }, [company?.id]);

  // Run simulation on parameter changes
  useEffect(() => {
    if (!company?.id || !selectedProductId) return;
    setSimulating(true);
    simulateDelay({
      company_id: company.id,
      product_id: selectedProductId,
      delay_days: Number(delayDays),
      demand_multiplier: Number(demandMultiplier),
      horizon_days: Number(horizonDays),
      emergency_order_qty: Number(emergencyQty),
      emergency_order_day: Number(emergencyDay),
    })
      .then(data => {
        setSimData(data);
        setError(null);
      })
      .catch(err => setError(err.response?.data?.detail || err.message))
      .finally(() => setSimulating(false));
  }, [company?.id, selectedProductId, delayDays, demandMultiplier, horizonDays, emergencyQty, emergencyDay]);

  if (loadingProducts) {
    return (
      <div className="page" style={{ padding: '32px' }}>
        <div className="skeleton" style={{ height: '40px', width: '300px', marginBottom: '24px' }} />
        <div className="skeleton" style={{ height: '400px', width: '100%' }} />
      </div>
    );
  }

  if (products.length === 0) {
    return (
      <div className="page animate-fade" style={{ padding: '64px 24px', textAlign: 'center' }}>
        <SlidersHorizontal size={36} color="var(--accent-primary)" style={{ margin: '0 auto 16px' }} />
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
          No Products Available for Delay Simulation
        </h2>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', maxWidth: '480px', margin: '0 auto' }}>
          Delay simulation models delivery disruptions on your inventory. Upload products and sales in Data & Imports to run simulations.
        </p>
      </div>
    );
  }

  if (error && !simData) {
    return (
      <div className="page animate-fade" style={{ padding: '32px', textAlign: 'center' }}>
        <p style={{ color: 'var(--status-critical)', marginBottom: '16px' }}>{error}</p>
        <button className="btn-secondary" onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  if (!simData) {
    return (
      <div className="page" style={{ padding: '32px' }}>
        <div className="skeleton" style={{ height: '40px', width: '300px', marginBottom: '24px' }} />
        <div className="skeleton" style={{ height: '400px', width: '100%' }} />
      </div>
    );
  }

  const summary = simData?.summary || {};
  const params = simData?.parameters || {};
  const dates = simData?.dates || {};
  const timeline = simData?.timeline || [];
  const alternatives = simData?.alternatives || [];

  return (
    <div className="page" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Inventory Delay Impact Simulator
            </h1>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              Discrete-Event Engine
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
            Model supplier delivery disruptions, simulate stockout timing, evaluate unmet demand, and compare mitigation alternatives.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <label style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-secondary)' }}>Target SKU:</label>
          <select
            value={selectedProductId || ''}
            onChange={e => setSelectedProductId(Number(e.target.value))}
            style={{
              background: 'var(--bg-surface-1)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-default)',
              padding: '8px 12px',
              borderRadius: 'var(--r-md)',
              fontSize: '13px',
              minWidth: '220px',
            }}
          >
            {products.map(p => (
              <option key={p.product_id} value={p.product_id}>
                {p.product_name} ({p.external_product_id})
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: 'var(--status-critical-bg)', border: '1px solid var(--status-critical-border)', borderRadius: 'var(--r-md)', color: 'var(--status-critical)', fontSize: '13px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* KPI Cards Strip */}
      <div className="sim-kpi-grid">
        <div className={`sim-kpi-card ${summary.scenario_stockout_days > 0 ? 'critical' : 'healthy'}`}>
          <div className="kpi-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <AlertTriangle size={14} color={summary.scenario_stockout_days > 0 ? 'var(--status-critical)' : 'var(--status-healthy)'} />
            Stockout Exposure
          </div>
          <div className="kpi-value" style={{ color: summary.scenario_stockout_days > 0 ? 'var(--status-critical)' : 'var(--status-healthy)' }}>
            {summary.scenario_stockout_days} <span style={{ fontSize: '14px', fontWeight: 400 }}>days</span>
          </div>
          <div className="kpi-sub">
            {summary.scenario_stockout_days > 0 ? `Earliest: ${dates.earliest_stockout_date}` : 'Zero stockout projected'}
          </div>
        </div>

        <div className="sim-kpi-card">
          <div className="kpi-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <TrendingDown size={14} color="var(--status-watch)" />
            Total Unmet Demand
          </div>
          <div className="kpi-value">
            {summary.total_unmet_demand_units != null ? Number(summary.total_unmet_demand_units).toLocaleString() : '0'} <span style={{ fontSize: '14px', fontWeight: 400 }}>units</span>
          </div>
          <div className="kpi-sub">
            Max Single-Day Shortage: {summary.maximum_shortage_units || 0} units
          </div>
        </div>

        <div className="sim-kpi-card">
          <div className="kpi-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <DollarSign size={14} color="var(--accent-primary)" />
            Inventory Value at Risk
          </div>
          <div className="kpi-value">
            {summary.value_at_risk != null ? `$${Number(summary.value_at_risk).toLocaleString()}` : 'N/A'}
          </div>
          <div className="kpi-sub">
            {summary.has_cost_data ? `Unit Cost: $${summary.unit_cost?.toFixed(2)}` : 'Unit cost data unmapped'}
          </div>
        </div>

        <div className="sim-kpi-card">
          <div className="kpi-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Clock size={14} color="var(--text-secondary)" />
            Receipt Timeline
          </div>
          <div className="kpi-value" style={{ fontSize: '18px' }}>
            +{delayDays} <span style={{ fontSize: '14px', fontWeight: 400 }}>days delay</span>
          </div>
          <div className="kpi-sub">
            {dates.baseline_receipt_date || 'N/A'} → <span style={{ color: delayDays > 0 ? 'var(--status-watch)' : 'inherit' }}>{dates.delayed_receipt_date || 'N/A'}</span>
          </div>
        </div>
      </div>

      {/* Main Simulation Workspace */}
      <div className="simulator-workspace">
        {/* Interactive Parameter Controls Panel */}
        <div className="sim-panel">
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <SlidersHorizontal size={16} color="var(--accent-primary)" />
            Scenario Controls
          </h3>

          {/* Delay Slider */}
          <div className="sim-control-group">
            <div className="sim-control-header">
              <span className="sim-control-label">Inbound Delay (Days)</span>
              <span className="sim-control-val">+{delayDays} d</span>
            </div>
            <input
              type="range"
              min="0"
              max="60"
              step="1"
              value={delayDays}
              onChange={e => setDelayDays(Number(e.target.value))}
              className="sim-slider"
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
              <span>0 (On-Time)</span>
              <span>30d</span>
              <span>60d Max</span>
            </div>
          </div>

          {/* Demand Multiplier Slider */}
          <div className="sim-control-group">
            <div className="sim-control-header">
              <span className="sim-control-label">Demand Surge / Multiplier</span>
              <span className="sim-control-val">{demandMultiplier.toFixed(1)}x</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="3.0"
              step="0.1"
              value={demandMultiplier}
              onChange={e => setDemandMultiplier(Number(e.target.value))}
              className="sim-slider"
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
              <span>0.5x (-50%)</span>
              <span>1.0x (Normal)</span>
              <span>3.0x (+200%)</span>
            </div>
          </div>

          {/* Horizon Selector */}
          <div className="sim-control-group">
            <div className="sim-control-header">
              <span className="sim-control-label">Simulation Horizon</span>
              <span className="sim-control-val">{horizonDays} days</span>
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
              {[15, 30, 60, 90].map(h => (
                <button
                  key={h}
                  onClick={() => setHorizonDays(h)}
                  style={{
                    flex: 1,
                    padding: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    background: horizonDays === h ? 'var(--accent-primary)' : 'var(--bg-surface-2)',
                    color: horizonDays === h ? '#fff' : 'var(--text-secondary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--r-sm)',
                    cursor: 'pointer',
                  }}
                >
                  {h}d
                </button>
              ))}
            </div>
          </div>

          {/* Emergency Order Action Toggle */}
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px', marginTop: '20px' }}>
            <div className="sim-control-header">
              <span className="sim-control-label">Emergency Order Injection</span>
              <span className="sim-control-val">{emergencyQty} units</span>
            </div>
            <input
              type="range"
              min="0"
              max="200"
              step="25"
              value={emergencyQty}
              onChange={e => setEmergencyQty(Number(e.target.value))}
              className="sim-slider"
            />
            {emergencyQty > 0 && (
              <p style={{ fontSize: '11px', color: 'var(--status-healthy)', marginTop: '6px' }}>
                Injecting batch of {emergencyQty} units arriving on Day {emergencyDay}.
              </p>
            )}
          </div>

          <button
            onClick={() => { setDelayDays(0); setDemandMultiplier(1.0); setEmergencyQty(0); }}
            style={{
              width: '100%',
              marginTop: '20px',
              padding: '8px',
              fontSize: '12px',
              fontWeight: 500,
              background: 'transparent',
              color: 'var(--text-tertiary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--r-sm)',
              cursor: 'pointer',
            }}
          >
            Reset to Baseline (0 Delay)
          </button>
        </div>

        {/* Dynamic Trajectory Chart */}
        <div className="sim-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Inventory Balance Trajectory (Units on Hand)
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', margin: '4px 0 0' }}>
                Comparing Baseline Planned Inflow vs. Delay Scenario Timeline
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', fontSize: '12px' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: 12, height: 2, background: 'var(--status-healthy)' }} />
                Baseline Stock
              </span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: 12, height: 2, background: delayDays > 0 ? 'var(--status-critical)' : 'var(--accent-primary)' }} />
                Scenario Stock
              </span>
            </div>
          </div>

          <div style={{ height: '360px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={timeline} margin={{ top: 10, right: 20, bottom: 10, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis
                  dataKey="day"
                  tickFormatter={d => `D${d}`}
                  stroke="var(--text-tertiary)"
                  fontSize={11}
                />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', padding: '10px 14px', borderRadius: 'var(--r-sm)', fontSize: '12px' }}>
                          <div style={{ fontWeight: 600, marginBottom: '4px' }}>Day {data.day} ({data.date})</div>
                          <div style={{ color: 'var(--status-healthy)' }}>Baseline Stock: {data.baseline_stock} units</div>
                          <div style={{ color: delayDays > 0 ? 'var(--status-critical)' : 'var(--accent-primary)' }}>Scenario Stock: {data.scenario_stock} units</div>
                          <div style={{ color: 'var(--text-secondary)' }}>Daily Demand: {data.scenario_demand} units</div>
                          {data.events && (
                            <div style={{ color: 'var(--status-watch)', marginTop: '4px', fontWeight: 500 }}>
                              Event: {data.events}
                            </div>
                          )}
                          {data.shortage_units > 0 && (
                            <div style={{ color: 'var(--status-critical)', marginTop: '4px', fontWeight: 600 }}>
                              Shortage: {data.shortage_units} units
                            </div>
                          )}
                        </div>
                      );
                    }
                    return null;
                  }}
                />

                {/* Reference Lines for Inventory Thresholds */}
                {params.safety_stock != null && (
                  <ReferenceLine
                    y={params.safety_stock}
                    label={{ value: `Safety Stock (${params.safety_stock})`, fill: 'var(--status-watch)', fontSize: 10, position: 'right' }}
                    stroke="var(--status-watch)"
                    strokeDasharray="4 4"
                  />
                )}
                {params.reorder_point != null && (
                  <ReferenceLine
                    y={params.reorder_point}
                    label={{ value: `Reorder Point (${params.reorder_point})`, fill: 'var(--accent-primary)', fontSize: 10, position: 'right' }}
                    stroke="var(--accent-primary)"
                    strokeDasharray="4 4"
                  />
                )}

                <Area type="monotone" dataKey="baseline_stock" stroke="var(--status-healthy)" fill="rgba(45, 212, 167, 0.08)" strokeWidth={2} />
                <Line type="monotone" dataKey="scenario_stock" stroke={delayDays > 0 ? 'var(--status-critical)' : 'var(--accent-primary)'} strokeWidth={2.5} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Scenario Assumptions & Calculation Evidence Banner */}
      {summary.assumptions_narrative && (
        <div style={{ marginTop: '24px', background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-md)', padding: '18px 22px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Sparkles size={16} color="var(--accent-primary)" />
              <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                Scenario Assumptions & Discrete-Event Audit Narrative
              </h4>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', background: params.is_assumed_order ? 'var(--status-watch-bg)' : 'var(--status-healthy-bg)', color: params.is_assumed_order ? 'var(--status-watch)' : 'var(--status-healthy)' }}>
                {params.is_assumed_order ? 'Assumed Replenishment Schedule' : 'Verified Open Purchase Order'}
              </span>
              <span style={{ fontSize: '11px', fontWeight: 600, padding: '2px 8px', borderRadius: '4px', background: 'var(--bg-surface-2)', color: 'var(--text-secondary)' }}>
                Min Balance: {summary.min_scenario_stock} units (Day {summary.min_scenario_stock_day})
              </span>
            </div>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: '1.5', margin: 0 }}>
            {summary.assumptions_narrative}
          </p>
        </div>
      )}

      {/* Decision Alternatives & Mitigation Matrix */}
      <div style={{ marginTop: '28px' }}>

        <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldCheck size={18} color="var(--status-healthy)" />
          What-If Mitigation Decision Comparison
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
          {alternatives.map((alt, idx) => (
            <div
              key={idx}
              style={{
                background: 'var(--bg-surface-1)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--r-md)',
                padding: '16px',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
              }}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>{alt.action}</span>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: alt.risk_tier === 'CRITICAL' ? 'var(--status-critical-bg)' : alt.risk_tier === 'HIGH' ? 'var(--status-watch-bg)' : 'var(--status-healthy-bg)',
                      color: alt.risk_tier === 'CRITICAL' ? 'var(--status-critical)' : alt.risk_tier === 'HIGH' ? 'var(--status-watch)' : 'var(--status-healthy)',
                    }}
                  >
                    {alt.risk_tier}
                  </span>
                </div>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4', marginBottom: '16px' }}>
                  {alt.description}
                </p>
              </div>

              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '12px', fontSize: '12px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>Stockout Days:</span>
                  <span style={{ fontWeight: 600, color: alt.projected_stockout_days > 0 ? 'var(--status-critical)' : 'var(--status-healthy)' }}>
                    {alt.projected_stockout_days} days
                  </span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>Unmet Demand:</span>
                  <span style={{ fontWeight: 600 }}>{alt.unmet_demand_units} units</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-tertiary)' }}>Cost / Impact:</span>
                  <span style={{ fontWeight: 600, color: 'var(--accent-primary)' }}>{alt.financial_impact}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Day-by-Day Impact Table */}
      <div style={{ marginTop: '32px', background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            Day-by-Day Discrete Simulation Log
          </h3>
          <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
            Showing 1 to {Math.min(15, timeline.length)} of {timeline.length} days
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '10px 16px' }}>Timeline Day</th>
                <th style={{ padding: '10px 16px' }}>Calendar Date</th>
                <th style={{ padding: '10px 16px' }}>Demand</th>
                <th style={{ padding: '10px 16px' }}>Inbound Receipts</th>
                <th style={{ padding: '10px 16px' }}>Baseline Stock</th>
                <th style={{ padding: '10px 16px' }}>Scenario Stock</th>
                <th style={{ padding: '10px 16px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {timeline.slice(0, 15).map(row => (
                <tr
                  key={row.day}
                  style={{
                    borderBottom: '1px solid var(--border-subtle)',
                    background: row.is_stockout ? 'rgba(255, 77, 95, 0.05)' : 'transparent',
                  }}
                >
                  <td style={{ padding: '10px 16px', fontWeight: 600 }}>Day {row.day}</td>
                  <td style={{ padding: '10px 16px', color: 'var(--text-secondary)' }}>{row.date}</td>
                  <td style={{ padding: '10px 16px' }}>{row.scenario_demand} units</td>
                  <td style={{ padding: '10px 16px', color: row.scenario_inflow > 0 ? 'var(--status-healthy)' : 'var(--text-tertiary)' }}>
                    {row.events || (row.scenario_inflow > 0 ? `+${row.scenario_inflow}` : '—')}
                  </td>
                  <td style={{ padding: '10px 16px', color: 'var(--status-healthy)' }}>{row.baseline_stock}</td>
                  <td style={{ padding: '10px 16px', fontWeight: 600, color: row.is_stockout ? 'var(--status-critical)' : 'var(--text-primary)' }}>
                    {row.scenario_stock}
                  </td>
                  <td style={{ padding: '10px 16px' }}>
                    {row.is_stockout ? (
                      <span style={{ color: 'var(--status-critical)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <AlertTriangle size={12} /> Stockout (-{row.shortage_units})
                      </span>
                    ) : (
                      <span style={{ color: 'var(--status-healthy)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <CheckCircle2 size={12} /> Sufficient
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
