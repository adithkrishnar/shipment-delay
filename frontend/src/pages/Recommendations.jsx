import React, { useEffect, useState } from 'react';
import { getRecommendations } from '../services/api';
import Loader from '../components/Loader';

export default function Recommendations({ company }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (company) {
      getRecommendations(company.id).then(setData).catch(e => setError(e.message));
    }
  }, [company]);

  if (error) return (
    <div className="page animate-fade" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Unable to load this data.</p>
      <button className="btn-secondary" onClick={() => { setError(null); getRecommendations(company.id).then(setData).catch(e => setError(e.message)); }}>Retry</button>
    </div>
  );
  if (!data) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">Action Center</h1>
        <p className="page-subtitle">Prioritized operational recommendations.</p>
      </div>

      <div className="op-list">
         {(!data.recommendations || data.recommendations.length === 0) ? (
            <div className="panel" style={{ padding: '64px 24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
              No pending recommendations.
            </div>
         ) : data.recommendations.map((r, i) => (
            <div key={i} className="op-item info" style={{ padding: '16px 24px', alignItems: 'center' }}>
               <div className="op-content">
                  <div className="op-title" style={{ color: 'var(--accent-primary)' }}>{r.action}</div>
                  <div className="op-details" style={{ marginTop: '8px', display: 'flex', gap: '24px' }}>
                     <div><strong style={{ color: 'var(--text-primary)' }}>ISSUE:</strong> {r.reason}</div>
                     <div><strong style={{ color: 'var(--text-primary)' }}>IMPACT:</strong> High risk of delay</div>
                     <div><strong style={{ color: 'var(--text-primary)' }}>TARGET:</strong> {r.target_type} {r.target_id}</div>
                  </div>
               </div>
               <div className="op-action">
                  <button className="btn-primary" style={{ padding: '6px 12px', fontSize: '12px' }}>Execute Action</button>
               </div>
            </div>
         ))}
      </div>
    </div>
  );
}
