import React, { useEffect, useState } from 'react';
import { getInventory } from '../services/api';
import Loader from '../components/Loader';

export default function Inventory({ company }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (company) {
      getInventory(company.id).then(setData).catch(e => setError(e.message));
    }
  }, [company]);

  if (error) return (
    <div className="page animate-fade" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Unable to load this data.</p>
      <button className="btn-secondary" onClick={() => { setError(null); getInventory(company.id).then(setData).catch(e => setError(e.message)); }}>Retry</button>
    </div>
  );
  if (!data) return <Loader />;

  const items = data.products || [];
  const healthy = items.filter(x => x.stockout_risk === 'LOW').length;
  const watch = items.filter(x => x.stockout_risk === 'MEDIUM').length;
  const critical = items.filter(x => x.stockout_risk === 'HIGH' || x.stockout_risk === 'CRITICAL').length;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">Inventory Intelligence</h1>
        <p className="page-subtitle">What could run out or become excessive?</p>
      </div>

      <div className="kpi-strip">
         <div className="kpi-card">
            <div className="kpi-label">Healthy</div>
            <div className="kpi-value" style={{ color: 'var(--status-healthy)' }}>{healthy}</div>
         </div>
         <div className="kpi-card">
            <div className="kpi-label">At Risk</div>
            <div className="kpi-value" style={{ color: 'var(--status-watch)' }}>{watch}</div>
         </div>
         <div className="kpi-card">
            <div className="kpi-label">Stockout Risk</div>
            <div className="kpi-value" style={{ color: 'var(--status-critical)' }}>{critical}</div>
         </div>
         <div className="kpi-card">
            <div className="kpi-label">Total SKUs</div>
            <div className="kpi-value">{items.length}</div>
         </div>
      </div>

      {items.length === 0 ? (
        <div className="panel" style={{ textAlign: 'center', padding: '64px 24px' }}>
          <p style={{ color: 'var(--text-secondary)' }}>No inventory records are available.</p>
        </div>
      ) : (
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Product</th>
              <th>Warehouse</th>
              <th>Current Stock</th>
              <th>Daily Demand</th>
              <th>Coverage</th>
              <th>Risk</th>
              <th>Recommended Action</th>
            </tr>
          </thead>
          <tbody>
             {items.map(item => {
               const isCrit = item.stockout_risk === 'CRITICAL' || item.stockout_risk === 'HIGH';
               let badgeClass = 'badge-healthy';
               let badgeText = 'HEALTHY';
               if (isCrit) { badgeClass = 'badge-critical'; badgeText = 'STOCKOUT'; }
               else if (item.stockout_risk === 'MEDIUM') { badgeClass = 'badge-risk'; badgeText = 'AT RISK'; }
               return (
                  <tr key={item.product_id} style={{ background: isCrit ? 'rgba(255, 77, 95, 0.05)' : 'inherit' }}>
                     <td><strong>{item.product_name}</strong></td>
                     <td>{item.warehouse || 'Main'}</td>
                     <td>{item.inventory_level}</td>
                     <td>{item.daily_demand || '—'}</td>
                     <td style={{ color: isCrit ? 'var(--status-critical)' : 'inherit', fontWeight: isCrit ? 600 : 400 }}>
                        {item.inventory_coverage_days ? `${item.inventory_coverage_days.toFixed(1)} days` : '—'}
                     </td>
                     <td>
                        <span className={`badge ${badgeClass}`}>
                           {badgeText}
                        </span>
                     </td>
                     <td style={{ color: isCrit ? 'var(--status-watch)' : 'var(--text-secondary)' }}>
                        {isCrit ? 'Expedite Replenishment' : 'Monitor'}
                     </td>
                  </tr>
               );
            })}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
}
