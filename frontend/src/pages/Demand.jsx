import React, { useEffect, useState, useMemo } from 'react';
import { getForecast as getDemandForecast } from '../services/api';
import Loader from '../components/Loader';
import { LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer } from 'recharts';

export default function Demand({ company }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [is400, setIs400] = useState(false);

  useEffect(() => {
    if (company) {
      getDemandForecast(company.id)
        .then(setData)
        .catch(e => {
           if (e.response && e.response.status === 400) {
              setIs400(true);
           } else {
              setError(e.message);
           }
        });
    }
  }, [company]);

  const aggregatedForecast = useMemo(() => {
    if (!data || !data.products) return [];
    const map = {};
    data.products.forEach(p => {
      p.forecast?.forEach(f => {
        if (!map[f.date]) map[f.date] = 0;
        map[f.date] += f.projected_demand || 0;
      });
    });
    return Object.entries(map)
      .map(([date, val]) => ({ date, projected_demand: Math.round(val) }))
      .sort((a,b) => a.date.localeCompare(b.date));
  }, [data]);

  const totalExpected = useMemo(() => {
     return aggregatedForecast.reduce((sum, f) => sum + f.projected_demand, 0);
  }, [aggregatedForecast]);

  const trend = useMemo(() => {
     if (aggregatedForecast.length < 2) return 'STABLE';
     const first = aggregatedForecast[0].projected_demand;
     const last = aggregatedForecast[aggregatedForecast.length - 1].projected_demand;
     if (last > first * 1.05) return 'UP';
     if (last < first * 0.95) return 'DOWN';
     return 'STABLE';
  }, [aggregatedForecast]);

  if (error) return (
    <div className="page animate-fade" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Unable to load this data.</p>
      <button className="btn-secondary" onClick={() => { setError(null); getDemandForecast(company.id).then(setData).catch(e => { if(e.response?.status === 400) setIs400(true); else setError(e.message); }); }}>Retry</button>
    </div>
  );
  if (!data && !is400) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">Demand Forecast</h1>
        <p className="page-subtitle">Expected demand over the forecast horizon.</p>
      </div>
      
      {is400 || !data?.products?.length ? (
         <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-secondary)' }}>
           No demand history available. Upload demand/sales history to generate a forecast.
         </div>
      ) : (
      <div className="panel-bare" style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', padding: '24px', background: 'var(--bg-surface-1)' }}>
         <div className="flex-between" style={{ marginBottom: '24px' }}>
            <h2 className="section-title" style={{ margin: 0, border: 'none', padding: 0 }}>Projected Volume</h2>
         </div>
         
         <div style={{ height: 300, marginBottom: '32px' }}>
            <ResponsiveContainer width="100%" height="100%">
               <LineChart data={aggregatedForecast}>
                 <CartesianGrid strokeDasharray="3 3" vertical={false} />
                 <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                 <YAxis tick={{ fontSize: 11 }} />
                 <Tooltip />
                 <Line type="monotone" dataKey="projected_demand" stroke="var(--accent-primary)" strokeWidth={2} dot={false} />
               </LineChart>
            </ResponsiveContainer>
         </div>

         <div className="grid-3" style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '24px' }}>
            <div>
               <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Expected Total Demand</div>
               <div style={{ fontSize: '20px', fontWeight: 600 }}>{totalExpected.toLocaleString()}</div>
            </div>
            <div>
               <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Trend</div>
               <div style={{ fontSize: '20px', fontWeight: 600, color: trend === 'UP' ? 'var(--status-healthy)' : 'var(--text-primary)' }}>{trend}</div>
            </div>
            <div>
               <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Forecast Confidence</div>
               <div style={{ fontSize: '20px', fontWeight: 600 }}>N/A</div>
            </div>
         </div>
      </div>
      )}
    </div>
  );
}
