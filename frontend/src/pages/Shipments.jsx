import React, { useEffect, useState, useMemo } from 'react';
import { 
  getShipments, 
  getShipmentImpact, 
  getTransporterOrgs, 
  getCompanies, 
  createShipment, 
  completeShipmentLeg, 
  confirmDelivery,
  reportShipmentDelay 
} from '../services/api';
import Loader from '../components/Loader';
import MultiLegDemo from '../components/MultiLegDemo';
import { 
  Plus, X, Truck, CheckCircle2, ArrowRight, Clock, 
  AlertTriangle, RefreshCw, ShieldCheck, Warehouse as WhIcon, Box, ArrowUpRight 
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';

export default function Shipments({ company }) {
  const { user } = useAuth();
  const [d, setD] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [impactData, setImpactData] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [directionFilter, setDirectionFilter] = useState('ALL'); // ALL, OUTBOUND, INBOUND
  const [actionLoading, setActionLoading] = useState(false);
  const [actionSuccessMsg, setActionSuccessMsg] = useState('');

  // Quick Delay Modal inside row
  const [delayModalShipment, setDelayModalShipment] = useState(null);
  const [delayHoursInput, setDelayHoursInput] = useState(16);
  const [delayReasonInput, setDelayReasonInput] = useState('Severe Weather / Landslide');

  // Shipment Creation Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [transporterOrgs, setTransporterOrgs] = useState([]);
  const [allCompanies, setAllCompanies] = useState([]);
  const [creating, setCreating] = useState(false);
  const [createMsg, setCreateMsg] = useState('');
  const [formData, setFormData] = useState({
    external_shipment_id: '',
    receiver_company_id: '',
    origin: 'Bengaluru Electronic City Plant, Karnataka',
    destination: 'Chennai Central DC, Tamil Nadu',
    transport_mode: 'ROAD',
    planned_delivery: '',
    transporter_org_id: '',
    quantity: 100,
    distance_km: 360
  });

  const loadShipments = () => {
    if (company && company.id) {
      getShipments(company.id)
        .then(res => {
          setD(res);
          setError(null);
        })
        .catch(e => {
          // If error is 404/no shipments, keep empty array
          if (e.response?.status === 404) {
            setD({ company_id: company.id, model_source: 'BASE_MODEL', shipments: [] });
          } else {
            setError(e.message);
          }
        });
    }
  };

  useEffect(() => {
    loadShipments();
    getTransporterOrgs().then(setTransporterOrgs).catch(() => {});
    getCompanies().then(setAllCompanies).catch(() => {});

    // Live real-time multi-laptop polling interval (3.5s)
    const interval = setInterval(() => {
      loadShipments();
    }, 3500);

    return () => clearInterval(interval);
  }, [company?.id]);

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    if (!company) return;
    setCreating(true);
    setCreateMsg('');
    try {
      const fallbackPid = d?.shipments?.[0]?.product_id || 1;
      const payload = {
        ...formData,
        product_id: fallbackPid,
        receiver_company_id: formData.receiver_company_id ? parseInt(formData.receiver_company_id, 10) : null,
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

  // Handover / Complete Leg
  const handleAdvanceLeg = async (shipmentId, legId) => {
    setActionLoading(true);
    try {
      const res = await completeShipmentLeg(shipmentId, legId);
      setActionSuccessMsg(res.message || 'Leg advanced successfully!');
      loadShipments();
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Could not advance leg');
    } finally {
      setActionLoading(false);
    }
  };

  // Receiver Confirm Delivery
  const handleConfirmDelivery = async (shipmentId) => {
    setActionLoading(true);
    try {
      const res = await confirmDelivery(shipmentId);
      setActionSuccessMsg(res.message || 'Delivery confirmed and stock added to inventory!');
      loadShipments();
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Could not confirm delivery');
    } finally {
      setActionLoading(false);
    }
  };

  // Report Delay
  const handleReportDelaySubmit = async (e) => {
    e.preventDefault();
    if (!delayModalShipment) return;
    setActionLoading(true);
    try {
      await reportShipmentDelay(delayModalShipment.shipment_id, {
        delay_hours: parseFloat(delayHoursInput),
        reason: delayReasonInput,
        notes: `Operational delay logged on ${delayModalShipment.external_shipment_id}`
      });
      setDelayModalShipment(null);
      setActionSuccessMsg(`Delay of +${delayHoursInput}h reported! Control Tower and Action Center notified.`);
      loadShipments();
      setTimeout(() => setActionSuccessMsg(''), 4000);
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Failed to report delay');
    } finally {
      setActionLoading(false);
    }
  };

  if (error && !d) return (
    <div className="page animate-fade" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', minHeight: '50vh' }}>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '16px' }}>Unable to load shipment records.</p>
      <button className="btn-secondary" onClick={() => { setError(null); loadShipments(); }}>Retry</button>
    </div>
  );
  if (!d) return <Loader />;

  // Filter logic
  const filteredShipments = (d.shipments || []).filter(s => {
    // Search
    const q = search.toLowerCase();
    const matchesSearch = 
      (s.external_shipment_id || '').toLowerCase().includes(q) ||
      (s.origin || '').toLowerCase().includes(q) ||
      (s.destination || '').toLowerCase().includes(q) ||
      (s.carrier || '').toLowerCase().includes(q) ||
      (s.sender_company_name || '').toLowerCase().includes(q) ||
      (s.receiver_company_name || '').toLowerCase().includes(q);

    if (!matchesSearch) return false;

    // Status filter
    if (statusFilter !== 'ALL') {
      const st = (s.assignment_status || 'IN_TRANSIT').toUpperCase();
      if (statusFilter === 'DELAYED' && st !== 'DELAYED' && s.risk_tier !== 'CRITICAL') return false;
      if (statusFilter === 'IN_TRANSIT' && st !== 'IN_TRANSIT' && st !== 'ACCEPTED') return false;
      if (statusFilter === 'ARRIVED' && st !== 'ARRIVED') return false;
      if (statusFilter === 'DELIVERED' && st !== 'DELIVERED') return false;
    }

    // Direction filter
    if (directionFilter === 'OUTBOUND') {
      // outbound = company is sender
      if (s.receiver_company_id && s.receiver_company_id === company.id) return false;
    } else if (directionFilter === 'INBOUND') {
      // inbound = company is receiver
      if (s.receiver_company_id && s.receiver_company_id !== company.id) return false;
    }

    return true;
  });

  const total = (d.shipments || []).length;
  const critical = (d.shipments || []).filter(s => String(s.risk_tier).toUpperCase() === 'CRITICAL' || s.assignment_status === 'DELAYED').length;
  const inTransitCount = (d.shipments || []).filter(s => ['IN_TRANSIT', 'ACCEPTED', 'PENDING'].includes((s.assignment_status || '').toUpperCase())).length;
  const deliveredCount = (d.shipments || []).filter(s => (s.assignment_status || '').toUpperCase() === 'DELIVERED').length;

  const isCompanyC = (company?.name || '').toLowerCase().includes('chennai');
  const isCompanyA = (company?.name || '').toLowerCase().includes('bengaluru');

  return (
    <div className="page animate-fade">
      {/* Header Banner */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <h1 className="page-title" style={{ margin: 0 }}>Multi-Company Shipment Control Tower</h1>
            <span style={{ 
              display: 'inline-flex', alignItems: 'center', gap: '4px',
              fontSize: '11px', padding: '2px 8px', borderRadius: '12px',
              background: 'rgba(45, 212, 167, 0.15)', color: '#2DD4A7', fontWeight: 600 
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#2DD4A7' }} /> Live 3.5s Sync
            </span>
          </div>
          <p className="page-subtitle" style={{ margin: 0 }}>
            Real-time inter-company tracking across <strong>Manufacturer</strong> (Company A), <strong>Logistics Carrier</strong> (Company B), and <strong>Receiver DC</strong> (Company C).
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 16px', fontSize: '13px' }}
          >
            <Plus size={16} /> Dispatch New Shipment
          </button>
        </div>
      </div>

      {/* Global Action Success Toast */}
      {actionSuccessMsg && (
        <div style={{ 
          background: 'rgba(45, 212, 167, 0.15)', border: '1px solid #2DD4A7', 
          color: '#2DD4A7', padding: '12px 18px', borderRadius: '8px', marginBottom: '20px', 
          display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px', fontWeight: 500 
        }}>
          <CheckCircle2 size={18} /> {actionSuccessMsg}
        </div>
      )}

      {/* KPI Cards */}
      <div className="kpi-strip">
        <div className="kpi-card">
          <div className="kpi-label">Total Enterprise Shipments</div>
          <div className="kpi-value">{total}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Transit Disrupted / Critical Risk</div>
          <div className="kpi-value" style={{ color: critical > 0 ? 'var(--status-critical)' : 'inherit' }}>{critical}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Active In-Transit</div>
          <div className="kpi-value" style={{ color: 'var(--accent-primary)' }}>{inTransitCount}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Delivered & Stock Received</div>
          <div className="kpi-value" style={{ color: 'var(--status-healthy)' }}>{deliveredCount}</div>
        </div>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {/* Direction filters */}
          <div style={{ display: 'inline-flex', background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: '6px', padding: '2px' }}>
            <button
              onClick={() => setDirectionFilter('ALL')}
              style={{
                padding: '6px 12px', fontSize: '12px', borderRadius: '4px', border: 'none', cursor: 'pointer',
                background: directionFilter === 'ALL' ? 'var(--accent-primary)' : 'transparent',
                color: directionFilter === 'ALL' ? '#fff' : 'var(--text-secondary)',
                fontWeight: directionFilter === 'ALL' ? 600 : 400
              }}
            >
              All Movements
            </button>
            <button
              onClick={() => setDirectionFilter('OUTBOUND')}
              style={{
                padding: '6px 12px', fontSize: '12px', borderRadius: '4px', border: 'none', cursor: 'pointer',
                background: directionFilter === 'OUTBOUND' ? 'var(--accent-primary)' : 'transparent',
                color: directionFilter === 'OUTBOUND' ? '#fff' : 'var(--text-secondary)',
                fontWeight: directionFilter === 'OUTBOUND' ? 600 : 400
              }}
            >
              Outbound (Sender)
            </button>
            <button
              onClick={() => setDirectionFilter('INBOUND')}
              style={{
                padding: '6px 12px', fontSize: '12px', borderRadius: '4px', border: 'none', cursor: 'pointer',
                background: directionFilter === 'INBOUND' ? 'var(--accent-primary)' : 'transparent',
                color: directionFilter === 'INBOUND' ? '#fff' : 'var(--text-secondary)',
                fontWeight: directionFilter === 'INBOUND' ? 600 : 400
              }}
            >
              Inbound (Receiver)
            </button>
          </div>

          {/* Status filters */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              padding: '6px 12px', fontSize: '12px', background: 'var(--bg-surface-1)',
              border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)'
            }}
          >
            <option value="ALL">All Statuses</option>
            <option value="IN_TRANSIT">In Transit</option>
            <option value="DELAYED">Delayed / Critical</option>
            <option value="ARRIVED">Arrived (Ready for Receipt)</option>
            <option value="DELIVERED">Delivered</option>
          </select>
        </div>

        <input 
          type="text" 
          placeholder="Search by ID, city, carrier, or partner..." 
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ padding: '8px 12px', background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-md)', color: 'var(--text-primary)', width: '280px', fontSize: '12px' }}
        />
      </div>

      {/* Shipments Table */}
      {filteredShipments.length === 0 ? (
        <div className="panel" style={{ textAlign: 'center', padding: '64px 24px' }}>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '8px' }}>No shipments match your criteria.</p>
          <button className="btn-secondary" onClick={() => { setSearch(''); setStatusFilter('ALL'); setDirectionFilter('ALL'); }}>
            Reset Filters
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Reference</th>
                <th>Parties (Consignor → Consignee)</th>
                <th>Corridor Route</th>
                <th>Mode</th>
                <th>Current Status</th>
                <th>ETA & Delay</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredShipments.map(s => {
                 const statusUpper = (s.assignment_status || 'IN_TRANSIT').toUpperCase();
                 const isDelayed = statusUpper === 'DELAYED' || s.risk_tier === 'CRITICAL';
                 const isArrived = statusUpper === 'ARRIVED';
                 const isDelivered = statusUpper === 'DELIVERED';

                 let badgeClass = 'badge-info';
                 let badgeText = statusUpper;
                 if (isDelayed) { badgeClass = 'badge-critical'; badgeText = 'DELAYED'; }
                 else if (isDelivered) { badgeClass = 'badge-healthy'; badgeText = 'DELIVERED'; }
                 else if (isArrived) { badgeClass = 'badge-warning'; badgeText = 'ARRIVED'; }
                 else if (statusUpper === 'IN_TRANSIT') { badgeClass = 'badge-info'; badgeText = 'IN TRANSIT'; }

                 const expectedStr = s.planned_delivery ? s.planned_delivery.split('T')[0] : '—';
                 const delayStr = s.expected_delay_days ? `+${(s.expected_delay_days * 24).toFixed(0)}h` : (isDelayed ? '+16h' : '0h');

                 const senderName = s.sender_company_name || company.name;
                 const receiverName = s.receiver_company_name || 'Destination DC';

                 return (
                    <React.Fragment key={s.shipment_id}>
                      <tr onClick={() => toggleRow(s.shipment_id)} style={{ cursor: 'pointer', background: expandedId === s.shipment_id ? 'var(--bg-surface-2)' : 'inherit' }}>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <strong style={{ color: 'var(--accent-primary)', fontSize: '13px' }}>{s.external_shipment_id}</strong>
                            <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>{s.carrier || 'Logistics Carrier'}</span>
                          </div>
                        </td>
                        <td>
                          <div style={{ fontSize: '12px' }}>
                            <span style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{senderName}</span>
                            <span style={{ margin: '0 6px', color: 'var(--text-tertiary)' }}>→</span>
                            <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{receiverName}</span>
                          </div>
                        </td>
                        <td>
                          <div style={{ fontSize: '12px' }}>
                            <span>{s.origin}</span>
                            <span style={{ margin: '0 4px', color: 'var(--text-tertiary)' }}>→</span>
                            <span>{s.destination}</span>
                          </div>
                        </td>
                        <td>
                          <span style={{ fontSize: '11px', padding: '2px 6px', background: 'var(--bg-surface-1)', borderRadius: '4px', border: '1px solid var(--border-default)' }}>
                            {s.transport_mode}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${badgeClass}`}>
                            {badgeText}
                          </span>
                        </td>
                        <td>
                          <div style={{ fontSize: '12px' }}>
                            <div>{expectedStr}</div>
                            {isDelayed && (
                              <span style={{ color: 'var(--status-critical)', fontWeight: 600, fontSize: '11px' }}>
                                {delayStr} delay
                              </span>
                            )}
                          </div>
                        </td>
                        <td>
                          <button className="btn-secondary" style={{ padding: '4px 10px', fontSize: '11px' }}>
                            {expandedId === s.shipment_id ? 'Close' : 'View Operations'}
                          </button>
                        </td>
                      </tr>

                      {/* Expanded Operational Detail Row */}
                      {expandedId === s.shipment_id && (
                        <tr>
                          <td colSpan="7" style={{ padding: '0', background: 'var(--bg-surface-2)' }}>
                            <div style={{ padding: '24px 28px' }}>
                              
                              {/* Top Bar inside expanded drawer */}
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
                                <div>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                    <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                                      {s.external_shipment_id}
                                    </h2>
                                    <span className={`badge ${badgeClass}`}>{badgeText}</span>
                                    {s.current_eta && (
                                      <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                                        Current ETA: <strong>{s.current_eta}</strong>
                                      </span>
                                    )}
                                  </div>
                                  <p style={{ color: 'var(--text-tertiary)', fontSize: '12px', margin: '4px 0 0' }}>
                                    Consignor: {senderName} | Consignee: {receiverName} | Carrier: {s.carrier || 'Fleet Logistics'}
                                  </p>
                                </div>

                                {/* Operational Action Buttons */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                  {/* Report Delay Button */}
                                  {!isDelivered && (
                                    <button 
                                      onClick={() => setDelayModalShipment(s)}
                                      className="btn-secondary" 
                                      style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px', fontSize: '12px', color: 'var(--status-watch)' }}
                                    >
                                      <AlertTriangle size={14} /> Report Transit Delay
                                    </button>
                                  )}

                                  {/* Confirm Delivery Button for Receiver / Consignee */}
                                  {!isDelivered && (
                                    <button
                                      disabled={actionLoading}
                                      onClick={() => handleConfirmDelivery(s.shipment_id)}
                                      className="btn-primary"
                                      style={{ 
                                        display: 'flex', alignItems: 'center', gap: '6px', 
                                        padding: '6px 14px', fontSize: '12px', 
                                        background: '#10B981', borderColor: '#10B981', color: '#fff' 
                                      }}
                                    >
                                      <CheckCircle2 size={14} /> Confirm Delivery & Receive Stock
                                    </button>
                                  )}
                                </div>
                              </div>

                              {/* Multi-Leg Progression Map */}
                              <MultiLegDemo companyId={company.id} shipmentId={s.shipment_id} />

                              {/* Multi-Leg Handover Transition Panel */}
                              <div style={{ marginTop: '24px', padding: '16px 20px', background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: '8px' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                                  <h3 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: 0 }}>
                                    Transportation Leg Handover Controls
                                  </h3>
                                  <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                                    Autonomous next-leg activation enabled
                                  </span>
                                </div>

                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '12px' }}>
                                  {/* Leg 1 */}
                                  <div style={{ padding: '12px', border: '1px solid var(--border-subtle)', borderRadius: '6px', background: 'var(--bg-base)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                                      <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)' }}>LEG #1 (ROAD)</span>
                                      <span style={{ fontSize: '11px', color: '#10B981', fontWeight: 600 }}>COMPLETED</span>
                                    </div>
                                    <div style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: 500 }}>Bengaluru Plant → Hosur Hub</div>
                                    <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '4px' }}>First-Mile Consolidation</div>
                                  </div>

                                  {/* Leg 2 */}
                                  <div style={{ padding: '12px', border: '1px solid var(--accent-primary)', borderRadius: '6px', background: 'var(--bg-base)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                                      <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent-primary)' }}>LEG #2 (HIGHWAY CORRIDOR)</span>
                                      <span style={{ fontSize: '11px', color: isDelayed ? 'var(--status-critical)' : 'var(--accent-primary)', fontWeight: 600 }}>
                                        {isDelayed ? 'DELAYED (+16h)' : 'IN TRANSIT'}
                                      </span>
                                    </div>
                                    <div style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: 500 }}>Hosur Hub → Sriperumbudur Depot</div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                                      <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>Carrier: {s.carrier || 'Express Fleet'}</span>
                                      {!isDelivered && (
                                        <button
                                          disabled={actionLoading}
                                          onClick={() => handleAdvanceLeg(s.shipment_id, 9012)}
                                          className="btn-secondary"
                                          style={{ padding: '3px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                                        >
                                          Advance to Leg #3 <ArrowRight size={12} />
                                        </button>
                                      )}
                                    </div>
                                  </div>

                                  {/* Leg 3 */}
                                  <div style={{ padding: '12px', border: '1px solid var(--border-subtle)', borderRadius: '6px', background: 'var(--bg-base)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                                      <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)' }}>LEG #3 (LAST-MILE)</span>
                                      <span style={{ fontSize: '11px', color: isDelivered ? '#10B981' : 'var(--text-tertiary)', fontWeight: 600 }}>
                                        {isDelivered ? 'COMPLETED' : (isArrived ? 'ARRIVED' : 'SCHEDULED')}
                                      </span>
                                    </div>
                                    <div style={{ fontSize: '12px', color: 'var(--text-primary)', fontWeight: 500 }}>Sriperumbudur Depot → Chennai DC</div>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                                      <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>Final Destination Delivery</span>
                                      {!isDelivered && isArrived && (
                                        <button
                                          disabled={actionLoading}
                                          onClick={() => handleConfirmDelivery(s.shipment_id)}
                                          className="btn-primary"
                                          style={{ padding: '3px 8px', fontSize: '11px', background: '#10B981', borderColor: '#10B981', color: '#fff' }}
                                        >
                                          Accept Stock
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </div>

                              {/* Downstream Inventory Impact Panel */}
                              <div className="grid-2" style={{ marginTop: '24px' }}>
                                <div>
                                  <h2 className="section-title">DESTINATION INVENTORY EXPOSURE</h2>
                                  <div className="panel" style={{ padding: '16px' }}>
                                    <div className="flex-col" style={{ gap: '10px' }}>
                                      <div className="flex-between">
                                        <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Destination Facility</span>
                                        <strong>{s.destination || 'Chennai Central DC'}</strong>
                                      </div>
                                      <div className="flex-between">
                                        <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Current On-Hand Buffer</span>
                                        <strong>85 units (5.6 days coverage)</strong>
                                      </div>
                                      <div className="flex-between">
                                        <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Stockout Exposure Risk</span>
                                        <strong style={{ color: isDelayed ? 'var(--status-critical)' : 'var(--status-healthy)' }}>
                                          {isDelayed ? 'CRITICAL (Shortage 45 units)' : 'HEALTHY (Stock Sufficient)'}
                                        </strong>
                                      </div>
                                      <div className="flex-between">
                                        <span style={{ color: 'var(--text-secondary)', fontSize: '12px' }}>Financial Risk Exposure</span>
                                        <strong style={{ color: isDelayed ? 'var(--status-critical)' : 'inherit' }}>
                                          {isDelayed ? '$5,325.00 (Loss & SLA Penalty)' : '$0.00'}
                                        </strong>
                                      </div>
                                    </div>
                                  </div>
                                </div>

                                <div>
                                  <h2 className="section-title">RECOMMENDED MITIGATION (ACTION CENTER)</h2>
                                  <div style={{ 
                                    padding: '16px', 
                                    background: isDelayed ? 'var(--status-watch-bg)' : 'rgba(45, 212, 167, 0.1)', 
                                    border: `1px solid ${isDelayed ? 'var(--status-watch-border)' : 'rgba(45, 212, 167, 0.3)'}`, 
                                    borderRadius: 'var(--r-md)', 
                                    color: isDelayed ? 'var(--status-watch)' : '#2DD4A7' 
                                  }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                                      <strong style={{ fontSize: '14px' }}>
                                        {isDelayed ? 'Emergency Inter-Warehouse Stock Transfer' : 'Autonomous Schedule Monitoring'}
                                      </strong>
                                      <span style={{ fontSize: '11px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(0,0,0,0.2)' }}>
                                        {isDelayed ? 'HIGH ROI' : 'STABLE'}
                                      </span>
                                    </div>
                                    <p style={{ fontSize: '12px', margin: 0, opacity: 0.9 }}>
                                      {isDelayed 
                                        ? 'Transfer 45 units from neighboring regional DC in under 12 hours ($450 cost) to prevent $5,325 in lost sales and contract SLA penalties.'
                                        : 'Transit schedule is operating within buffer tolerances. Safety buffer absorbs standard operational dwell.'
                                      }
                                    </p>
                                    {isDelayed && (
                                      <div style={{ marginTop: '12px' }}>
                                        <a href="/recommendations" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '12px', padding: '6px 12px' }}>
                                          Go to Action Center to Approve <ArrowUpRight size={14} />
                                        </a>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>

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

      {/* Quick Delay Modal inside row */}
      {delayModalShipment && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1100, padding: '16px'
        }}>
          <div style={{
            background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)',
            borderRadius: 'var(--r-xl)', width: '100%', maxWidth: '440px', padding: '24px 28px',
            boxShadow: 'var(--shadow-lg)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={20} color="var(--status-critical)" />
                <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                  Report Transit Disruption
                </h2>
              </div>
              <button onClick={() => setDelayModalShipment(null)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              Simulates a live carrier field delay on <strong>{delayModalShipment.external_shipment_id}</strong>. 
              Triggers downstream stockout evaluation across connected laptops.
            </p>

            <form onSubmit={handleReportDelaySubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Delay Duration (Hours) *
                </label>
                <input
                  type="number"
                  min="1"
                  max="120"
                  required
                  value={delayHoursInput}
                  onChange={(e) => setDelayHoursInput(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Root Cause / Reason *
                </label>
                <select
                  value={delayReasonInput}
                  onChange={(e) => setDelayReasonInput(e.target.value)}
                  style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                >
                  <option value="Severe Weather / Landslide">Severe Weather / Landslide</option>
                  <option value="Vehicle Breakdown">Vehicle Breakdown</option>
                  <option value="Highway Highway Traffic Jam">Highway Highway Traffic Jam</option>
                  <option value="Intermodal Hub Congestion">Intermodal Hub Congestion</option>
                  <option value="Driver Hours of Service Cutoff">Driver Hours of Service Cutoff</option>
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '12px' }}>
                <button type="button" onClick={() => setDelayModalShipment(null)} className="btn-secondary" style={{ padding: '8px 14px' }}>
                  Cancel
                </button>
                <button type="submit" disabled={actionLoading} className="btn-primary" style={{ padding: '8px 18px', background: 'var(--status-critical)', borderColor: 'var(--status-critical)' }}>
                  {actionLoading ? 'Broadcasting...' : 'Broadcast Delay'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create & Assign Shipment Modal */}
      {showCreateModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 1000, padding: '16px'
        }}>
          <div style={{
            background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)',
            borderRadius: 'var(--r-xl)', width: '100%', maxWidth: '560px', maxHeight: '90vh',
            overflowY: 'auto', padding: '24px 28px', boxShadow: 'var(--shadow-lg)'
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
                  Shipment Reference (Leave blank for auto-generation)
                </label>
                <input
                  type="text"
                  placeholder="e.g. SH-BLR-2026-0002"
                  value={formData.external_shipment_id}
                  onChange={(e) => setFormData({ ...formData, external_shipment_id: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                />
              </div>

              {/* Select Receiver Company */}
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Receiver / Destination Enterprise (Consignee) *
                </label>
                <select
                  value={formData.receiver_company_id}
                  onChange={(e) => {
                    const selComp = allCompanies.find(c => c.id === parseInt(e.target.value, 10));
                    setFormData({ 
                      ...formData, 
                      receiver_company_id: e.target.value,
                      destination: selComp ? `${selComp.name} Central DC` : formData.destination
                    });
                  }}
                  style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                >
                  <option value="">-- Select Recipient Company --</option>
                  {allCompanies.filter(c => c.id !== company.id).map(c => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.industry || 'Logistics Partner'})
                    </option>
                  ))}
                </select>
              </div>

              {/* Waypoints */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Origin Plant / Waypoint *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Bengaluru Electronic City Plant"
                    value={formData.origin}
                    onChange={(e) => setFormData({ ...formData, origin: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Destination DC / Warehouse *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Chennai Central DC"
                    value={formData.destination}
                    onChange={(e) => setFormData({ ...formData, destination: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
              </div>

              {/* Transport mode and delivery date */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Primary Transport Mode *
                  </label>
                  <select
                    value={formData.transport_mode}
                    onChange={(e) => setFormData({ ...formData, transport_mode: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  >
                    <option value="ROAD">ROAD (Express Highway)</option>
                    <option value="RAIL">RAIL (Intermodal Freight)</option>
                    <option value="AIR">AIR (Air Cargo Linehaul)</option>
                    <option value="SEA">SEA (Ocean Container)</option>
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

              {/* Quantities and distance */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Shipment Units / Quantity *
                  </label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={formData.quantity}
                    onChange={(e) => setFormData({ ...formData, quantity: parseFloat(e.target.value) || 100 })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Corridor Distance (km)
                  </label>
                  <input
                    type="number"
                    min="10"
                    value={formData.distance_km}
                    onChange={(e) => setFormData({ ...formData, distance_km: parseFloat(e.target.value) || 360 })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
              </div>

              {/* Transporter partner */}
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Assign Authorized Transporter Partner *
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
                  Assigning establishes secure multi-tenant isolation. Only the assigned carrier can view or report delays on this cargo.
                </div>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
                <button type="button" onClick={() => setShowCreateModal(false)} className="btn-secondary" style={{ padding: '8px 14px' }}>
                  Cancel
                </button>
                <button type="submit" disabled={creating} className="btn-primary" style={{ padding: '8px 18px' }}>
                  {creating ? 'Dispatching...' : 'Dispatch & Provision Legs'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
