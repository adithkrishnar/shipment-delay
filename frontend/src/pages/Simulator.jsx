import { useEffect, useState } from 'react';
import { getInventory, simulate } from '../services/api';
import Panel from '../components/Panel';
import Loader from '../components/Loader';
import RiskBadge from '../components/RiskBadge';
import { ArrowRight, Play } from 'lucide-react';

const FIELDS = [
  ['demand_multiplier',  'Demand multiplier',           '1.0',  0.1],
  ['inventory_delta',    'Inventory change (units)',     '0',    1],
  ['delay_days',         'Extra shipment delay (days)',  '0',    1],
  ['lead_time_delta',    'Lead-time change (days)',      '0',    1],
  ['incoming_delta',     'Incoming quantity change',     '0',    1],
  ['reorder_delta',      'Reorder adjustment',          '0',    1],
];

/* ── Delta callout ───────────────────────────────────────────── */
function DeltaCallout({ delta }) {
  const change = delta?.stockout_probability_change || 0;
  const pct = (change * 100).toFixed(1);
  const positive = change > 0;
  return (
    <div style={{
      padding: '14px 16px',
      background: positive ? 'var(--status-critical-bg)' : 'var(--status-healthy-bg)',
      border: `1px solid ${positive ? 'var(--status-critical-border)' : 'var(--status-healthy-border)'}`,
      borderRadius: 'var(--r-lg)',
      marginTop: 16,
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: positive ? 'var(--status-critical)' : 'var(--status-healthy)', marginBottom: 4 }}>
        Impact summary
      </div>
      <div style={{ fontSize: 14, color: 'var(--text-primary)', fontWeight: 600 }}>
        Stockout probability{' '}
        <span style={{ color: positive ? 'var(--status-critical)' : 'var(--status-healthy)', fontWeight: 800 }}>
          {positive ? '+' : ''}{pct}pp
        </span>
      </div>
    </div>
  );
}

/* ── Before/After card ───────────────────────────────────────── */
function BACard({ label, value, risk, isScenario }) {
  return (
    <div style={{
      background: isScenario ? 'var(--accent-primary-dim)' : 'var(--bg-surface-2)',
      border: `1px solid ${isScenario ? 'rgba(34,211,238,0.25)' : 'var(--border-default)'}`,
      borderRadius: 'var(--r-xl)',
      padding: '20px 16px',
      textAlign: 'center',
      transition: 'all var(--t-base)',
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: isScenario ? 'var(--accent-primary)' : 'var(--text-tertiary)', marginBottom: 10 }}>
        {label}
      </div>
      <div style={{ fontSize: 40, fontWeight: 800, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.04em', color: 'var(--text-primary)', lineHeight: 1, marginBottom: 10 }}>
        {value}
      </div>
      <RiskBadge risk={risk} />
    </div>
  );
}

export default function Simulator({ company }) {
  const [inv, setInv] = useState(null);
  const [pid, setPid] = useState(0);
  const [form, setForm] = useState({
    demand_multiplier: 1,
    inventory_delta: 0,
    delay_days: 0,
    lead_time_delta: 0,
    incoming_delta: 0,
    reorder_delta: 0,
  });
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (company) {
      getInventory(company.id).then(x => {
        setInv(x);
        setPid(x.products[0]?.product_id || 0);
      });
    }
  }, [company]);

  if (!inv) return <Loader />;

  const run = () => {
    setRunning(true);
    simulate({
      company_id: company.id,
      product_id: pid,
      ...Object.fromEntries(Object.entries(form).map(([k, v]) => [k, Number(v)]))
    }).then(r => {
      setResult(r);
      setRunning(false);
    }).catch(() => setRunning(false));
  };

  const change = (k, v) => setForm(f => ({ ...f, [k]: v }));

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div className="page-eyebrow">What-If Simulator</div>
        <h1 className="page-title">Test a decision before making it.</h1>
        <p className="page-subtitle">
          Adjust supply chain parameters and simulate the downstream impact on stockout risk and inventory levels.
        </p>
      </div>

      <div className="sim-grid">
        {/* ── Controls ────────────────────────────────────────── */}
        <Panel title="Scenario controls">
          <label className="field-label" htmlFor="sim-product-select">Product</label>
          <select
            id="sim-product-select"
            value={pid}
            onChange={e => setPid(Number(e.target.value))}
            style={{ marginBottom: 20 }}
          >
            {inv.products.map(x => (
              <option key={x.product_id} value={x.product_id}>{x.product_name}</option>
            ))}
          </select>

          <div style={{ display: 'grid', gap: 14 }}>
            {FIELDS.map(([k, l, placeholder, step]) => (
              <div key={k}>
                <label className="field-label" htmlFor={`sim-${k}`}>{l}</label>
                <input
                  id={`sim-${k}`}
                  type="number"
                  step={step}
                  placeholder={placeholder}
                  value={form[k]}
                  onChange={e => change(k, e.target.value)}
                />
              </div>
            ))}
          </div>

          <button
            className="primary full"
            onClick={run}
            disabled={running}
            style={{ marginTop: 20, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}
          >
            {running ? (
              <>
                <div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} aria-hidden="true" />
                Running…
              </>
            ) : (
              <>
                <Play size={13} aria-hidden="true" />
                Run simulation
              </>
            )}
          </button>
        </Panel>

        {/* ── Results ─────────────────────────────────────────── */}
        <Panel title="Scenario result">
          {!result ? (
            <div className="empty">
              Adjust the scenario controls and run the simulator to see the impact.
            </div>
          ) : (
            <div className="animate-fade">
              {/* Before / After */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 36px 1fr', alignItems: 'center', gap: 12, marginBottom: 16 }}>
                <BACard
                  label="Current stockout"
                  value={`${(result.baseline.stockout_probability * 100).toFixed(0)}%`}
                  risk={result.baseline.stockout_risk}
                  isScenario={false}
                />
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <ArrowRight size={18} style={{ color: 'var(--accent-primary)' }} aria-hidden="true" />
                </div>
                <BACard
                  label="Scenario stockout"
                  value={`${(result.scenario.stockout_probability * 100).toFixed(0)}%`}
                  risk={result.scenario.stockout_risk}
                  isScenario={true}
                />
              </div>

              {/* Scenario metrics */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 0 }}>
                <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '14px 16px' }}>
                  <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 8 }}>Scenario inventory</div>
                  <div style={{ fontSize: 22, fontWeight: 800, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.03em', color: 'var(--text-primary)' }}>
                    {result.scenario.inventory_level?.toLocaleString()}
                  </div>
                </div>
                <div style={{ background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '14px 16px' }}>
                  <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: 8 }}>Recommended order</div>
                  <div style={{ fontSize: 22, fontWeight: 800, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.03em', color: 'var(--accent-primary)' }}>
                    {result.scenario.recommended_order_quantity?.toLocaleString()}
                  </div>
                </div>
              </div>

              {/* Delta callout */}
              <DeltaCallout delta={result.delta} />
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
