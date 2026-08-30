import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import { getDashboard, explainDashboard } from '../services/api';
import MetricCard from '../components/MetricCard';
import Panel from '../components/Panel';
import RiskBadge from '../components/RiskBadge';
import Loader from '../components/Loader';
import Modal from '../components/Modal';

export default function Overview({ company }) {
  const [d, setD] = useState(null);
  const [e, setE] = useState('');
  
  const [isExplainModalOpen, setIsExplainModalOpen] = useState(false);
  const [explanation, setExplanation] = useState('');
  const [isExplaining, setIsExplaining] = useState(false);
  const [explainError, setExplainError] = useState('');

  useEffect(() => {
    if (company) {
      getDashboard(company.id)
        .then(setD)
        .catch(x => setE(x.response?.data?.detail || x.message));
    }
  }, [company]);

  const handleExplainClick = async () => {
    setIsExplainModalOpen(true);
    if (explanation || isExplaining) return; // Don't fetch if we already have it or are fetching
    
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

  if (e) return <div className="error">{e}</div>;
  if (!d) return <Loader />;

  const risk = Object.entries(d.shipment_risk_distribution).map(([name, value]) => ({ name, value }));
  const suppliers = d.top_suppliers.map(s => ({ name: s.name.replace(' Supply Co', ''), score: s.risk_score }));

  const renderMarkdown = (text) => {
    return text.split('\n').map((line, i) => {
      if (line.startsWith('### ')) {
        return <h3 key={i} style={{ marginTop: '16px', marginBottom: '8px', color: '#f8fafc' }}>{line.replace('### ', '')}</h3>;
      }
      if (line.startsWith('- **')) {
        const parts = line.split('**: ');
        return (
          <li key={i} style={{ margin: '4px 0', marginLeft: '20px' }}>
            <strong style={{ color: '#e2e8f0' }}>{parts[0].replace('- **', '')}:</strong> {parts[1]}
          </li>
        );
      }
      if (line.trim() === '') return <br key={i} />;
      
      // Handle simple bold text
      const parts = line.split('**');
      return (
        <p key={i} style={{ margin: '4px 0' }}>
          {parts.map((part, index) => index % 2 === 1 ? <strong key={index} style={{ color: '#e2e8f0' }}>{part}</strong> : part)}
        </p>
      );
    });
  };

  return (
    <div className="page">
      <div className="hero">
        <div>
          <span className="eyebrow">EXECUTIVE OVERVIEW</span>
          <h2>See the next disruption before it becomes a problem.</h2>
          <p>SupplyIQ connects demand, shipment risk and inventory impact into one decision layer.</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={handleExplainClick} className="primary" style={{ backgroundColor: '#10b981', color: 'white' }}>
            Explain Situation
          </button>
          <Link className="primary" to="/simulator">Run a scenario →</Link>
        </div>
      </div>
      
      <div className="metrics">
        <MetricCard label="Products" value={d.kpis.products} />
        <MetricCard label="High-risk shipments" value={d.kpis.high_risk_shipments} tone="danger" />
        <MetricCard label="Stockout risks" value={d.kpis.stockout_risks} tone="warning" />
        <MetricCard label="Inventory units" value={d.kpis.inventory_units.toLocaleString()} />
        <MetricCard label="Supply-chain health" value={`${d.kpis.supply_chain_health}%`} tone="success" />
      </div>
      
      <div className="grid2">
        <Panel title="Shipment risk distribution">
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={risk} dataKey="value" nameKey="name" innerRadius={65} outerRadius={95}>
                  {risk.map((x, i) => (
                    <Cell key={x.name} fill={['#22c55e', '#eab308', '#ef4444', '#7f1d1d'][i]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="legend">
            {risk.map(x => (
              <span key={x.name}><i className={`dot ${x.name.toLowerCase()}`} />{x.name}: {x.value}</span>
            ))}
          </div>
        </Panel>
        
        <Panel title="Supplier risk score">
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={suppliers} layout="vertical">
                <XAxis type="number" domain={[0, 100]} />
                <YAxis type="category" dataKey="name" width={110} />
                <Tooltip />
                <Bar dataKey="score" fill="#38bdf8" radius={[0, 5, 5, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
      
      <Panel title="Priority actions">
        <div className="recommendations">
          {d.top_recommendations.map((r, i) => (
            <div className="recommendation" key={i}>
              <RiskBadge risk={r.priority} />
              <div>
                <b>{r.title}</b>
                <p>{r.reason}</p>
                <small>{r.expected_impact}</small>
              </div>
            </div>
          ))}
          {!d.top_recommendations.length && <p className="muted">No urgent recommendations for this company.</p>}
        </div>
      </Panel>

      <Modal isOpen={isExplainModalOpen} onClose={() => setIsExplainModalOpen(false)} title="Situation Explanation">
        {isExplaining ? (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px 0' }}>
            <div className="spinner"></div>
            <p style={{ marginTop: '20px', color: '#8da0b7' }}>Analyzing supply chain metrics...</p>
          </div>
        ) : explainError ? (
          <div className="error">{explainError}</div>
        ) : (
          <div style={{ lineHeight: '1.6' }}>
            {renderMarkdown(explanation)}
          </div>
        )}
      </Modal>
    </div>
  );
}

