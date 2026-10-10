import React, { useEffect, useState } from 'react';
import { getSuppliers } from '../services/api';
import Loader from '../components/Loader';

export default function Suppliers({ company }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (company) {
      getSuppliers(company.id).then(setData).catch(e => setError(e.message));
    }
  }, [company]);

  if (error) return (
    <div className="page animate-fade" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Unable to load this data.</p>
      <button className="btn-secondary" onClick={() => { setError(null); getSuppliers(company.id).then(setData).catch(e => setError(e.message)); }}>Retry</button>
    </div>
  );
  if (!data) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">Supplier Intelligence</h1>
        <p className="page-subtitle">Which suppliers need attention?</p>
      </div>

      {!data.suppliers || data.suppliers.length === 0 ? (
        <div className="panel" style={{ padding: '64px 24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
          No supplier information is available.
        </div>
      ) : (
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Supplier</th>
              <th>Reliability</th>
              <th>Average Delay</th>
              <th>Risk</th>
              <th>Shipments</th>
            </tr>
          </thead>
          <tbody>
            {data.suppliers?.map(s => {
               const isHigh = s.risk_tier === 'HIGH' || s.risk_tier === 'CRITICAL';
               return (
                  <tr key={s.supplier_id}>
                     <td><strong>{s.name}</strong></td>
                     <td>{s.reliability ? `${(s.reliability*100).toFixed(0)}%` : '—'}</td>
                     <td>{s.avg_delay_days ? `${s.avg_delay_days.toFixed(1)}d` : '—'}</td>
                     <td>
                        <span className={`badge ${isHigh ? 'badge-critical' : (s.risk_tier === 'MEDIUM' ? 'badge-warning' : 'badge-healthy')}`}>
                           {s.risk_tier}
                        </span>
                     </td>
                     <td>{s.shipment_count || 0}</td>
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
