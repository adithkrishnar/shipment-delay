import { useEffect, useState } from 'react';
import { getAnomalies } from '../services/api';
import Panel from '../components/Panel';
import Loader from '../components/Loader';
import RiskBadge from '../components/RiskBadge';

/* ── Anomaly score bar ───────────────────────────────────────── */
function ScoreBar({ score, max = 10 }) {
  const pct = Math.min(100, ((score || 0) / max) * 100);
  const color = pct >= 80 ? 'var(--status-critical)'
              : pct >= 60 ? 'var(--status-risk)'
              : pct >= 40 ? 'var(--status-watch)'
              : 'var(--status-healthy)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 60,
        height: 3,
        background: 'var(--bg-surface-3)',
        borderRadius: 999,
        overflow: 'hidden',
        flexShrink: 0,
      }}>
        <div style={{
          width: `${pct}%`,
          height: '100%',
          background: color,
          borderRadius: 999,
          transition: 'width 0.8s var(--ease-out)',
        }} />
      </div>
      <span style={{ fontSize: 11, fontVariantNumeric: 'tabular-nums', color, fontWeight: 700 }}>
        {typeof score === 'number' ? score.toFixed(1) : score}
      </span>
    </div>
  );
}

/* ── Severity border colour ──────────────────────────────────── */
function severityBorderColor(severity) {
  const s = String(severity || '').toLowerCase();
  if (s === 'critical') return 'var(--status-critical)';
  if (s === 'high')     return 'var(--status-risk)';
  if (s === 'medium')   return 'var(--status-watch)';
  return 'var(--status-healthy)';
}

export default function Anomalies({ company }) {
  const [d, setD] = useState(null);

  const [error, setError] = useState(null);

  const load = () => {
    if (company) {
      setError(null);
      getAnomalies(company.id)
        .then(setD)
        .catch(e => {
          const detail = e.response?.data?.detail;
          setError(typeof detail === 'string' ? detail : (Array.isArray(detail) ? JSON.stringify(detail) : (e.message || "Failed to load anomalies")));
        });
    }
  };

  useEffect(() => {
    load();
  }, [company]);

  if (error) {
    return (
      <div className="page animate-fade">
        <div className="page-header">
          <div className="page-eyebrow">Anomaly Detection</div>
          <h1 className="page-title">Find behavior that deserves investigation.</h1>
        </div>
        <Panel title="Error Loading Anomalies">
          <div style={{ color: 'var(--status-critical)', padding: '20px 0' }}>
            <p style={{ marginBottom: 16 }}>{error}</p>
            <button className="primary" onClick={load}>Retry</button>
          </div>
        </Panel>
      </div>
    );
  }

  if (!d) return <Loader />;

  const criticalCount = d.anomalies.filter(a =>
    String(a.severity || '').toLowerCase() === 'critical'
  ).length;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div className="page-eyebrow">Anomaly Detection</div>
        <h1 className="page-title">Find behavior that deserves investigation.</h1>
        <p className="page-subtitle">
          {d.anomalies.length} anomalies detected
          {criticalCount > 0 && (
            <span style={{
              marginLeft: 10,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '2px 8px',
              background: 'var(--status-critical-bg)',
              border: '1px solid var(--status-critical-border)',
              borderRadius: 'var(--r-sm)',
              fontSize: 10,
              fontWeight: 700,
              color: 'var(--status-critical)',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
            }}>
              {criticalCount} critical
            </span>
          )}
        </p>
      </div>

      <Panel title={`${d.anomalies.length} detected anomalies`}>
        {d.anomalies.length === 0 ? (
          <div className="empty">No anomalies detected. Supply chain signals are within normal ranges.</div>
        ) : (
          <div className="stagger" style={{ display: 'grid', gap: 8 }}>
            {d.anomalies.map((a, i) => {
              const isCritical = String(a.severity || '').toLowerCase() === 'critical';
              return (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    gap: 14,
                    alignItems: 'flex-start',
                    padding: '14px 16px',
                    background: 'var(--bg-surface-1)',
                    border: '1px solid var(--border-subtle)',
                    borderLeft: `3px solid ${severityBorderColor(a.severity)}`,
                    borderRadius: 'var(--r-lg)',
                    transition: 'background var(--t-fast)',
                  }}
                >
                  <div style={{ paddingTop: 1 }}>
                    <span
                      className={`risk risk-${String(a.severity || 'low').toLowerCase()}${isCritical ? ' pulse-active' : ''}`}
                    >
                      {String(a.severity || 'LOW').toUpperCase()}
                    </span>
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontWeight: 700,
                      fontSize: 13,
                      color: 'var(--text-primary)',
                      marginBottom: 4,
                    }}>
                      {a.entity_type} · {a.metric}
                    </div>
                    <p style={{
                      fontSize: 12,
                      color: 'var(--text-secondary)',
                      margin: '0 0 8px',
                      lineHeight: 1.6,
                    }}>
                      {a.explanation}
                    </p>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                      <ScoreBar score={a.score} />
                      {a.value != null && (
                        <span style={{ fontSize: 11, color: 'var(--text-tertiary)', fontWeight: 500 }}>
                          Value: <span style={{ color: 'var(--text-secondary)', fontWeight: 700 }}>{a.value}</span>
                        </span>
                      )}
                      {a.date && (
                        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                          {a.date}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
}
