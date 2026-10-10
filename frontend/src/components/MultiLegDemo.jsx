import React, { useState, useEffect } from 'react';
import { getMultiLegShipment } from '../services/api';
import { Ship, Truck, Plane, Train, Box, Pause } from 'lucide-react';
import Loader from './Loader';

export default function MultiLegDemo({ companyId, shipmentId }) {
  const [scenario, setScenario] = useState(1);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadScenario = async (sc) => {
    setLoading(true);
    setError(null);
    try {
      const res = await getMultiLegShipment(companyId, shipmentId, sc);
      setData(res);
      setScenario(sc);
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScenario(1);
  }, []);

  const getIcon = (mode) => {
    switch (mode?.toLowerCase()) {
      case 'air': return <Plane size={14} />;
      case 'ocean': return <Ship size={14} />;
      case 'rail': return <Train size={14} />;
      default: return <Truck size={14} />;
    }
  };

  if (error) return <div style={{ color: 'var(--status-critical)' }}>{error}</div>;
  if (!data) return <Loader />;

  return (
    <div style={{ marginTop: '24px' }}>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
        <button onClick={() => loadScenario(1)} className={scenario === 1 ? 'btn-primary' : 'btn-secondary'} style={{ padding: '4px 12px', fontSize: '11px' }}>Low Risk (Demo 1)</button>
        <button onClick={() => loadScenario(2)} className={scenario === 2 ? 'btn-primary' : 'btn-secondary'} style={{ padding: '4px 12px', fontSize: '11px' }}>Moderate Risk (Demo 2)</button>
        <button onClick={() => loadScenario(3)} className={scenario === 3 ? 'btn-primary' : 'btn-secondary'} style={{ padding: '4px 12px', fontSize: '11px' }}>High Risk (Demo 3)</button>
      </div>

      <div className="grid-2">
        <div>
          <h2 className="section-title" style={{ marginTop: 0 }}>JOURNEY TIMELINE</h2>
          <div className="timeline">
            {data.legs.map((leg, i) => (
              <React.Fragment key={leg.leg_id}>
                <div className="timeline-step">
                  <div className={`timeline-icon ${leg.transport_delay > 0 ? 'warning' : 'active'}`}>
                    {getIcon(leg.mode)}
                  </div>
                  <div className="timeline-content">
                    <div className="timeline-title">{leg.mode}</div>
                    <div className="timeline-desc">{leg.origin} → {leg.destination}</div>
                    <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                      <span className="timeline-meta">Expected {leg.expected_duration}h</span>
                      {leg.transport_delay > 0 && <span className="timeline-meta delay">Delay +{leg.transport_delay}h</span>}
                    </div>
                  </div>
                </div>
                {i < data.legs.length - 1 && (() => {
                  const waiting = data.waiting_periods.find(w => w.between_leg === `${leg.sequence}-${data.legs[i+1].sequence}`);
                  if (waiting) {
                    return (
                      <div className="timeline-step" key={`wait-${leg.sequence}`}>
                        <div className="timeline-icon" style={{ borderColor: waiting.waiting_duration > 12 ? 'var(--status-watch)' : 'var(--border-strong)' }}>
                          <Pause size={14} />
                        </div>
                        <div className="timeline-content">
                          <div className="timeline-title">WAITING</div>
                          <div className="timeline-desc">Intermediate handling</div>
                          <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                            <span className={`timeline-meta ${waiting.waiting_duration > 12 ? 'delay' : ''}`}>+{waiting.waiting_duration}h delay</span>
                          </div>
                        </div>
                      </div>
                    );
                  }
                  return null;
                })()}
              </React.Fragment>
            ))}
          </div>
        </div>

        <div>
          <div className="panel-bare" style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--r-lg)', padding: '24px' }}>
             <div className="grid-2" style={{ marginBottom: '24px' }}>
               <div>
                 <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>TOTAL DELAY</div>
                 <div style={{ fontSize: '24px', fontWeight: 600, color: data.total_delay_hours > 24 ? 'var(--status-critical)' : 'var(--text-primary)' }}>
                    {data.total_delay_hours}h
                 </div>
               </div>
               <div>
                 <div style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>ETA</div>
                 <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '4px' }}>
                    {new Date(data.predicted_final_arrival).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                 </div>
               </div>
             </div>

             <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '24px' }}>
               <h3 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', marginBottom: '16px' }}>PREDICTION DETAILS</h3>
               <div className="flex-col">
                 <div className="flex-between">
                   <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Historical ML delay probability</span>
                   <strong style={{ fontSize: '13px' }}>{(data.delay_probability * 100).toFixed(1)}%</strong>
                 </div>
                 <div className="flex-between">
                   <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Transport delay (Calculated)</span>
                   <strong style={{ fontSize: '13px' }}>{data.total_transport_delay_hours}h</strong>
                 </div>
                 <div className="flex-between">
                   <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Waiting delay (Calculated)</span>
                   <strong style={{ fontSize: '13px' }}>{data.total_waiting_delay_hours}h</strong>
                 </div>
                 <div className="flex-between">
                   <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Live risk tier (Context)</span>
                   <strong style={{ fontSize: '13px', color: data.risk_tier === 'CRITICAL' ? 'var(--status-critical)' : 'var(--text-primary)' }}>{data.risk_tier}</strong>
                 </div>
               </div>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
}
