import React, { useEffect, useState } from 'react';
import { getAnomalies } from '../services/api';
import Loader from '../components/Loader';

export default function Anomalies({ company }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (company) {
      getAnomalies(company.id).then(setData).catch(e => setError(e.message));
    }
  }, [company]);

  if (error) return (
    <div className="page animate-fade" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Unable to load this data.</p>
      <button className="btn-secondary" onClick={() => { setError(null); getAnomalies(company.id).then(setData).catch(e => setError(e.message)); }}>Retry</button>
    </div>
  );
  if (!data) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">Anomaly Detection</h1>
        <p className="page-subtitle">Actionable system deviations</p>
      </div>

      {(!data.anomalies || data.anomalies.length === 0) ? (
        <div className="panel" style={{ textAlign: 'center', padding: '64px 24px', color: 'var(--text-secondary)' }}>
          No anomalies detected.
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Detected anomaly</th>
                <th>Entity</th>
                <th>Severity</th>
                <th>Detected time</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {data.anomalies.map(a => {
                let badgeClass = 'badge-info';
                if (a.severity === 'CRITICAL') badgeClass = 'badge-critical';
                else if (a.severity === 'HIGH') badgeClass = 'badge-risk';
                else if (a.severity === 'MEDIUM') badgeClass = 'badge-warning';

                return (
                  <tr key={a.id}>
                    <td><strong>{a.description || `Anomaly on ${a.entity_type} ${a.entity_id}`}</strong></td>
                    <td style={{ color: 'var(--text-secondary)' }}>{a.entity_type} {a.entity_id}</td>
                    <td>
                      <span className={`badge ${badgeClass}`}>{a.severity || 'LOW'}</span>
                    </td>
                    <td style={{ color: 'var(--text-secondary)' }}>{a.detected_at ? new Date(a.detected_at).toLocaleString() : '—'}</td>
                    <td><button className="btn-secondary" style={{ padding: '2px 8px', fontSize: '11px' }}>Investigate</button></td>
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
