import React, { useEffect, useState, useMemo } from 'react';
import { getDashboard as getOverview } from '../services/api';
import Loader from '../components/Loader';
import { Ship, TriangleAlert, Boxes, Map } from 'lucide-react';
import { Link } from 'react-router-dom';

export default function Overview({ company }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (company) {
      setLoading(true);
      getOverview(company.id)
        .then(setData)
        .catch(console.error)
        .finally(() => setLoading(false));
    }
  }, [company]);

  if (loading) return <Loader />;
  if (!data) return (
    <div className="page animate-fade" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Unable to load dashboard data</p>
      <button className="btn-secondary" onClick={() => { setLoading(true); getOverview(company.id).then(setData).catch(console.error).finally(() => setLoading(false)); }}>Retry</button>
    </div>
  );

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">SUPPLY CHAIN OVERVIEW</h1>
        <p className="page-subtitle">Know what needs attention today.</p>
      </div>

      <div className="kpi-strip">
        <div className="kpi-card">
          <div className="kpi-label">Shipments at Risk</div>
          <div className="kpi-value" style={{ color: 'var(--status-critical)' }}>{data.kpis?.high_risk_shipments || 0}</div>
          <div className="kpi-sub">Expected delays &gt; 24h</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Inventory at Risk</div>
          <div className="kpi-value" style={{ color: 'var(--status-watch)' }}>{data.kpis?.stockout_risks || 0}</div>
          <div className="kpi-sub">Low coverage items</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Total Shipments</div>
          <div className="kpi-value">{data.kpis?.shipments || 0}</div>
          <div className="kpi-sub">In transit</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Active Anomalies</div>
          <div className="kpi-value">{data.anomaly_categories?.reduce((sum, cat) => sum + cat.count, 0) || 0}</div>
          <div className="kpi-sub">Detected this week</div>
        </div>
      </div>

      <h2 className="section-title">WHAT NEEDS ATTENTION</h2>
      <div className="op-list">
        {data.kpis?.high_risk_shipments > 0 && (
          <div className="op-item critical">
            <div className="op-content">
              <div className="op-title">🔴 {data.kpis.high_risk_shipments} Shipments at Critical Risk</div>
              <div className="op-details">
                <span>Severe delays expected due to operational bottlenecks.</span>
                <span>Inventory impact: High</span>
              </div>
            </div>
            <div className="op-action">
              <Link to="/shipments" className="btn-secondary">View shipments</Link>
            </div>
          </div>
        )}
        
        {data.kpis?.stockout_risks > 0 && (
          <div className="op-item warning">
            <div className="op-content">
              <div className="op-title">🟡 {data.kpis.stockout_risks} Items approaching stockout</div>
              <div className="op-details">
                <span>Coverage &lt; 3 days for key products.</span>
              </div>
            </div>
            <div className="op-action">
              <Link to="/inventory" className="btn-secondary">View inventory</Link>
            </div>
          </div>
        )}
      </div>

      <div className="grid-2" style={{ marginTop: '32px' }}>
        <div>
          <h2 className="section-title">SHIPMENT HEALTH</h2>
          <div className="panel-bare" style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', padding: '24px' }}>
             {data.kpis?.has_shipments ? (
               <>
                 <div className="flex-between" style={{ marginBottom: '16px' }}>
                    <span style={{ fontSize: '14px', fontWeight: 500 }}>On Track</span>
                    <span style={{ fontWeight: 600, color: 'var(--status-healthy)' }}>
                       {(data.kpis?.shipments || 0) - (data.kpis?.high_risk_shipments || 0)}
                    </span>
                 </div>
                 <div className="flex-between">
                    <span style={{ fontSize: '14px', fontWeight: 500 }}>At Risk</span>
                    <span style={{ fontWeight: 600, color: 'var(--status-critical)' }}>
                       {data.kpis?.high_risk_shipments || 0}
                    </span>
                 </div>
               </>
             ) : (
               <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>No shipment data available.</p>
             )}
          </div>
        </div>
        <div>
          <h2 className="section-title">RECENT RECOMMENDATIONS</h2>
          <div className="panel-bare" style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', padding: '24px' }}>
             {data.top_recommendations?.length > 0 ? (
               <>
                 <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Review operational actions to mitigate risks.</p>
                 <Link to="/recommendations" className="btn-secondary" style={{ marginTop: '16px' }}>View all recommendations</Link>
               </>
             ) : (
               <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>No recent recommendations.</p>
             )}
          </div>
        </div>
      </div>
    </div>
  );
}
