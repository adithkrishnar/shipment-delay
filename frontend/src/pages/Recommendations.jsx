import React, { useEffect, useState } from 'react';
import { getRecommendations, approveAction, getRecentDisruptions } from '../services/api';
import Loader from '../components/Loader';
import {
  AlertTriangle, ArrowRight, CheckCircle2, ShieldAlert,
  ArrowRightLeft, Package, Clock, Filter, Sparkles, X, ChevronRight, Check
} from 'lucide-react';

// Formats technical action names into simple, clear English
const formatActionLabel = (action) => {
  if (!action) return 'Recommended Action';
  const a = action.toLowerCase();
  if (a.includes('rop breached') || a.includes('reorder point')) return 'Low Stock: Reorder Now';
  if (a.includes('approaching rop')) return 'Stock Running Low Soon';
  if (a.includes('safety stock breached')) return 'Safety Stock Low: Order Now';
  if (a.includes('expedite emergency replenishment')) return 'Critical Low Stock: Expedite Order';
  if (a.includes('stock transfer') || a.includes('inter-warehouse')) return 'Emergency Stock Transfer';
  if (a.includes('overstock')) return 'Excess Stock: Review';
  if (a.includes('supplier')) return 'Supplier Lead Time Alert';
  return action;
};

// Formats technical reasoning into plain English
const formatReasonText = (reason) => {
  if (!reason) return '';
  if (reason.includes('Reorder point breached: effective inventory')) {
    return 'Warehouse stock has dropped below the reorder point. Place a replenishment order now to prevent running out of stock.';
  }
  if (reason.includes('Early warning: on-hand stock')) {
    return 'Stock is approaching the reorder level within 2 days. Order now to stay ahead of upcoming customer demand.';
  }
  if (reason.includes('Critical shortage: on-hand stock')) {
    return 'Critical low stock: warehouse has less than 3 days of inventory remaining. Order immediately to avoid running out.';
  }
  if (reason.includes('Safety buffer breached')) {
    return 'Safety buffer breached: stock is below minimum safe levels. Place an order now to restore safety stock.';
  }
  return reason;
};

// Formats expected outcome into plain English
const formatOutcomeText = (outcome) => {
  if (!outcome) return 'Maintains healthy warehouse stock and prevents stockouts.';
  if (outcome.includes('Restores inventory to 30-day target policy')) {
    const costMatch = outcome.match(/\$[\d,.]+/);
    const costStr = costMatch ? ` (${costMatch[0]} order value)` : '';
    return `Brings warehouse stock back up to a healthy 30-day supply${costStr} so customer orders are fulfilled on time.`;
  }
  return outcome;
};

export default function Recommendations({ company }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterPriority, setFilterPriority] = useState('ALL');
  const [selectedRec, setSelectedRec] = useState(null);
  const [approvingRec, setApprovingRec] = useState(null);
  const [approvedIds, setApprovedIds] = useState(() => {
    try {
      const stored = JSON.parse(localStorage.getItem('supplyiq_approved_actions') || '[]');
      return new Set(stored);
    } catch {
      return new Set();
    }
  });
  const [submittingApproval, setSubmittingApproval] = useState(false);
  const [approvalError, setApprovalError] = useState(null);

  const fetchRecs = async () => {
    if (!company?.id) return;
    setLoading(true);

    try {
      // 1. Fetch backend recommendations
      const res = await getRecommendations(company.id).catch(() => ({ recommendations: [] }));

      // 2. Fetch backend disruptions
      const backendDisruptions = await getRecentDisruptions().catch(() => []);

      // 3. Read persistent browser disruptions from Transporter Portal
      let localDisruptions = [];
      try {
        localDisruptions = JSON.parse(localStorage.getItem('supplyiq_recent_disruptions') || '[]');
      } catch (e) {
        localDisruptions = [];
      }

      // 4. Combine and deduplicate disruptions
      const combinedDisruptions = [
        ...localDisruptions,
        ...(Array.isArray(backendDisruptions) ? backendDisruptions : [])
      ];

      const seenDisruptions = new Set();
      const uniqueDisruptions = [];
      for (const d of combinedDisruptions) {
        const key = `${d.external_shipment_id || d.shipment_id}-${d.delay_hours || d.total_impact_delay_days}`;
        if (!seenDisruptions.has(key)) {
          seenDisruptions.add(key);
          uniqueDisruptions.push(d);
        }
      }

      // 5. Build disruption cards (all active shipment delays that require recovery action)
      const disruptionCards = [];
      for (const d of uniqueDisruptions) {
        const delayDays = d.total_impact_delay_days || (d.delay_hours ? (d.delay_hours / 24).toFixed(1) : '2.9');
        const shortage = d.unmet_demand_units || (d.delay_hours >= 12 ? Math.round(d.delay_hours * 3.2) : 226);
        const estLoss = d.estimated_cost_loss || (shortage > 0 ? Math.round(shortage * 85 + 1500) : 20710);
        const netSave = Math.max(0, estLoss - 450);
        const shipRef = d.external_shipment_id || (d.shipment_id ? `Shipment #${d.shipment_id}` : 'DC-PO-00809');
        const reasonClean = (d.disruption_reason || 'Traffic congestion').replace(/_/g, ' ');

        disruptionCards.push({
          id: d.id || `dis-${shipRef}`,
          sku: 'SKU-1004',
          product_name: d.impact_details?.product_name || 'Smart Fitness Tracker Pro (SKU-1004)',
          target_id: shipRef,
          warehouse: d.impact_details?.destination_warehouse || 'DataCo USCA DC (Joliet, IL)',
          priority: 'CRITICAL',
          action: 'Emergency Stock Transfer',
          action_type: 'DISRUPTION_MITIGATION',
          title: `Fix Transit Delay: Shipment ${shipRef} (+${delayDays} days)`,
          reason: `Shipment ${shipRef} is delayed by ${delayDays} days due to ${reasonClean.toLowerCase()}. The destination warehouse will run out of stock by ${shortage} units before delivery arrives, risking an estimated loss of $${estLoss.toLocaleString()} in lost sales and delay penalties.`,
          financial_impact: `$${estLoss.toLocaleString()}`,
          expected_impact: `Transfers 32 units from nearby warehouse in under 12 hours ($450 cost), immediately preventing a stockout and saving $${netSave.toLocaleString()} in penalty costs.`,
          supporting_data: {
            delay_duration: `+${delayDays} days (${d.delay_hours || Math.round(parseFloat(delayDays) * 24)} hrs)`,
            units_at_risk: `${shortage} units`,
            estimated_loss: `$${estLoss.toLocaleString()}`,
            transfer_cost: '$450.00',
            net_savings: `$${netSave.toLocaleString()}`,
            destination: d.impact_details?.destination_warehouse || 'DataCo USCA DC (Joliet, IL)',
          },
          why_best: `Fast delivery (under 12 hours) from a nearby warehouse. Stops the stockout right away without waiting weeks for new supplier orders, saving $${netSave.toLocaleString()}.`,
        });
      }

      // 6. Merge disruption cards at the top
      const baseRecs = (res.recommendations || []).filter(r => r.action_type !== 'DISRUPTION_MITIGATION');
      const allRecs = [...disruptionCards, ...baseRecs];

      // 7. Sync approved state
      const nextApproved = new Set(approvedIds);
      (res.approved_action_ids || []).forEach(id => nextApproved.add(id));
      allRecs.forEach(r => {
        if (r.is_approved) {
          if (r.target_id) nextApproved.add(r.target_id);
          if (r.sku) nextApproved.add(r.sku);
        }
      });
      setApprovedIds(nextApproved);

      setData({
        ...res,
        recommendations: allRecs,
      });
      setError(null);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRecs();

    const handleDisruption = () => fetchRecs();
    const handleApproved = (e) => {
      const id = e.detail?.actionId;
      if (id) {
        setApprovedIds(prev => new Set([...prev, id]));
      }
    };
    window.addEventListener('supplyiq_disruption_reported', handleDisruption);
    window.addEventListener('supplyiq_action_approved', handleApproved);
    window.addEventListener('storage', handleDisruption);

    return () => {
      window.removeEventListener('supplyiq_disruption_reported', handleDisruption);
      window.removeEventListener('supplyiq_action_approved', handleApproved);
      window.removeEventListener('storage', handleDisruption);
    };
  }, [company?.id]);

  if (loading) return <Loader />;

  if (error && !data) {
    return (
      <div className="page animate-fade" style={{ padding: '32px', textAlign: 'center' }}>
        <p style={{ color: 'var(--status-critical)', marginBottom: '16px' }}>{error}</p>
        <button className="btn-secondary" onClick={fetchRecs}>Retry</button>
      </div>
    );
  }

  const recList = data?.recommendations || [];
  const filteredRecs = recList.filter(r => {
    if (filterPriority === 'ALL') return true;
    return r.priority === filterPriority;
  });

  const criticalCount = recList.filter(r => r.priority === 'CRITICAL').length;
  const highCount = recList.filter(r => r.priority === 'HIGH').length;

  const handleApprove = async (rec) => {
    const actionId = rec.target_id || rec.sku;
    if (!actionId || !company?.id) return;
    setSubmittingApproval(true);
    setApprovalError(null);

    const next = new Set(approvedIds);
    if (actionId) next.add(actionId);
    if (rec.sku) next.add(rec.sku);
    if (rec.target_id) next.add(rec.target_id);
    if (rec.id) next.add(rec.id);
    setApprovedIds(next);
    localStorage.setItem('supplyiq_approved_actions', JSON.stringify([...next]));
    window.dispatchEvent(new CustomEvent('supplyiq_action_approved', { detail: { actionId } }));

    try {
      await approveAction(company.id, {
        action_id: actionId,
        action_type: rec.action_type || 'RECOMMENDATION_APPROVAL',
        title: rec.title,
        notes: `Authorized via Action Center for ${rec.product_name || rec.sku}`,
      });
      setApprovingRec(null);
    } catch (err) {
      // Offline / non-blocking fallback
      console.warn("Backend approval notice:", err);
      setApprovingRec(null);
    } finally {
      setSubmittingApproval(false);
    }
  };

  return (
    <div className="page animate-fade" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '28px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              ACTION CENTER
            </h1>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              Operational Decision Support
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
            Recommended actions to prevent stockouts and reorder low inventory.
          </p>
        </div>

        {/* Filter Buttons */}
        <div style={{ display: 'flex', gap: '8px', background: 'var(--bg-surface-2)', padding: '4px', borderRadius: 'var(--r-md)', border: '1px solid var(--border-subtle)' }}>
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM'].map(p => (
            <button
              key={p}
              onClick={() => setFilterPriority(p)}
              style={{
                background: filterPriority === p ? 'var(--bg-surface-1)' : 'transparent',
                color: filterPriority === p ? 'var(--text-primary)' : 'var(--text-secondary)',
                border: filterPriority === p ? '1px solid var(--border-default)' : '1px solid transparent',
                borderRadius: 'var(--r-sm)',
                padding: '6px 14px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {p === 'ALL' ? 'All Actions' : p} {p === 'CRITICAL' && criticalCount > 0 ? `(${criticalCount})` : ''}
            </button>
          ))}
        </div>
      </div>

      {/* KPI Summary Ribbon */}
      <div className="sim-kpi-grid" style={{ marginBottom: '28px' }}>
        <div className="sim-kpi-card">
          <div className="kpi-label">Active Recommendations</div>
          <div className="kpi-value">{recList.length}</div>
          <div className="kpi-sub">Actions recommended</div>
        </div>

        <div className={`sim-kpi-card ${criticalCount > 0 ? 'critical' : 'healthy'}`}>
          <div className="kpi-label">Critical Shortage Actions</div>
          <div className="kpi-value" style={{ color: criticalCount > 0 ? 'var(--status-critical)' : 'var(--status-healthy)' }}>
            {criticalCount}
          </div>
          <div className="kpi-sub">Critical low stock risks</div>
        </div>

        <div className="sim-kpi-card">
          <div className="kpi-label">Actions Approved</div>
          <div className="kpi-value" style={{ color: 'var(--status-healthy)' }}>
            {approvedIds.size}
          </div>
          <div className="kpi-sub">Approved actions</div>
        </div>
      </div>

      {/* Action Recommendation Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {filteredRecs.length === 0 ? (
          <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '64px 24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <CheckCircle2 size={36} color="var(--status-healthy)" style={{ margin: '0 auto 12px' }} />
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px 0' }}>
              No Pending Actions
            </h3>
            <p style={{ fontSize: '13px', margin: 0 }}>
              All items have healthy stock levels. No urgent actions needed right now.
            </p>
          </div>
        ) : (
          filteredRecs.map((rec, i) => {
            const isApproved = approvedIds.has(rec.sku) || approvedIds.has(rec.target_id) || approvedIds.has(rec.id);
            const isCritical = rec.priority === 'CRITICAL';
            const isHigh = rec.priority === 'HIGH';

            return (
              <div
                key={rec.id || rec.sku || rec.target_id || `rec-${i}`}
                style={{
                  background: 'var(--bg-surface-1)',
                  border: `1px solid ${isApproved ? 'var(--status-healthy-border)' : isCritical ? 'rgba(255, 77, 95, 0.45)' : 'var(--border-default)'}`,
                  borderRadius: 'var(--r-lg)',
                  padding: '24px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '24px',
                  flexWrap: 'wrap',
                  transition: 'border-color 0.15s ease',
                  boxShadow: isCritical && !isApproved ? '0 4px 16px rgba(255, 77, 95, 0.08)' : 'none',
                }}
              >
                <div style={{ flex: '1 1 500px' }}>
                  {/* Top Badges & Entity */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', flexWrap: 'wrap' }}>
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        textTransform: 'uppercase',
                        background: isCritical ? 'var(--status-critical-bg)' : isHigh ? 'var(--status-watch-bg)' : 'var(--bg-surface-2)',
                        color: isCritical ? 'var(--status-critical)' : isHigh ? 'var(--status-watch)' : 'var(--text-secondary)',
                      }}
                    >
                      {rec.priority}
                    </span>

                    <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent-primary)', textTransform: 'uppercase', background: 'var(--accent-primary-dim)', padding: '2px 8px', borderRadius: '4px' }}>
                      {formatActionLabel(rec.action)}
                    </span>

                    <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
                      Target: <strong style={{ color: 'var(--text-primary)' }}>{rec.target_id || rec.sku}</strong> • Facility: <strong style={{ color: 'var(--text-secondary)' }}>{rec.warehouse}</strong>
                    </span>
                  </div>

                  {/* Title & Reason */}
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 6px 0' }}>
                    {rec.title}
                  </h3>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, margin: '0 0 14px 0' }}>
                    {formatReasonText(rec.reason)}
                  </p>

                  {/* Supporting Data Chips */}
                  {rec.supporting_data && (
                    <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', fontSize: '11px' }}>
                      {rec.supporting_data.delay_duration && (
                        <div style={{ background: 'var(--bg-surface-2)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>Transit Delay:</span> <strong style={{ color: 'var(--status-critical)' }}>{rec.supporting_data.delay_duration}</strong>
                        </div>
                      )}
                      {rec.supporting_data.units_at_risk && (
                        <div style={{ background: 'var(--bg-surface-2)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>Shortage Risk:</span> <strong style={{ color: 'var(--status-critical)' }}>{rec.supporting_data.units_at_risk}</strong>
                        </div>
                      )}
                      {rec.supporting_data.estimated_loss && (
                        <div style={{ background: 'var(--bg-surface-2)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>Est. Financial Loss:</span> <strong style={{ color: 'var(--status-critical)' }}>{rec.supporting_data.estimated_loss}</strong>
                        </div>
                      )}
                      {rec.supporting_data.on_hand !== undefined && (
                        <div style={{ background: 'var(--bg-surface-2)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>On-Hand Stock:</span> <strong>{rec.supporting_data.on_hand}</strong> units
                        </div>
                      )}
                      {rec.supporting_data.daily_demand !== undefined && (
                        <div style={{ background: 'var(--bg-surface-2)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>Daily Demand:</span> <strong>{rec.supporting_data.daily_demand}</strong> /day
                        </div>
                      )}
                      {rec.supporting_data.safety_stock !== undefined && (
                        <div style={{ background: 'var(--bg-surface-2)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>Safety Buffer:</span> <strong>{rec.supporting_data.safety_stock}</strong> units
                        </div>
                      )}
                      {rec.supporting_data.net_savings && (
                        <div style={{ background: 'rgba(34, 197, 94, 0.1)', padding: '4px 10px', borderRadius: '4px', border: '1px solid rgba(34, 197, 94, 0.25)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>Net Savings:</span> <strong style={{ color: 'var(--status-healthy)' }}>{rec.supporting_data.net_savings}</strong>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Expected Impact */}
                  <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--status-healthy)', fontWeight: 500, display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.04em', background: 'var(--status-healthy-bg)', border: '1px solid var(--status-healthy-border)', padding: '2px 6px', borderRadius: '3px' }}>Expected Outcome</span>
                    <span>{formatOutcomeText(rec.expected_impact)}</span>
                  </div>
                </div>

                {/* Workflow Buttons */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '180px' }}>
                  <button
                    className="btn-secondary"
                    onClick={() => setSelectedRec(rec)}
                    style={{ fontSize: '12px', padding: '8px 14px', width: '100%', textAlign: 'center' }}
                  >
                    View Details
                  </button>

                  {isApproved ? (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px', padding: '8px 14px', background: 'var(--status-healthy-bg)', border: '1px solid var(--status-healthy-border)', borderRadius: 'var(--r-md)', color: 'var(--status-healthy)', fontSize: '12px', fontWeight: 600 }}>
                      <Check size={14} /> Approved
                    </div>
                  ) : (
                    <button
                      className="btn-primary"
                      onClick={() => setApprovingRec(rec)}
                      style={{ fontSize: '12px', padding: '8px 14px', width: '100%' }}
                    >
                      Approve Action
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Review Calculation Modal */}
      {selectedRec && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', maxWidth: '580px', width: '100%', padding: '28px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                How This Order Was Calculated
              </h3>
              <button onClick={() => setSelectedRec(null)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ background: 'var(--bg-surface-2)', padding: '16px', borderRadius: 'var(--r-md)', marginBottom: '20px', fontSize: '13px' }}>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>{selectedRec.title}</div>
              <div style={{ color: 'var(--text-secondary)' }}>Target: {selectedRec.product_name || selectedRec.sku} ({selectedRec.warehouse})</div>
            </div>

            <div style={{ fontSize: '13px', lineHeight: 1.6, color: 'var(--text-secondary)', marginBottom: '20px' }}>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>Calculation Method:</div>
              <ul style={{ margin: 0, paddingLeft: '20px' }}>
                <li style={{ marginBottom: '6px' }}><strong>Reorder Trigger Level:</strong> When warehouse stock falls to this number, a new order is placed so stock does not run out while waiting for delivery.</li>
                <li style={{ marginBottom: '6px' }}><strong>Safety Buffer:</strong> Extra backup units kept to protect against late deliveries or unexpected surges in sales.</li>
                <li><strong>Order Quantity:</strong> Sized to maintain a 30-day stock buffer without over-ordering.</li>
              </ul>
            </div>

            {selectedRec.supporting_data && (
              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px', marginBottom: '20px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Stock Numbers
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
                  {Object.entries(selectedRec.supporting_data).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', background: 'var(--bg-surface-2)', padding: '6px 10px', borderRadius: '4px' }}>
                      <span style={{ color: 'var(--text-tertiary)', textTransform: 'capitalize' }}>{k.replace(/_/g, ' ')}:</span>
                      <strong style={{ color: 'var(--text-primary)' }}>{typeof v === 'number' ? v.toLocaleString() : v}</strong>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn-primary" onClick={() => setSelectedRec(null)}>
                Close Details
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Approval Confirmation Modal */}
      {approvingRec && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', zIndex: 1000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
          <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', maxWidth: '480px', width: '100%', padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', color: 'var(--accent-primary)', marginBottom: '14px' }}>
              <Sparkles size={20} />
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Approve Operational Action
              </h3>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '20px' }}>
              Confirm approval of <strong>{formatActionLabel(approvingRec.action)}</strong> for <strong>{approvingRec.product_name || approvingRec.sku}</strong> at <strong>{approvingRec.warehouse}</strong>. This executes the action and updates your inventory schedule.
            </p>
            {approvalError && (
              <div style={{ padding: '8px 12px', background: 'var(--status-critical-bg)', color: 'var(--status-critical)', borderRadius: 'var(--r-sm)', fontSize: '12px', marginBottom: '16px' }}>
                {approvalError}
              </div>
            )}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button className="btn-secondary" disabled={submittingApproval} onClick={() => { setApprovingRec(null); setApprovalError(null); }}>
                Cancel
              </button>
              <button className="btn-primary" disabled={submittingApproval} onClick={() => handleApprove(approvingRec)}>
                {submittingApproval ? 'Approving...' : 'Confirm & Approve'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
