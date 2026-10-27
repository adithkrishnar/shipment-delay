import React, { useState, useEffect } from 'react';
import { Warehouse, Boxes, MapPin, Search, ArrowRight, ShieldCheck, AlertTriangle } from 'lucide-react';
import { getWarehousesAnalytics, getInventoryExplorer } from '../services/api';

export default function Products({ company }) {
  const [warehouses, setWarehouses] = useState([]);
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState('');
  const [selectedWarehouseId, setSelectedWarehouseId] = useState('ALL');
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!company?.id) return;
    setLoading(true);
    Promise.all([
      getWarehousesAnalytics(company.id),
      getInventoryExplorer(company.id),
    ])
      .then(([whData, prodData]) => {
        setWarehouses(whData || []);
        setProducts(prodData.items || []);
        setError(null);
      })
      .catch(err => setError(err.response?.data?.detail || err.message))
      .finally(() => setLoading(false));
  }, [company?.id]);

  const filtered = products.filter(p => {
    const matchesSearch = !search || p.product_name.toLowerCase().includes(search.toLowerCase()) || p.external_product_id.toLowerCase().includes(search.toLowerCase());
    return matchesSearch;
  });

  if (loading) {
    return (
      <div className="page" style={{ padding: '32px' }}>
        <div className="skeleton" style={{ height: '40px', width: '300px', marginBottom: '24px' }} />
        <div className="skeleton" style={{ height: '350px', width: '100%' }} />
      </div>
    );
  }

  return (
    <div className="page" style={{ padding: '32px', maxWidth: '1440px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Products & Distribution Centers
          </h1>
          <span style={{ fontSize: '11px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: 'var(--accent-primary-dim)', color: 'var(--accent-primary)', textTransform: 'uppercase' }}>
            Multi-Node Network
          </span>
        </div>
        <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '6px' }}>
          Warehouse capacity utilization, SKU footprint, and multi-location inventory levels.
        </p>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', background: 'var(--status-critical-bg)', border: '1px solid var(--status-critical-border)', borderRadius: 'var(--r-md)', color: 'var(--status-critical)', fontSize: '13px', marginBottom: '20px' }}>
          {error}
        </div>
      )}

      {/* Warehouse Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px', marginBottom: '32px' }}>
        {warehouses.map(wh => (
          <div
            key={wh.id}
            style={{
              background: 'var(--bg-surface-1)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--r-md)',
              padding: '20px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>{wh.name}</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-tertiary)', fontSize: '12px', marginTop: '2px' }}>
                    <MapPin size={12} /> {wh.location}
                  </div>
                </div>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    fontWeight: 700,
                    background: wh.status === 'HEALTHY' ? 'var(--status-healthy-bg)' : 'var(--status-watch-bg)',
                    color: wh.status === 'HEALTHY' ? 'var(--status-healthy)' : 'var(--status-watch)',
                  }}
                >
                  {wh.status}
                </span>
              </div>

              <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Total Stock:</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{wh.total_units?.toLocaleString()} units</span>
              </div>
              <div style={{ marginTop: '6px', display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Active SKUs:</span>
                <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{wh.total_skus}</span>
              </div>
            </div>

            <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
              {wh.utilization_pct !== null && wh.utilization_pct !== undefined ? (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-tertiary)', marginBottom: '6px' }}>
                    <span>Storage Utilization</span>
                    <span>{wh.utilization_pct}%</span>
                  </div>
                  <div style={{ width: '100%', height: '6px', background: 'var(--bg-surface-2)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ width: `${Math.min(100, wh.utilization_pct)}%`, height: '100%', background: wh.utilization_pct > 90 ? 'var(--status-critical)' : 'var(--accent-primary)' }} />
                  </div>
                </>
              ) : (
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', color: 'var(--text-tertiary)' }}>
                  <span>Storage Capacity</span>
                  <span style={{ padding: '2px 6px', background: 'var(--bg-surface-2)', borderRadius: '3px', fontSize: '10px', color: 'var(--text-tertiary)' }}>
                    Capacity Data Unavailable
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Product Catalog Explorer */}
      <div style={{ background: 'var(--bg-surface-1)', border: '1px solid var(--border-default)', borderRadius: 'var(--r-lg)', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            Master Product Inventory Register
          </h3>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ position: 'relative' }}>
              <Search size={14} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-tertiary)' }} />
              <input
                type="text"
                placeholder="Search SKU or Name..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                style={{
                  background: 'var(--bg-surface-2)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--r-sm)',
                  padding: '6px 12px 6px 30px',
                  color: 'var(--text-primary)',
                  fontSize: '12px',
                  outline: 'none',
                  minWidth: '220px',
                }}
              />
            </div>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-surface-2)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}>
                <th style={{ padding: '10px 16px' }}>Product</th>
                <th style={{ padding: '10px 16px' }}>Category</th>
                <th style={{ padding: '10px 16px' }}>Current Stock</th>
                <th style={{ padding: '10px 16px' }}>Daily Demand</th>
                <th style={{ padding: '10px 16px' }}>Coverage</th>
                <th style={{ padding: '10px 16px' }}>Supplier</th>
                <th style={{ padding: '10px 16px' }}>Lead Time</th>
                <th style={{ padding: '10px 16px' }}>Risk Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.slice(0, 20).map(p => (
                <tr key={p.product_id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 16px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{p.product_name}</div>
                    <div style={{ color: 'var(--text-tertiary)', fontSize: '11px' }}>{p.external_product_id}</div>
                  </td>
                  <td style={{ padding: '10px 16px', color: 'var(--text-secondary)' }}>{p.category || 'General'}</td>
                  <td style={{ padding: '10px 16px', fontWeight: 600 }}>{p.inventory_level} units</td>
                  <td style={{ padding: '10px 16px' }}>{p.daily_demand} /day</td>
                  <td style={{ padding: '10px 16px', color: p.inventory_coverage_days < 7 ? 'var(--status-critical)' : 'var(--text-primary)' }}>
                    {p.inventory_coverage_days ? `${p.inventory_coverage_days} days` : 'Depleted'}
                  </td>
                  <td style={{ padding: '10px 16px', color: 'var(--text-secondary)' }}>{p.supplier_name || 'Primary'}</td>
                  <td style={{ padding: '10px 16px' }}>{p.lead_time_days} days</td>
                  <td style={{ padding: '10px 16px' }}>
                    <span
                      style={{
                        padding: '2px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        background: p.stockout_risk === 'CRITICAL' ? 'var(--status-critical-bg)' : p.stockout_risk === 'HIGH' ? 'var(--status-watch-bg)' : 'var(--status-healthy-bg)',
                        color: p.stockout_risk === 'CRITICAL' ? 'var(--status-critical)' : p.stockout_risk === 'HIGH' ? 'var(--status-watch)' : 'var(--status-healthy)',
                      }}
                    >
                      {p.stockout_risk}
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
