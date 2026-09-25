import { useEffect, useState, useRef } from 'react';
import { getModels, retrain, getJob } from '../services/api';
import Panel from '../components/Panel';
import Loader from '../components/Loader';
import { RefreshCw, CheckCircle } from 'lucide-react';

/* ── Model type chip ─────────────────────────────────────────── */
function ModelTypeChip({ type }) {
  const colors = {
    demand_forecast:   { color: 'var(--accent-primary)',   bg: 'var(--accent-primary-dim)',    border: 'rgba(34,211,238,0.2)' },
    shipment_risk:     { color: 'var(--status-risk)',      bg: 'var(--status-risk-bg)',        border: 'var(--status-risk-border)' },
    inventory_risk:    { color: 'var(--status-watch)',     bg: 'var(--status-watch-bg)',       border: 'var(--status-watch-border)' },
    supplier_analysis: { color: 'var(--status-healthy)',   bg: 'var(--status-healthy-bg)',     border: 'var(--status-healthy-border)' },
  };
  const t = String(type || '').toLowerCase().replace(/ /g, '_');
  const style = colors[t] || { color: 'var(--text-tertiary)', bg: 'var(--bg-surface-3)', border: 'var(--border-default)' };
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '2px 8px',
      borderRadius: 'var(--r-sm)',
      fontSize: 10,
      fontWeight: 700,
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
      background: style.bg,
      color: style.color,
      border: `1px solid ${style.border}`,
      whiteSpace: 'nowrap',
    }}>
      {type}
    </span>
  );
}

/* ── Status chip ─────────────────────────────────────────────── */
function StatusChip({ status }) {
  if (status === 'active') {
    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '2px 8px',
        background: 'var(--status-healthy-bg)',
        border: '1px solid var(--status-healthy-border)',
        borderRadius: 'var(--r-sm)',
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: 'var(--status-healthy)',
      }}>
        <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--status-healthy)', display: 'inline-block' }} />
        Active
      </span>
    );
  }
  return (
    <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 500 }}>
      {status}
    </span>
  );
}

/* ── Metrics display ─────────────────────────────────────────── */
function MetricsPill({ metrics }) {
  if (!metrics || Object.keys(metrics).length === 0) {
    return <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>—</span>;
  }
  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
      {Object.entries(metrics).slice(0, 3).map(([k, v]) => (
        <div key={k} style={{
          background: 'var(--bg-surface-3)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-sm)',
          padding: '2px 8px',
          fontSize: 10,
          color: 'var(--text-secondary)',
          fontWeight: 500,
        }}>
          <span style={{ color: 'var(--text-tertiary)', marginRight: 3 }}>{k}:</span>
          <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 700, color: 'var(--text-primary)' }}>
            {typeof v === 'number' ? v.toFixed(3) : String(v)}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Models({ company }) {
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState('info'); // 'info' | 'success' | 'error'
  const [activeJobs, setActiveJobs] = useState([]);

  const pollIntervals = useRef({});

  const [error, setError] = useState(null);

  const load = () => {
    if (company) {
      setError(null);
      getModels(company.id)
        .then(data => {
            if (Array.isArray(data)) setD(data);
            else setError("Invalid response format");
        })
        .catch(e => {
            const detail = e.response?.data?.detail;
            const errMsg = typeof detail === 'string' ? detail : (Array.isArray(detail) ? JSON.stringify(detail) : e.message);
            setError(errMsg || "Failed to load models");
        });
        
      getCompanyJobs(company.id).then(jobs => {
        if (!Array.isArray(jobs)) return;
        const active = jobs.filter(j => j.status === 'queued' || j.status === 'in_progress');
        if (active.length > 0) {
          const ids = active.map(j => j.job_id);
          setActiveJobs(prev => [...new Set([...prev, ...ids])]);
          ids.forEach(pollJob);
        }
      }).catch(() => {});
    }
  };

  useEffect(() => {
    load();
    return () => {
      Object.values(pollIntervals.current).forEach(clearInterval);
    };
  }, [company]);

  const handleRetrain = async () => {
    setMsg('Queuing background training jobs…');
    setMsgType('info');
    try {
      const response = await retrain(company.id);
      if (response.jobs && response.jobs.length > 0) {
        setMsg('Training started in background.');
        setMsgType('info');
        const jobIds = response.jobs.map(j => j.job_id);
        setActiveJobs(prev => [...new Set([...prev, ...jobIds])]);

        jobIds.forEach(jobId => {
          pollJob(jobId);
        });
      }
    } catch (e) {
      const detail = e.response?.data?.detail;
      setMsg(typeof detail === 'string' ? detail : (Array.isArray(detail) ? JSON.stringify(detail) : e.message));
      setMsgType('error');
    }
  };

  const pollJob = (jobId) => {
    if (pollIntervals.current[jobId]) return;

    pollIntervals.current[jobId] = setInterval(async () => {
      try {
        const jobInfo = await getJob(jobId);
        if (jobInfo.status === 'completed' || jobInfo.status === 'failed') {
          clearInterval(pollIntervals.current[jobId]);
          delete pollIntervals.current[jobId];

          setActiveJobs(prev => prev.filter(id => id !== jobId));

          if (jobInfo.status === 'completed') {
            setMsg(`Job ${jobId.substring(0, 6)} completed — metrics updated.`);
            setMsgType('success');
            load();
          } else {
            setMsg(`Job ${jobId.substring(0, 6)} failed: ${jobInfo.error}`);
            setMsgType('error');
          }
        } else {
          setMsg(`Job ${jobId.substring(0, 6)} is ${jobInfo.status}…`);
          setMsgType('info');
        }
      } catch (err) {
        console.error('Polling error', err);
      }
    }, 2500);
  };

  if (error) {
    return (
      <div className="page animate-fade">
        <Panel title="Error Loading Models">
          <div style={{ color: 'var(--status-critical)', padding: '20px 0' }}>
            <p><strong>Failed to load models.</strong></p>
            <p>{error}</p>
          </div>
        </Panel>
      </div>
    );
  }

  if (!d) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div className="page-eyebrow">Model Center</div>
            <h1 className="page-title">Track training, versions and real test metrics.</h1>
            <p className="page-subtitle">{d.length} models registered for this company.</p>
          </div>
          <button
            className="primary"
            onClick={handleRetrain}
            disabled={activeJobs.length > 0}
            style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4, flexShrink: 0 }}
          >
            <RefreshCw size={13} style={{ animation: activeJobs.length > 0 ? 'spin 1s linear infinite' : 'none' }} aria-hidden="true" />
            {activeJobs.length > 0 ? `Training (${activeJobs.length} active)…` : 'Retrain models'}
          </button>
        </div>
      </div>

      {msg && (
        <div style={{
          marginBottom: 20,
          padding: '12px 16px',
          background: msgType === 'error' ? 'var(--status-critical-bg)'
                    : msgType === 'success' ? 'var(--status-healthy-bg)'
                    : 'var(--bg-surface-2)',
          border: `1px solid ${msgType === 'error' ? 'var(--status-critical-border)'
                              : msgType === 'success' ? 'var(--status-healthy-border)'
                              : 'var(--border-default)'}`,
          borderRadius: 'var(--r-lg)',
          fontSize: 13,
          fontWeight: 500,
          color: msgType === 'error' ? 'var(--status-critical)'
               : msgType === 'success' ? 'var(--status-healthy)'
               : 'var(--text-secondary)',
          display: 'flex',
          alignItems: 'center',
          gap: 8,
        }}>
          {msgType === 'success' && <CheckCircle size={14} aria-hidden="true" />}
          {msg}
        </div>
      )}

      {d.length === 0 && activeJobs.length === 0 ? (
        <Panel title="No Models Found">
          <div style={{ padding: '40px 20px', textAlign: 'center' }}>
            <h3 style={{ marginBottom: 12 }}>No trained model available for this company.</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>Upload data and train a model to unlock intelligence.</p>
            <button className="primary" onClick={handleRetrain}>Train Model</button>
          </div>
        </Panel>
      ) : d.length === 0 && activeJobs.length > 0 ? (
        <Panel title="Training Models">
          <div style={{ padding: '40px 20px', textAlign: 'center' }}>
            <h3 style={{ marginBottom: 12 }}>Model training in progress...</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>This might take a few moments depending on data size.</p>
            <button className="primary" onClick={load} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
              <RefreshCw size={13} aria-hidden="true" /> Refresh Status
            </button>
          </div>
        </Panel>
      ) : (
        <Panel title="Model registry">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Model type</th>
                  <th>Source</th>
                  <th>Version</th>
                  <th>Dataset size</th>
                  <th>Metrics</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {d.map(m => (
                  <tr key={m.id}>
                    <td><ModelTypeChip type={m.model_type} /></td>
                    <td style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{m.model_source}</td>
                    <td>
                      <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-tertiary)', fontSize: 11, fontFamily: 'var(--font-mono)' }}>
                        v{m.version}
                      </span>
                    </td>
                    <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {m.dataset_size
                        ? <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{m.dataset_size.toLocaleString()}<span style={{ color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 2 }}>rows</span></span>
                        : <span style={{ color: 'var(--text-muted)' }}>—</span>
                      }
                    </td>
                    <td>
                      <MetricsPill metrics={m.metrics} />
                    </td>
                    <td>
                      <StatusChip status={m.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  );
}
