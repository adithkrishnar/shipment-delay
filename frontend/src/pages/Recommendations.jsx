import { useEffect, useState } from 'react';
import { getRecommendations } from '../services/api';
import Panel from '../components/Panel';
import Loader from '../components/Loader';
import RiskBadge from '../components/RiskBadge';

/* ── Priority → border colour ─────────────────────────────────── */
function priorityBorderColor(priority) {
  const p = String(priority || '').toLowerCase();
  if (p === 'critical' || p === 'high') return 'var(--status-critical)';
  if (p === 'medium') return 'var(--status-watch)';
  return 'var(--status-healthy)';
}

/* ── Summary chips ───────────────────────────────────────────── */
function PrioritySummary({ recs }) {
  const counts = { critical: 0, high: 0, medium: 0, low: 0 };
  recs.forEach(r => {
    const p = String(r.priority || 'low').toLowerCase();
    if (counts[p] !== undefined) counts[p]++;
  });

  const items = [
    { key: 'critical', label: 'Critical', color: 'var(--status-critical)', bg: 'var(--status-critical-bg)', border: 'var(--status-critical-border)' },
    { key: 'high',     label: 'High',     color: 'var(--status-risk)',     bg: 'var(--status-risk-bg)',     border: 'var(--status-risk-border)' },
    { key: 'medium',   label: 'Medium',   color: 'var(--status-watch)',    bg: 'var(--status-watch-bg)',    border: 'var(--status-watch-border)' },
    { key: 'low',      label: 'Low',      color: 'var(--status-healthy)',  bg: 'var(--status-healthy-bg)', border: 'var(--status-healthy-border)' },
  ].filter(x => counts[x.key] > 0);

  if (!items.length) return null;

  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
      {items.map(({ key, label, color, bg, border }) => (
        <div key={key} style={{
          display: 'flex', alignItems: 'center', gap: 6,
          background: bg, border: `1px solid ${border}`,
          borderRadius: 'var(--r-md)', padding: '6px 12px',
        }}>
          <span style={{ fontSize: 16, fontWeight: 800, fontVariantNumeric: 'tabular-nums', color, lineHeight: 1 }}>
            {counts[key]}
          </span>
          <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color }}>
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Recommendations({ company }) {
  const [d, setD] = useState(null);

  useEffect(() => {
    if (company) getRecommendations(company.id).then(setD);
  }, [company]);

  if (!d) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div className="page-eyebrow">AI Recommendations</div>
        <h1 className="page-title">Turn risk signals into actions.</h1>
        <p className="page-subtitle">
          {d.recommendations.length} prioritized actions generated from current supply chain intelligence.
        </p>
      </div>

      <PrioritySummary recs={d.recommendations} />

      <Panel title="Prioritized actions">
        {d.recommendations.length === 0 ? (
          <div className="empty">No active recommendations. Supply chain is operating within acceptable parameters.</div>
        ) : (
          <div className="stagger" style={{ display: 'grid', gap: 8 }}>
            {d.recommendations.map((r, i) => {
              const tier = String(r.priority || 'low').toLowerCase();
              return (
                <div key={i} style={{
                  display: 'flex',
                  gap: 14,
                  alignItems: 'flex-start',
                  padding: '16px 18px',
                  background: 'var(--bg-surface-1)',
                  border: '1px solid var(--border-subtle)',
                  borderLeft: `3px solid ${priorityBorderColor(r.priority)}`,
                  borderRadius: 'var(--r-lg)',
                  transition: 'background var(--t-fast)',
                }}>
                  <div style={{ paddingTop: 1, flexShrink: 0 }}>
                    <RiskBadge risk={r.priority} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: 13, color: 'var(--text-primary)', marginBottom: 6 }}>
                      {r.title}
                    </div>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)', margin: '0 0 8px', lineHeight: 1.6 }}>
                      {r.reason}
                    </p>
                    <div style={{
                      fontSize: 11,
                      color: 'var(--accent-primary)',
                      fontWeight: 600,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}>
                      Expected impact: {r.expected_impact}
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
