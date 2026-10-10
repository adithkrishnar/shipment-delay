import React, { useState, useEffect } from 'react';
import { simulate as runSimulation, getInventory } from '../services/api';
import Loader from '../components/Loader';

export default function Simulator({ company }) {
  const [inventory, setInventory] = useState([]);
  const [productId, setProductId] = useState('');
  const [demandMultiplier, setDemandMultiplier] = useState(1.0);
  const [delayDays, setDelayDays] = useState(0);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [initLoading, setInitLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (company) {
      setInitLoading(true);
      getInventory(company.id)
        .then(res => {
           setInventory(res.inventory || []);
           if (res.inventory && res.inventory.length > 0) {
             setProductId(res.inventory[0].product_id);
           }
        })
        .catch(e => setError(e.message))
        .finally(() => setInitLoading(false));
    }
  }, [company]);

  const handleSimulate = () => {
    if (!company || !productId) return;
    setLoading(true);
    setError(null);
    runSimulation({
      company_id: company.id,
      product_id: productId,
      demand_multiplier: demandMultiplier,
      delay_days: delayDays
    }).then(setResult).catch(e => {
        let msg = e.message;
        if (e.response?.data?.detail) {
           msg = typeof e.response.data.detail === 'string' ? e.response.data.detail : JSON.stringify(e.response.data.detail);
        }
        setError(msg);
    }).finally(() => setLoading(false));
  };

  if (initLoading) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">What-If Simulator</h1>
        <p className="page-subtitle">Test operational scenarios and view impact using actual backend calculations.</p>
      </div>

      <div className="grid-2">
         <div>
            <div className="panel" style={{ padding: '24px' }}>
               <h2 className="section-title" style={{ marginTop: 0 }}>Scenario Controls</h2>
               
               <div className="flex-col" style={{ marginBottom: '24px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 600 }}>Product</label>
                  <select value={productId} onChange={e=>setProductId(Number(e.target.value))} style={{ padding: '8px 12px', background: 'var(--bg-surface-2)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-md)', color: 'var(--text-primary)' }}>
                     {inventory.map(inv => (
                        <option key={inv.inventory_id} value={inv.product_id}>
                           {inv.external_product_id} (Current stock: {inv.inventory_level})
                        </option>
                     ))}
                  </select>
               </div>

               <div className="flex-col" style={{ marginBottom: '24px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 600 }}>Demand Multiplier ({demandMultiplier}x)</label>
                  <input type="range" min="0.1" max="5.0" step="0.1" value={demandMultiplier} onChange={e=>setDemandMultiplier(Number(e.target.value))} />
               </div>

               <div className="flex-col" style={{ marginBottom: '32px' }}>
                  <label style={{ fontSize: '12px', fontWeight: 600 }}>Delay Days ({delayDays})</label>
                  <input type="range" min="0" max="60" step="1" value={delayDays} onChange={e=>setDelayDays(Number(e.target.value))} />
               </div>

               <button className="btn-primary" onClick={handleSimulate} disabled={loading || !productId} style={{ width: '100%' }}>
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
                           <span style={{ color: 'var(--text-secondary)' }}>Baseline Stockout Risk</span>
                           <strong>{result.baseline?.stockout_risk || '—'}</strong>
                        </div>
                        <div className="flex-between" style={{ padding: '12px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                           <span style={{ color: 'var(--text-secondary)' }}>Scenario Stockout Risk</span>
                           <strong style={{ color: result.scenario?.stockout_risk === 'CRITICAL' ? 'var(--status-critical)' : 'var(--text-primary)' }}>
                             {result.scenario?.stockout_risk || '—'}
                           </strong>
                        </div>
                        <div className="flex-between" style={{ padding: '12px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                           <span style={{ color: 'var(--text-secondary)' }}>Baseline Expected Shortage</span>
                           <strong>{result.baseline?.expected_shortage?.toFixed(2) || 0}</strong>
                        </div>
                        <div className="flex-between" style={{ padding: '12px 0', borderBottom: '1px solid var(--border-subtle)' }}>
                           <span style={{ color: 'var(--text-secondary)' }}>Scenario Expected Shortage</span>
                           <strong style={{ color: result.scenario?.expected_shortage > 0 ? 'var(--status-critical)' : 'var(--text-primary)' }}>
                              {result.scenario?.expected_shortage?.toFixed(2) || 0}
                           </strong>
                        </div>
                     </div>
                     <div style={{ marginTop: '24px' }}>
                        <h3 style={{ fontSize: '12px', textTransform: 'uppercase', color: 'var(--text-tertiary)', marginBottom: '8px' }}>Recommended Action (Hypothetical)</h3>
                        <div style={{ padding: '12px', background: 'var(--status-info-bg)', color: 'var(--status-info)', borderRadius: 'var(--r-md)' }}>
                           {result.scenario?.expected_shortage > 0 ? 'Expedite replenishment to avoid shortages.' : 'No immediate action required under this scenario.'}
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
