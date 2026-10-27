import React, { useEffect, useState } from 'react';
import { getModels, retrainModel } from '../services/api';
import Loader from '../components/Loader';
import { Brain, Sparkles, CheckCircle2, TrendingUp, RefreshCw, BarChart2, ShieldCheck, AlertCircle } from 'lucide-react';

export default function Models({ company }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retraining, setRetraining] = useState(false);
  const [retrainSuccess, setRetrainSuccess] = useState(null);

  const fetchModels = () => {
    if (!company?.id) return;
    setLoading(true);
    getModels(company.id)
      .then(res => {
        setData(res);
        setError(null);
      })
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchModels();
  }, [company?.id]);

  const handleRetrain = async () => {
    if (!company?.id) return;
    setRetraining(true);
    setRetrainSuccess(null);
    try {
      const res = await retrainModel(company.id);
      setRetrainSuccess('Demand forecasting retrain job initiated successfully.');
      setTimeout(fetchModels, 2500);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setRetraining(false);
    }
  };

  if (loading) return <Loader />;

  if (error && !data) {
    return (
      <div className="page animate-fade" style={{ padding: '32px', textAlign: 'center' }}>
        <p style={{ color: 'var(--status-critical)', marginBottom: '16px' }}>{error}</p>
        <button className="btn-secondary" onClick={fetchModels}>Retry</button>
      </div>
    );
  }

  const modelsArray = Array.isArray(data) ? data : (data?.models || []);
  // Filter exclusively for demand forecasting models (purging shipment delay models)
  const demandModels = modelsArray.filter(m => m.model_type === 'demand_forecast');
  const activeModel = demandModels.find(m => m.status === 'active' && m.company_id === company?.id) 
    || demandModels.find(m => m.status === 'active')
    || demandModels[0];

  const metrics = activeModel?.metrics || {};
  const comp = metrics.comparison || {};
  const selectedModelMetrics = comp[metrics.selected_model] || {};
  const baselineMetrics = comp.naive_seasonal_baseline || {};

  return (
    <div className="page animate-fade" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '28px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              MODELS & QUALITY
            </h1>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              Inventory Demand Intelligence
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
            Machine learning model architectures, training telemetry, cross-validation metrics, and prediction quality.
          </p>
        </div>

        <div>
          <button
            className="btn-primary"
            onClick={handleRetrain}
            disabled={retraining}
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', fontSize: '13px' }}
          >
            <RefreshCw size={14} className={retraining ? 'animate-spin' : ''} />
            {retraining ? 'Retraining...' : 'Retrain Demand Model'}
          </button>
        </div>
      </div>

      {retrainSuccess && (
        <div style={{ padding: '12px 16px', background: 'var(--status-healthy-bg)', border: '1px solid var(--status-healthy-border)', borderRadius: 'var(--r-md)', color: 'var(--status-healthy)', marginBottom: '24px', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle2 size={16} />
          {retrainSuccess}
        </div>
      )}

      {activeModel ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Active Model Hero Card */}
          <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '28px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: 'var(--accent-primary-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <Brain size={22} color="var(--accent-primary)" />
                </div>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                    {activeModel.metrics?.selected_model ? activeModel.metrics.selected_model.replace('_', ' ').toUpperCase() : 'GRADIENT BOOSTING'} DEMAND FORECASTER
                  </h2>
                  <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginTop: '2px' }}>
                    Version {activeModel.version} • Source: <strong style={{ color: 'var(--text-secondary)' }}>{activeModel.model_source === 'company_specific' ? 'Company Specific Model' : 'Shared Baseline Engine'}</strong>
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, padding: '4px 10px', borderRadius: '4px', background: 'var(--status-healthy-bg)', color: 'var(--status-healthy)', textTransform: 'uppercase' }}>
                  {activeModel.status || 'ACTIVE'}
                </span>
                <span style={{ fontSize: '11px', fontWeight: 600, padding: '4px 10px', borderRadius: '4px', background: 'var(--bg-surface-2)', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)' }}>
                  Trained {activeModel.training_date ? new Date(activeModel.training_date).toLocaleDateString() : 'Recent'}
                </span>
              </div>
            </div>

            {/* Metrics Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '28px' }}>
              <div style={{ background: 'var(--bg-surface-2)', padding: '16px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '6px' }}>Mean Absolute Error (MAE)</div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {typeof selectedModelMetrics.mae === 'number'
                    ? selectedModelMetrics.mae.toFixed(2)
                    : (typeof metrics.mae === 'number' ? metrics.mae.toFixed(2) : '—')} <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-tertiary)' }}>units</span>
                </div>
                {typeof baselineMetrics.mae === 'number' && typeof selectedModelMetrics.mae === 'number' && (
                  <div style={{ fontSize: '11px', color: 'var(--status-healthy)', marginTop: '4px' }}>
                    ↓ {(((baselineMetrics.mae - selectedModelMetrics.mae) / baselineMetrics.mae) * 100).toFixed(1)}% vs seasonal baseline
                  </div>
                )}
              </div>

              <div style={{ background: 'var(--bg-surface-2)', padding: '16px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '6px' }}>Root Mean Square Error (RMSE)</div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {typeof selectedModelMetrics.rmse === 'number'
                    ? selectedModelMetrics.rmse.toFixed(2)
                    : (typeof metrics.rmse === 'number' ? metrics.rmse.toFixed(2) : '—')}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '4px' }}>Penalizes outlier forecast deviations</div>
              </div>

              <div style={{ background: 'var(--bg-surface-2)', padding: '16px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '6px' }}>Mean Absolute % Error (MAPE)</div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--status-healthy)' }}>
                  {typeof selectedModelMetrics.mape === 'number'
                    ? `${selectedModelMetrics.mape.toFixed(2)}%`
                    : (typeof metrics.mape === 'number' ? `${metrics.mape.toFixed(2)}%` : '—')}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--status-healthy)', marginTop: '4px' }}>Percentage deviation per day</div>
              </div>

              <div style={{ background: 'var(--bg-surface-2)', padding: '16px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '6px' }}>Weighted Absolute % Error (WAPE)</div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--status-healthy)' }}>
                  {typeof selectedModelMetrics.wape === 'number'
                    ? `${(selectedModelMetrics.wape * 100).toFixed(2)}%`
                    : (typeof metrics.wape === 'number' ? `${(metrics.wape * 100).toFixed(2)}%` : '—')}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--status-healthy)', marginTop: '4px' }}>Total volume normalized accuracy</div>
              </div>

              <div style={{ background: 'var(--bg-surface-2)', padding: '16px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '6px' }}>Training Sample Volume</div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  {typeof metrics.train_rows === 'number' ? metrics.train_rows.toLocaleString() : (activeModel.dataset_size?.toLocaleString() || '—')}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                  {typeof metrics.test_rows === 'number' ? `+ ${metrics.test_rows.toLocaleString()} test points` : 'Cross-validated records'}
                </div>
              </div>
            </div>

            {/* Architecture Details */}
            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '20px' }}>
              <div>
                <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '12px' }}>
                  Algorithm Configuration
                </h3>
                <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-tertiary)' }}>Model Family:</span>
                    <strong style={{ color: 'var(--text-primary)' }}>Nonlinear Ensemble Regressor</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-tertiary)' }}>Primary Features:</span>
                    <strong style={{ color: 'var(--text-primary)' }}>Lags (t-1, t-7, t-14), DayOfWeek, Trend</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-tertiary)' }}>Forecast Horizon:</span>
                    <strong style={{ color: 'var(--text-primary)' }}>Multi-step (7, 30, 60, 90 Days)</strong>
                  </div>
                </div>
              </div>

              <div>
                <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '12px' }}>
                  Quality & Integrity Safeguards
                </h3>
                <div style={{ fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--status-healthy)' }}>
                    <ShieldCheck size={14} /> Time-Series Walk-Forward Split (No data leakage)
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--status-healthy)' }}>
                    <ShieldCheck size={14} /> Non-negative Demand Enforced (clipping at 0)
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--status-healthy)' }}>
                    <ShieldCheck size={14} /> Automatic Fallback to Baseline if History &lt; 20 Days
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Model Registry Version History */}
          <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <BarChart2 size={16} color="var(--accent-primary)" />
                <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                  Demand Model Training Registry
                </h3>
              </div>
              <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
                {demandModels.length} Registered Version(s)
              </span>
            </div>

            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                    <th style={{ padding: '10px 16px' }}>Version</th>
                    <th style={{ padding: '10px 16px' }}>Source</th>
                    <th style={{ padding: '10px 16px' }}>Algorithm</th>
                    <th style={{ padding: '10px 16px' }}>Training Date</th>
                    <th style={{ padding: '10px 16px' }}>Dataset Size</th>
                    <th style={{ padding: '10px 16px' }}>Test MAE</th>
                    <th style={{ padding: '10px 16px' }}>Test MAPE</th>
                    <th style={{ padding: '10px 16px' }}>Test WAPE</th>
                    <th style={{ padding: '10px 16px' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {demandModels.map(m => {
                    const mMetrics = m.metrics || {};
                    const mComp = mMetrics.comparison || {};
                    const mSelected = mComp[mMetrics.selected_model] || {};
                    return (
                      <tr key={m.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                        <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {m.version}
                        </td>
                        <td style={{ padding: '10px 16px' }}>
                          <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', background: m.company_id ? 'var(--accent-primary-dim)' : 'var(--bg-surface-2)', color: m.company_id ? 'var(--accent-primary)' : 'var(--text-secondary)' }}>
                            {m.model_source === 'company_specific' ? 'Company' : 'Base'}
                          </span>
                        </td>
                        <td style={{ padding: '10px 16px' }}>
                          {mMetrics.selected_model ? mMetrics.selected_model.replace('_', ' ') : 'Gradient Boosting'}
                        </td>
                        <td style={{ padding: '10px 16px', color: 'var(--text-secondary)' }}>
                          {m.training_date ? new Date(m.training_date).toLocaleDateString() : 'N/A'}
                        </td>
                        <td style={{ padding: '10px 16px' }}>
                          {mMetrics.train_rows ? mMetrics.train_rows.toLocaleString() : (m.dataset_size?.toLocaleString() || 'N/A')}
                        </td>
                        <td style={{ padding: '10px 16px', fontWeight: 600 }}>
                          {typeof mSelected.mae === 'number' ? mSelected.mae.toFixed(2) : (typeof mMetrics.mae === 'number' ? mMetrics.mae.toFixed(2) : '—')}
                        </td>
                        <td style={{ padding: '10px 16px', color: 'var(--status-healthy)', fontWeight: 600 }}>
                          {typeof mSelected.mape === 'number' ? `${mSelected.mape.toFixed(2)}%` : (typeof mMetrics.mape === 'number' ? `${mMetrics.mape.toFixed(2)}%` : '—')}
                        </td>
                        <td style={{ padding: '10px 16px', color: 'var(--status-healthy)', fontWeight: 600 }}>
                          {typeof mSelected.wape === 'number' ? `${(mSelected.wape * 100).toFixed(2)}%` : (typeof mMetrics.wape === 'number' ? `${(mMetrics.wape * 100).toFixed(2)}%` : '—')}
                        </td>
                        <td style={{ padding: '10px 16px' }}>
                          <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, background: m.status === 'active' ? 'var(--status-healthy-bg)' : 'var(--bg-surface-2)', color: m.status === 'active' ? 'var(--status-healthy)' : 'var(--text-tertiary)' }}>
                            {m.status?.toUpperCase() || 'REGISTERED'}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '64px 24px', textAlign: 'center' }}>
          <AlertCircle size={36} color="var(--status-watch)" style={{ margin: '0 auto 16px' }} />
          <h3 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
            No Demand Forecasting Model Registered
          </h3>
          <p style={{ color: 'var(--text-secondary)', maxWidth: '480px', margin: '0 auto 20px', fontSize: '13px' }}>
            Upload company sales records to build an enterprise-grade forecasting model tailored to your demand patterns.
          </p>
          <button className="btn-primary" onClick={handleRetrain} disabled={retraining}>
            {retraining ? 'Initializing...' : 'Train Initial Demand Model'}
          </button>
        </div>
      )}
    </div>
  );
}
