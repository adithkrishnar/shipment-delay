import React, { useState, useEffect } from 'react';
import { Grid3X3, DollarSign, Clock, AlertTriangle, ArrowUpDown, Filter } from 'lucide-react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts';
import { getAbcXyzInsights, getAgingInsights } from '../services/api';

export default function Insights({ company }) {
  const [abcData, setAbcData] = useState(null);
  const [agingData, setAgingData] = useState(null);
  const [selectedSegment, setSelectedSegment] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!company?.id) return;
    setLoading(true);
    Promise.all([
      getAbcXyzInsights(company.id),
      getAgingInsights(company.id),
    ])
      .then(([abc, aging]) => {
        setAbcData(abc);
        setAgingData(aging);
        setError(null);
      })
      .catch(err => setError(err.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [company?.id]);

  if (loading) {
    return (
      <div className="page" style={{ padding: '32px' }}>
        <div className="skeleton" style={{ height: '40px', width: '300px', marginBottom: '24px' }} />
        <div className="skeleton" style={{ height: '350px', width: '100%' }} />
      </div>
    );
  }

  const matrix = abcData?.matrix || {};
  const summary = abcData?.summary || {};
  const agingBuckets = agingData?.aging_buckets || {};
  const slowMoving = agingData?.slow_moving_skus || [];

  const agingChartData = Object.entries(agingBuckets).map(([bucket, val]) => ({
    bucket: bucket.replace(/ \(.*\)/, ''),
    units: val.units,
    value: val.value,
  }));

  const allProducts = abcData?.products || [];
  const filteredProducts = selectedSegment
    ? allProducts.filter(p => p.segment === selectedSegment)
    : allProducts;

  return (
    <div className="page" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Page Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Inventory Insights & ABC/XYZ Segmentation
          </h1>
          <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
            Portfolio Analytics
          </span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
          Evaluate inventory value distribution (ABC), demand predictability (XYZ), and aging capital exposure.
        </p>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: 'var(--status-critical-bg)', border: '1px solid var(--status-critical-border)', borderRadius: 'var(--r-md)', color: 'var(--status-critical)', fontSize: '13px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="sim-kpi-grid">
        <div className="sim-kpi-card">
          <span className="kpi-label">Class A Products (Top 80% Value)</span>
          <div className="kpi-value" style={{ color: 'var(--accent-primary)' }}>
            {summary.a_count} <span style={{ fontSize: '13px', fontWeight: 400, color: 'var(--text-tertiary)' }}>of {summary.total_products} SKUs</span>
          </div>
          <span className="kpi-sub">High-priority revenue drivers</span>
        </div>

        <div className="sim-kpi-card">
          <span className="kpi-label">Class X (Stable Demand, CV &lt; 0.5)</span>
          <div className="kpi-value" style={{ color: 'var(--status-healthy)' }}>
            {summary.x_count} <span style={{ fontSize: '13px', fontWeight: 400, color: 'var(--text-tertiary)' }}>SKUs</span>
          </div>
          <span className="kpi-sub">High forecast accuracy</span>
        </div>

        <div className="sim-kpi-card">
          <span className="kpi-label">Class Z (Erratic Demand, CV &gt; 1.0)</span>
          <div className="kpi-value" style={{ color: 'var(--status-critical)' }}>
            {summary.z_count} <span style={{ fontSize: '13px', fontWeight: 400, color: 'var(--text-tertiary)' }}>SKUs</span>
          </div>
          <span className="kpi-sub">Requires larger safety stock buffers</span>
        </div>

        <div className="sim-kpi-card">
          <span className="kpi-label">Slow & Non-Moving Capital</span>
          <div className="kpi-value" style={{ color: 'var(--status-watch)' }}>
            ${agingData?.total_at_risk_capital?.toLocaleString()}
          </div>
          <span className="kpi-sub">{slowMoving.length} SKUs with &gt; 90 days inactivity</span>
        </div>
      </div>

      {/* ABC/XYZ 9-Box Matrix Section */}
      <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '24px', marginBottom: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div>
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
              9-Box ABC / XYZ Portfolio Matrix
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', margin: '4px 0 0' }}>
              Click any quadrant to filter SKUs. Rows indicate Consumption Value (A/B/C); Columns indicate Demand Volatility (X/Y/Z).
            </p>
          </div>
          {selectedSegment && (
            <button
              onClick={() => setSelectedSegment(null)}
              style={{
                fontSize: '12px',
                padding: '6px 12px',
                background: 'var(--bg-surface-2)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--r-sm)',
                cursor: 'pointer',
              }}
            >
              Clear Filter ({selectedSegment})
            </button>
          )}
        </div>

        <div className="abc-matrix-grid">
          {['AX', 'AY', 'AZ', 'BX', 'BY', 'BZ', 'CX', 'CY', 'CZ'].map(seg => {
            const cell = matrix[seg] || { count: 0, total_value: 0, total_stock: 0 };
            const isSelected = selectedSegment === seg;
            return (
              <div
                key={seg}
                onClick={() => setSelectedSegment(isSelected ? null : seg)}
                className={`abc-matrix-card ${isSelected ? 'selected' : ''}`}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                  <span style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>{seg}</span>
                  <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-tertiary)' }}>
                    {seg.startsWith('A') ? 'High Value' : seg.startsWith('B') ? 'Medium Value' : 'Low Value'} •{' '}
                    {seg.endsWith('X') ? 'Stable' : seg.endsWith('Y') ? 'Variable' : 'Erratic'}
                  </span>
                </div>
                <div style={{ fontSize: '20px', fontWeight: 600, color: cell.count > 0 ? 'var(--accent-primary)' : 'var(--text-tertiary)' }}>
                  {cell.count} <span style={{ fontSize: '12px', fontWeight: 400 }}>SKUs</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)', marginTop: '8px' }}>
                  <span>Stock: {cell.total_stock} units</span>
                  <span>Value: ${cell.total_value.toLocaleString()}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Aging Analysis Chart */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>
        <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '24px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
            Inventory Aging Distribution (Units on Hand)
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '16px' }}>
            Days elapsed since last transaction activity.
          </p>
          <div style={{ height: '240px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={agingChartData} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis dataKey="bucket" stroke="var(--text-tertiary)" fontSize={10} />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} />
                <Tooltip contentStyle={{ background: 'var(--bg-surface-1)', borderColor: 'var(--border-default)', fontSize: '12px' }} />
                <Bar dataKey="units" fill="var(--accent-primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '24px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
            Slow-Moving & Dead Stock Exposure
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '16px' }}>
            SKUs with no sales activity in over 90 days.
          </p>
          <div style={{ maxHeight: '240px', overflowY: 'auto' }}>
            {slowMoving.length === 0 ? (
              <p style={{ color: 'var(--status-healthy)', fontSize: '13px' }}>No slow-moving inventory detected.</p>
            ) : (
              slowMoving.slice(0, 5).map(item => (
                <div
                  key={item.product_id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '8px 12px',
                    borderBottom: '1px solid var(--border-subtle)',
                    fontSize: '12px',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.name}</div>
                    <div style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>
                      {item.sku} • Inactive for {item.days_inactive} days
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontWeight: 600, color: 'var(--status-watch)' }}>${item.stock_value.toLocaleString()}</div>
                    <div style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>{item.stock_on_hand} units</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Filtered Product Details Table */}
      <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            SKU Classification Table {selectedSegment && `(${selectedSegment})`}
          </h3>
          <span style={{ fontSize: '12px', color: 'var(--text-tertiary)' }}>
            Showing {filteredProducts.length} products
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '10px 16px' }}>Product</th>
                <th style={{ padding: '10px 16px' }}>Category</th>
                <th style={{ padding: '10px 16px' }}>Segment</th>
                <th style={{ padding: '10px 16px' }}>Annual Sales</th>
                <th style={{ padding: '10px 16px' }}>Demand Volatility (CV)</th>
                <th style={{ padding: '10px 16px' }}>Current Stock</th>
                <th style={{ padding: '10px 16px' }}>Stock Valuation</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.slice(0, 15).map(p => (
                <tr key={p.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 16px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{p.name}</div>
                    <div style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>{p.external_id}</div>
                  </td>
                  <td style={{ padding: '10px 16px', color: 'var(--text-secondary)' }}>{p.category}</td>
                  <td style={{ padding: '10px 16px' }}>
                    <span className={`abc-tag ${p.abc_class}`}>{p.abc_class}</span>
                    <span style={{ marginLeft: '4px', fontWeight: 600 }} className={`xyz-tag ${p.xyz_class}`}>{p.xyz_class}</span>
                  </td>
                  <td style={{ padding: '10px 16px' }}>${p.annual_consumption_value.toLocaleString()}</td>
                  <td style={{ padding: '10px 16px', color: p.cv < 0.5 ? 'var(--status-healthy)' : p.cv <= 1.0 ? 'var(--status-watch)' : 'var(--status-critical)' }}>
                    {p.cv}
                  </td>
                  <td style={{ padding: '10px 16px' }}>{p.current_stock} units</td>
                  <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>${p.stock_value.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
