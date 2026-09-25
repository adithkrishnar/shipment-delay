import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell
} from 'recharts';
import { getDashboard, explainDashboard } from '../services/api';
import MetricCard from '../components/MetricCard';
import Panel from '../components/Panel';
import RiskBadge from '../components/RiskBadge';
import Loader from '../components/Loader';
import Modal from '../components/Modal';
import { Cpu, ArrowRight, Activity } from 'lucide-react';

/* ── Risk colour map ─────────────────────────────────────────── */
const RISK_COLORS = {
  low:      '#10b981',
  medium:   '#f59e0b',
  high:     '#f97316',
  critical: '#ef4444',
};

/* ── Custom Recharts Tooltip ─────────────────────────────────── */
function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: 'var(--bg-surface-3)',
      border: '1px solid var(--border-default)',
      borderRadius: 'var(--r-md)',
      padding: '8px 12px',
      fontSize: 12,
      color: 'var(--text-primary)',
      fontWeight: 500,
    }}>
      {label && <div style={{ color: 'var(--text-tertiary)', marginBottom: 4, fontSize: 10 }}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || 'var(--text-primary)' }}>
          {p.name}: <strong>{p.value}</strong>
        </div>
      ))}
    </div>
  );
}

/* ── Markdown renderer (unchanged logic) ─────────────────────── */
function renderMarkdown(text) {
  return text.split('\n').map((line, i) => {
    if (line.startsWith('### ')) {
      return <h3 key={i} style={{ marginTop: 16, marginBottom: 8, color: 'var(--text-primary)', fontSize: 14, fontWeight: 700 }}>{line.replace('### ', '')}</h3>;
    }
    if (line.startsWith('- **')) {
      const parts = line.split('**: ');
      return (
        <li key={i} style={{ margin: '4px 0', marginLeft: 20, color: 'var(--text-secondary)', fontSize: 13 }}>
          <strong style={{ color: 'var(--text-primary)' }}>{parts[0].replace('- **', '')}:</strong> {parts[1]}
        </li>
      );
    }
    if (line.trim() === '') return <br key={i} />;
    const parts = line.split('**');
    return (
      <p key={i} style={{ margin: '4px 0', fontSize: 13, color: 'var(--text-secondary)' }}>
        {parts.map((part, index) =>
          index % 2 === 1
            ? <strong key={index} style={{ color: 'var(--text-primary)' }}>{part}</strong>
            : part
        )}
      </p>
    );
  });
}

export default function Overview({ company }) {
  const [d, setD] = useState(null);
  const [e, setE] = useState('');

  const [isExplainModalOpen, setIsExplainModalOpen] = useState(false);
  const [explanation, setExplanation] = useState('');
  const [isExplaining, setIsExplaining] = useState(false);
  const [explainError, setExplainError] = useState('');

  const load = () => {
    if (company) {
      setE('');
      getDashboard(company.id)
        .then(setD)
        .catch(x => setE(x.response?.data?.detail || x.message));
    }
  };

  useEffect(() => {
    load();
  }, [company]);

  const handleExplainClick = async () => {
    setIsExplainModalOpen(true);
    if (explanation || isExplaining) return;

    setIsExplaining(true);
    setExplainError('');
    try {
      const result = await explainDashboard(company.id);
      setExplanation(result.explanation);
    } catch (err) {
      setExplainError('Failed to generate explanation. Please try again later.');
    } finally {
      setIsExplaining(false);
    }
  };

  if (e) {
    return (
      <div className="page animate-fade">
        <Panel title="Error Loading Overview">
          <div style={{ color: 'var(--status-critical)', padding: '20px 0' }}>
            <p style={{ marginBottom: 16 }}>{e}</p>
            <button className="primary" onClick={load}>Retry</button>
          </div>
        </Panel>
      </div>
    );
  }
  if (!d) return <Loader />;

  const risk = Object.entries(d.shipment_risk_distribution).map(([name, value]) => ({ name, value }));
  const suppliers = d.top_suppliers.map(s => ({
    name: s.name.replace(' Supply Co', ''),
    score: s.risk_score
  }));

  const health = d.kpis.supply_chain_health;
  const healthColor = health >= 80 ? 'var(--status-healthy)' : health >= 60 ? 'var(--status-watch)' : 'var(--status-critical)';

  return (
    <div className="page animate-fade">
      {/* ── Hero ──────────────────────────────────────────────── */}
      <div className="hero" style={{ marginBottom: 24 }}>
        <div>
          <span className="eyebrow">Executive Overview</span>
          <h2 className="hero-title">See the next disruption before it becomes a problem.</h2>
          <p style={{ marginTop: 6, fontSize: 13, color: 'var(--text-secondary)', maxWidth: 540 }}>
            SupplyIQ connects demand, shipment risk and inventory impact into one decision layer.
          </p>
        </div>
        <div className="hero-actions">
          <button
            onClick={handleExplainClick}
            className="btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Cpu size={13} aria-hidden="true" />
            Explain Situation
          </button>
          <Link className="primary" to="/simulator" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            Run a scenario
            <ArrowRight size={13} aria-hidden="true" />
          </Link>
        </div>
      </div>
      
      {d.model_source && (
        <div style={{ marginBottom: 20, padding: '10px 14px', background: 'var(--bg-surface-2)', borderRadius: 'var(--r-md)', fontSize: 12, display: 'flex', gap: 20 }}>
          <div><span style={{ color: 'var(--text-tertiary)' }}>Shipment Risk Model Source:</span> <strong>{d.model_source}</strong></div>
        </div>
      )}

      {/* ── KPI Row ───────────────────────────────────────────── */}
      {(!d.kpis.has_shipments || !d.kpis.has_inventory) && (
        <div style={{ marginBottom: 20, padding: '12px 16px', background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-md)', fontSize: 13, color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {!d.kpis.has_inventory && <div><strong style={{color: 'var(--text-primary)'}}>Inventory data not available for this company.</strong> Import inventory data to unlock stockout analysis.</div>}
          {!d.kpis.has_shipments && <div><strong style={{color: 'var(--text-primary)'}}>Shipment data not available for this company.</strong> Import shipment data to unlock delay risk models.</div>}
        </div>
      )}

      <div className="metrics stagger" style={{ marginBottom: 20 }}>
        <MetricCard label="Products" value={d.kpis.products} sub="Active products" />
        <MetricCard label="High-risk shipments" value={d.kpis.has_shipments ? d.kpis.high_risk_shipments : 'N/A'} tone={d.kpis.has_shipments ? "danger" : ""} sub="Require attention" />
        <MetricCard label="Stockout risks" value={d.kpis.has_inventory ? d.kpis.stockout_risks : 'N/A'} tone={d.kpis.has_inventory ? "warning" : ""} sub="Inventory exposure" />
        <MetricCard label="Inventory units" value={d.kpis.has_inventory && d.kpis.inventory_units != null ? d.kpis.inventory_units.toLocaleString() : 'N/A'} sub="Total on-hand" />
        <MetricCard
          label="Supply-chain health"
          value={`${d.kpis.supply_chain_health}%`}
          tone="success"
          sub="Overall score"
        />
      </div>

      {/* ── Charts Row ────────────────────────────────────────── */}
      <div className="grid2" style={{ marginBottom: 0 }}>
        {/* Shipment risk donut */}
        <Panel title="Shipment risk distribution">
          {d.kpis.has_shipments ? (
            <>
              <div className="chart">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={risk}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={70}
                      outerRadius={100}
                      strokeWidth={0}
                    >
                      {risk.map((x) => (
                        <Cell
                          key={x.name}
                          fill={RISK_COLORS[x.name.toLowerCase()] || '#334e68'}
                        />
                      ))}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="legend">
                {risk.map(x => (
                  <span key={x.name}>
                    <i className={`dot ${x.name.toLowerCase()}`} aria-hidden="true" />
                    {x.name}: <strong style={{ color: 'var(--text-primary)', marginLeft: 2 }}>{x.value}</strong>
                  </span>
                ))}
              </div>
            </>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
              Shipment data not available.
            </div>
          )}
        </Panel>

        {/* Supplier risk bar chart */}
        <Panel title="Supplier risk scores">
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={suppliers} layout="vertical" barCategoryGap="30%">
                <XAxis
                  type="number"
                  domain={[0, 100]}
                  tick={{ fill: 'var(--text-tertiary)', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={100}
                  tick={{ fill: 'var(--text-secondary)', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="score" fill="var(--accent-primary)" radius={[0, 3, 3, 0]} maxBarSize={18} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      {/* ── Priority Actions Feed ─────────────────────────────── */}
      <Panel title="Priority actions">
        {d.top_recommendations.length > 0 ? (
          <div className="recommendations stagger">
            {d.top_recommendations.map((r, i) => {
              const tier = String(r.priority || 'low').toLowerCase();
              return (
                <div
                  key={i}
                  className={`recommendation priority-${tier}`}
                >
                  <RiskBadge risk={r.priority} />
                  <div>
                    <b>{r.title}</b>
                    <p>{r.reason}</p>
                    <small>{r.expected_impact}</small>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="muted" style={{ padding: '8px 0' }}>No urgent recommendations for this company.</p>
        )}
      </Panel>

      {/* ── Explain Modal ─────────────────────────────────────── */}
      <Modal isOpen={isExplainModalOpen} onClose={() => setIsExplainModalOpen(false)} title="Situation Analysis">
        {isExplaining ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px 0', gap: 14 }}>
            <div className="spinner" aria-hidden="true" />
            <p style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>Analyzing supply chain metrics…</p>
          </div>
        ) : explainError ? (
          <div className="error">{explainError}</div>
        ) : (
          <div style={{ lineHeight: 1.7 }}>
            {renderMarkdown(explanation)}
          </div>
        )}
      </Modal>
    </div>
  );
}
