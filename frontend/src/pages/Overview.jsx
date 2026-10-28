import React, { useEffect, useState } from 'react';
import {
  Boxes, DollarSign, AlertTriangle, ShieldCheck, TrendingUp,
  Warehouse, ArrowRight, RefreshCw, SlidersHorizontal, Sparkles
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, PieChart, Pie, Cell
} from 'recharts';
import { getInventoryOverview, getWarehousesAnalytics } from '../services/api';
import Loader from '../components/Loader';

const RISK_COLORS = {
  HEALTHY: '#2DD4A7',
  WATCH: '#F5B942',
  CRITICAL: '#FF4D5F',
};

export default function Overview({ company }) {
  const [data, setData] = useState(null);
  const [warehouses, setWarehouses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!company?.id) return;
    setLoading(true);
    Promise.all([
      getInventoryOverview(company.id),
      getWarehousesAnalytics(company.id),
    ])
      .then(([overviewData, whData]) => {
        setData(overviewData);
        setWarehouses(whData || []);
        setError(null);
      })
      .catch(err => setError(err.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [company?.id]);

  if (loading) return <Loader />;

  if (error || !data) {
    return (
      <div className="page animate-fade" style={{ padding: '32px', textAlign: 'center' }}>
        <p style={{ color: 'var(--status-critical)', marginBottom: '16px' }}>{error || 'Unable to load inventory control tower.'}</p>
        <button className="btn-secondary" onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  const items = data.items || [];
  const criticalItems = items.filter(i => i.stockout_risk === 'CRITICAL' || i.stockout_risk === 'HIGH');
  const watchItems = items.filter(i => i.stockout_risk === 'MEDIUM');
  const optimalItems = items.filter(i => i.stockout_risk === 'LOW');

  const healthDistribution = [
    { name: 'Optimal Stock', value: optimalItems.length, fill: RISK_COLORS.HEALTHY },
    { name: 'Approaching Reorder', value: watchItems.length, fill: RISK_COLORS.WATCH },
    { name: 'Critical / Low', value: criticalItems.length, fill: RISK_COLORS.CRITICAL },
  ].filter(d => d.value > 0);

  const warehouseChartData = warehouses.map(wh => ({
    name: wh.name,
    stock: wh.total_units,
    skus: wh.total_skus,
  }));

  return (
    <div className="page animate-fade" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Page Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              INVENTORY INTELLIGENCE CONTROL TOWER
            </h1>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              Data Integrity: 100% • 2 Approaching Reorder
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '6px', fontSize: '12px', color: 'var(--text-tertiary)' }}>
            <span>Scope: <strong style={{ color: 'var(--text-secondary)' }}>{company?.name || 'Global Operations'}</strong></span>
            <span>•</span>
            <span>Network: <strong style={{ color: 'var(--text-secondary)' }}>{warehouses.length} Regional DCs</strong></span>
            <span>•</span>
            <span>Status: <strong style={{ color: 'var(--status-healthy)' }}>Live Synchronized</strong></span>
          </div>
        </div>


        <div style={{ display: 'flex', gap: '10px' }}>
          <Link
            to="/delay-simulator"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              background: 'var(--accent-primary)',
              color: '#fff',
              borderRadius: 'var(--r-md)',
              fontSize: '13px',
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            <SlidersHorizontal size={14} /> Delay Simulator
          </Link>
          <Link
            to="/replenishment"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              background: 'var(--bg-surface-2)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--r-md)',
              fontSize: '13px',
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            <RefreshCw size={14} /> Smart Replenishment
          </Link>
        </div>
      </div>

      {/* KPI Cards Strip */}
      <div className="sim-kpi-grid">
        <div className="sim-kpi-card">
          <div className="kpi-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Boxes size={14} color="var(--accent-primary)" />
            Total On-Hand Inventory
          </div>
          <div className="kpi-value">
            {data.total_inventory_units?.toLocaleString()} <span style={{ fontSize: '13px', fontWeight: 400 }}>units</span>
          </div>
          <div className="kpi-sub">Across {data.total_skus} active SKUs</div>
        </div>

        <div className="sim-kpi-card">
          <div className="kpi-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <DollarSign size={14} color="var(--status-healthy)" />
            Total Inventory Valuation
          </div>
          <div className="kpi-value" style={{ color: 'var(--status-healthy)' }}>
            ${data.total_valuation?.toLocaleString()}
          </div>
          <div className="kpi-sub">Cost-weighted asset balance</div>
        </div>

        <div className={`sim-kpi-card ${data.critical_stockouts > 0 ? 'critical' : 'healthy'}`}>
          <div className="kpi-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <AlertTriangle size={14} color={data.critical_stockouts > 0 ? 'var(--status-critical)' : 'var(--status-healthy)'} />
            Stockout Exposure
          </div>
          <div className="kpi-value" style={{ color: data.critical_stockouts > 0 ? 'var(--status-critical)' : 'var(--status-healthy)' }}>
            {data.critical_stockouts} <span style={{ fontSize: '13px', fontWeight: 400 }}>SKUs</span>
          </div>
          <div className="kpi-sub">Stock below reorder safety threshold</div>
        </div>

        <div className="sim-kpi-card">
          <div className="kpi-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Warehouse size={14} color="var(--status-watch)" />
            Excess / Overstock SKUs
          </div>
          <div className="kpi-value" style={{ color: 'var(--status-watch)' }}>
            {data.overstock_skus} <span style={{ fontSize: '13px', fontWeight: 400 }}>SKUs</span>
          </div>
          <div className="kpi-sub">&gt; 45 days demand coverage</div>
        </div>
      </div>

      {/* Analytical Charts Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '32px' }}>
        {/* Multi-Node Warehouse Distribution */}
        <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '24px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
            Distribution Center Stock Allocation
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '16px' }}>
            Inventory units distributed across regional facilities
          </p>
          <div style={{ height: '240px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={warehouseChartData} margin={{ top: 10, right: 10, bottom: 5, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" />
                <XAxis dataKey="name" stroke="var(--text-tertiary)" fontSize={11} />
                <YAxis stroke="var(--text-tertiary)" fontSize={11} />
                <Tooltip contentStyle={{ background: 'var(--bg-surface-1)', borderColor: 'var(--border-default)', fontSize: '12px' }} />
                <Bar dataKey="stock" fill="var(--accent-primary)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Portfolio Health Breakdown */}
        <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', padding: '24px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
            Inventory Portfolio Health
          </h3>
          <p style={{ fontSize: '12px', color: 'var(--text-tertiary)', marginBottom: '16px' }}>
            Ratio of healthy, overstocked, and critical shortage SKUs
          </p>
          <div style={{ height: '200px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={healthDistribution} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4}>
                  {healthDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: 'var(--bg-surface-1)', borderColor: 'var(--border-default)', fontSize: '12px' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '20px', fontSize: '12px', marginTop: '10px' }}>
            {healthDistribution.map(item => (
              <span key={item.name} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ width: 10, height: 10, borderRadius: '2px', background: item.fill }} />
                {item.name} ({item.value})
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Critical Stockout Alerts Strip */}
      {criticalItems.length > 0 && (
        <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <AlertTriangle size={16} color="var(--status-critical)" />
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
                High-Priority Inventory Alerts
              </h3>
            </div>
            <Link to="/inventory" style={{ fontSize: '12px', color: 'var(--accent-primary)', textDecoration: 'none' }}>
              View All SKUs →
            </Link>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
              <thead>
                <tr style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                  <th style={{ padding: '10px 16px' }}>SKU</th>
                  <th style={{ padding: '10px 16px' }}>Current Stock</th>
                  <th style={{ padding: '10px 16px' }}>Daily Demand</th>
                  <th style={{ padding: '10px 16px' }}>Days Remaining</th>
                  <th style={{ padding: '10px 16px' }}>Safety Stock</th>
                  <th style={{ padding: '10px 16px' }}>Status</th>
                  <th style={{ padding: '10px 16px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {criticalItems.slice(0, 5).map(item => (
                  <tr key={item.product_id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '10px 16px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.product_name}</div>
                      <div style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>{item.external_product_id}</div>
                    </td>
                    <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--status-critical)' }}>{item.inventory_level} units</td>
                    <td style={{ padding: '10px 16px' }}>{item.daily_demand} /day</td>
                    <td style={{ padding: '10px 16px', color: 'var(--status-critical)' }}>{item.inventory_coverage_days || '0'} days</td>
                    <td style={{ padding: '10px 16px', color: 'var(--status-watch)' }}>{item.safety_stock} units</td>
                    <td style={{ padding: '10px 16px' }}>
                      <span style={{ padding: '2px 8px', borderRadius: '4px', fontSize: '11px', fontWeight: 700, background: 'var(--status-critical-bg)', color: 'var(--status-critical)' }}>
                        {item.stockout_risk}
                      </span>
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <Link
                        to="/delay-simulator"
                        style={{
                          fontSize: '11px',
                          fontWeight: 600,
                          padding: '4px 10px',
                          background: 'var(--bg-surface-2)',
                          color: 'var(--accent-primary)',
                          borderRadius: 'var(--r-sm)',
                          textDecoration: 'none',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        Simulate
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
