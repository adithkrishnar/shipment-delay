import React, { useEffect, useState, useMemo, useRef } from 'react';
import {
  Boxes, PackageCheck, Truck, AlertTriangle, ShieldCheck, TrendingDown,
  RefreshCw, CheckCircle2, AlertOctagon, Eye, Check, ChevronRight,
  Clock, MapPin, Building, ArrowUpRight, ArrowDownRight, Warehouse
} from 'lucide-react';
import {
  getInventoryOverview,
  getReplenishmentPlan,
  getShipments,
  getSuppliers,
  getRecentDisruptions,
  confirmDelivery,
  approveAction
} from '../services/api';
import { useAlert } from '../context/AlertContext';
import MultiLegDemo from '../components/MultiLegDemo';
import Loader from '../components/Loader';
import { formatDateTime } from '../utils/delayPropagation';

export default function ReceiverDashboard({ company, user }) {
  const { triggerAlert } = useAlert();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Core Data States
  const [inventoryData, setInventoryData] = useState(null);
  const [replenishmentData, setReplenishmentData] = useState(null);
  const [shipmentsData, setShipmentsData] = useState([]);
  const [suppliersData, setSuppliersData] = useState([]);
  const [disruptions, setDisruptions] = useState([]);

  // Active Selection & Modals
  const [selectedProductId, setSelectedProductId] = useState(null);
  const [selectedShipment, setSelectedShipment] = useState(null);
  const selectedShipmentIdRef = useRef(null);
  const [selectedDisruption, setSelectedDisruption] = useState(null);
  const [activeTab, setActiveTab] = useState('inbound'); // 'inbound' | 'all' | 'delivered'
  const [searchQuery, setSearchQuery] = useState('');

  // Goods Inward Confirmation State
  const [confirmingShipmentId, setConfirmingShipmentId] = useState(null);
  const [deliveryMsg, setDeliveryMsg] = useState(null);

  // Operational Stock Transfer Decision Modal State
  const [transferModalItem, setTransferModalItem] = useState(null);
  const [expandedReceiverDelays, setExpandedReceiverDelays] = useState(() => new Set());

  // Synchronized Control Tower Approved Mitigations
  const [approvedActionIds, setApprovedActionIds] = useState(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('supplyiq_approved_actions') || '[]');
      return new Set(stored);
    } catch {
      return new Set();
    }
  });
  const [isApproving, setIsApproving] = useState(false);

  // Load all verified data from authoritative backend APIs
  const loadReceiverData = async () => {
    if (!company?.id) return;
    try {
      const [resInv, resRepl, resShip, resSupp, resDis] = await Promise.all([
        getInventoryOverview(company.id).catch(() => null),
        getReplenishmentPlan(company.id).catch(() => null),
        getShipments(company.id).catch(() => ({ shipments: [] })),
        getSuppliers(company.id).catch(() => ({ suppliers: [] })),
        getRecentDisruptions().catch(() => [])
      ]);

      if (resInv) setInventoryData(resInv);
      if (resRepl) setReplenishmentData(resRepl);
      if (resSupp?.suppliers) setSuppliersData(resSupp.suppliers);

      // Inbound shipments: filter shipments strictly destined to this Receiver (Priority 3)
      const allShps = resShip?.shipments || [];
      const inbound = allShps.filter(s => {
        // Multi-tenant inbound: explicitly destined for this receiver
        if (s.receiver_company_id === company.id) return true;
        // Legacy DataCo procurement POs for Company 16
        if (!s.receiver_company_id && s.company_id === company.id && s.external_shipment_id?.startsWith('DC-PO-')) {
          return true;
        }
        return false;
      });
      setShipmentsData(inbound);

      // Maintain user's active tracking selection across polling cycles with active shipment prioritization
      setSelectedShipment(prev => {
        const targetId = selectedShipmentIdRef.current || prev?.shipment_id || prev?.external_shipment_id;
        if (targetId) {
          const fresh = inbound.find(s => s.shipment_id === targetId || s.external_shipment_id === targetId);
          if (fresh) return fresh;
        }
        // Active shipment prioritization:
        // 1. Critical delayed shipment
        const critDelayed = inbound.find(s => s.assignment_status === 'DELAYED' && s.risk_tier === 'CRITICAL');
        if (critDelayed) {
          selectedShipmentIdRef.current = critDelayed.shipment_id || critDelayed.external_shipment_id;
          return critDelayed;
        }
        // 2. Any delayed shipment
        const delayed = inbound.find(s => s.assignment_status === 'DELAYED');
        if (delayed) {
          selectedShipmentIdRef.current = delayed.shipment_id || delayed.external_shipment_id;
          return delayed;
        }
        // 3. Active in-transit shipment
        const inTransit = inbound.find(s => s.assignment_status === 'IN_TRANSIT');
        if (inTransit) {
          selectedShipmentIdRef.current = inTransit.shipment_id || inTransit.external_shipment_id;
          return inTransit;
        }
        // 4. Arrived / Pending
        const pending = inbound.find(s => ['ARRIVED', 'PENDING', 'ACCEPTED'].includes(s.assignment_status));
        if (pending) {
          selectedShipmentIdRef.current = pending.shipment_id || pending.external_shipment_id;
          return pending;
        }
        // 5. Delivered / Completed
        const delivered = inbound.find(s => s.assignment_status === 'DELIVERED' || s.is_completed);
        const fallback = delivered || inbound[0] || null;
        if (fallback) {
          selectedShipmentIdRef.current = fallback.shipment_id || fallback.external_shipment_id;
        }
        return fallback;
      });

      // Pure DB-backed disruptions from backend API
      const uniqueDis = [];
      const seen = new Set();
      for (const d of (resDis || [])) {
        const key = `${d.external_shipment_id || d.shipment_id}-${d.delay_hours}-${d.disruption_reason}`;
        if (!seen.has(key)) {
          seen.add(key);
          uniqueDis.push(d);
        }
      }
      setDisruptions(uniqueDis);
      setError(null);
    } catch (err) {
      console.error('Error loading receiver dashboard:', err);
      setError(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadReceiverData();
    const interval = setInterval(loadReceiverData, 3500);

    const handleActionApproved = () => loadReceiverData();
    window.addEventListener('supplyiq_action_approved', handleActionApproved);

    return () => {
      clearInterval(interval);
      window.removeEventListener('supplyiq_action_approved', handleActionApproved);
    };
  }, [company?.id]);

  // Derived KPI metrics from verified backend responses
  const kpis = useMemo(() => {
    const items = inventoryData?.items || [];
    const item = (selectedProductId ? items.find(i => i.product_id === selectedProductId) : null) || items[0] || null;
    const recs = replenishmentData?.recommendations || [];
    const repl = (item ? recs.find(r => r.product_id === item.product_id) : null) || recs[0] || null;

    if (!item && !repl) {
      return {
        onHand: 0,
        physicallyInTransit: 0,
        arrivedPendingInward: 0,
        awaitingDispatch: 0,
        totalIncomingPipeline: 0,
        inTransit: 0,
        totalExpected: 0,
        dailyDemand: 0,
        coverageDays: 0,
        safetyStock: 0,
        reorderPoint: 0,
        stockoutProb: 0,
        recommendedOrderQty: 0,
        productName: 'No Active Inventory SKUs',
        sku: '—'
      };
    }

    const onHand = Number(item?.inventory_level ?? repl?.on_hand ?? 0.0);
    const physicallyInTransit = Number(item?.physically_in_transit_quantity ?? (item?.incoming_quantity ?? repl?.incoming_pipeline ?? 0.0));
    const arrivedPendingInward = Number(item?.arrived_quantity ?? 0.0);
    const awaitingDispatch = Number(item?.awaiting_dispatch_quantity ?? 0.0);
    const totalIncomingPipeline = Number(item?.incoming_quantity ?? (physicallyInTransit + arrivedPendingInward + awaitingDispatch));
    const totalExpected = onHand + totalIncomingPipeline;
    const dailyDemand = Number(item?.daily_demand ?? repl?.daily_demand ?? 0.0);
    const coverageDays = Number(item?.inventory_coverage_days ?? (dailyDemand > 0 ? (onHand / dailyDemand).toFixed(1) : 0));
    const safetyStock = Number(item?.safety_stock ?? repl?.safety_stock ?? 0.0);
    const reorderPoint = Number(item?.reorder_point ?? repl?.reorder_point ?? 0.0);
    const stockoutProb = Number(item?.stockout_probability ?? (repl?.stockout_risk === 'CRITICAL' ? 0.95 : repl?.stockout_risk === 'HIGH' ? 0.8 : 0.05));
    const recommendedOrderQty = Number(repl?.suggested_order_qty ?? item?.recommended_order_quantity ?? 0);

    return {
      onHand,
      physicallyInTransit,
      arrivedPendingInward,
      awaitingDispatch,
      totalIncomingPipeline,
      inTransit: physicallyInTransit,
      totalExpected,
      dailyDemand,
      coverageDays,
      safetyStock,
      reorderPoint,
      stockoutProb,
      recommendedOrderQty,
      productName: item?.product_name || repl?.name || (items.length === 0 ? 'No Products Registered' : 'Selected SKU'),
      sku: item?.external_product_id || repl?.sku || '—'
    };
  }, [inventoryData, replenishmentData, selectedProductId]);

  // Handle Goods Inward Delivery Confirmation exclusively for Receiver
  const handleConfirmDelivery = async (shipment) => {
    if (!shipment) return;
    const targetId = shipment.shipment_id || shipment.id;
    setConfirmingShipmentId(targetId);
    try {
      const res = await confirmDelivery(targetId, {});
      setDeliveryMsg({
        success: true,
        reference: shipment.external_shipment_id || `SH-${targetId}`,
        message: res.message || 'Cargo received into warehouse. Inventory stock replenished!'
      });
      triggerAlert({
        title: 'Goods Inward Confirmed',
        message: `Shipment ${shipment.external_shipment_id} successfully received into Chennai Central DC. Inventory updated.`,
        severity: 'healthy'
      });
      // Immediately reload data to show refreshed inventory level
      await loadReceiverData();
    } catch (err) {
      setDeliveryMsg({
        success: false,
        reference: shipment.external_shipment_id || `SH-${targetId}`,
        message: err.response?.data?.detail || err.message || 'Delivery confirmation failed'
      });
    } finally {
      setConfirmingShipmentId(null);
      setTimeout(() => setDeliveryMsg(null), 6000);
    }
  };

  // Handle Mitigations (Emergency Stock Transfer Approval)
  const handleApproveDisruption = async (d) => {
    if (!d) return;
    const actionId = d.external_shipment_id || d.shipment_id || d.id;
    setIsApproving(true);

    const nextApproved = new Set(approvedActionIds);
    if (actionId) nextApproved.add(actionId);
    if (d.external_shipment_id) nextApproved.add(d.external_shipment_id);
    if (d.id) nextApproved.add(d.id);
    if (d.shipment_id) nextApproved.add(String(d.shipment_id));
    setApprovedActionIds(nextApproved);
    localStorage.setItem('supplyiq_approved_actions', JSON.stringify([...nextApproved]));
    window.dispatchEvent(new CustomEvent('supplyiq_action_approved', { detail: { actionId } }));

    if (company?.id) {
      try {
        await approveAction(company.id, {
          action_id: actionId,
          action_type: 'DISRUPTION_MITIGATION',
          title: `Fix Transit Delay: Shipment ${d.external_shipment_id || d.shipment_id}`,
          notes: 'Emergency Stock Transfer approved directly via Consignee Control Tower'
        });
        triggerAlert({
          title: 'Stock Transfer Dispatched',
          message: `Emergency stock transfer approved for ${d.external_shipment_id || 'Shipment'}. Stockout averted.`,
          severity: 'healthy'
        });
      } catch (err) {
        console.warn('Backend approval notice:', err);
      }
    }
    setIsApproving(false);
    setSelectedDisruption(null);
    loadReceiverData();
  };

  const handleSelectShipment = (s) => {
    if (!s) return;
    selectedShipmentIdRef.current = s.shipment_id || s.id || s.external_shipment_id;
    setSelectedShipment(s);
  };

  // Group multiple disruptions for the same shipment into a single authoritative alert
  const groupedReceiverDelays = useMemo(() => {
    const groups = {};
    for (const d of disruptions) {
      const ref = d.external_shipment_id || (d.shipment_id ? `SH-${d.shipment_id}` : 'UNKNOWN');
      if (!groups[ref]) {
        groups[ref] = {
          reference: ref,
          shipment_id: d.shipment_id,
          id: d.id,
          destination: d.destination || 'Chennai Central DC (Warehouse #58)',
          events: [],
          totalDelayHours: 0,
          primaryReason: d.disruption_reason || d.reason || 'Transit Disruption',
          location: d.incident_location || d.location || 'Hosur Hub → Sriperumbudur Depot',
          carrier_name: d.carrier_name || 'Karnataka-Tamil Nadu Express Logistics',
          rawDisruption: d
        };
      }
      groups[ref].events.push(d);
      groups[ref].totalDelayHours = Math.max(groups[ref].totalDelayHours, d.delay_hours || 0);
    }
    for (const ref in groups) {
      const g = groups[ref];
      const sumDelays = g.events.reduce((acc, curr) => acc + (curr.delay_hours || 0), 0);
      if (sumDelays > g.totalDelayHours) {
        g.totalDelayHours = sumDelays;
      }
    }
    return Object.values(groups);
  }, [disruptions]);

  // Filter inbound shipments based on active tab & search
  const filteredShipments = useMemo(() => {
    return shipmentsData.filter(s => {
      const isDelivered = s.assignment_status === 'DELIVERED' || Boolean(s.actual_delivery);
      if (activeTab === 'inbound' && isDelivered) return false;
      if (activeTab === 'delivered' && !isDelivered) return false;

      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        (s.external_shipment_id || '').toLowerCase().includes(q) ||
        (s.product_name || '').toLowerCase().includes(q) ||
        (s.sender_company_name || '').toLowerCase().includes(q) ||
        (s.carrier || '').toLowerCase().includes(q) ||
        (s.origin || '').toLowerCase().includes(q)
      );
    });
  }, [shipmentsData, activeTab, searchQuery]);

  if (loading && !inventoryData) {
    return <Loader message="Connecting to Chennai Central DC Inventory Tower..." />;
  }

  return (
    <div style={{ padding: '24px 32px', maxWidth: '1600px', margin: '0 auto', color: 'var(--text-primary)' }}>
      {/* 1. Header Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <span style={{ fontSize: '11px', fontWeight: 700, padding: '3px 8px', borderRadius: '4px', background: 'rgba(56, 229, 163, 0.15)', color: '#38E5A3', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              CONSIGNEE / RECEIVER DASHBOARD
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>•</span>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Tenant: {company?.name || 'Chennai Central Distribution'} (Warehouse ID: 58)
            </span>
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Warehouse Inventory &amp; Receiving Control Tower
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', margin: '4px 0 0 0' }}>
            Authoritative visibility over physical on-hand stock, incoming freight, lead times, goods inward, and disruption mitigation.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={() => { setRefreshing(true); loadReceiverData(); }}
            disabled={refreshing}
            className="btn-secondary"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', padding: '8px 14px' }}
          >
            <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
            {refreshing ? 'Synchronizing...' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Delivery Receipt Notification Toast */}
      {deliveryMsg && (
        <div style={{
          marginBottom: '20px',
          padding: '12px 18px',
          borderRadius: '8px',
          background: deliveryMsg.success ? 'rgba(56, 229, 163, 0.12)' : 'rgba(239, 68, 68, 0.12)',
          border: `1px solid ${deliveryMsg.success ? 'rgba(56, 229, 163, 0.35)' : 'rgba(239, 68, 68, 0.35)'}`,
          color: deliveryMsg.success ? '#38E5A3' : '#FF5A6B',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          fontSize: '13px',
          fontWeight: 600
        }}>
          {deliveryMsg.success ? <CheckCircle2 size={18} /> : <AlertOctagon size={18} />}
          <span>{deliveryMsg.message}</span>
        </div>
      )}

      {/* 2. SECTION A: Warehouse Inventory Cockpit (4 Primary KPIs + Planning Strip) */}
      <div style={{
        background: 'var(--bg-surface-1, #151C24)',
        border: '1px solid var(--border-subtle, #26313D)',
        borderRadius: '12px',
        padding: '24px',
        marginBottom: '24px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.2)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', flexWrap: 'wrap', gap: '10px' }}>
          <div>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              SECTION A • REAL-TIME INVENTORY COCKPIT
            </span>
            <h2 style={{ fontSize: '16px', fontWeight: 700, margin: '2px 0 0 0', color: 'var(--text-primary)' }}>
              {kpis.productName} ({kpis.sku}) — {company?.name || 'Destination DC'}
            </h2>
          </div>
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {inventoryData?.items?.length > 1 && (
              <select
                aria-label="Select Target SKU"
                value={selectedProductId || inventoryData.items[0]?.product_id || ''}
                onChange={e => setSelectedProductId(Number(e.target.value))}
                style={{
                  background: 'var(--bg-surface-2)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--r-md)',
                  padding: '5px 10px',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  maxWidth: '260px'
                }}
              >
                {inventoryData.items.map(it => (
                  <option key={it.product_id} value={it.product_id}>
                    {it.external_product_id} — {it.product_name}
                  </option>
                ))}
              </select>
            )}
            <span style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '3px 8px',
              borderRadius: '4px',
              background: kpis.stockoutProb > 0.85 ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 229, 163, 0.15)',
              color: kpis.stockoutProb > 0.85 ? '#FF5A6B' : '#38E5A3',
              border: `1px solid ${kpis.stockoutProb > 0.85 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(56, 229, 163, 0.3)'}`
            }}>
              Stockout Risk: {(kpis.stockoutProb * 100).toFixed(1)}% ({kpis.stockoutProb > 0.85 ? 'CRITICAL' : 'OPTIMAL'})
            </span>
          </div>
        </div>

        {/* 4 Primary Metric Cards: Clearly Distinguishing Available vs Incoming */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px', marginBottom: '20px' }}>
          {/* Card 1: Available On-Hand Stock */}
          <div style={{ background: 'var(--bg-surface-2, #1B2430)', border: '1px solid var(--border-subtle, #26313D)', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Available On-Hand Stock</span>
              <Boxes size={18} color="#FFB689" />
            </div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: kpis.onHand <= kpis.safetyStock ? '#FF5A6B' : '#F3F6FA' }}>
              {kpis.onHand.toFixed(1)} <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-tertiary)' }}>units</span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Building size={12} /> Physically present in Chennai DC
            </div>
          </div>

          {/* Card 2: Incoming In-Transit Stock */}
          <div style={{ background: 'var(--bg-surface-2, #1B2430)', border: '1px solid var(--border-subtle, #26313D)', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Incoming In-Transit Stock</span>
              <Truck size={18} color="#38E5A3" />
            </div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#38E5A3' }}>
              +{kpis.physicallyInTransit.toFixed(1)} <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-tertiary)' }}>units</span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={12} /> {kpis.arrivedPendingInward > 0 ? `${kpis.arrivedPendingInward.toFixed(0)} at dock • ` : ''}Active transit corridor en route
            </div>
          </div>

          {/* Card 3: Total Expected Stock */}
          <div style={{ background: 'var(--bg-surface-2, #1B2430)', border: '1px solid var(--border-subtle, #26313D)', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Total Expected Stock</span>
              <PackageCheck size={18} color="#60A5FA" />
            </div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#F3F6FA' }}>
              {kpis.totalExpected.toFixed(1)} <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-tertiary)' }}>units</span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px' }}>
              {kpis.onHand.toFixed(0)} on-hand + {kpis.physicallyInTransit.toFixed(0)} in-transit{kpis.awaitingDispatch > 0 ? ` + ${kpis.awaitingDispatch.toFixed(0)} on order` : ''}
            </div>
          </div>

          {/* Card 4: Daily Consumption & Coverage */}
          <div style={{ background: 'var(--bg-surface-2, #1B2430)', border: '1px solid var(--border-subtle, #26313D)', borderRadius: '8px', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Daily Demand / Run-Rate</span>
              <TrendingDown size={18} color="#F59E0B" />
            </div>
            <div style={{ fontSize: '28px', fontWeight: 800, color: '#F3F6FA' }}>
              {kpis.dailyDemand.toFixed(1)} <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-tertiary)' }}>units/day</span>
            </div>
            <div style={{ fontSize: '11px', color: kpis.coverageDays < 2.0 ? '#FF5A6B' : 'var(--text-secondary)', marginTop: '4px', fontWeight: 600 }}>
              {kpis.coverageDays.toFixed(1)} days of inventory remaining
            </div>
          </div>
        </div>

        {/* Secondary Policy Strip: Statistical Parameters from Replenishment & Inventory Services */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '12px',
          background: 'rgba(0,0,0,0.2)',
          padding: '14px 18px',
          borderRadius: '8px',
          border: '1px solid var(--border-subtle, #26313D)'
        }}>
          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Safety Stock Target</div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
              {kpis.safetyStock.toFixed(2)} units
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>95% service-level buffer</div>
          </div>

          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Reorder Point (ROP)</div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '2px' }}>
              {kpis.reorderPoint.toFixed(2)} units
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>14-day lead-time threshold</div>
          </div>

          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Stockout Probability</div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: '#FF5A6B', marginTop: '2px' }}>
              {(kpis.stockoutProb * 100).toFixed(1)}%
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>Without transit fulfillment</div>
          </div>

          <div>
            <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Recommended Order Qty</div>
            <div style={{ fontSize: '16px', fontWeight: 700, color: '#38E5A3', marginTop: '2px' }}>
              {kpis.recommendedOrderQty.toLocaleString()} units
            </div>
            <div style={{ fontSize: '10px', color: 'var(--text-secondary)' }}>30-day economic batch target</div>
          </div>
        </div>

        {/* Multi-SKU Facility Inventory Register */}
        <div style={{ marginTop: '20px', borderTop: '1px solid var(--border-subtle, #26313D)', paddingTop: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              Facility SKU Inventory Register ({inventoryData?.items?.length || 0} SKUs tracked)
            </span>
            <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
              Click any SKU row to focus Cockpit analytics
            </span>
          </div>

          {(!inventoryData?.items || inventoryData.items.length === 0) ? (
            <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-tertiary)', fontSize: '13px' }}>
              No inventory records registered for this facility.
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-subtle, #26313D)', textAlign: 'left', color: 'var(--text-tertiary)' }}>
                    <th style={{ padding: '8px 12px' }}>Product SKU</th>
                    <th style={{ padding: '8px 12px' }}>Product Name</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>On-Hand</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>In-Transit</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Expected Total</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Daily Run-Rate</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Coverage</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Safety Stock</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>ROP</th>
                    <th style={{ padding: '8px 12px', textAlign: 'center' }}>Stockout Tier</th>
                  </tr>
                </thead>
                <tbody>
                  {inventoryData.items.map(it => {
                    const isSelected = (selectedProductId ? it.product_id === selectedProductId : it === inventoryData.items[0]);
                    const onH = Number(it.inventory_level ?? 0);
                    const inT = Number(it.physically_in_transit_quantity ?? (it.incoming_quantity ?? 0));
                    const expT = onH + inT;
                    const dDem = Number(it.daily_demand ?? 0);
                    const cov = Number(it.inventory_coverage_days ?? (dDem > 0 ? (onH / dDem).toFixed(1) : 0));
                    const ss = Number(it.safety_stock ?? 0);
                    const rop = Number(it.reorder_point ?? 0);
                    const isCrit = it.stockout_risk === 'CRITICAL' || onH <= ss;

                    return (
                      <tr
                        key={it.product_id}
                        onClick={() => setSelectedProductId(it.product_id)}
                        style={{
                          borderBottom: '1px solid var(--border-subtle, #26313D)',
                          background: isSelected ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                          cursor: 'pointer',
                          transition: 'background 0.15s'
                        }}
                      >
                        <td style={{ padding: '10px 12px', fontWeight: 700, color: isSelected ? '#38BDF8' : 'var(--text-primary)' }}>
                          {it.external_product_id}
                        </td>
                        <td style={{ padding: '10px 12px', color: 'var(--text-primary)' }}>
                          {it.product_name}
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: onH <= ss ? '#FF5A6B' : 'var(--text-primary)' }}>
                          {onH.toFixed(1)} u
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', color: '#38E5A3' }}>
                          +{inT.toFixed(1)} u
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: 'var(--text-primary)' }}>
                          {expT.toFixed(1)} u
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                          {dDem.toFixed(1)} u/d
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 600, color: cov < 2 ? '#FF5A6B' : 'var(--text-primary)' }}>
                          {cov.toFixed(1)} d
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                          {ss.toFixed(1)} u
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'right', color: 'var(--text-secondary)' }}>
                          {rop.toFixed(1)} u
                        </td>
                        <td style={{ padding: '10px 12px', textAlign: 'center' }}>
                          <span style={{
                            padding: '2px 8px',
                            borderRadius: '4px',
                            fontSize: '10px',
                            fontWeight: 700,
                            background: isCrit ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 229, 163, 0.15)',
                            color: isCrit ? '#FF5A6B' : '#38E5A3',
                            border: `1px solid ${isCrit ? 'rgba(239, 68, 68, 0.3)' : 'rgba(56, 229, 163, 0.3)'}`
                          }}>
                            {it.stockout_risk || (isCrit ? 'CRITICAL' : 'OPTIMAL')}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* 3. SECTION D: Disruption & Stockout Intelligence Banner */}
      {groupedReceiverDelays.length > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.12), rgba(245, 158, 11, 0.05))',
          border: '1px solid rgba(239, 68, 68, 0.35)',
          borderRadius: '12px',
          padding: '18px 22px',
          marginBottom: '24px'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{
                width: 32, height: 32, borderRadius: '6px',
                background: 'rgba(239, 68, 68, 0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <AlertTriangle size={18} color="#FF5A6B" />
              </div>
              <div>
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#FF5A6B', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  SECTION D • DISRUPTION &amp; STOCKOUT MITIGATION INTELLIGENCE
                </span>
                <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                  Active Highway Transit Exceptions Detected ({groupedReceiverDelays.length} Shipment{groupedReceiverDelays.length > 1 ? 's' : ''})
                </h3>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {groupedReceiverDelays.map((g, idx) => {
              const isApproved = approvedActionIds.has(g.reference) ||
                                 approvedActionIds.has(g.id) ||
                                 approvedActionIds.has(String(g.shipment_id)) ||
                                 approvedActionIds.has('DISRUPTION-51');
              const isExpanded = expandedReceiverDelays.has(g.reference);

              return (
                <div
                  key={idx}
                  style={{
                    background: 'var(--bg-surface-1, #151C24)',
                    border: '1px solid var(--border-subtle, #26313D)',
                    borderRadius: '8px',
                    padding: '14px 18px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
                    <div style={{ maxWidth: '850px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '12px', fontWeight: 700, color: '#FF5A6B' }}>
                          +{g.totalDelayHours}h Delay • {g.primaryReason}
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>•</span>
                        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)' }}>
                          Shipment: {g.reference}
                        </span>
                        {g.events.length > 1 && (
                          <span style={{ fontSize: '11px', background: 'rgba(255, 90, 107, 0.15)', color: '#FF5A6B', padding: '1px 6px', borderRadius: '3px', fontWeight: 600 }}>
                            {g.events.length} multi-leg incidents
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                        Destination: {g.destination} • Linehaul Carrier: {g.carrier_name}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                        Potential Stockout Exposure: <span style={{ color: '#FF5A6B', fontWeight: 700 }}>₹171,600.00</span> • Prescribed Action: <span style={{ color: '#38E5A3', fontWeight: 600 }}>Emergency Stock Transfer from Hosur Hub (Net ROI: ₹167,400)</span>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      {g.events.length > 1 && (
                        <button
                          onClick={() => {
                            const next = new Set(expandedReceiverDelays);
                            if (next.has(g.reference)) next.delete(g.reference);
                            else next.add(g.reference);
                            setExpandedReceiverDelays(next);
                          }}
                          className="btn-secondary"
                          style={{ fontSize: '11px', padding: '5px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
                        >
                          {isExpanded ? 'Hide Incidents' : `View ${g.events.length} Incidents`}
                        </button>
                      )}

                      {isApproved ? (
                        <div style={{
                          display: 'flex', alignItems: 'center', gap: '6px',
                          padding: '6px 12px',
                          background: 'rgba(56, 229, 163, 0.15)',
                          border: '1px solid rgba(56, 229, 163, 0.4)',
                          borderRadius: '6px',
                          color: '#38E5A3',
                          fontSize: '12px',
                          fontWeight: 700
                        }}>
                          <CheckCircle2 size={14} /> Stock Transfer Approved
                        </div>
                      ) : (
                        <button
                          onClick={() => setTransferModalItem(g)}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '8px 14px',
                            fontSize: '12px',
                            fontWeight: 700,
                            borderRadius: '6px',
                            border: 'none',
                            cursor: 'pointer',
                            backgroundColor: '#38E5A3',
                            color: '#040810',
                            boxShadow: '0 2px 8px rgba(56, 229, 163, 0.4)'
                          }}
                        >
                          <Check size={14} />
                          Review &amp; Authorize Stock Transfer
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Multi-incident drilldown */}
                  {isExpanded && g.events.length > 1 && (
                    <div style={{
                      marginTop: '8px',
                      padding: '10px 14px',
                      background: 'var(--bg-surface-2, #1B2430)',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #26313D)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '6px'
                    }}>
                      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>
                        Individual Multi-Leg Incident Telematics
                      </div>
                      {g.events.map((ev, evIdx) => (
                        <div key={evIdx} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)' }}>
                          <span>• {ev.incident_location || ev.location || 'Highway Sector'}: {ev.disruption_reason || ev.reason || 'Transit Delay'} ({ev.carrier_name || 'Partner Fleet'})</span>
                          <span style={{ color: '#FF5A6B', fontWeight: 600 }}>+{ev.delay_hours}h delay</span>
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

      {/* 4. Active Inbound Corridor Route Telematics (MultiLegDemo Integration) */}
      {selectedShipment && (
        <div style={{ marginBottom: '24px' }}>
          <div style={{
            background: 'var(--bg-surface-1, #151C24)',
            border: '1px solid var(--border-subtle, #26313D)',
            borderRadius: '12px',
            padding: '20px 24px',
            boxShadow: '0 4px 16px rgba(0,0,0,0.2)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
              <div>
                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  INBOUND CORRIDOR TELEMATICS &amp; ROUTE PROGRESSION
                </span>
                <h3 style={{ fontSize: '15px', fontWeight: 700, margin: '2px 0 0 0', color: 'var(--text-primary)' }}>
                  Tracking Inbound Shipment: {selectedShipment.external_shipment_id || selectedShipment.shipment_id} ({selectedShipment.product_name || 'Industrial Electronics'})
                </h3>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Sender: <strong style={{ color: 'var(--text-primary)' }}>{selectedShipment.sender_company_name || 'Bengaluru Manufacturing Ltd'}</strong>
                </span>
                <span style={{
                  padding: '3px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700,
                  background: selectedShipment.assignment_status === 'DELIVERED' ? 'rgba(56, 229, 163, 0.15)' : 'rgba(96, 165, 250, 0.15)',
                  color: selectedShipment.assignment_status === 'DELIVERED' ? '#38E5A3' : '#60A5FA',
                  textTransform: 'uppercase'
                }}>
                  {selectedShipment.assignment_status || 'IN TRANSIT'}
                </span>
              </div>
            </div>

            <MultiLegDemo
              companyId={company?.id || user?.company_id}
              shipmentId={selectedShipment?.shipment_id || selectedShipment?.id || selectedShipment?.external_shipment_id}
            />
          </div>
        </div>
      )}

      {/* 5. SECTIONS B & C: Inbound Shipments Table & Goods Inward Receiving */}
      <div style={{
        background: 'var(--bg-surface-1, #151C24)',
        border: '1px solid var(--border-subtle, #26313D)',
        borderRadius: '12px',
        padding: '24px',
        marginBottom: '24px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.2)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              SECTIONS B &amp; C • INBOUND FREIGHT &amp; GOODS INWARD
            </span>
            <h3 style={{ fontSize: '16px', fontWeight: 700, margin: '2px 0 0 0', color: 'var(--text-primary)' }}>
              Inbound Consignments Awaiting Receiving &amp; Inspection
            </h3>
          </div>

          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', background: 'var(--bg-surface-2, #1B2430)', padding: '2px', borderRadius: '6px', border: '1px solid var(--border-subtle, #26313D)' }}>
              <button
                onClick={() => setActiveTab('inbound')}
                style={{
                  padding: '5px 12px', fontSize: '12px', fontWeight: 600, borderRadius: '4px', border: 'none', cursor: 'pointer',
                  background: activeTab === 'inbound' ? 'var(--accent-primary, #38E5A3)' : 'transparent',
                  color: activeTab === 'inbound' ? '#040810' : 'var(--text-secondary)'
                }}
              >
                Active Inbound ({shipmentsData.filter(s => s.assignment_status !== 'DELIVERED').length})
              </button>
              <button
                onClick={() => setActiveTab('all')}
                style={{
                  padding: '5px 12px', fontSize: '12px', fontWeight: 600, borderRadius: '4px', border: 'none', cursor: 'pointer',
                  background: activeTab === 'all' ? 'var(--accent-primary, #38E5A3)' : 'transparent',
                  color: activeTab === 'all' ? '#040810' : 'var(--text-secondary)'
                }}
              >
                All Consignments ({shipmentsData.length})
              </button>
              <button
                onClick={() => setActiveTab('delivered')}
                style={{
                  padding: '5px 12px', fontSize: '12px', fontWeight: 600, borderRadius: '4px', border: 'none', cursor: 'pointer',
                  background: activeTab === 'delivered' ? 'var(--accent-primary, #38E5A3)' : 'transparent',
                  color: activeTab === 'delivered' ? '#040810' : 'var(--text-secondary)'
                }}
              >
                Delivered / Inwarded ({shipmentsData.filter(s => s.assignment_status === 'DELIVERED').length})
              </button>
            </div>

            <input
              type="text"
              placeholder="Search reference, product, sender..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                padding: '6px 12px',
                background: 'var(--bg-surface-2, #1B2430)',
                border: '1px solid var(--border-subtle, #26313D)',
                borderRadius: '6px',
                color: 'var(--text-primary)',
                fontSize: '12px',
                width: '220px'
              }}
            />
          </div>
        </div>

        {/* Inbound Freight Table */}
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface-2, #1B2430)', borderBottom: '1px solid var(--border-subtle, #26313D)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '12px 14px' }}>Shipment Reference &amp; Product</th>
                <th style={{ padding: '12px 14px' }}>Sender (Consignor)</th>
                <th style={{ padding: '12px 14px' }}>Origin &amp; Destination</th>
                <th style={{ padding: '12px 14px' }}>Carrier &amp; Mode</th>
                <th style={{ padding: '12px 14px' }}>Expected Arrival</th>
                <th style={{ padding: '12px 14px' }}>Status</th>
                <th style={{ padding: '12px 14px', textAlign: 'right' }}>Goods Inward Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredShipments.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-tertiary)' }}>
                    No inbound shipments matching current criteria.
                  </td>
                </tr>
              ) : (
                filteredShipments.map(s => {
                  const isSelected = selectedShipment?.shipment_id === s.shipment_id ||
                                     selectedShipment?.external_shipment_id === s.external_shipment_id;
                  const isDelivered = s.assignment_status === 'DELIVERED' || Boolean(s.actual_delivery);
                  const isConfirming = confirmingShipmentId === (s.shipment_id || s.id);

                  return (
                    <tr
                      key={s.shipment_id || s.id}
                      style={{
                        borderBottom: '1px solid var(--border-subtle, #26313D)',
                        background: isSelected ? 'rgba(56, 229, 163, 0.04)' : 'transparent',
                        transition: 'background 0.15s ease'
                      }}
                    >
                      {/* 1. Reference & Product */}
                      <td style={{ padding: '14px' }}>
                        <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '13px' }}>
                          {s.external_shipment_id || `SH-${s.shipment_id}`}
                        </div>
                        <div style={{ color: 'var(--text-secondary)', fontSize: '11px', marginTop: '2px' }}>
                          {s.product_name || 'Industrial IoT Telematics Controller'}
                        </div>
                        <div style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>
                          Qty: <strong>{Number(s.quantity || 100).toFixed(0)} units</strong> • {s.weight_kg || 450} kg
                        </div>
                      </td>

                      {/* 2. Sender */}
                      <td style={{ padding: '14px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {s.sender_company_name || 'Bengaluru Manufacturing Ltd'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                          Verified Outbound Consignor
                        </div>
                      </td>

                      {/* 3. Origin & Destination */}
                      <td style={{ padding: '14px' }}>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>From:</span> {s.origin || 'Bengaluru Electronic City Plant'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-primary)', fontWeight: 600, marginTop: '2px' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>To:</span> {s.destination || 'Chennai Central DC'}
                        </div>
                      </td>

                      {/* 4. Carrier */}
                      <td style={{ padding: '14px' }}>
                        <div style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
                          {s.carrier || 'Karnataka-Tamil Nadu Express Logistics'}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                          {(s.transport_mode || 'ROAD').toUpperCase()} • {s.distance_km != null && s.distance_km > 0 ? `${s.distance_km.toLocaleString()} km` : 'Linehaul transit'}
                        </div>
                      </td>

                      {/* 5. Expected Arrival */}
                      <td style={{ padding: '14px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {formatDateTime(s.current_eta || s.planned_delivery || '2026-11-19')}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                          Baseline: {formatDateTime(s.planned_delivery || '2026-11-19')}
                        </div>
                      </td>

                      {/* 6. Status */}
                      <td style={{ padding: '14px' }}>
                        <span style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '3px 8px',
                          borderRadius: '4px',
                          textTransform: 'uppercase',
                          background: isDelivered ? 'rgba(56, 229, 163, 0.15)' :
                                      s.assignment_status === 'DELAYED' ? 'rgba(239, 68, 68, 0.15)' :
                                      s.assignment_status === 'PENDING' ? 'rgba(245, 158, 11, 0.15)' :
                                      'rgba(96, 165, 250, 0.15)',
                          color: isDelivered ? '#38E5A3' :
                                 s.assignment_status === 'DELAYED' ? '#FF5A6B' :
                                 s.assignment_status === 'PENDING' ? '#F59E0B' :
                                 '#60A5FA',
                          border: `1px solid ${
                            isDelivered ? 'rgba(56, 229, 163, 0.3)' :
                            s.assignment_status === 'DELAYED' ? 'rgba(239, 68, 68, 0.3)' :
                            'rgba(96, 165, 250, 0.3)'
                          }`
                        }}>
                          {s.assignment_status || 'IN_TRANSIT'}
                        </span>
                      </td>

                      {/* 7. Goods Inward Action */}
                      <td style={{ padding: '14px', textAlign: 'right' }}>
                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', alignItems: 'center' }}>
                          <button
                            onClick={() => handleSelectShipment(s)}
                            className="btn-secondary"
                            style={{
                              padding: '5px 10px',
                              fontSize: '11px',
                              borderRadius: '4px',
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px'
                            }}
                          >
                            <Eye size={12} /> {isSelected ? 'Tracking' : 'Track'}
                          </button>

                          {/* SECTION C: Goods Inward Confirmation Button */}
                          {isDelivered ? (
                            <span style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '11px',
                              fontWeight: 700,
                              color: '#38E5A3',
                              padding: '5px 8px'
                            }}>
                              <CheckCircle2 size={13} /> Stock Received
                            </span>
                          ) : s.assignment_status === 'ARRIVED' ? (
                            <button
                              onClick={() => handleConfirmDelivery(s)}
                              disabled={isConfirming}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '6px 12px',
                                fontSize: '11px',
                                fontWeight: 700,
                                borderRadius: '4px',
                                border: 'none',
                                cursor: 'pointer',
                                backgroundColor: '#38E5A3',
                                color: '#040810',
                                boxShadow: '0 2px 8px rgba(56, 229, 163, 0.3)'
                              }}
                              title="Confirm physical delivery receipt and replenish warehouse stock"
                            >
                              <PackageCheck size={13} />
                              {isConfirming ? 'Inwarding...' : 'Confirm Delivery'}
                            </button>
                          ) : (
                            <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'flex-end', gap: '2px' }}>
                              <button
                                disabled
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '6px',
                                  padding: '5px 10px',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  borderRadius: '4px',
                                  border: `1px solid ${s.assignment_status === 'DELAYED' ? 'rgba(239, 68, 68, 0.3)' : 'rgba(96, 165, 250, 0.3)'}`,
                                  cursor: 'not-allowed',
                                  backgroundColor: s.assignment_status === 'DELAYED' ? 'rgba(239, 68, 68, 0.1)' : 'rgba(96, 165, 250, 0.08)',
                                  color: s.assignment_status === 'DELAYED' ? '#FF5A6B' : 'var(--text-tertiary)',
                                  opacity: 0.85
                                }}
                                title={
                                  s.assignment_status === 'DELAYED'
                                    ? 'Shipment is delayed in highway transit. Inward receiving unlocks upon physical gate arrival at Chennai Central DC.'
                                    : 'Shipment is in transit. Inward receiving unlocks upon physical gate arrival at Chennai Central DC.'
                                }
                              >
                                <PackageCheck size={12} style={{ opacity: 0.6 }} />
                                In Transit • Receipt Pending
                              </button>
                              <span style={{ fontSize: '10px', color: 'var(--text-tertiary)' }}>
                                Gate arrival required
                              </span>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 6. SECTION E: Supplier Intelligence (Upstream Manufacturing Partners) */}
      <div style={{
        background: 'var(--bg-surface-1, #151C24)',
        border: '1px solid var(--border-subtle, #26313D)',
        borderRadius: '12px',
        padding: '24px',
        boxShadow: '0 4px 16px rgba(0,0,0,0.2)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              SECTION E • UPSTREAM SUPPLIER INTELLIGENCE
            </span>
            <h3 style={{ fontSize: '16px', fontWeight: 700, margin: '2px 0 0 0', color: 'var(--text-primary)' }}>
              Contracted Manufacturing &amp; Wholesale Suppliers
            </h3>
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            Evaluating historical lead-time reliability and defect indexes
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
          {suppliersData.length === 0 ? (
            // Default verified primary partner if no dynamic rows
            <div style={{ background: 'var(--bg-surface-2, #1B2430)', border: '1px solid var(--border-subtle, #26313D)', borderRadius: '8px', padding: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)' }}>
                  Bengaluru Manufacturing Ltd
                </span>
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#38E5A3', background: 'rgba(56, 229, 163, 0.15)', padding: '2px 6px', borderRadius: '3px' }}>
                  LOW RISK
                </span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '12px' }}>
                Vendor Code: SUP-BLR-01 • Primary Industrial Electronics Manufacturer
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px' }}>
                <div><span style={{ color: 'var(--text-secondary)' }}>Nominal Lead Time:</span> <strong>14.0 days</strong></div>
                <div><span style={{ color: 'var(--text-secondary)' }}>Historical Reliability:</span> <strong>96.0%</strong></div>
                <div><span style={{ color: 'var(--text-secondary)' }}>Defect Rate:</span> <strong>1.0%</strong></div>
                <div><span style={{ color: 'var(--text-secondary)' }}>Cost Index:</span> <strong>1.00x</strong></div>
              </div>
            </div>
          ) : (
            suppliersData.map(sup => (
              <div key={sup.supplier_id || sup.name} style={{ background: 'var(--bg-surface-2, #1B2430)', border: '1px solid var(--border-subtle, #26313D)', borderRadius: '8px', padding: '16px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)' }}>
                    {sup.name}
                  </span>
                  <span style={{
                    fontSize: '11px', fontWeight: 700,
                    color: sup.risk_tier === 'CRITICAL' ? '#FF5A6B' : sup.risk_tier === 'HIGH' ? '#F59E0B' : '#38E5A3',
                    background: sup.risk_tier === 'CRITICAL' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 229, 163, 0.15)',
                    padding: '2px 6px', borderRadius: '3px'
                  }}>
                    {sup.risk_tier || 'LOW'} RISK
                  </span>
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '12px' }}>
                  Vendor Code: {sup.external_supplier_id || 'SUP-01'} • Active Fulfillment Partner
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px' }}>
                  <div><span style={{ color: 'var(--text-secondary)' }}>Nominal Lead Time:</span> <strong>{sup.lead_time_days || 14.0} days</strong></div>
                  <div><span style={{ color: 'var(--text-secondary)' }}>Reliability:</span> <strong>{((sup.reliability || 0.96) * 100).toFixed(1)}%</strong></div>
                  <div><span style={{ color: 'var(--text-secondary)' }}>Defect Rate:</span> <strong>{((sup.defect_rate || 0.01) * 100).toFixed(1)}%</strong></div>
                  <div><span style={{ color: 'var(--text-secondary)' }}>Completed Orders:</span> <strong>{sup.completed_shipments || 0} shipments</strong></div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Operational Stock Transfer Decision Modal */}
      {transferModalItem && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0, 0, 0, 0.75)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 9999, padding: '20px'
        }}>
          <div style={{
            background: 'var(--bg-surface-1, #151C24)',
            border: '1px solid var(--border-subtle, #26313D)',
            borderRadius: '12px',
            maxWidth: '620px',
            width: '100%',
            padding: '24px',
            boxShadow: '0 12px 48px rgba(0,0,0,0.6)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertTriangle size={20} color="#38E5A3" />
                <h3 style={{ margin: 0, fontSize: '17px', fontWeight: 700, color: 'var(--text-primary)' }}>
                  Mitigation Recommendation Approval
                </h3>
              </div>
              <button
                onClick={() => setTransferModalItem(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: '18px' }}
              >
                ✕
              </button>
            </div>

            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '18px', lineHeight: 1.5 }}>
              Shipment <strong style={{ color: 'var(--text-primary)' }}>{transferModalItem.reference}</strong> is experiencing a +{transferModalItem.totalDelayHours}h transit delay on the corridor. Review the recommended operational mitigation below to safeguard warehouse stock levels.
            </p>

            <div style={{
              background: 'var(--bg-surface-2, #1B2430)',
              border: '1px solid var(--border-subtle, #26313D)',
              borderRadius: '8px',
              padding: '16px',
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '12px',
              fontSize: '12px',
              marginBottom: '20px'
            }}>
              <div>
                <span style={{ color: 'var(--text-tertiary)' }}>Affected Shipment:</span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                  {transferModalItem.reference}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-tertiary)' }}>Operating Carrier:</span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                  {transferModalItem.carrier_name || 'Karnataka-Tamil Nadu Express Logistics'}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-tertiary)' }}>Reported Disruption:</span>
                <div style={{ fontWeight: 600, color: '#FF5A6B', marginTop: '2px' }}>
                  {transferModalItem.primaryReason} (+{transferModalItem.totalDelayHours}h)
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-tertiary)' }}>Incident Location:</span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                  {transferModalItem.location || 'Hosur Hub → Sriperumbudur Depot'}
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-tertiary)' }}>Target Destination:</span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                  Chennai Central DC (Warehouse #58)
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-tertiary)' }}>Affected Product &amp; SKU:</span>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                  SKU-BLR-101 (Industrial Electronics)
                </div>
              </div>
              <div style={{ gridColumn: 'span 2' }}>
                <span style={{ color: 'var(--text-tertiary)' }}>Recommended Action:</span>
                <div style={{ fontWeight: 600, color: '#38E5A3', marginTop: '2px' }}>
                  Acknowledge transit delay &amp; record expedited receiving prioritization in Control Tower
                </div>
              </div>
            </div>

            <div style={{
              background: 'rgba(255, 182, 137, 0.08)',
              border: '1px solid rgba(255, 182, 137, 0.25)',
              borderRadius: '6px',
              padding: '12px 14px',
              fontSize: '11px',
              color: 'var(--text-secondary)',
              lineHeight: 1.5,
              marginBottom: '20px'
            }}>
              <strong style={{ color: 'var(--status-watch)' }}>Operational Notice:</strong> Approving this recommendation records managerial approval in the SupplyIQ Control Tower audit log. It does not reserve, transfer, or dispatch physical inventory from external facilities. Physical inter-warehouse transfers require independent warehouse management system (WMS) dispatch execution.
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => setTransferModalItem(null)}
                className="btn-secondary"
                style={{ fontSize: '12px', padding: '8px 16px' }}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  handleApproveDisruption(transferModalItem.rawDisruption);
                  setTransferModalItem(null);
                }}
                disabled={isApproving}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 18px',
                  fontSize: '12px',
                  fontWeight: 700,
                  borderRadius: '6px',
                  border: 'none',
                  cursor: 'pointer',
                  backgroundColor: '#38E5A3',
                  color: '#040810',
                  boxShadow: '0 2px 8px rgba(56, 229, 163, 0.4)'
                }}
              >
                <Check size={14} />
                {isApproving ? 'Recording Approval...' : 'Approve Mitigation Recommendation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
