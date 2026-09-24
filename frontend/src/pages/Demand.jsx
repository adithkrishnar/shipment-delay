import { useEffect, useState } from 'react';
import { getForecast } from '../services/api';
import Panel from '../components/Panel';
import Loader from '../components/Loader';
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, ReferenceLine
} from 'recharts';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

/* ── Custom Tooltip ──────────────────────────────────────────── */
function ForecastTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-surface-3)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--r-md)',
      padding: '10px 14px',
      fontSize: 12,
    }}>
      <div style={{ color: 'var(--text-tertiary)', marginBottom: 6, fontWeight: 600, fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        {label}
      </div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums', fontWeight: 700 }}>
          {p.value?.toLocaleString()} units
        </div>
      ))}
    </div>
  );
}

/* ── Trend indicator ─────────────────────────────────────────── */
function TrendIndicator({ data }) {
  if (!data || data.length < 2) return null;
  const first = data[0]?.predicted_quantity || 0;
  const last = data[data.length - 1]?.predicted_quantity || 0;
  const pct = first > 0 ? Math.round(((last - first) / first) * 100) : 0;

  if (pct > 2) return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--status-healthy)', fontSize: 12, fontWeight: 700 }}>
      <TrendingUp size={13} /> +{pct}%
    </span>
  );
  if (pct < -2) return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--status-critical)', fontSize: 12, fontWeight: 700 }}>
      <TrendingDown size={13} /> {pct}%
    </span>
  );
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--text-tertiary)', fontSize: 12, fontWeight: 600 }}>
      <Minus size={13} /> Stable
    </span>
  );
}

export default function Demand({ company }) {
  const [d, setD] = useState(null);
  const [h, setH] = useState(30);
  const [p, setP] = useState(0);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (company) {
      setError(null);
      setD(null);
      getForecast(company.id, h)
        .then(x => {
          setD(x);
          setP(x.products[0]?.product_id || 0);
        })
        .catch(e => {
          const detail = e.response?.data?.detail;
          setError(typeof detail === 'string' ? detail : (Array.isArray(detail) ? JSON.stringify(detail) : (e.message || "Failed to load demand forecast")));
        });
    }
  }, [company, h]);

  if (error) {
    return (
      <div className="page animate-fade">
        <div className="page-header">
          <div className="page-eyebrow">Demand Forecasting</div>
          <h1 className="page-title">Turn historical demand into a planning signal.</h1>
        </div>
        <Panel title="Error Loading Forecast">
          <div style={{ color: 'var(--status-critical)', padding: '20px 0' }}>
            {error}
          </div>
        </Panel>
      </div>
    );
  }

  if (!d) return <Loader />;

  const selected = d.products?.find(x => x.product_id === p) || d.products?.[0];

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div className="page-eyebrow">Demand Forecasting</div>
        <h1 className="page-title">Turn historical demand into a planning signal.</h1>
      </div>

      {/* ── Toolbar ───────────────────────────────────────────── */}
      <div className="toolbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <select
            value={p}
            onChange={e => setP(Number(e.target.value))}
            style={{ width: 'auto', minWidth: 220 }}
            aria-label="Select product"
          >
            {d.products.map(x => (
              <option value={x.product_id} key={x.product_id}>{x.product_name}</option>
            ))}
          </select>

          {selected && (
            <TrendIndicator data={selected.forecast} />
          )}
        </div>

        <div className="seg" role="group" aria-label="Forecast horizon">
          {[7, 30, 90].map(x => (
            <button
              key={x}
              className={h === x ? 'selected' : ''}
              onClick={() => setH(x)}
              aria-pressed={h === x}
            >
              {x}D
            </button>
          ))}
        </div>
      </div>

      {/* ── Forecast Chart ────────────────────────────────────── */}
      {selected && (
        <Panel
          title={`${selected.product_name} · ${h}-day forecast`}
          action={
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--text-tertiary)' }}>
                <span style={{ width: 24, height: 2, background: 'var(--accent-primary)', display: 'inline-block', borderRadius: 1 }} />
                Predicted demand
              </span>
            </div>
          }
        >
          <div className="chart large">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={selected.forecast} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="2 6" stroke="var(--border-subtle)" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  width={48}
                />
                <Tooltip content={<ForecastTooltip />} />
                <Line
                  type="monotone"
                  dataKey="predicted_quantity"
                  stroke="var(--accent-primary)"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4, fill: 'var(--accent-primary)', strokeWidth: 0 }}
                  animationDuration={800}
                  animationEasing="ease-out"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="model-note" style={{ marginTop: 14 }}>
            Model source: <b>{selected.model_source}</b>
            <span style={{ margin: '0 10px', color: 'var(--text-muted)' }}>·</span>
            Last actual: <b>{selected.last_actual_quantity?.toLocaleString()}</b> units
          </div>
        </Panel>
      )}
    </div>
  );
}
