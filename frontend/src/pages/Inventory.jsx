import { useEffect, useState } from 'react';
import { getInventory } from '../services/api';
import Panel from '../components/Panel';
import Loader from '../components/Loader';
import RiskBadge from '../components/RiskBadge';

/* ── Coverage bar ────────────────────────────────────────────── */
function CoverageBar({ days, maxDays = 90 }) {
  if (days == null || !isFinite(days)) {
    return <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>∞</span>;
  }
  const pct = Math.min(100, (days / maxDays) * 100);
  const color = days <= 7  ? 'var(--status-critical)'
              : days <= 14 ? 'var(--status-risk)'
              : days <= 30 ? 'var(--status-watch)'
              : 'var(--status-healthy)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 64,
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
        {days}d
      </span>
    </div>
  );
}

/* ── Stockout probability bar ────────────────────────────────── */
function StockoutBar({ prob }) {
  const pct = Math.round((prob || 0) * 100);
  const color = pct >= 70 ? 'var(--status-critical)'
              : pct >= 40 ? 'var(--status-risk)'
              : pct >= 20 ? 'var(--status-watch)'
              : 'var(--status-healthy)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{
        width: 48,
        height: 3,
        background: 'var(--bg-surface-3)',
        borderRadius: 999,
        overflow: 'hidden',
        flexShrink: 0,
      }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 999 }} />
      </div>
      <span style={{ fontSize: 11, fontVariantNumeric: 'tabular-nums', color, fontWeight: 700 }}>{pct}%</span>
    </div>
  );
}

export default function Inventory({ company }) {
  const [d, setD] = useState(null);

  useEffect(() => {
    if (company) getInventory(company.id).then(setD);
  }, [company]);

  if (!d) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div className="page-eyebrow">Inventory Intelligence</div>
        <h1 className="page-title">See what can run out — and what is sitting idle.</h1>
      </div>

      {/* ── Summary KPIs ──────────────────────────────────────── */}
      <div className="metrics stagger" style={{ gridTemplateColumns: 'repeat(3, 1fr)', marginBottom: 20 }}>
        <div className="metric">
          <span>Inventory units</span>
          <strong>{d.summary.inventory_units.toLocaleString()}</strong>
          <small>Total on-hand</small>
        </div>
        <div className="metric danger">
          <span>High stockout risk</span>
          <strong>{d.summary.stockout_high}</strong>
          <small>Products at risk</small>
        </div>
        <div className="metric warning">
          <span>High overstock risk</span>
          <strong>{d.summary.overstock_high}</strong>
          <small>Products overstocked</small>
        </div>
      </div>

      <Panel title="Product inventory health">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Product</th>
                <th>On-hand inventory</th>
                <th>Daily demand</th>
                <th>Coverage</th>
                <th>Stockout risk</th>
                <th>Reorder qty</th>
              </tr>
            </thead>
            <tbody>
              {d.products.map(x => (
                <tr key={x.product_id}>
                  <td>
                    <strong>{x.product_name}</strong>
                    <small>{x.category}</small>
                  </td>
                  <td style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: 'var(--text-primary)' }}>
                    {x.inventory_level.toLocaleString()}
                  </td>
                  <td style={{ fontVariantNumeric: 'tabular-nums' }}>
                    {x.daily_demand}
                  </td>
                  <td>
                    <CoverageBar days={x.inventory_coverage_days} />
                  </td>
                  <td>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <RiskBadge risk={x.stockout_risk} />
                      <StockoutBar prob={x.stockout_probability} />
                    </div>
                  </td>
                  <td style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: 'var(--accent-primary)' }}>
                    {x.recommended_order_quantity.toLocaleString()}
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
