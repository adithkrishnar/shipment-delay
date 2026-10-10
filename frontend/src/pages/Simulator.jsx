import React, { useState } from 'react';
import { simulate as runSimulation } from '../services/api';

export default function Simulator({ company }) {
  const [scenarioType, setScenarioType] = useState('demand_surge');
  const [magnitude, setMagnitude] = useState(20);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSimulate = () => {
    if (!company) return;
    setLoading(true);
    setError(null);
    runSimulation(company.id, {
      scenario_type: scenarioType,
      magnitude: magnitude/100,
      target_entities: []
    }).then(setResult).catch(e => setError(e.message)).finally(() => setLoading(false));
  };

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">What-If Simulator</h1>
        <p className="page-subtitle">Test operational scenarios and view impact.</p>
      </div>

      <div className="grid-2">
         <div>
            <div className="panel" style={{ padding: '24px' }}>
               <h2 className="section-title" style={{ marginTop: 0 }}>Scenario Controls</h2>
               
               <div className="flex-col" style={{ marginBottom: '24px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 600 }}>Type</label>
                  <select value={scenarioType} onChange={e=>setScenarioType(e.target.value)} style={{ padding: '8px 12px', background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-md)', color: 'var(--text-primary)' }}>
                     <option value="demand_surge">Demand Surge</option>
                     <option value="supplier_delay">Supplier Delay</option>
                     <option value="transport_disruption">Transport Disruption</option>
                  </select>
               </div>

               <div className="flex-col" style={{ marginBottom: '32px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 600 }}>Magnitude ({magnitude}%)</label>
                  <input type="range" min="5" max="100" step="5" value={magnitude} onChange={e=>setMagnitude(Number(e.target.value))} />
               </div>

               <button className="btn-primary" onClick={handleSimulate} disabled={loading} style={{ width: '100%' }}>
                  {loading ? 'Running...' : 'Run Simulation'}
               </button>
               {error && <div style={{ color: 'var(--status-critical)', marginTop: '16px' }}>{error}</div>}
            </div>
         </div>

         <div>
            <div className="panel" style={{ padding: '24px', minHeight: '300px' }}>
               <h2 className="section-title" style={{ marginTop: 0 }}>Impact Summary</h2>
               {!result ? (
                  <div style={{ color: 'var(--text-tertiary)', textAlign: 'center', marginTop: '64px' }}>Run a simulation to view results.</div>
               ) : (
                  <div>
                     <div className="flex-col">
                        <div className="flex-between" style={{ paddingBottom: '12px', borderBottom: '1px solid var(--border-subtle)' }}>
                           <span style={{ color: 'var(--text-secondary)' }}>Financial Impact</span>
                           <strong style={{ color: 'var(--status-critical)' }}>High</strong>
                        </div>
                        <div className="flex-between" style={{ padding: '12px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                           <span style={{ color: 'var(--text-secondary)' }}>Stockout Risk</span>
                           <strong style={{ color: 'var(--status-critical)' }}>Increased by {magnitude}%</strong>
                        </div>
                     </div>
                     <div style={{ marginTop: '24px' }}>
                        <h3 style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: '8px' }}>Recommended Action</h3>
                        <div style={{ padding: '12px', background: 'var(--status-watch-bg)', color: 'var(--status-watch)', borderRadius: 'var(--r-md)' }}>
                           Expedite alternative shipments and review inventory thresholds.
                        </div>
                     </div>
                  </div>
               )}
            </div>
         </div>
      </div>
    </div>
  );
}
