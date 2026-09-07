import { useEffect, useState } from 'react';
import { getShipments } from '../services/api';
import Loader from '../components/Loader';
import RiskBadge from '../components/RiskBadge';
import Panel from '../components/Panel';

/* ── Risk tier to highlight class ────────────────────────────── */
function rowClass(tier) {
  const t = String(tier || '').toLowerCase();
  if (t === 'critical') return ' risk-row-critical';
  if (t === 'high')     return ' risk-row-high';
  return '';
}

/* ── Delay probability bar ───────────────────────────────────── */
function ProbBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct >= 70 ? 'var(--status-critical)'
              : pct >= 40 ? 'var(--status-risk)'
              : pct >= 20 ? 'var(--status-watch)'
              : 'var(--status-healthy)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 72,
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
      <span style={{ fontSize: 12, fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)', fontWeight: 600 }}>
        {pct}%
      </span>
    </div>
  );
}

/* ── Risk distribution summary ────────────────────────────────── */
function RiskSummaryBar({ shipments }) {
  const counts = { low: 0, medium: 0, high: 0, critical: 0 };
  shipments.forEach(s => {
    const t = String(s.risk_tier || 'low').toLowerCase();
    if (counts[t] !== undefined) counts[t]++;
  });
  const total = shipments.length || 1;
  const items = [
    { key: 'low',      label: 'Low',      color: 'var(--status-healthy)',  bg: 'var(--status-healthy-bg)' },
    { key: 'medium',   label: 'Medium',   color: 'var(--status-watch)',    bg: 'var(--status-watch-bg)' },
    { key: 'high',     label: 'High',     color: 'var(--status-risk)',     bg: 'var(--status-risk-bg)' },
    { key: 'critical', label: 'Critical', color: 'var(--status-critical)', bg: 'var(--status-critical-bg)' },
  ];

  return (
    <div style={{
      display: 'flex',
      gap: 8,
      marginBottom: 16,
      flexWrap: 'wrap',
    }}>
      {items.map(({ key, label, color, bg }) => (
        <div key={key} style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          background: bg,
          border: `1px solid ${color}33`,
          borderRadius: 'var(--r-md)',
          padding: '6px 12px',
          flex: 1,
          minWidth: 100,
        }}>
          <span style={{ fontSize: 18, fontWeight: 800, fontVariantNumeric: 'tabular-nums', color, lineHeight: 1 }}>
            {counts[key]}
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color }}>
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Shipments({ company }) {
  const [d, setD] = useState(null);

  useEffect(() => {
    if (company) getShipments(company.id).then(setD);
  }, [company]);

  if (!d) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div className="page-eyebrow">Shipment Intelligence</div>
        <h1 className="page-title">Predict disruption before arrival.</h1>
        <p className="page-subtitle">
          {d.shipments.length} shipments monitored · Model: <strong style={{ color: 'var(--text-primary)' }}>{d.model_source}</strong>
        </p>
      </div>

      <RiskSummaryBar shipments={d.shipments} />

      <Panel title="Shipment register">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Shipment</th>
                <th>Route</th>
                <th>Carrier</th>
                <th>Delay probability</th>
                <th>Risk</th>
                <th>Expected delay</th>
              </tr>
            </thead>
            <tbody>
              {d.shipments.map(s => (
                <tr key={s.shipment_id} className={rowClass(s.risk_tier)}>
                  <td>
                    <strong>{s.external_shipment_id}</strong>
                    <small>{s.transport_mode}</small>
                  </td>
                  <td style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
                    {s.origin} <span style={{ color: 'var(--text-muted)', margin: '0 4px' }}>→</span> {s.destination}
                  </td>
                  <td>{s.carrier || <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                  <td><ProbBar value={s.delay_probability} /></td>
                  <td><RiskBadge risk={s.risk_tier} /></td>
                  <td style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {s.expected_delay_days != null
                      ? <>{s.expected_delay_days}<span style={{ color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 2 }}>d</span></>
                      : <span style={{ color: 'var(--text-muted)' }}>—</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
