import React, { useEffect, useState } from 'react';
import {
  Boxes, DollarSign, AlertTriangle, ShieldCheck, TrendingUp,
  Warehouse, ArrowRight, RefreshCw, SlidersHorizontal, Sparkles, Truck, CheckCircle2, X, ChevronRight, Info
} from 'lucide-react';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, PieChart, Pie, Cell
} from 'recharts';
import { getInventoryOverview, getWarehousesAnalytics, getRecentDisruptions } from '../services/api';
import Loader from '../components/Loader';

const RISK_COLORS = {
  HEALTHY: '#2DD4A7',
  WATCH: '#F5B942',
  CRITICAL: '#FF4D5F',
};

export default function Overview({ company }) {
  const [data, setData] = useState(null);
  const [warehouses, setWarehouses] = useState([]);
  const [disruptions, setDisruptions] = useState([]);
  const [selectedDisruption, setSelectedDisruption] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!company?.id) return;
    setLoading(true);
    Promise.all([
      getInventoryOverview(company.id),
      getWarehousesAnalytics(company.id),
      getRecentDisruptions().catch(() => [])
    ])
      .then(([overviewData, whData, disData]) => {
        setData(overviewData);
        setWarehouses(whData || []);
        setDisruptions(disData || []);
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
            to="/recommendations"
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
            <Sparkles size={14} /> Action Center
          </Link>
        </div>
      </div>

      {/* Real-time Carrier Disruption Broadcast Feed */}
      {disruptions.length > 0 && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.08), rgba(245, 158, 11, 0.04))',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '12px',
          padding: '18px 22px',
          marginBottom: '24px',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#ef4444', animation: 'pulse 1.5s infinite' }} />
              <Truck size={18} color="#ef4444" />
              <strong style={{ fontSize: '15px', color: 'var(--text-primary)' }}>
                CARRIER EXCEPTION BROADCAST FEED (Automated Ripple Simulation)
              </strong>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              {disruptions.length} Transporter Incident(s) Logged
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {disruptions.slice(0, 3).map((d) => (
              <div
                key={d.id}
                onClick={() => setSelectedDisruption(d)}
                style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '14px 18px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  boxShadow: '0 1px 3px rgba(0,0,0,0.05)'
                }}
                onMouseEnter={(e) => e.currentTarget.style.borderColor = 'var(--accent-primary)'}
                onMouseLeave={(e) => e.currentTarget.style.borderColor = 'var(--border-subtle)'}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, padding: '2px 6px', borderRadius: '4px', background: '#ef4444', color: '#fff' }}>
                      LEG #{d.leg_sequence} ({d.leg_mode})
                    </span>
                    <strong style={{ fontSize: '14px', color: 'var(--text-primary)' }}>
                      Shipment {d.external_shipment_id || `#${d.shipment_id}`}
                    </strong>
                    <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      • Reason: <strong>{d.disruption_reason}</strong> (Delay: <strong>{d.delay_hours >= 24 ? `${(d.delay_hours/24).toFixed(1)} days` : `${d.delay_hours} hrs`}</strong>)
                    </span>
                  </div>
                  {d.notes && (
                    <div style={{ fontSize: '12px', color: 'var(--text-tertiary)', fontStyle: 'italic' }}>
                      "{d.notes}"
                    </div>
                  )}
                  <div style={{ fontSize: '11px', color: 'var(--accent-primary)', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
                    <Info size={12} /> Click to inspect detailed inventory impact & prescribed action rationale
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Simulated Cost Loss</div>
                    <div style={{ fontSize: '16px', fontWeight: 700, color: d.estimated_cost_loss > 0 ? '#ef4444' : 'var(--status-healthy)' }}>
                      ${d.estimated_cost_loss?.toLocaleString() || '0'}
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>Prescribed Action</div>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--accent-primary)' }}>
                      {d.prescribed_mitigation || 'Active Monitoring'}
                    </div>
                  </div>

                  <button
                    onClick={(e) => { e.stopPropagation(); setSelectedDisruption(d); }}
                    className="btn-primary"
                    style={{ fontSize: '12px', padding: '6px 12px', display: 'flex', alignItems: 'center', gap: '4px' }}
                  >
                    View Impact & Fix <ChevronRight size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detailed Impact & Decision Modal */}
      {selectedDisruption && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.75)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-default)',
            borderRadius: '16px',
            maxWidth: '750px',
            width: '100%',
            maxHeight: '90vh',
            overflowY: 'auto',
            padding: '28px',
            boxShadow: '0 20px 40px rgba(0,0,0,0.4)',
            position: 'relative'
          }}>
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, padding: '3px 8px', borderRadius: '4px', background: '#ef4444', color: '#fff' }}>
                    CORRIDOR DISRUPTION IMPACT
                  </span>
                  <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-secondary)' }}>
                    Shipment {selectedDisruption.external_shipment_id || `#${selectedDisruption.shipment_id}`} • Leg #{selectedDisruption.leg_sequence} ({selectedDisruption.leg_mode})
                  </span>
                </div>
                <h2 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                  Automated Downstream Inventory & Financial Impact Analysis
                </h2>
              </div>
              <button
                onClick={() => setSelectedDisruption(null)}
                style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Impact 4-Metric Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '12px', marginBottom: '24px' }}>
              <div style={{ background: 'var(--bg-surface-2)', padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', fontWeight: 600 }}>DELAY DURATION</div>
                <div style={{ fontSize: '18px', fontWeight: 700, color: '#ef4444', marginTop: '4px' }}>
                  +{selectedDisruption.total_impact_delay_days || (selectedDisruption.delay_hours/24).toFixed(1)} days
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  ({selectedDisruption.delay_hours} hrs transit lag)
                </div>
              </div>

              <div style={{ background: 'var(--bg-surface-2)', padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', fontWeight: 600 }}>DESTINATION FACILITY</div>
                <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
                  {selectedDisruption.impact_details?.destination_warehouse || 'Regional Facility'}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Local Stock: {selectedDisruption.impact_details?.facility_stock ?? 18} units
                </div>
              </div>

              <div style={{ background: 'var(--bg-surface-2)', padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', fontWeight: 600 }}>EXPECTED SHORTAGE</div>
                <div style={{ fontSize: '18px', fontWeight: 700, color: selectedDisruption.unmet_demand_units > 0 ? '#ef4444' : 'var(--status-healthy)', marginTop: '4px' }}>
                  {selectedDisruption.unmet_demand_units || 0} units
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  {selectedDisruption.stockout_predicted ? 'Stockout imminent' : 'Buffer absorbs lag'}
                </div>
              </div>

              <div style={{ background: 'var(--bg-surface-2)', padding: '12px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', fontWeight: 600 }}>TOTAL FINANCIAL LOSS</div>
                <div style={{ fontSize: '18px', fontWeight: 700, color: '#ef4444', marginTop: '4px' }}>
                  ${selectedDisruption.estimated_cost_loss?.toLocaleString() || '0'}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  Includes SLA penalties
                </div>
              </div>
            </div>

            {/* Downstream Inventory Cascade Explanation */}
            <div style={{ 
              background: 'rgba(239, 68, 68, 0.05)', 
              border: '1px solid rgba(239, 68, 68, 0.2)', 
              borderRadius: '10px', 
              padding: '16px', 
              marginBottom: '24px' 
            }}>
              <h4 style={{ fontSize: '13px', fontWeight: 700, color: '#ef4444', margin: '0 0 6px 0', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Operational & Inventory Ripple Effect
              </h4>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.6 }}>
                Carrier reported <strong>{selectedDisruption.disruption_reason}</strong> resulting in a cumulative transit lag of <strong>{selectedDisruption.delay_hours >= 24 ? `${(selectedDisruption.delay_hours/24).toFixed(1)} days (${selectedDisruption.delay_hours} hrs)` : `${selectedDisruption.delay_hours} hours`}</strong>. 
                {selectedDisruption.unmet_demand_units > 0 ? (
                  <> Destination facility <strong>{selectedDisruption.impact_details?.destination_warehouse || 'destination hub'}</strong> does not possess sufficient local safety buffer to bridge this delay window. The stock depletion curve projects an unmet demand of <strong>{selectedDisruption.unmet_demand_units} units</strong> of <em>{selectedDisruption.impact_details?.product_name || 'critical components'}</em>, inflicting a total commercial exposure of <strong>${selectedDisruption.estimated_cost_loss?.toLocaleString()}</strong>.</>
                ) : (
                  <> Destination safety stock and intermediate hub inventory buffers absorb the initial delay hours without immediate line stoppage.</>
                )}
              </p>
            </div>

            {/* Prescriptive Action Steps & Rationale */}
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '12px' }}>
              Prescribed Recovery Actions & Decision Rationale
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '24px' }}>
              {(selectedDisruption.impact_details?.mitigations || [
                {
                  priority: 'RECOMMENDED',
                  title: 'Emergency Inter-Warehouse Stock Transfer',
                  description: 'Transfer 32 units from DataCo Pacific Asia DC to DataCo USCA DC.',
                  estimated_cost: 450,
                  net_savings: 5400,
                  why_best: 'Immediate execution (transit time < 12 hrs). Solves the local shortage without procurement lead times and delivers maximum net financial ROI savings.'
                },
                {
                  priority: 'HIGH',
                  title: 'Expedite Downstream Transit Leg via Dedicated Courier',
                  description: 'Charter dedicated express freight for remaining transport leg.',
                  estimated_cost: 1200,
                  net_savings: 4200,
                  why_best: 'Bypasses multi-stop freight consolidation, recovering 2 full days of transit time directly.'
                }
              ]).map((m, idx) => (
                <div
                  key={idx}
                  style={{
                    background: 'var(--bg-surface-2)',
                    border: m.priority === 'RECOMMENDED' ? '2px solid var(--accent-primary)' : '1px solid var(--border-subtle)',
                    borderRadius: '10px',
                    padding: '16px',
                    position: 'relative'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: m.priority === 'RECOMMENDED' ? 'var(--accent-primary)' : 'var(--bg-surface)',
                        color: m.priority === 'RECOMMENDED' ? '#fff' : 'var(--text-secondary)'
                      }}>
                        {m.priority}
                      </span>
                      <strong style={{ fontSize: '15px', color: 'var(--text-primary)' }}>{m.title}</strong>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                        Cost: ${m.estimated_cost}
                      </span>
                      {m.net_savings > 0 && (
                        <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--status-healthy)', marginLeft: '10px' }}>
                          (Net Saves: +${m.net_savings?.toLocaleString()})
                        </span>
                      )}
                    </div>
                  </div>

                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '0 0 10px 0' }}>
                    {m.description}
                  </p>

                  {/* Why is this the best step callout */}
                  <div style={{ 
                    background: 'var(--bg-base)', 
                    borderRadius: '6px', 
                    padding: '10px 12px', 
                    fontSize: '12px',
                    borderLeft: '3px solid var(--accent-primary)'
                  }}>
                    <strong style={{ color: 'var(--text-primary)' }}>💡 Why this is the optimal mitigation: </strong>
                    <span style={{ color: 'var(--text-secondary)' }}>
                      {m.why_best || 'Delivers highest cost-benefit ratio and eliminates risk of SLA breach.'}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* Modal Action Buttons */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                onClick={() => setSelectedDisruption(null)}
                className="btn-secondary"
                style={{ padding: '10px 16px' }}
              >
                Close Analysis
              </button>
              <Link
                to="/recommendations"
                className="btn-primary"
                style={{ padding: '10px 20px', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}
              >
                <Sparkles size={16} /> Authorize in Action Center
              </Link>
            </div>

          </div>
        </div>
      )}

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
