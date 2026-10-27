import React, { useEffect, useState } from 'react';
import { Search, Filter, SlidersHorizontal, AlertTriangle, CheckCircle2, Package, ArrowUpDown } from 'lucide-react';
import { Link } from 'react-router-dom';
import { getInventoryExplorer } from '../services/api';
import Loader from '../components/Loader';

export default function Inventory({ company }) {
  const [items, setItems] = useState([]);
  const [search, setSearch] = useState('');
  const [selectedRisk, setSelectedRisk] = useState('ALL');
  const [sortField, setSortField] = useState('stockout_risk');
  const [sortAsc, setSortAsc] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!company?.id) return;
    setLoading(true);
    getInventoryExplorer(company.id)
      .then(res => {
        setItems(res.items || []);
        setError(null);
      })
      .catch(err => setError(err.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [company?.id]);

  if (loading) return <Loader />;

  if (error) {
    return (
      <div className="page animate-fade" style={{ padding: '32px', textAlign: 'center' }}>
        <p style={{ color: 'var(--status-critical)', marginBottom: '16px' }}>{error}</p>
        <button className="btn-secondary" onClick={() => window.location.reload()}>Retry</button>
      </div>
    );
  }

  // Filter items
  const filtered = items.filter(item => {
    const matchesSearch = !search ||
      item.product_name.toLowerCase().includes(search.toLowerCase()) ||
      item.external_product_id.toLowerCase().includes(search.toLowerCase());
    const matchesRisk = selectedRisk === 'ALL' || item.stockout_risk === selectedRisk;
    return matchesSearch && matchesRisk;
  });

  // Sort items
  const sorted = [...filtered].sort((a, b) => {
    let valA = a[sortField];
    let valB = b[sortField];
    if (valA === null || valA === undefined) valA = 0;
    if (valB === null || valB === undefined) valB = 0;
    if (typeof valA === 'string') return sortAsc ? valA.localeCompare(valB) : valB.localeCompare(valA);
    return sortAsc ? valA - valB : valB - valA;
  });

  const handleSort = (field) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const healthyCount = items.filter(x => x.stockout_risk === 'LOW').length;
  const watchCount = items.filter(x => x.stockout_risk === 'MEDIUM').length;
  const criticalCount = items.filter(x => x.stockout_risk === 'HIGH' || x.stockout_risk === 'CRITICAL').length;

  return (
    <div className="page animate-fade" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
              Inventory Explorer
            </h1>
            <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
              {items.length} Active SKUs
            </span>
          </div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
            Search, filter, and inspect on-hand stock, lead times, safety stocks, and stockout probabilities across all products.
          </p>
        </div>

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
          <SlidersHorizontal size={14} /> Open Delay Simulator
        </Link>
      </div>

      {/* KPI Strip */}
      <div className="sim-kpi-grid">
        <div className="sim-kpi-card healthy">
          <span className="kpi-label">Optimal Stock Level</span>
          <div className="kpi-value" style={{ color: 'var(--status-healthy)' }}>{healthyCount}</div>
          <span className="kpi-sub">Sufficient coverage &gt; 14 days</span>
        </div>
        <div className="sim-kpi-card warning">
          <span className="kpi-label">Approaching Reorder</span>
          <div className="kpi-value" style={{ color: 'var(--status-watch)' }}>{watchCount}</div>
          <span className="kpi-sub">Watch buffer consumption</span>
        </div>
        <div className="sim-kpi-card critical">
          <span className="kpi-label">Critical Shortage Exposure</span>
          <div className="kpi-value" style={{ color: 'var(--status-critical)' }}>{criticalCount}</div>
          <span className="kpi-sub">Immediate replenishment required</span>
        </div>
        <div className="sim-kpi-card">
          <span className="kpi-label">Total Catalog Units</span>
          <div className="kpi-value">
            {items.reduce((s, x) => s + (x.inventory_level || 0), 0).toLocaleString()}
          </div>
          <span className="kpi-sub">Live synchronized records</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
        <div style={{ display: 'flex', gap: '6px' }}>
          {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(risk => (
            <button
              key={risk}
              onClick={() => setSelectedRisk(risk)}
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                fontWeight: 600,
                background: selectedRisk === risk ? 'var(--accent-primary)' : 'var(--bg-surface-1)',
                color: selectedRisk === risk ? '#fff' : 'var(--text-secondary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--r-sm)',
                cursor: 'pointer',
              }}
            >
              {risk} {risk === 'CRITICAL' && `(${items.filter(x => x.stockout_risk === 'CRITICAL').length})`}
            </button>
          ))}
        </div>

        <div style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-tertiary)' }} />
          <input
            type="text"
            placeholder="Search SKU or Name..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{
              background: 'var(--bg-surface-1)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--r-sm)',
              padding: '6px 12px 6px 30px',
              color: 'var(--text-primary)',
              fontSize: '12px',
              outline: 'none',
              minWidth: '240px',
            }}
          />
        </div>
      </div>

      {/* SKU Table */}
      <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '10px 16px', cursor: 'pointer' }} onClick={() => handleSort('product_name')}>
                  Product Name <ArrowUpDown size={11} style={{ verticalAlign: 'middle' }} />
                </th>
                <th style={{ padding: '10px 16px', cursor: 'pointer' }} onClick={() => handleSort('inventory_level')}>
                  On-Hand Stock <ArrowUpDown size={11} style={{ verticalAlign: 'middle' }} />
                </th>
                <th style={{ padding: '10px 16px', cursor: 'pointer' }} onClick={() => handleSort('daily_demand')}>
                  Daily Demand <ArrowUpDown size={11} style={{ verticalAlign: 'middle' }} />
                </th>
                <th style={{ padding: '10px 16px', cursor: 'pointer' }} onClick={() => handleSort('inventory_coverage_days')}>
                  Coverage <ArrowUpDown size={11} style={{ verticalAlign: 'middle' }} />
                </th>
                <th style={{ padding: '10px 16px' }}>Safety Stock</th>
                <th style={{ padding: '10px 16px' }}>Reorder Point</th>
                <th style={{ padding: '10px 16px' }}>Stockout Tier</th>
                <th style={{ padding: '10px 16px' }}>Disruption Action</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map(item => {
                const isCrit = item.stockout_risk === 'CRITICAL' || item.stockout_risk === 'HIGH';
                return (
                  <tr
                    key={item.product_id}
                    style={{
                      borderBottom: '1px solid var(--border-subtle)',
                      background: isCrit ? 'rgba(255, 77, 95, 0.05)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '10px 16px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.product_name}</div>
                      <div style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>{item.external_product_id}</div>
                    </td>
                    <td style={{ padding: '10px 16px', fontWeight: 600 }}>{item.inventory_level} units</td>
                    <td style={{ padding: '10px 16px' }}>{item.daily_demand} /day</td>
                    <td style={{ padding: '10px 16px', color: isCrit ? 'var(--status-critical)' : 'var(--text-primary)' }}>
                      {item.inventory_coverage_days ? `${item.inventory_coverage_days} days` : 'Exhausted'}
                    </td>
                    <td style={{ padding: '10px 16px', color: 'var(--status-watch)' }}>{item.safety_stock}</td>
                    <td style={{ padding: '10px 16px', color: 'var(--accent-primary)', fontWeight: 600 }}>{item.reorder_point}</td>
                    <td style={{ padding: '10px 16px' }}>
                      <span
                        style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '11px',
                          fontWeight: 700,
                          background: isCrit ? 'var(--status-critical-bg)' : item.stockout_risk === 'MEDIUM' ? 'var(--status-watch-bg)' : 'var(--status-healthy-bg)',
                          color: isCrit ? 'var(--status-critical)' : item.stockout_risk === 'MEDIUM' ? 'var(--status-watch)' : 'var(--status-healthy)',
                        }}
                      >
                        {item.stockout_risk}
                      </span>
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <Link
                        to="/delay-simulator"
                        style={{
                          display: 'inline-block',
                          padding: '4px 10px',
                          background: 'var(--bg-surface-2)',
                          color: 'var(--accent-primary)',
                          border: '1px solid var(--border-subtle)',
                          borderRadius: 'var(--r-sm)',
                          fontSize: '11px',
                          fontWeight: 600,
                          textDecoration: 'none',
                        }}
                      >
                        Simulate Delay
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
