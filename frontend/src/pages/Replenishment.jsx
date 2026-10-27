import React, { useState, useEffect } from 'react';
import {
  RefreshCw, ArrowRightLeft, ShieldAlert, CheckCircle2,
  DollarSign, PackageCheck, AlertTriangle
} from 'lucide-react';
import { getReplenishmentPlan, getWarehouseTransfers, executeWarehouseTransfer } from '../services/api';

export default function Replenishment({ company }) {
  const [serviceLevel, setServiceLevel] = useState(0.95);
  const [horizonDays, setHorizonDays] = useState(30);
  const [plan, setPlan] = useState(null);
  const [transfers, setTransfers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [transferSuccess, setTransferSuccess] = useState(null);
  const [transferError, setTransferError] = useState(null);
  const [executingTransfer, setExecutingTransfer] = useState(false);

  const loadData = () => {
    if (!company?.id) return;
    setLoading(true);
    Promise.all([
      getReplenishmentPlan(company.id, serviceLevel, horizonDays),
      getWarehouseTransfers(company.id),
    ])
      .then(([planData, transferData]) => {
        setPlan(planData);
        setTransfers(transferData || []);
        setError(null);
      })
      .catch(err => setError(err.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, [company?.id, serviceLevel, horizonDays]);

  const handleExecuteTransfer = async (transfer) => {
    if (!company?.id) return;
    setExecutingTransfer(true);
    setTransferError(null);
    try {
      const res = await executeWarehouseTransfer({
        company_id: company.id,
        product_id: transfer.product_id,
        sku: transfer.sku,
        source_warehouse_id: transfer.source_warehouse_id,
        destination_warehouse_id: transfer.destination_warehouse_id,
        quantity: transfer.transfer_units,
        notes: 'Executed via Replenishment Dashboard',
      });
      setTransferSuccess(
        `Successfully transferred ${res.quantity} units of ${res.sku} from ${res.source_warehouse} ` +
        `(remaining: ${res.source_stock_after}) to ${res.destination_warehouse} (new balance: ${res.destination_stock_after}).`
      );
      // Reload inventory views to reflect updated physical stock levels
      Promise.all([
        getReplenishmentPlan(company.id, serviceLevel, horizonDays),
        getWarehouseTransfers(company.id),
      ]).then(([planData, transferData]) => {
        setPlan(planData);
        setTransfers(transferData || []);
      });
      setTimeout(() => setTransferSuccess(null), 8000);
    } catch (err) {
      setTransferError(err.response?.data?.detail || err.message);
    } finally {
      setExecutingTransfer(false);
    }
  };

  if (loading) {
    return (
      <div className="page" style={{ padding: '32px' }}>
        <div className="skeleton" style={{ height: '40px', width: '300px', marginBottom: '24px' }} />
        <div className="skeleton" style={{ height: '350px', width: '100%' }} />
      </div>
    );
  }

  const summary = plan?.summary || {};
  const recommendations = plan?.recommendations || [];

  return (
    <div className="page" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Smart Replenishment & Optimization
            </h1>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: 'var(--status-healthy-bg)', color: 'var(--status-healthy)', textTransform: 'uppercase' }}>
              Dynamic ROP Engine
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
            Automated reorder point calculations, dynamic safety stock, and surplus-to-shortage warehouse transfers.
          </p>
        </div>

        {/* Configuration Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div>
            <label style={{ fontSize: '11px', color: 'var(--text-tertiary)', display: 'block', marginBottom: '4px' }}>
              Service Level Target (Z={plan?.z_factor}):
            </label>
            <div style={{ display: 'flex', gap: '4px' }}>
              {[0.90, 0.95, 0.98, 0.99].map(sl => (
                <button
                  key={sl}
                  onClick={() => setServiceLevel(sl)}
                  style={{
                    padding: '4px 10px',
                    fontSize: '11px',
                    fontWeight: 600,
                    background: serviceLevel === sl ? 'var(--accent-primary)' : 'var(--bg-surface-1)',
                    color: serviceLevel === sl ? '#fff' : 'var(--text-secondary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--r-sm)',
                    cursor: 'pointer',
                  }}
                >
                  {(sl * 100).toFixed(0)}%
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={{ fontSize: '11px', color: 'var(--text-tertiary)', display: 'block', marginBottom: '4px' }}>
              Planning Horizon:
            </label>
            <select
              value={horizonDays}
              onChange={e => setHorizonDays(Number(e.target.value))}
              style={{
                background: 'var(--bg-surface-1)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-default)',
                padding: '6px 10px',
                borderRadius: 'var(--r-sm)',
                fontSize: '12px',
              }}
            >
              <option value={15}>15 Days</option>
              <option value={30}>30 Days</option>
              <option value={60}>60 Days</option>
              <option value={90}>90 Days</option>
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: 'var(--status-critical-bg)', border: '1px solid var(--status-critical-border)', borderRadius: 'var(--r-md)', color: 'var(--status-critical)', fontSize: '13px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {transferSuccess && (
        <div style={{ padding: '12px 16px', background: 'var(--status-healthy-bg)', border: '1px solid var(--status-healthy-border)', borderRadius: 'var(--r-md)', color: 'var(--status-healthy)', fontSize: '13px', marginBottom: '20px' }}>
          {transferSuccess}
        </div>
      )}

      {transferError && (
        <div style={{ padding: '12px 16px', background: 'var(--status-critical-bg)', border: '1px solid var(--status-critical-border)', borderRadius: 'var(--r-md)', color: 'var(--status-critical)', fontSize: '13px', marginBottom: '20px' }}>
          {transferError}
        </div>
      )}

      {/* KPI Cards Strip */}
      <div className="sim-kpi-grid">
        <div className={`sim-kpi-card ${summary.critical_stockouts > 0 ? 'critical' : 'healthy'}`}>
          <span className="kpi-label">Critical Stockouts</span>
          <div className="kpi-value" style={{ color: summary.critical_stockouts > 0 ? 'var(--status-critical)' : 'var(--status-healthy)' }}>
            {summary.critical_stockouts} <span style={{ fontSize: '13px', fontWeight: 400 }}>SKUs</span>
          </div>
          <span className="kpi-sub">Less than 3 days of stock remaining</span>
        </div>

        <div className="sim-kpi-card">
          <span className="kpi-label">SKUs Below Reorder Point</span>
          <div className="kpi-value" style={{ color: 'var(--status-watch)' }}>
            {summary.skus_needing_reorder} <span style={{ fontSize: '13px', fontWeight: 400 }}>of {summary.total_skus}</span>
          </div>
          <span className="kpi-sub">Action required to replenish safety buffer</span>
        </div>

        <div className="sim-kpi-card">
          <span className="kpi-label">Suggested Order Volume</span>
          <div className="kpi-value">
            {summary.total_reorder_units?.toLocaleString()} <span style={{ fontSize: '13px', fontWeight: 400 }}>units</span>
          </div>
          <span className="kpi-sub">Across all reorder candidates</span>
        </div>

        <div className="sim-kpi-card">
          <span className="kpi-label">Estimated Replenishment Capital</span>
          <div className="kpi-value" style={{ color: 'var(--accent-primary)' }}>
            ${summary.total_reorder_cost?.toLocaleString()}
          </div>
          <span className="kpi-sub">Based on mapped SKU unit costs</span>
        </div>
      </div>

      {/* Inter-Warehouse Transfer Proposals Section */}
      {transfers.length > 0 && (
        <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '20px', marginBottom: '32px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <ArrowRightLeft size={18} color="var(--accent-primary)" />
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              Surplus-to-Shortage Inter-Warehouse Transfer Proposals
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
            {transfers.map((t, idx) => (
              <div
                key={idx}
                style={{
                  background: 'var(--bg-surface-2)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--r-md)',
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '14px' }}>{t.product_name}</span>
                    <span style={{ fontSize: '11px', fontWeight: 700, padding: '2px 8px', borderRadius: '4px', background: 'var(--status-watch-bg)', color: 'var(--status-watch)' }}>
                      Transfer {t.transfer_units} Units
                    </span>
                  </div>
                  <p style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '12px' }}>SKU: {t.sku}</p>
                  <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.4', marginBottom: '12px' }}>
                    {t.reason}
                  </p>
                </div>

                <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-tertiary)' }}>
                    Est. Transit: {t.estimated_transfer_days} days
                  </div>
                  <button
                    disabled={executingTransfer}
                    onClick={() => handleExecuteTransfer(t)}
                    style={{
                      padding: '6px 12px',
                      background: executingTransfer ? 'var(--text-tertiary)' : 'var(--accent-primary)',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 'var(--r-sm)',
                      fontSize: '11px',
                      fontWeight: 600,
                      cursor: executingTransfer ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {executingTransfer ? 'Executing...' : 'Execute Transfer'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Replenishment Schedule Table */}
      <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            Automated Reorder Planning Table
          </h3>
          <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
            Sorted by Urgency Priority
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '10px 16px' }}>Product</th>
                <th style={{ padding: '10px 16px' }}>Category</th>
                <th style={{ padding: '10px 16px' }}>On-Hand</th>
                <th style={{ padding: '10px 16px' }}>On-Order</th>
                <th style={{ padding: '10px 16px' }}>Safety Stock (SS)</th>
                <th style={{ padding: '10px 16px' }}>Reorder Point (ROP)</th>
                <th style={{ padding: '10px 16px' }}>Suggested Order</th>
                <th style={{ padding: '10px 16px' }}>Est. Cost</th>
                <th style={{ padding: '10px 16px' }}>Urgency</th>
              </tr>
            </thead>
            <tbody>
              {recommendations.slice(0, 20).map(r => (
                <tr
                  key={r.product_id}
                  style={{
                    borderBottom: '1px solid var(--border-subtle)',
                    background: r.urgency === 'CRITICAL' ? 'rgba(255, 77, 95, 0.05)' : 'transparent',
                  }}
                >
                  <td style={{ padding: '10px 16px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{r.name}</div>
                    <div style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>{r.sku} • {r.supplier_name}</div>
                  </td>
                  <td style={{ padding: '10px 16px', color: 'var(--text-secondary)' }}>{r.category}</td>
                  <td style={{ padding: '10px 16px', fontWeight: 600 }}>{r.on_hand}</td>
                  <td style={{ padding: '10px 16px', color: 'var(--text-tertiary)' }}>{r.on_order}</td>
                  <td style={{ padding: '10px 16px', color: 'var(--status-watch)' }}>{r.safety_stock}</td>
                  <td style={{ padding: '10px 16px', color: 'var(--accent-primary)', fontWeight: 600 }}>{r.reorder_point}</td>
                  <td style={{ padding: '10px 16px', fontWeight: 700, color: r.suggested_order_qty > 0 ? 'var(--status-healthy)' : 'var(--text-tertiary)' }}>
                    {r.suggested_order_qty > 0 ? `${r.suggested_order_qty} units` : '—'}
                  </td>
                  <td style={{ padding: '10px 16px' }}>${r.estimated_order_cost.toLocaleString()}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        background: r.urgency === 'CRITICAL' ? 'var(--status-critical-bg)' : r.urgency === 'HIGH' ? 'var(--status-watch-bg)' : r.urgency === 'MEDIUM' ? 'var(--status-watch-bg)' : 'var(--status-healthy-bg)',
                        color: r.urgency === 'CRITICAL' ? 'var(--status-critical)' : r.urgency === 'HIGH' ? 'var(--status-watch)' : r.urgency === 'MEDIUM' ? 'var(--status-watch)' : 'var(--status-healthy)',
                      }}
                    >
                      {r.urgency}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
