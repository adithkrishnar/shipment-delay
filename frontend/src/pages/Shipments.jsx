import React, { useEffect, useState, useMemo } from 'react';
import { getShipments, getShipmentImpact, getTransporterOrgs, createShipment } from '../services/api';
import Loader from '../components/Loader';
import MultiLegDemo from '../components/MultiLegDemo';
import { Plus, X, Truck, CheckCircle2 } from 'lucide-react';

export default function Shipments({ company }) {
  const [d, setD] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [impactData, setImpactData] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');

  // Shipment Creation Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [transporterOrgs, setTransporterOrgs] = useState([]);
  const [creating, setCreating] = useState(false);
  const [createMsg, setCreateMsg] = useState('');
  const [formData, setFormData] = useState({
    external_shipment_id: '',
    product_id: '',
    origin: '',
    destination: '',
    transport_mode: 'ROAD',
    planned_delivery: '',
    transporter_org_id: '',
    quantity: 100,
    distance_km: 650
  });

  const loadShipments = () => {
    if (company) {
      getShipments(company.id)
        .then(setD)
        .catch(e => setError(e.message));
    }
  };

  useEffect(() => {
    loadShipments();
    getTransporterOrgs().then(setTransporterOrgs).catch(() => {});
  }, [company]);

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    if (!company) return;
    setCreating(true);
    setCreateMsg('');
    try {
      // If product_id not provided, pick first from existing shipments
      const fallbackPid = d?.shipments?.[0]?.product_id || 1;
      const payload = {
        ...formData,
        product_id: formData.product_id ? parseInt(formData.product_id, 10) : fallbackPid,
        transporter_org_id: formData.transporter_org_id ? parseInt(formData.transporter_org_id, 10) : null,
      };
      await createShipment(company.id, payload);
      setCreateMsg('Shipment created and assigned successfully!');
      setTimeout(() => {
        setShowCreateModal(false);
        setCreateMsg('');
        loadShipments();
      }, 1000);
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Creation failed');
    } finally {
      setCreating(false);
    }
  };

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
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h1 className="page-title">Shipment Control Tower</h1>
          <p className="page-subtitle">Track movements, manage carrier assignments, and predict delivery risks.</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary"
          style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', fontSize: '13px' }}
        >
          <Plus size={16} /> Create & Assign Shipment
        </button>
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

      {/* Create & Assign Shipment Modal */}
      {showCreateModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000,
          padding: '16px'
        }}>
          <div style={{
            background: 'var(--bg-surface-1)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--r-xl)',
            width: '100%',
            maxWidth: '560px',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '24px 28px',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Truck size={20} color="var(--accent-primary)" />
                <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                  Create & Assign Shipment
                </h2>
              </div>
              <button onClick={() => setShowCreateModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            {createMsg && (
              <div style={{ background: 'rgba(45, 212, 167, 0.15)', border: '1px solid #2DD4A7', color: '#2DD4A7', padding: '10px 14px', borderRadius: '6px', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                <CheckCircle2 size={16} /> {createMsg}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Shipment Reference / PO Number *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. DC-PO-00812"
                  value={formData.external_shipment_id}
                  onChange={(e) => setFormData({ ...formData, external_shipment_id: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Origin Waypoint *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Shenzhen Port"
                    value={formData.origin}
                    onChange={(e) => setFormData({ ...formData, origin: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Destination DC *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. DataCo USCA DC"
                    value={formData.destination}
                    onChange={(e) => setFormData({ ...formData, destination: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Primary Mode *
                  </label>
                  <select
                    value={formData.transport_mode}
                    onChange={(e) => setFormData({ ...formData, transport_mode: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  >
                    <option value="ROAD">ROAD</option>
                    <option value="SEA">SEA</option>
                    <option value="RAIL">RAIL</option>
                    <option value="AIR">AIR</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Planned Delivery Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={formData.planned_delivery}
                    onChange={(e) => setFormData({ ...formData, planned_delivery: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Assign Transporter Organization *
                </label>
                <select
                  value={formData.transporter_org_id}
                  onChange={(e) => setFormData({ ...formData, transporter_org_id: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                >
                  <option value="">-- Select Eligible Transporter Partner --</option>
                  {transporterOrgs.map(org => (
                    <option key={org.id} value={org.id}>
                      {org.name} ({org.code || 'CARRIER'})
                    </option>
                  ))}
                </select>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                  Assigning establishes strict tenant relationship. Only this transporter will see this shipment.
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
                <button type="button" onClick={() => setShowCreateModal(false)} className="btn-secondary" style={{ padding: '8px 14px' }}>
                  Cancel
                </button>
                <button type="submit" disabled={creating} className="btn-primary" style={{ padding: '8px 18px' }}>
                  {creating ? 'Saving...' : 'Create & Assign'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
