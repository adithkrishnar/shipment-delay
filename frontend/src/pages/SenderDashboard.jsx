import React, { useEffect, useState, useMemo } from 'react';
import {
  Truck, Package, Clock, AlertTriangle, CheckCircle2, MapPin,
  Calendar, ArrowRight, ChevronRight, RefreshCw, Plus, Search,
  Building2, ShieldCheck, Layers, Filter, X, Navigation
} from 'lucide-react';
import {
  getShipments,
  getRecentDisruptions,
  createShipment,
  getTransporterOrgs,
  getCompanies
} from '../services/api';
import MultiLegDemo from '../components/MultiLegDemo';
import Loader from '../components/Loader';
import { formatDateTime } from '../utils/delayPropagation';

export default function SenderDashboard({ company, user }) {
  const [shipmentsData, setShipmentsData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [disruptions, setDisruptions] = useState([]);
  const [activeTab, setActiveTab] = useState('ACTIVE'); // 'ACTIVE', 'ALL', 'COMPLETED'
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedShipment, setSelectedShipment] = useState(null);
  const selectedShipmentIdRef = React.useRef(null);

  // Create Outbound Dispatch Modal
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

  const handleSelectShipment = (shipment) => {
    if (!shipment) return;
    selectedShipmentIdRef.current = shipment.shipment_id || shipment.id || shipment.external_shipment_id;
    setSelectedShipment(shipment);
  };

  const loadDashboardData = async () => {
    if (!company?.id) return;
    try {
      const [resShipments, resDisruptions] = await Promise.all([
        getShipments(company.id),
        getRecentDisruptions().catch(() => [])
      ]);

      const list = resShipments?.shipments || [];
      // Filter shipments strictly dispatched by this company (Sender / Consignor)
      const outgoing = list.filter(s => s.company_id === company.id || !s.company_id);
      setShipmentsData(outgoing);

      // Merge backend disruptions with local stored reports
      const localDisruptions = JSON.parse(localStorage.getItem('supplyiq_recent_disruptions') || '[]');
      const combinedDisruptions = [...localDisruptions, ...(resDisruptions || [])];
      const uniqueDisruptions = [];
      const seen = new Set();
      for (const d of combinedDisruptions) {
        const key = `${d.external_shipment_id || d.shipment_id}-${d.delay_hours}-${d.disruption_reason}`;
        if (!seen.has(key)) {
          seen.add(key);
          uniqueDisruptions.push(d);
        }
      }
      setDisruptions(uniqueDisruptions);

      // Maintain user's active selection across polling intervals with active shipment prioritization
      setSelectedShipment(prev => {
        const targetId = selectedShipmentIdRef.current || prev?.shipment_id || prev?.external_shipment_id;
        if (targetId) {
          const fresh = outgoing.find(s => s.shipment_id === targetId || s.external_shipment_id === targetId);
          if (fresh) return fresh;
        }
        // Active shipment prioritization:
        // 1. Critical delayed shipment
        const critDelayed = outgoing.find(s => s.assignment_status === 'DELAYED' && s.risk_tier === 'CRITICAL');
        if (critDelayed) {
          selectedShipmentIdRef.current = critDelayed.shipment_id;
          return critDelayed;
        }
        // 2. Other delayed shipment
        const delayed = outgoing.find(s => s.assignment_status === 'DELAYED');
        if (delayed) {
          selectedShipmentIdRef.current = delayed.shipment_id;
          return delayed;
        }
        // 3. Active in-transit shipment
        const inTransit = outgoing.find(s => s.assignment_status === 'IN_TRANSIT');
        if (inTransit) {
          selectedShipmentIdRef.current = inTransit.shipment_id;
          return inTransit;
        }
        // 4. Arrived / Pending
        const pending = outgoing.find(s => ['ARRIVED', 'PENDING', 'ACCEPTED'].includes(s.assignment_status));
        if (pending) {
          selectedShipmentIdRef.current = pending.shipment_id;
          return pending;
        }
        // 5. Delivered / Completed
        const delivered = outgoing.find(s => s.assignment_status === 'DELIVERED' || s.is_completed);
        const fallback = delivered || outgoing[0] || null;
        if (fallback) {
          selectedShipmentIdRef.current = fallback.shipment_id;
        }
        return fallback;
      });
      setError(null);
    } catch (err) {
      console.error('Error loading sender dashboard:', err);
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
    getTransporterOrgs().then(orgs => {
      setTransporterOrgs(orgs || []);
      const ktn = (orgs || []).find(o => o.carrier_code === 'KTN-EXPRESS' || o.id === 5);
      if (ktn) {
        setFormData(prev => ({ ...prev, transporter_org_id: prev.transporter_org_id || String(ktn.id) }));
      }
    }).catch(() => {});

    getCompanies().then(comps => {
      setAllCompanies(comps || []);
      const chennai = (comps || []).find(c => c.name && c.name.toLowerCase().includes('chennai'));
      if (chennai) {
        setFormData(prev => ({ ...prev, receiver_company_id: prev.receiver_company_id || String(chennai.id) }));
      }
    }).catch(() => {});

    // Real-time synchronization interval (3.5s)
    const interval = setInterval(() => {
      loadDashboardData();
    }, 3500);

    const handleDisruptionReported = () => loadDashboardData();
    window.addEventListener('supplyiq_disruption_reported', handleDisruptionReported);

    return () => {
      clearInterval(interval);
      window.removeEventListener('supplyiq_disruption_reported', handleDisruptionReported);
    };
  }, [company?.id]);

  // Compute Sender KPIs
  const kpis = useMemo(() => {
    const totalDispatches = shipmentsData.length;
    
    // Physically in-transit: on the road/rail corridor
    const physicallyInTransitDispatches = shipmentsData.filter(s => 
      ['IN_TRANSIT', 'DELAYED'].includes(s.assignment_status) && !s.is_completed && !s.actual_delivery
    );
    // Arrived at destination facility, awaiting consignee goods inward confirmation
    const arrivedDispatches = shipmentsData.filter(s => 
      s.assignment_status === 'ARRIVED' && !s.is_completed && !s.actual_delivery
    );
    // Awaiting dispatch / carrier pickup
    const awaitingDispatchDispatches = shipmentsData.filter(s => 
      ['PENDING', 'ACCEPTED'].includes(s.assignment_status) && !s.is_completed && !s.actual_delivery
    );
    // Completed / delivered
    const completedDispatches = shipmentsData.filter(s => s.is_completed || s.assignment_status === 'DELIVERED');
    const delayedDispatches = shipmentsData.filter(s => s.assignment_status === 'DELAYED');
    
    const unitsPhysicallyInTransit = physicallyInTransitDispatches.reduce((acc, s) => acc + (Number(s.quantity) || 0), 0);
    const unitsArrivedPendingReceipt = arrivedDispatches.reduce((acc, s) => acc + (Number(s.quantity) || 0), 0);
    const unitsAwaitingDispatch = awaitingDispatchDispatches.reduce((acc, s) => acc + (Number(s.quantity) || 0), 0);
    
    // Open dispatches: transit + arrived awaiting inward + awaiting pickup
    const unitsInOpenDispatches = unitsPhysicallyInTransit + unitsArrivedPendingReceipt + unitsAwaitingDispatch;
    const completedUnits = completedDispatches.reduce((acc, s) => acc + (Number(s.quantity) || 0), 0);
    const totalUnitsDispatchedAllTime = unitsInOpenDispatches + completedUnits;
    
    const primaryCarrier = shipmentsData[0]?.carrier || 'Karnataka-Tamil Nadu Express Logistics';

    return {
      totalDispatches,
      activeCount: physicallyInTransitDispatches.length + arrivedDispatches.length + awaitingDispatchDispatches.length,
      delayedCount: delayedDispatches.length,
      arrivedCount: arrivedDispatches.length,
      unitsPhysicallyInTransit,
      unitsArrivedPendingReceipt,
      unitsAwaitingDispatch,
      unitsInOpenDispatches,
      completedUnits,
      totalUnitsDispatchedAllTime,
      primaryCarrier
    };
  }, [shipmentsData]);

  // Filtered shipments based on active tab and search query
  const filteredShipments = useMemo(() => {
    return shipmentsData.filter(s => {
      const isCompleted = s.is_completed || s.assignment_status === 'DELIVERED';
      if (activeTab === 'ACTIVE' && isCompleted) return false;
      if (activeTab === 'COMPLETED' && !isCompleted) return false;

      if (!searchQuery) return true;
      const q = searchQuery.toLowerCase();
      return (
        (s.external_shipment_id || '').toLowerCase().includes(q) ||
        (s.product_name || '').toLowerCase().includes(q) ||
        (s.receiver_company_name || '').toLowerCase().includes(q) ||
        (s.carrier || '').toLowerCase().includes(q) ||
        (s.destination || '').toLowerCase().includes(q)
      );
    });
  }, [shipmentsData, activeTab, searchQuery]);

  // Operational delay alerts relevant to sender's shipments
  const senderDelays = useMemo(() => {
    const shipmentRefs = new Set(shipmentsData.map(s => s.external_shipment_id || `SH-${s.shipment_id}`));
    return disruptions.filter(d => {
      const ref = d.external_shipment_id || (d.shipment_id ? `SH-${d.shipment_id}` : '');
      return shipmentRefs.has(ref) || d.external_shipment_id === 'SH-BLR-2026-0001' || d.external_shipment_id === 'SH-BLR-2026-0002';
    });
  }, [disruptions, shipmentsData]);

  // Group multiple disruptions for the same shipment into a single authoritative alert
  const [expandedDelays, setExpandedDelays] = useState(() => new Set());
  const groupedSenderDelays = useMemo(() => {
    const groups = {};
    for (const d of senderDelays) {
      const ref = d.external_shipment_id || (d.shipment_id ? `SH-${d.shipment_id}` : 'UNKNOWN');
      if (!groups[ref]) {
        groups[ref] = {
          reference: ref,
          shipment_id: d.shipment_id,
          destination: d.destination || 'Chennai Central DC, Tamil Nadu',
          events: [],
          totalDelayHours: 0,
          primaryReason: d.disruption_reason || d.reason || 'Transit Congestion',
          location: d.incident_location || d.location || 'NH-48 Intermodal Corridor',
          revisedEta: d.revised_eta || d.new_eta
        };
      }
      groups[ref].events.push(d);
      groups[ref].totalDelayHours = Math.max(groups[ref].totalDelayHours, d.delay_hours || 0);
    }
    // Compute cumulative delay if multi-leg reports exist
    for (const ref in groups) {
      const g = groups[ref];
      const legDelays = g.events.map(e => e.delay_hours || 0);
      const sumDelays = legDelays.reduce((acc, curr) => acc + curr, 0);
      if (sumDelays > g.totalDelayHours) {
        g.totalDelayHours = sumDelays;
      }
    }
    return Object.values(groups);
  }, [senderDelays]);

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    if (!company) return;
    setCreating(true);
    setCreateMsg('');
    try {
      const fallbackPid = shipmentsData[0]?.product_id || 1;
      const payload = {
        ...formData,
        product_id: fallbackPid,
        receiver_company_id: formData.receiver_company_id ? parseInt(formData.receiver_company_id, 10) : null,
        transporter_org_id: formData.transporter_org_id ? parseInt(formData.transporter_org_id, 10) : null,
      };
      await createShipment(company.id, payload);
      setCreateMsg('Outbound dispatch scheduled and assigned to carrier successfully!');
      setTimeout(() => {
        setShowCreateModal(false);
        setCreateMsg('');
        loadDashboardData();
      }, 1200);
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Creation failed');
    } finally {
      setCreating(false);
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'DELAYED':
        return <span className="badge badge-critical" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><AlertTriangle size={12} /> DELAYED</span>;
      case 'DELIVERED':
        return <span className="badge badge-healthy" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><CheckCircle2 size={12} /> DELIVERED</span>;
      case 'IN_TRANSIT':
        return <span className="badge badge-info" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Truck size={12} /> IN TRANSIT</span>;
      case 'ARRIVED':
        return <span className="badge badge-info" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(96, 165, 250, 0.15)', color: '#60A5FA', border: '1px solid rgba(96, 165, 250, 0.3)' }}><CheckCircle2 size={12} /> ARRIVED (INWARD PENDING)</span>;
      case 'PENDING':
        return <span className="badge badge-watch" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Clock size={12} /> PENDING ASSIGNMENT</span>;
      default:
        return <span className="badge badge-neutral">{status}</span>;
    }
  };

  if (loading && !shipmentsData.length) {
    return <Loader message="Loading Sender Outbound Logistics Cockpit..." />;
  }

  return (
    <div className="page animate-fade" style={{ paddingBottom: '40px' }}>
      {/* ── Top Header & Role Banner ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <span style={{ 
              background: 'rgba(94, 107, 255, 0.12)', 
              color: 'var(--accent-primary)', 
              border: '1px solid rgba(94, 107, 255, 0.3)', 
              padding: '2px 8px', 
              borderRadius: '4px', 
              fontSize: '11px', 
              fontWeight: 700,
              letterSpacing: '0.06em',
              textTransform: 'uppercase'
            }}>
              CONSIGNOR / SENDER DASHBOARD
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>•</span>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
              Tenant: <strong style={{ color: 'var(--text-primary)' }}>{company?.name || 'Bengaluru Manufacturing Ltd'}</strong>
            </span>
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Outbound Dispatch Operations Cockpit
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', margin: '4px 0 0 0' }}>
            Authoritative visibility over outgoing dispatches, authorized logistics carriers, highway transit corridors, and route ETAs.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button 
            className="btn-secondary" 
            onClick={loadDashboardData}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '13px', padding: '8px 14px' }}
          >
            <RefreshCw size={14} /> Refresh
          </button>
          <button 
            className="btn-primary" 
            onClick={() => setShowCreateModal(true)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '13px', padding: '8px 16px' }}
          >
            <Plus size={15} /> Create Outbound Dispatch
          </button>
        </div>
      </div>

      {/* ── Operational Disruption Alert Banner (Sender Focused) ── */}
      {senderDelays.length > 0 && (
        <div style={{ 
          background: 'rgba(255, 90, 107, 0.05)', 
          border: '1px solid rgba(255, 90, 107, 0.3)', 
          borderRadius: '8px', 
          padding: '16px 20px', 
          marginBottom: '24px' 
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ 
                width: '10px', height: '10px', borderRadius: '50%', 
                background: 'var(--status-critical)', 
                boxShadow: '0 0 8px var(--status-critical)' 
              }} />
              <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--status-critical)', margin: 0, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Operational Highway Delay Alerts ({groupedSenderDelays.length} Impacted Corridor)
              </h3>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
              Real-time Transporter Telematics Broadcast • Synchronized with Central Control Tower
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {groupedSenderDelays.map((g, idx) => {
              const isExpanded = expandedDelays.has(g.reference);
              const toggleExpand = () => {
                const next = new Set(expandedDelays);
                if (next.has(g.reference)) next.delete(g.reference);
                else next.add(g.reference);
                setExpandedDelays(next);
              };

              return (
                <div 
                  key={idx}
                  style={{ 
                    background: 'var(--bg-surface-1)', 
                    border: '1px solid var(--border-default)', 
                    borderRadius: '6px', 
                    padding: '14px 18px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                        <span style={{ 
                          fontSize: '11px', fontWeight: 700, 
                          color: 'var(--status-critical)', 
                          background: 'rgba(255, 90, 107, 0.1)', 
                          padding: '2px 6px', borderRadius: '4px' 
                        }}>
                          CORRIDOR DELAY • NH-48 Express
                        </span>
                        <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                          Shipment {g.reference}
                        </strong>
                        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>• Primary Disruption: {g.primaryReason}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Route: Bengaluru Plant → {g.destination} • {g.events.length} leg disruption event(s) recorded
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Authoritative Delay</div>
                        <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--status-critical)' }}>+{g.totalDelayHours} Hours</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Revised Destination ETA</div>
                        <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {g.revisedEta ? formatDateTime(g.revisedEta) : 'Nov 20, 2026 (Delayed)'}
                        </div>
                      </div>
                      <button 
                        className="btn-secondary"
                        onClick={() => {
                          const match = shipmentsData.find(s => s.external_shipment_id === g.reference);
                          if (match) handleSelectShipment(match);
                        }}
                        style={{ fontSize: '12px', padding: '6px 12px' }}
                      >
                        Track Corridor
                      </button>
                      {g.events.length > 1 && (
                        <button
                          onClick={toggleExpand}
                          style={{
                            background: 'none', border: '1px solid var(--border-subtle)', borderRadius: '4px',
                            color: 'var(--text-secondary)', fontSize: '11px', padding: '4px 8px', cursor: 'pointer'
                          }}
                        >
                          {isExpanded ? 'Hide Details' : `Breakdown (${g.events.length})`}
                        </button>
                      )}
                    </div>
                  </div>

                  {isExpanded && g.events.length > 1 && (
                    <div style={{ background: 'var(--bg-surface-2)', padding: '10px 14px', borderRadius: '6px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Individual Disruption Log:</span>
                      {g.events.map((ev, eIdx) => (
                        <div key={eIdx} style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)' }}>
                          <span>Leg #{ev.leg_sequence || eIdx + 1} ({ev.leg_mode || 'ROAD'}): {ev.disruption_reason || ev.reason} - {ev.notes || 'In transit delay'}</span>
                          <span style={{ fontWeight: 600, color: 'var(--status-critical)' }}>+{ev.delay_hours || 4}h</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── KPI Summary Cards ── */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', 
        gap: '16px', 
        marginBottom: '24px' 
      }}>
        <div className="kpi-card" style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: '8px', padding: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Total Outgoing Shipments
            </span>
            <div style={{ width: '32px', height: '32px', borderRadius: '6px', background: 'rgba(94, 107, 255, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-primary)' }}>
              <Package size={18} />
            </div>
          </div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {kpis.totalDispatches}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Dispatched from {company?.name || 'Bengaluru Plant'}
          </div>
        </div>

        <div className="kpi-card" style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: '8px', padding: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Active In-Transit Dispatches
            </span>
            <div style={{ width: '32px', height: '32px', borderRadius: '6px', background: 'rgba(80, 216, 233, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--accent-cyan)' }}>
              <Truck size={18} />
            </div>
          </div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--accent-cyan)' }}>
            {kpis.activeCount}
          </div>
          <div style={{ fontSize: '12px', color: kpis.delayedCount > 0 ? 'var(--status-critical)' : 'var(--text-secondary)', marginTop: '4px' }}>
            {kpis.delayedCount > 0 
              ? `${kpis.delayedCount} shipment currently delayed` 
              : (kpis.arrivedCount > 0 ? `${kpis.arrivedCount} arrived, inward pending` : 'All corridors on schedule')}
          </div>
        </div>

        <div className="kpi-card" style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: '8px', padding: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Units in Open Dispatches
            </span>
            <div style={{ width: '32px', height: '32px', borderRadius: '6px', background: 'rgba(56, 229, 163, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--status-healthy)' }}>
              <Layers size={18} />
            </div>
          </div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text-primary)' }}>
            {kpis.unitsInOpenDispatches.toLocaleString()} <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-secondary)' }}>units</span>
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {kpis.unitsPhysicallyInTransit.toLocaleString()} in transit{kpis.unitsArrivedPendingReceipt > 0 ? ` • ${kpis.unitsArrivedPendingReceipt.toLocaleString()} arrived (inward pending)` : ''} • {kpis.unitsAwaitingDispatch.toLocaleString()} awaiting pickup
          </div>
        </div>

        <div className="kpi-card" style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: '8px', padding: '18px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              Authorized Logistics Partner
            </span>
            <div style={{ width: '32px', height: '32px', borderRadius: '6px', background: 'rgba(255, 182, 137, 0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--status-watch)' }}>
              <ShieldCheck size={18} />
            </div>
          </div>
          <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {kpis.primaryCarrier}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Corridor: Bengaluru ⇄ Chennai NH-48
          </div>
        </div>
      </div>

      {/* ── Active Journey Corridor Tracker ── */}
      {selectedShipment && (
        <div style={{ 
          background: 'var(--bg-surface-1)', 
          border: '1px solid var(--border-default)', 
          borderRadius: '8px', 
          padding: '20px', 
          marginBottom: '24px' 
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '10px' }}>
            <div>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                LIVE CORRIDOR TELEMATICS & ROUTE PROGRESSION
              </div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', margin: '2px 0 0 0' }}>
                Tracking Shipment {selectedShipment.external_shipment_id} ({selectedShipment.product_name})
              </h3>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                Consignee: <strong style={{ color: 'var(--text-primary)' }}>{selectedShipment.receiver_company_name || 'Chennai Central Distribution'}</strong>
              </span>
              {getStatusBadge(selectedShipment.assignment_status)}
            </div>
          </div>

          <MultiLegDemo companyId={company?.id || user?.company_id} shipmentId={selectedShipment.shipment_id} />
        </div>
      )}

      {/* ── Outgoing Dispatches Table Section ── */}
      <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: '8px', padding: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => setActiveTab('ACTIVE')}
              className={activeTab === 'ACTIVE' ? 'btn-primary' : 'btn-secondary'}
              style={{ padding: '6px 14px', fontSize: '12px' }}
            >
              Active In-Transit ({kpis.activeCount})
            </button>
            <button
              onClick={() => setActiveTab('ALL')}
              className={activeTab === 'ALL' ? 'btn-primary' : 'btn-secondary'}
              style={{ padding: '6px 14px', fontSize: '12px' }}
            >
              All Outbound ({kpis.totalDispatches})
            </button>
            <button
              onClick={() => setActiveTab('COMPLETED')}
              className={activeTab === 'COMPLETED' ? 'btn-primary' : 'btn-secondary'}
              style={{ padding: '6px 14px', fontSize: '12px' }}
            >
              Completed / Delivered ({kpis.completedCount})
            </button>
          </div>

          {/* Search */}
          <div style={{ position: 'relative', width: '280px' }}>
            <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-tertiary)' }} />
            <input
              type="text"
              placeholder="Search reference, product, carrier..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '7px 10px 7px 32px',
                background: 'var(--bg-base)',
                border: '1px solid var(--border-default)',
                borderRadius: '6px',
                color: 'var(--text-primary)',
                fontSize: '12px'
              }}
            />
          </div>
        </div>

        {/* Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-default)', textAlign: 'left', color: 'var(--text-tertiary)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                <th style={{ padding: '12px 10px' }}>Shipment Reference & Product</th>
                <th style={{ padding: '12px 10px' }}>Origin (Source Plant)</th>
                <th style={{ padding: '12px 10px' }}>Destination Consignee</th>
                <th style={{ padding: '12px 10px' }}>Carrier & Route</th>
                <th style={{ padding: '12px 10px' }}>Dispatch / Planned</th>
                <th style={{ padding: '12px 10px' }}>Current ETA</th>
                <th style={{ padding: '12px 10px' }}>Status</th>
                <th style={{ padding: '12px 10px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredShipments.length === 0 ? (
                <tr>
                  <td colSpan="8" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-tertiary)' }}>
                    No outgoing shipments match the selected filter.
                  </td>
                </tr>
              ) : (
                filteredShipments.map(s => {
                  const isSelected = selectedShipment?.shipment_id === s.shipment_id;
                  return (
                    <tr 
                      key={s.shipment_id} 
                      style={{ 
                        borderBottom: '1px solid var(--border-subtle)',
                        background: isSelected ? 'rgba(94, 107, 255, 0.05)' : 'transparent',
                        transition: 'background 0.15s ease'
                      }}
                    >
                      <td style={{ padding: '12px 10px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {s.external_shipment_id}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                          {s.product_name}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                          Qty: <strong style={{ color: 'var(--text-secondary)' }}>{s.quantity || 100} units</strong> {s.weight_kg ? `• ${s.weight_kg} kg` : ''}
                        </div>
                      </td>

                      <td style={{ padding: '12px 10px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-primary)', fontWeight: 500 }}>
                          <MapPin size={12} style={{ color: 'var(--accent-primary)' }} />
                          {s.origin ? s.origin.split(',')[0] : 'Bengaluru Plant'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>Karnataka</div>
                      </td>

                      <td style={{ padding: '12px 10px', color: 'var(--text-secondary)', fontSize: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-primary)', fontWeight: 500 }}>
                          <Building2 size={12} style={{ color: 'var(--accent-cyan)' }} />
                          {s.receiver_company_name || 'Chennai Central Distribution'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                          {s.destination_warehouse || s.destination || 'Chennai Central DC'}
                        </div>
                      </td>

                      <td style={{ padding: '12px 10px', fontSize: '12px' }}>
                        <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                          {s.carrier || 'Karnataka-Tamil Nadu Express Logistics'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                          {s.transport_mode || 'ROAD'} • NH-48 (360 km)
                        </div>
                      </td>

                      <td style={{ padding: '12px 10px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                        <div>Dep: {formatDateTime(s.order_date || '2026-11-16')}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>Plan: {formatDateTime(s.planned_delivery)}</div>
                      </td>

                      <td style={{ padding: '12px 10px', fontSize: '12px' }}>
                        <div style={{ 
                          fontWeight: 600, 
                          color: s.assignment_status === 'DELAYED' ? 'var(--status-critical)' : 'var(--text-primary)' 
                        }}>
                          {formatDateTime(s.current_eta || s.planned_delivery)}
                        </div>
                        {s.assignment_status === 'DELAYED' && (
                          <div style={{ fontSize: '11px', color: 'var(--status-critical)', fontWeight: 600 }}>
                            +16h Highway Delay
                          </div>
                        )}
                      </td>

                      <td style={{ padding: '12px 10px' }}>
                        {getStatusBadge(s.assignment_status)}
                      </td>

                      <td style={{ padding: '12px 10px', textAlign: 'right' }}>
                        <button
                          onClick={() => handleSelectShipment(s)}
                          className={isSelected ? 'btn-primary' : 'btn-secondary'}
                          style={{ fontSize: '11px', padding: '4px 10px' }}
                        >
                          {isSelected ? 'Viewing' : 'Track'}
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Create Outbound Dispatch Modal ── */}
      {showCreateModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9999, backdropFilter: 'blur(4px)'
        }}>
          <div style={{
            background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)',
            borderRadius: '10px', width: '540px', maxWidth: '90%', padding: '24px',
            boxShadow: '0 20px 40px rgba(0,0,0,0.5)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Truck size={18} style={{ color: 'var(--accent-primary)' }} />
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  Create & Assign Outbound Dispatch
                </h3>
              </div>
              <button 
                onClick={() => setShowCreateModal(false)}
                style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                <X size={18} />
              </button>
            </div>

            {createMsg && (
              <div style={{ background: 'rgba(56, 229, 163, 0.1)', border: '1px solid rgba(56, 229, 163, 0.3)', borderRadius: '6px', padding: '10px 14px', marginBottom: '16px', color: 'var(--status-healthy)', fontSize: '13px' }}>
                {createMsg}
              </div>
            )}

            <form onSubmit={handleCreateSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Shipment Reference (Leave blank for auto-generation)
                </label>
                <input
                  type="text"
                  placeholder="e.g. SH-BLR-2026-0002"
                  value={formData.external_shipment_id}
                  onChange={e => setFormData({ ...formData, external_shipment_id: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Receiver / Destination Enterprise (Consignee) *
                </label>
                <select
                  required
                  value={formData.receiver_company_id}
                  onChange={(e) => {
                    const selComp = allCompanies.find(c => c.id === parseInt(e.target.value, 10));
                    let destName = formData.destination;
                    if (selComp) {
                      destName = selComp.name.toLowerCase().includes('chennai') 
                        ? 'Chennai Central DC, Tamil Nadu' 
                        : `${selComp.name} Central DC`;
                    }
                    setFormData({ 
                      ...formData, 
                      receiver_company_id: e.target.value,
                      destination: destName
                    });
                  }}
                  style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                >
                  <option value="">-- Select Recipient Company --</option>
                  {allCompanies.filter(c => c.id !== company?.id).map(c => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Origin Plant / Waypoint *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.origin}
                    onChange={e => setFormData({ ...formData, origin: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Destination DC / Warehouse *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.destination}
                    onChange={e => setFormData({ ...formData, destination: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Primary Transport Mode *
                  </label>
                  <select
                    value={formData.transport_mode}
                    onChange={e => setFormData({ ...formData, transport_mode: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  >
                    <option value="ROAD">ROAD (Express Highway)</option>
                    <option value="RAIL">RAIL (Express Freight)</option>
                    <option value="AIR">AIR (Priority Cargo)</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Planned Delivery Date *
                  </label>
                  <input
                    type="date"
                    required
                    value={formData.planned_delivery}
                    onChange={e => setFormData({ ...formData, planned_delivery: e.target.value })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Shipment Units / Quantity *
                  </label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={formData.quantity}
                    onChange={e => setFormData({ ...formData, quantity: parseInt(e.target.value, 10) || 1 })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                    Corridor Distance (km)
                  </label>
                  <input
                    type="number"
                    value={formData.distance_km}
                    onChange={e => setFormData({ ...formData, distance_km: parseInt(e.target.value, 10) || 360 })}
                    style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
                  Assign Authorized Transporter Partner *
                </label>
                <select
                  required
                  value={formData.transporter_org_id}
                  onChange={e => setFormData({ ...formData, transporter_org_id: e.target.value })}
                  style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-base)', border: '1px solid var(--border-default)', borderRadius: '6px', color: 'var(--text-primary)', fontSize: '13px' }}
                >
                  <option value="">-- Select Eligible Transporter Partner --</option>
                  {transporterOrgs.map(org => (
                    <option key={org.id} value={org.id}>{org.name} ({org.carrier_code})</option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowCreateModal(false)}
                  style={{ padding: '8px 16px', fontSize: '13px' }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={creating}
                  style={{ padding: '8px 20px', fontSize: '13px' }}
                >
                  {creating ? 'Dispatching...' : 'Dispatch Shipment'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
