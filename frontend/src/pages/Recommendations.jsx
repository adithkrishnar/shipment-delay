import React, { useEffect, useState } from 'react';
import { getRecommendations, approveAction } from '../services/api';
import Loader from '../components/Loader';
import {
  AlertTriangle, ArrowRight, CheckCircle2, ShieldAlert,
  ArrowRightLeft, Package, Clock, Filter, Sparkles, X, ChevronRight, Check
} from 'lucide-react';

export default function Recommendations({ company }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filterPriority, setFilterPriority] = useState('ALL');
  const [selectedRec, setSelectedRec] = useState(null);
  const [approvingRec, setApprovingRec] = useState(null);
  const [approvedIds, setApprovedIds] = useState(new Set());
  const [submittingApproval, setSubmittingApproval] = useState(false);
  const [approvalError, setApprovalError] = useState(null);

  const fetchRecs = () => {
    if (!company?.id) return;
    setLoading(true);
    getRecommendations(company.id)
      .then(res => {
        setData(res);
        const initialApproved = new Set(res.approved_action_ids || []);
        if (res.recommendations) {
          res.recommendations.forEach(r => {
            if (r.is_approved) {
              if (r.target_id) initialApproved.add(r.target_id);
              if (r.sku) initialApproved.add(r.sku);
            }
          });
        }
        setApprovedIds(initialApproved);
        setError(null);
      })
      .catch(e => setError(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchRecs();
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
    try {
      await approveAction(company.id, {
        action_id: actionId,
        action_type: rec.action_type || 'RECOMMENDATION_APPROVAL',
        title: rec.title,
        notes: `Authorized via Action Center for ${rec.product_name || rec.sku}`,
      });
      setApprovedIds(prev => {
        const next = new Set(prev);
        if (actionId) next.add(actionId);
        if (rec.sku) next.add(rec.sku);
        if (rec.target_id) next.add(rec.target_id);
        return next;
      });
      setApprovingRec(null);
    } catch (err) {
      setApprovalError(err.response?.data?.detail || err.message);
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
            Prioritized inventory actions, replenishment authorizations, and stock rebalancing recommendations.
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
          <div className="kpi-sub">Decision opportunities identified</div>
        </div>

        <div className={`sim-kpi-card ${criticalCount > 0 ? 'critical' : 'healthy'}`}>
          <div className="kpi-label">Critical Shortage Actions</div>
          <div className="kpi-value" style={{ color: criticalCount > 0 ? 'var(--status-critical)' : 'var(--status-healthy)' }}>
            {criticalCount}
          </div>
          <div className="kpi-sub">Imminent stockout exposure</div>
        </div>

        <div className="sim-kpi-card">
          <div className="kpi-label">Actions Approved</div>
          <div className="kpi-value" style={{ color: 'var(--status-healthy)' }}>
            {approvedIds.size}
          </div>
          <div className="kpi-sub">Audited and authorized</div>
        </div>
      </div>

      {/* Action Recommendation Cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {filteredRecs.length === 0 ? (
          <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '64px 24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <CheckCircle2 size={36} color="var(--status-healthy)" style={{ margin: '0 auto 12px' }} />
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 6px 0' }}>
              No Pending Recommendations
            </h3>
            <p style={{ fontSize: '13px', margin: 0 }}>
              All inventory levels and warehouse distributions conform to target safety stock policies.
            </p>
          </div>
        ) : (
          filteredRecs.map((rec, i) => {
            const isApproved = approvedIds.has(rec.sku || rec.target_id);
            const isCritical = rec.priority === 'CRITICAL';
            const isHigh = rec.priority === 'HIGH';

            return (
              <div
                key={i}
                style={{
                  background: 'var(--bg-surface-1)',
                  border: `1px solid ${isApproved ? 'var(--status-healthy-border)' : isCritical ? 'rgba(255, 77, 95, 0.35)' : 'var(--border-default)'}`,
                  borderRadius: 'var(--r-lg)',
                  padding: '24px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '24px',
                  flexWrap: 'wrap',
                  transition: 'border-color 0.15s ease',
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
                      {rec.action}
                    </span>

                    <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
                      Target: <strong style={{ color: 'var(--text-primary)' }}>{rec.target_id}</strong> • Facility: <strong style={{ color: 'var(--text-secondary)' }}>{rec.warehouse}</strong>
                    </span>
                  </div>

                  {/* Title & Reason */}
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', margin: '0 0 6px 0' }}>
                    {rec.title}
                  </h3>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, margin: '0 0 14px 0' }}>
                    {rec.reason}
                  </p>

                  {/* Supporting Data Chips */}
                  {rec.supporting_data && (
                    <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '11px' }}>
                      {rec.supporting_data.on_hand !== undefined && (
                        <div style={{ background: 'var(--bg-surface-2)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>On-Hand:</span> <strong>{rec.supporting_data.on_hand}</strong> units
                        </div>
                      )}
                      {rec.supporting_data.daily_demand !== undefined && (
                        <div style={{ background: 'var(--bg-surface-2)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>Daily Demand:</span> <strong>{rec.supporting_data.daily_demand}</strong> /day
                        </div>
                      )}
                      {rec.supporting_data.safety_stock !== undefined && (
                        <div style={{ background: 'var(--bg-surface-2)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>Safety Threshold:</span> <strong>{rec.supporting_data.safety_stock}</strong> units
                        </div>
                      )}
                      {rec.supporting_data.coverage_days !== undefined && (
                        <div style={{ background: 'var(--bg-surface-2)', padding: '4px 10px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                          <span style={{ color: 'var(--text-tertiary)' }}>Coverage:</span> <strong style={{ color: rec.supporting_data.coverage_days < 7 ? 'var(--status-critical)' : 'inherit' }}>{rec.supporting_data.coverage_days}</strong> days
                        </div>
                      )}
                    </div>
                  )}

                  {/* Expected Impact */}
                  <div style={{ marginTop: '10px', fontSize: '12px', color: 'var(--status-healthy)', fontWeight: 500 }}>
                    💡 Expected Outcome: {rec.expected_impact}
                  </div>
                </div>

                {/* Workflow Buttons */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '180px' }}>
                  <button
                    className="btn-secondary"
                    onClick={() => setSelectedRec(rec)}
                    style={{ fontSize: '12px', padding: '8px 14px', width: '100%', textAlign: 'center' }}
                  >
                    Review Calculation
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
                Decision Logic & Mathematical Audit
              </h3>
              <button onClick={() => setSelectedRec(null)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ background: 'var(--bg-surface-2)', padding: '16px', borderRadius: 'var(--r-md)', marginBottom: '20px', fontSize: '13px' }}>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>{selectedRec.title}</div>
              <div style={{ color: 'var(--text-secondary)' }}>Target SKU: {selectedRec.sku} ({selectedRec.warehouse})</div>
            </div>

            <div style={{ fontSize: '13px', lineHeight: 1.6, color: 'var(--text-secondary)', marginBottom: '20px' }}>
              <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>Applied Mathematical Formulation:</div>
              <ul style={{ margin: 0, paddingLeft: '20px' }}>
                <li><strong>Reorder Point (ROP):</strong> <code>ROP = (Daily Demand × Lead Time) + Safety Stock</code></li>
                <li><strong>Safety Stock:</strong> <code>SS = Z × √((Lead Time × σ_d²) + (Demand² × σ_LT²))</code> (Service Level 95%, Z=1.65)</li>
                <li><strong>Order Multiples:</strong> Adjusted for Minimum Order Quantity (MOQ = 25 units)</li>
              </ul>
            </div>

            {selectedRec.supporting_data && (
              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px', marginBottom: '20px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Input Parameters
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '12px' }}>
                  {Object.entries(selectedRec.supporting_data).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', background: 'var(--bg-surface-2)', padding: '6px 10px', borderRadius: '4px' }}>
                      <span style={{ color: 'var(--text-tertiary)', textTransform: 'capitalize' }}>{k.replace('_', ' ')}:</span>
                      <strong style={{ color: 'var(--text-primary)' }}>{typeof v === 'number' ? v.toLocaleString() : v}</strong>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn-primary" onClick={() => setSelectedRec(null)}>
                Close Audit View
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
                Authorize Operational Action
              </h3>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5, marginBottom: '20px' }}>
              Confirm authorization of <strong>{approvingRec.action}</strong> for SKU <strong>{approvingRec.sku}</strong> at <strong>{approvingRec.warehouse}</strong>. This logs the action in the tenant audit register.
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
                {submittingApproval ? 'Authorizing...' : 'Confirm & Authorize'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
