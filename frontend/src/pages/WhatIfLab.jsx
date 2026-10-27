import React, { useState, useEffect } from 'react';
import {
  FlaskConical, ArrowRight, Check, RotateCcw, AlertCircle, Save,
  Trash2, Play, CheckCircle2, Bookmark, ExternalLink, X
} from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend
} from 'recharts';
import {
  getInventoryExplorer,
  simulateWhatIf,
  saveScenario,
  getSavedScenarios,
  deleteSavedScenario
} from '../services/api';

export default function WhatIfLab({ company }) {
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState(null);
  const [demandMultiplier, setDemandMultiplier] = useState(1.2);
  const [leadTimeDelta, setLeadTimeDelta] = useState(5);
  const [serviceLevel, setServiceLevel] = useState(0.95);

  const [loading, setLoading] = useState(true);
  const [simulating, setSimulating] = useState(false);
  const [result, setResult] = useState(null);
  const [savedScenarios, setSavedScenarios] = useState([]);
  const [error, setError] = useState(null);
  const [saveSuccess, setSaveSuccess] = useState(null);

  // Save Modal State
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [scenarioName, setScenarioName] = useState('');
  const [scenarioDesc, setScenarioDesc] = useState('');
  const [savingScenario, setSavingScenario] = useState(false);

  const fetchSavedScenarios = () => {
    if (!company?.id) return;
    getSavedScenarios(company.id)
      .then(scenarios => setSavedScenarios(scenarios || []))
      .catch(err => console.error("Failed to fetch saved scenarios", err));
  };

  useEffect(() => {
    if (!company?.id) return;
    setLoading(true);
    Promise.all([
      getInventoryExplorer(company.id),
      getSavedScenarios(company.id).catch(() => []),
    ])
      .then(([res, scenarios]) => {
        const items = res.items || [];
        setProducts(items);
        setSavedScenarios(scenarios || []);
        if (items.length > 0) {
          setSelectedProductId(items[0].product_id);
        }
      })
      .catch(err => setError(err.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [company?.id]);

  const runScenario = () => {
    if (!company?.id || !selectedProductId) return;
    setSimulating(true);
    simulateWhatIf({
      company_id: company.id,
      product_id: selectedProductId,
      demand_multiplier: Number(demandMultiplier),
      lead_time_delta: Number(leadTimeDelta),
      service_level_target: Number(serviceLevel),
    })
      .then(data => {
        setResult(data);
        setError(null);
      })
      .catch(err => setError(err.response?.data?.detail || err.message))
      .finally(() => setSimulating(false));
  };

  useEffect(() => {
    runScenario();
  }, [company?.id, selectedProductId, demandMultiplier, leadTimeDelta, serviceLevel]);

  const handleOpenSaveModal = () => {
    if (!result) return;
    const currentProd = products.find(p => p.product_id === selectedProductId);
    const prodName = currentProd ? currentProd.product_name : `Product #${selectedProductId}`;
    setScenarioName(`${prodName} — ${demandMultiplier}x Demand, +${leadTimeDelta}d Lead`);
    setScenarioDesc(`Stress test at ${(serviceLevel * 100).toFixed(0)}% SL`);
    setShowSaveModal(true);
  };

  const handleConfirmSave = async (e) => {
    e.preventDefault();
    if (!scenarioName.trim() || !company?.id) return;
    setSavingScenario(true);
    setError(null);
    try {
      await saveScenario({
        company_id: company.id,
        name: scenarioName.trim(),
        description: scenarioDesc.trim() || undefined,
        scenario_type: 'WHAT_IF',
        parameters: {
          product_id: selectedProductId,
          demand_multiplier: Number(demandMultiplier),
          lead_time_delta: Number(leadTimeDelta),
          service_level_target: Number(serviceLevel),
        },
        results: result || {},
      });
      setShowSaveModal(false);
      setSaveSuccess(`Scenario "${scenarioName.trim()}" saved to database successfully.`);
      setTimeout(() => setSaveSuccess(null), 5000);
      fetchSavedScenarios();
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to persist scenario.');
    } finally {
      setSavingScenario(false);
    }
  };

  const handleLoadSavedScenario = (sc) => {
    const params = sc.parameters || {};
    if (params.product_id) setSelectedProductId(params.product_id);
    if (params.demand_multiplier != null) setDemandMultiplier(Number(params.demand_multiplier));
    if (params.lead_time_delta != null) setLeadTimeDelta(Number(params.lead_time_delta));
    if (params.service_level_target != null) setServiceLevel(Number(params.service_level_target));
    if (sc.results) setResult(sc.results);
    setSaveSuccess(`Loaded parameters from "${sc.name}" into Decision Lab.`);
    setTimeout(() => setSaveSuccess(null), 4000);
  };

  const handleDeleteSavedScenario = async (scenarioId, scName) => {
    if (!company?.id) return;
    try {
      await deleteSavedScenario(company.id, scenarioId);
      setSavedScenarios(prev => prev.filter(s => s.id !== scenarioId));
      setSaveSuccess(`Deleted scenario "${scName}".`);
      setTimeout(() => setSaveSuccess(null), 4000);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to delete scenario.');
    }
  };

  if (loading) {
    return (
      <div className="page" style={{ padding: '32px' }}>
        <div className="skeleton" style={{ height: '40px', width: '300px', marginBottom: '24px' }} />
        <div className="skeleton" style={{ height: '300px', width: '100%' }} />
      </div>
    );
  }

  const baseline = result?.baseline || {};
  const scenario = result?.scenario || {};
  const deltas = result?.deltas || {};

  const comparisonChartData = [
    { name: 'Daily Demand', Baseline: baseline.daily_demand || 0, Scenario: scenario.daily_demand || 0 },
    { name: 'Safety Stock', Baseline: baseline.safety_stock || 0, Scenario: scenario.safety_stock || 0 },
    { name: 'Reorder Point', Baseline: baseline.reorder_point || 0, Scenario: scenario.reorder_point || 0 },
    { name: 'Coverage (Days)', Baseline: baseline.coverage_days || 0, Scenario: scenario.coverage_days || 0 },
  ];

  return (
    <div className="page" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              What-If Decision Lab
            </h1>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              Strategic Planning & Scenarios
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
            Test macro policy changes: demand shocks, supplier lead time shifts, and target service levels. Persist and compare iterations across sessions.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
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
          <button
            onClick={handleOpenSaveModal}
            disabled={!result || simulating}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              background: 'var(--accent-primary)',
              color: '#fff',
              border: 'none',
              borderRadius: 'var(--r-md)',
              fontSize: '13px',
              fontWeight: 600,
              cursor: (!result || simulating) ? 'not-allowed' : 'pointer',
              opacity: (!result || simulating) ? 0.6 : 1,
            }}
          >
            <Save size={14} /> Save Scenario
          </button>
        </div>
      </div>

      {saveSuccess && (
        <div style={{ padding: '12px 16px', background: 'var(--status-healthy-bg)', border: '1px solid var(--status-healthy-border)', borderRadius: 'var(--r-md)', color: 'var(--status-healthy)', fontSize: '13px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle2 size={16} />
          {saveSuccess}
        </div>
      )}

      {error && (
        <div style={{ padding: '12px 16px', background: 'var(--status-critical-bg)', border: '1px solid var(--status-critical-border)', borderRadius: 'var(--r-md)', color: 'var(--status-critical)', fontSize: '13px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Main Simulation Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', gap: '24px', marginBottom: '32px' }}>
        {/* Controls */}
        <div className="sim-panel">
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>
            Policy Parameters
          </h3>

          <div className="sim-control-group">
            <div className="sim-control-header">
              <span className="sim-control-label">Demand Growth Factor</span>
              <span className="sim-control-val">{demandMultiplier}x</span>
            </div>
            <input
              type="range"
              min="0.5"
              max="2.5"
              step="0.1"
              value={demandMultiplier}
              onChange={e => setDemandMultiplier(Number(e.target.value))}
              className="sim-slider"
            />
          </div>

          <div className="sim-control-group">
            <div className="sim-control-header">
              <span className="sim-control-label">Lead Time Shift</span>
              <span className="sim-control-val">+{leadTimeDelta} days</span>
            </div>
            <input
              type="range"
              min="-5"
              max="30"
              step="1"
              value={leadTimeDelta}
              onChange={e => setLeadTimeDelta(Number(e.target.value))}
              className="sim-slider"
            />
          </div>

          <div className="sim-control-group">
            <div className="sim-control-header">
              <span className="sim-control-label">Target Service Level</span>
              <span className="sim-control-val">{(serviceLevel * 100).toFixed(0)}%</span>
            </div>
            <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
              {[0.90, 0.95, 0.98, 0.99].map(sl => (
                <button
                  key={sl}
                  onClick={() => setServiceLevel(sl)}
                  style={{
                    flex: 1,
                    padding: '6px',
                    fontSize: '11px',
                    fontWeight: 600,
                    background: serviceLevel === sl ? 'var(--accent-primary)' : 'var(--bg-surface-2)',
                    color: serviceLevel === sl ? '#fff' : 'var(--text-secondary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--r-sm)',
                    cursor: 'pointer',
                  }}
                >
                  {(sl * 100).toFixed(0)}%
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Comparison Result Cards & Chart */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
            <div className="sim-kpi-card">
              <span className="kpi-label">Safety Stock Impact</span>
              <div className="kpi-value" style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                {scenario.safety_stock}
                <span style={{ fontSize: '12px', color: deltas.safety_stock_diff >= 0 ? 'var(--status-watch)' : 'var(--status-healthy)' }}>
                  ({deltas.safety_stock_diff >= 0 ? `+${deltas.safety_stock_diff}` : deltas.safety_stock_diff} units)
                </span>
              </div>
              <span className="kpi-sub">Baseline: {baseline.safety_stock} units</span>
            </div>

            <div className="sim-kpi-card">
              <span className="kpi-label">Reorder Point Impact</span>
              <div className="kpi-value" style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
                {scenario.reorder_point}
                <span style={{ fontSize: '12px', color: deltas.reorder_point_diff >= 0 ? 'var(--status-watch)' : 'var(--status-healthy)' }}>
                  ({deltas.reorder_point_diff >= 0 ? `+${deltas.reorder_point_diff}` : deltas.reorder_point_diff} units)
                </span>
              </div>
              <span className="kpi-sub">Baseline: {baseline.reorder_point} units</span>
            </div>

            <div className="sim-kpi-card">
              <span className="kpi-label">Projected Stockout Risk</span>
              <div className="kpi-value" style={{ color: scenario.stockout_risk === 'CRITICAL' ? 'var(--status-critical)' : 'var(--status-healthy)' }}>
                {scenario.stockout_risk}
              </div>
              <span className="kpi-sub">Coverage: {scenario.coverage_days ? `${scenario.coverage_days} days` : 'Exhausted'}</span>
            </div>
          </div>

          {/* Grouped Bar Chart */}
          <div className="sim-panel" style={{ height: '320px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>
              Baseline Policy vs. What-If Scenario Policy
            </h4>
            <ResponsiveContainer width="100%" height="85%">
              <BarChart data={comparisonChartData} margin={{ top: 10, right: 20, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis dataKey="name" stroke="var(--text-tertiary)" fontSize={11} />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-surface-1)', borderColor: 'var(--border-default)', fontSize: '12px' }}
                />
                <Legend wrapperStyle={{ fontSize: '12px', paddingTop: '8px' }} />
                <Bar dataKey="Baseline" fill="var(--accent-primary)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Scenario" fill="var(--status-watch)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Persistent Saved Scenarios Section */}
      <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Bookmark size={16} color="var(--accent-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Persisted Policy Scenarios
            </h3>
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
            {savedScenarios.length} Saved Scenario(s)
          </span>
        </div>

        {savedScenarios.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
              <thead>
                <tr style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '10px 16px' }}>Scenario Name</th>
                  <th style={{ padding: '10px 16px' }}>Target SKU</th>
                  <th style={{ padding: '10px 16px' }}>Policy Parameters</th>
                  <th style={{ padding: '10px 16px' }}>Simulated Safety Stock</th>
                  <th style={{ padding: '10px 16px' }}>Stockout Risk</th>
                  <th style={{ padding: '10px 16px' }}>Saved Date</th>
                  <th style={{ padding: '10px 16px', textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {savedScenarios.map(sc => {
                  const scParams = sc.parameters || {};
                  const scResults = sc.results || {};
                  const scBaseline = scResults.baseline || {};
                  const scScenario = scResults.scenario || {};
                  const prod = products.find(p => p.product_id === scParams.product_id);
                  return (
                    <tr key={sc.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                      <td style={{ padding: '10px 16px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{sc.name}</div>
                        {sc.description && (
                          <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '2px' }}>
                            {sc.description}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: '10px 16px', color: 'var(--text-secondary)' }}>
                        {prod ? `${prod.product_name} (${prod.external_product_id})` : `Product #${scParams.product_id}`}
                      </td>
                      <td style={{ padding: '10px 16px' }}>
                        <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', background: 'var(--bg-surface-2)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                          {scParams.demand_multiplier}x Demand • +{scParams.lead_time_delta}d Lead • {((scParams.service_level_target || 0.95) * 100).toFixed(0)}% SL
                        </span>
                      </td>
                      <td style={{ padding: '10px 16px', fontWeight: 600 }}>
                        {scScenario.safety_stock != null ? `${scScenario.safety_stock} units` : '—'}
                      </td>
                      <td style={{ padding: '10px 16px' }}>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontWeight: 700,
                          background: scScenario.stockout_risk === 'CRITICAL' ? 'var(--status-critical-bg)' : 'var(--status-healthy-bg)',
                          color: scScenario.stockout_risk === 'CRITICAL' ? 'var(--status-critical)' : 'var(--status-healthy)',
                        }}>
                          {scScenario.stockout_risk || 'LOW'}
                        </span>
                      </td>
                      <td style={{ padding: '10px 16px', color: 'var(--text-secondary)' }}>
                        {sc.created_at ? new Date(sc.created_at).toLocaleDateString() : 'Recent'}
                      </td>
                      <td style={{ padding: '10px 16px', textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                          <button
                            onClick={() => handleLoadSavedScenario(sc)}
                            style={{
                              padding: '4px 8px',
                              fontSize: '11px',
                              background: 'var(--accent-primary-dim)',
                              color: 'var(--accent-primary)',
                              border: 'none',
                              borderRadius: 'var(--r-sm)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <Play size={11} /> Load
                          </button>
                          <button
                            onClick={() => handleDeleteSavedScenario(sc.id, sc.name)}
                            style={{
                              padding: '4px 8px',
                              fontSize: '11px',
                              background: 'var(--status-critical-bg)',
                              color: 'var(--status-critical)',
                              border: 'none',
                              borderRadius: 'var(--r-sm)',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px',
                            }}
                          >
                            <Trash2 size={11} /> Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: '48px 24px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
            <Bookmark size={28} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
            <p style={{ margin: 0, fontSize: '13px' }}>
              No scenarios saved yet. Use the controls above to test parameter variations and click "Save Scenario" to persist them.
            </p>
          </div>
        )}
      </div>

      {/* Save Modal */}
      {showSaveModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0, 0, 0, 0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            background: 'var(--bg-surface-1)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--r-lg)',
            width: '100%', maxWidth: '480px',
            padding: '24px',
            boxShadow: 'var(--shadow-lg)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Save What-If Scenario
              </h3>
              <button onClick={() => setShowSaveModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleConfirmSave}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Scenario Title
                </label>
                <input
                  type="text"
                  required
                  value={scenarioName}
                  onChange={e => setScenarioName(e.target.value)}
                  placeholder="e.g. Q4 Surge Scenario (+20% Demand, +5d Lead)"
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--r-md)',
                    border: '1px solid var(--border-default)',
                    background: 'var(--bg-surface-2)',
                    color: 'var(--text-primary)',
                    fontSize: '13px',
                  }}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  Description / Notes (Optional)
                </label>
                <textarea
                  rows={3}
                  value={scenarioDesc}
                  onChange={e => setScenarioDesc(e.target.value)}
                  placeholder="Rationale or assumptions for this policy simulation..."
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 'var(--r-md)',
                    border: '1px solid var(--border-default)',
                    background: 'var(--bg-surface-2)',
                    color: 'var(--text-primary)',
                    fontSize: '13px',
                    resize: 'vertical',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button
                  type="button"
                  onClick={() => setShowSaveModal(false)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 'var(--r-md)',
                    border: '1px solid var(--border-default)',
                    background: 'transparent',
                    color: 'var(--text-secondary)',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={savingScenario}
                  style={{
                    padding: '8px 16px',
                    borderRadius: 'var(--r-md)',
                    border: 'none',
                    background: 'var(--accent-primary)',
                    color: '#fff',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: savingScenario ? 'not-allowed' : 'pointer',
                  }}
                >
                  {savingScenario ? 'Saving...' : 'Save Scenario'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
