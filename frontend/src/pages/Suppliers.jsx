import { useEffect, useState } from 'react';
import { getSuppliers } from '../services/api';
import Panel from '../components/Panel';
import Loader from '../components/Loader';
import RiskBadge from '../components/RiskBadge';

/* ── Reliability bar ─────────────────────────────────────────── */
function ReliabilityBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct >= 85 ? 'var(--status-healthy)'
              : pct >= 70 ? 'var(--status-watch)'
              : 'var(--status-critical)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 80,
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
      <span style={{ fontSize: 12, fontVariantNumeric: 'tabular-nums', fontWeight: 700, color }}>
        {pct}%
      </span>
    </div>
  );
}

/* ── Rank badge ──────────────────────────────────────────────── */
function RankBadge({ rank }) {
  const colors = {
    1: { bg: 'rgba(251, 191, 36, 0.15)', color: '#fbbf24', border: 'rgba(251,191,36,0.3)' },
    2: { bg: 'rgba(148, 163, 184, 0.1)',  color: '#94a3b8', border: 'rgba(148,163,184,0.2)' },
    3: { bg: 'rgba(180, 120, 80, 0.1)',   color: '#b47850', border: 'rgba(180,120,80,0.2)' },
  };
  const style = colors[rank] || { bg: 'var(--bg-surface-3)', color: 'var(--text-tertiary)', border: 'var(--border-default)' };
  return (
    <div style={{
      width: 22, height: 22,
      borderRadius: '50%',
      background: style.bg,
      border: `1px solid ${style.border}`,
      display: 'grid',
      placeItems: 'center',
      fontSize: 10,
      fontWeight: 800,
      color: style.color,
      flexShrink: 0,
    }}>
      {rank}
    </div>
  );
}

export default function Suppliers({ company }) {
  const [d, setD] = useState(null);

  useEffect(() => {
    if (company) getSuppliers(company.id).then(setD);
  }, [company]);

  if (!d) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div className="page-eyebrow">Supplier Intelligence</div>
        <h1 className="page-title">Balance cost, reliability and disruption risk.</h1>
        <p className="page-subtitle">{d.suppliers.length} suppliers tracked across your network.</p>
      </div>

      <Panel title="Supplier scorecard">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ width: 32 }}>#</th>
                <th>Supplier</th>
                <th>Reliability</th>
                <th>Lead time</th>
                <th>Delay rate</th>
                <th>Cost index</th>
                <th>Risk tier</th>
              </tr>
            </thead>
            <tbody>
              {d.suppliers.map((s, idx) => (
                <tr key={s.supplier_id}>
                  <td style={{ paddingRight: 0 }}>
                    <RankBadge rank={idx + 1} />
                  </td>
                  <td>
                    <strong>{s.name}</strong>
                    <small>{s.shipment_count} shipments</small>
                  </td>
                  <td>
                    <ReliabilityBar value={s.reliability} />
                  </td>
                  <td style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {s.lead_time_days}
                    <span style={{ color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 2 }}>d</span>
                  </td>
                  <td>
                    <span style={{
                      fontVariantNumeric: 'tabular-nums',
                      fontWeight: 700,
                      color: s.delay_rate > 0.3 ? 'var(--status-critical)'
                           : s.delay_rate > 0.15 ? 'var(--status-watch)'
                           : 'var(--status-healthy)',
                    }}>
                      {(s.delay_rate * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)', fontWeight: 600 }}>
                    {s.cost_index}
                  </td>
                  <td>
                    <RiskBadge risk={s.risk_tier} />
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
