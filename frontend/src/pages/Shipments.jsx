import React, { useEffect, useState, useMemo } from 'react';
import { getShipments, getShipmentImpact } from '../services/api';
import Loader from '../components/Loader';
import MultiLegDemo from '../components/MultiLegDemo';

export default function Shipments({ company }) {
  const [d, setD] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [impactData, setImpactData] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (company) {
      getShipments(company.id)
        .then(setD)
        .catch(e => setError(e.message));
    }
  }, [company]);

  const toggleRow = (id) => {
    if (expandedId === id) {
      setExpandedId(null);
      setImpactData(null);
    } else {
      setExpandedId(id);
      setImpactData(null);
      setImpactLoading(true);
      getShipmentImpact(company.id, id).then(data => {
        setImpactData(data);
        setImpactLoading(false);
      }).catch(() => setImpactLoading(false));
    }
  };

  if (error) return (
    <div className="page animate-fade" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Unable to load this data.</p>
      <button className="btn-secondary" onClick={() => { setError(null); getShipments(company.id).then(setD).catch(e => setError(e.message)); }}>Retry</button>
    </div>
  );
  if (!d) return <Loader />;

  const filteredShipments = d.shipments.filter(s => 
    (s.external_shipment_id || '').toLowerCase().includes(search.toLowerCase()) ||
    (s.origin || '').toLowerCase().includes(search.toLowerCase()) ||
    (s.destination || '').toLowerCase().includes(search.toLowerCase())
  );

  const total = d.shipments.length;
  const critical = d.shipments.filter(s => String(s.risk_tier).toUpperCase() === 'CRITICAL').length;
  const atRisk = d.shipments.filter(s => String(s.risk_tier).toUpperCase() === 'HIGH').length;
  const delayed = d.shipments.filter(s => s.expected_delay_days > 0).length;
  const onTime = total - delayed;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <h1 className="page-title">Shipment Control Tower</h1>
        <p className="page-subtitle">Track movements and predict delivery risks.</p>
      </div>

      <div className="kpi-strip">
        <div className="kpi-card">
          <div className="kpi-label">Total Shipments</div>
          <div className="kpi-value">{total}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Critical Risk</div>
          <div className="kpi-value" style={{ color: 'var(--status-critical)' }}>{critical}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">At Risk</div>
          <div className="kpi-value" style={{ color: 'var(--status-watch)' }}>{atRisk}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">On Time</div>
          <div className="kpi-value" style={{ color: 'var(--status-healthy)' }}>{onTime}</div>
        </div>
      </div>

      <div style={{ marginBottom: '16px' }}>
        <input 
          type="text" 
          placeholder="Search shipments..." 
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ padding: '8px 12px', background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-md)', color: 'var(--text-primary)', width: '300px' }}
        />
      </div>

      {total === 0 ? (
        <div className="panel" style={{ textAlign: 'center', padding: '64px 24px' }}>
          <p style={{ color: 'var(--text-secondary)' }}>No shipment records are available for this company.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Shipment</th>
                <th>Route</th>
                <th>Mode</th>
                <th>Expected Arrival</th>
                <th>Delay</th>
                <th>Risk</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredShipments.map(s => {
                 const riskClass = String(s.risk_tier || '').toUpperCase();
                 const isHigh = riskClass === 'CRITICAL' || riskClass === 'HIGH';
                 const expectedStr = s.planned_delivery ? s.planned_delivery.split('T')[0] : '—';
                 const delayStr = s.expected_delay_days ? `+${(s.expected_delay_days * 24).toFixed(0)}h` : '—';
                 
                 let badgeClass = 'badge-info';
                 let badgeText = 'ON TIME';
                 if (riskClass === 'CRITICAL') { badgeClass = 'badge-critical'; badgeText = 'CRITICAL'; }
                 else if (riskClass === 'HIGH') { badgeClass = 'badge-risk'; badgeText = 'AT RISK'; }
                 else if (riskClass === 'MEDIUM') { badgeClass = 'badge-warning'; badgeText = 'MONITOR'; }
                 else if (riskClass === 'LOW') { badgeClass = 'badge-healthy'; badgeText = 'ON TIME'; }

                 return (
                    <React.Fragment key={s.shipment_id}>
                      <tr onClick={() => toggleRow(s.shipment_id)} style={{ cursor: 'pointer' }}>
                        <td><strong>{s.external_shipment_id || `SHP-${s.shipment_id}`}</strong></td>
                        <td>{s.origin} → {s.destination}</td>
                        <td>{s.transport_mode}</td>
                        <td>{expectedStr}</td>
                        <td style={{ color: isHigh ? 'var(--status-critical)' : 'inherit', fontWeight: isHigh ? 600 : 400 }}>{delayStr}</td>
                        <td>
                          <span className={`badge ${badgeClass}`}>
                             {badgeText}
                          </span>
                        </td>
                        <td>
                          <button className="btn-secondary" style={{ padding: '4px 8px', fontSize: '11px' }}>
                             {expandedId === s.shipment_id ? 'Close' : 'View'}
                          </button>
                        </td>
                      </tr>
                      {expandedId === s.shipment_id && (
                        <tr>
                          <td colSpan="7" style={{ padding: '0', background: 'var(--bg-surface-2)' }}>
                            <div style={{ padding: '24px 32px' }}>
                               {impactLoading ? <Loader /> : (
                                  <div>
                                     <div style={{ marginBottom: '24px' }}>
                                        <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                                           SHIPMENT {s.external_shipment_id || `SHP-${s.shipment_id}`}
                                        </h2>
                                        <p style={{ color: 'var(--text-secondary)' }}>{s.origin} → {s.destination}</p>
                                     </div>
  
                                     <MultiLegDemo companyId={company.id} shipmentId={s.shipment_id} />
                                     
                                     {impactData && (
                                       <div className="grid-2" style={{ marginTop: '32px' }}>
                                         <div>
                                            <h2 className="section-title">INVENTORY IMPACT</h2>
                                            <div className="flex-col">
                                              <div className="flex-between">
                                                <span style={{ color: 'var(--text-secondary)' }}>Current stock</span>
                                                <strong>{impactData.inventory_impact?.inventory_level || '—'}</strong>
                                              </div>
                                              <div className="flex-between">
                                                <span style={{ color: 'var(--text-secondary)' }}>Stockout risk</span>
                                                <strong style={{ color: 'var(--status-critical)' }}>
                                                  {impactData.inventory_impact?.stockout_probability ? `${(impactData.inventory_impact.stockout_probability * 100).toFixed(0)}%` : '—'}
                                                </strong>
                                              </div>
                                            </div>
                                         </div>
                                         <div>
                                            <h2 className="section-title">RECOMMENDED ACTION</h2>
                                            <div style={{ padding: '16px', background: 'var(--status-watch-bg)', border: '1px solid var(--status-watch-border)', borderRadius: 'var(--r-md)', color: 'var(--status-watch)', fontWeight: 500 }}>
                                               {impactData.recommended_action || "Expedite Replenishment"}
                                            </div>
                                         </div>
                                       </div>
                                     )}
                                  </div>
                               )}
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                 );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
