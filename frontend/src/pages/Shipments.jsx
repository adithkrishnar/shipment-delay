import { useEffect, useState } from 'react';
import { getShipments, getShipmentImpact } from '../services/api';
import Loader from '../components/Loader';
import RiskBadge from '../components/RiskBadge';
import Panel from '../components/Panel';
import React from 'react';

/* ── Risk tier to highlight class ────────────────────────────── */
function rowClass(tier) {
  const t = String(tier || '').toLowerCase();
  if (t === 'critical') return ' risk-row-critical';
  if (t === 'high')     return ' risk-row-high';
  return '';
}

/* ── Delay probability bar ───────────────────────────────────── */
function ProbBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  const color = pct >= 70 ? 'var(--status-critical)'
              : pct >= 40 ? 'var(--status-risk)'
              : pct >= 20 ? 'var(--status-watch)'
              : 'var(--status-healthy)';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{
        width: 72,
        height: 3,
        background: 'var(--bg-surface-3)',
        borderRadius: 999,
        overflow: 'hidden',
        flexShrink: 0,
      }}>
        <div style={{
          width: `${pct}%`,
          height: '100%',
          background: color,
          borderRadius: 999,
          transition: 'width 0.8s var(--ease-out)',
        }} />
      </div>
      <span style={{ fontSize: 12, fontVariantNumeric: 'tabular-nums', color: 'var(--text-primary)', fontWeight: 600 }}>
        {pct}%
      </span>
    </div>
  );
}

/* ── Risk distribution summary ────────────────────────────────── */
function RiskSummaryBar({ shipments }) {
  const counts = { low: 0, medium: 0, high: 0, critical: 0 };
  shipments.forEach(s => {
    const t = String(s.risk_tier || 'low').toLowerCase();
    if (counts[t] !== undefined) counts[t]++;
  });
  const total = shipments.length || 1;
  const items = [
    { key: 'low',      label: 'Low',      color: 'var(--status-healthy)',  bg: 'var(--status-healthy-bg)' },
    { key: 'medium',   label: 'Medium',   color: 'var(--status-watch)',    bg: 'var(--status-watch-bg)' },
    { key: 'high',     label: 'High',     color: 'var(--status-risk)',     bg: 'var(--status-risk-bg)' },
    { key: 'critical', label: 'Critical', color: 'var(--status-critical)', bg: 'var(--status-critical-bg)' },
  ];

  return (
    <div style={{
      display: 'flex',
      gap: 8,
      marginBottom: 16,
      flexWrap: 'wrap',
    }}>
      {items.map(({ key, label, color, bg }) => (
        <div key={key} style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          background: bg,
          border: `1px solid ${color}33`,
          borderRadius: 'var(--r-md)',
          padding: '6px 12px',
          flex: 1,
          minWidth: 100,
        }}>
          <span style={{ fontSize: 18, fontWeight: 800, fontVariantNumeric: 'tabular-nums', color, lineHeight: 1 }}>
            {counts[key]}
          </span>
          <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase', color }}>
            {label}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Shipments({ company }) {
  const [d, setD] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [impactData, setImpactData] = useState(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [error, setError] = useState(null);

  const load = () => {
    if (company) {
      setError(null);
      getShipments(company.id)
        .then(setD)
        .catch(e => {
          const detail = e.response?.data?.detail;
          setError(typeof detail === 'string' ? detail : (Array.isArray(detail) ? JSON.stringify(detail) : (e.message || "Failed to load shipments")));
        });
    }
  };

  useEffect(() => {
    load();
  }, [company]);

  const toggleRow = (id) => {
    if (expandedId === id) {
      setExpandedId(null);
      setImpactData(null);
    } else {
      setExpandedId(id);
      setImpactData(null);
      setImpactLoading(true);
      getShipmentImpact(company.id, id)
        .then(data => {
          setImpactData(data);
          setImpactLoading(false);
        })
        .catch(() => {
          setImpactLoading(false);
        });
    }
  };

  if (error) {
    return (
      <div className="page animate-fade">
        <div className="page-header">
          <div className="page-eyebrow">Shipment Intelligence</div>
          <h1 className="page-title">Predict disruption before arrival.</h1>
        </div>
        <Panel title="Error Loading Shipments">
          <div style={{ color: 'var(--status-critical)', padding: '20px 0' }}>
            <p style={{ marginBottom: 16 }}>{error}</p>
            <button className="primary" onClick={load}>Retry</button>
          </div>
        </Panel>
      </div>
    );
  }

  if (!d) return <Loader />;

  return (
    <div className="page animate-fade">
      <div className="page-header">
        <div className="page-eyebrow">Shipment Intelligence</div>
        <h1 className="page-title">Predict disruption before arrival.</h1>
        <p className="page-subtitle">
          {d.shipments.length} shipments monitored · Model: <strong style={{ color: 'var(--text-primary)' }}>{d.model_source}</strong>
        </p>
      </div>

      <RiskSummaryBar shipments={d.shipments} />

      <Panel title="Shipment register">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Shipment</th>
                <th>Route</th>
                <th>Carrier</th>
                <th>Delay probability</th>
                <th>Risk</th>
                <th>Expected delay</th>
              </tr>
            </thead>
            <tbody>
              {d.shipments.map(s => (
                <React.Fragment key={s.shipment_id}>
                  <tr 
                    className={rowClass(s.risk_tier)} 
                    style={{ cursor: 'pointer' }}
                    onClick={() => toggleRow(s.shipment_id)}
                  >
                    <td>
                      <strong>{s.external_shipment_id}</strong>
                      <small>{s.transport_mode}</small>
                    </td>
                    <td style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>
                      {s.origin} <span style={{ color: 'var(--text-muted)', margin: '0 4px' }}>→</span> {s.destination}
                    </td>
                    <td>{s.carrier || <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                    <td><ProbBar value={s.delay_probability} /></td>
                    <td><RiskBadge risk={s.risk_tier} /></td>
                    <td style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {s.expected_delay_days != null
                        ? <>{s.expected_delay_days}<span style={{ color: 'var(--text-tertiary)', fontWeight: 400, marginLeft: 2 }}>d</span></>
                        : <span style={{ color: 'var(--text-muted)' }}>—</span>
                      }
                    </td>
                  </tr>
                  {expandedId === s.shipment_id && (
                    <tr style={{ background: 'var(--bg-surface-2)' }}>
                      <td colSpan="6" style={{ padding: 0 }}>
                        <div style={{ padding: 24, borderTop: '1px solid var(--border-default)', borderBottom: '1px solid var(--border-default)' }}>
                          {impactLoading ? (
                            <div style={{ padding: 20, textAlign: 'center' }}><Loader /></div>
                          ) : impactData ? (
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
                              
                              <div style={{ gridColumn: '1 / -1', background: 'var(--bg-surface-3)', padding: 16, borderRadius: 8 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                                  <h4 style={{ fontSize: 14, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-primary)', margin: 0 }}>Live Intelligence</h4>
                                  <span style={{ 
                                    padding: '4px 8px', borderRadius: 4, fontSize: 11, fontWeight: 700,
                                    background: impactData.live_risk?.status === 'LIVE' ? 'var(--status-healthy-bg)' : impactData.live_risk?.status === 'PARTIAL' ? 'var(--status-watch-bg)' : 'var(--status-risk-bg)',
                                    color: impactData.live_risk?.status === 'LIVE' ? 'var(--status-healthy)' : impactData.live_risk?.status === 'PARTIAL' ? 'var(--status-watch)' : 'var(--status-risk)'
                                  }}>
                                    {impactData.live_risk?.status || 'OFFLINE'}
                                  </span>
                                </div>
                                
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginBottom: 16 }}>
                                  <div>
                                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>ML Probability</div>
                                    <div style={{ fontSize: 18, fontWeight: 600 }}>{(impactData.ml_prediction?.delay_probability * 100).toFixed(1)}%</div>
                                  </div>
                                  <div>
                                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Weather Risk</div>
                                    <div style={{ fontSize: 18, fontWeight: 600 }}>{impactData.live_intelligence?.weather?.weather_risk_tier || 'N/A'}</div>
                                  </div>
                                  <div>
                                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>News Risk</div>
                                    <div style={{ fontSize: 18, fontWeight: 600 }}>{impactData.live_intelligence?.news?.news_risk_tier || 'N/A'}</div>
                                  </div>
                                  <div style={{ borderLeft: '2px solid var(--border-default)', paddingLeft: 16 }}>
                                    <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>Live Risk Tier</div>
                                    <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--status-critical)' }}>{impactData.live_risk?.live_risk_tier || 'N/A'}</div>
                                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{(impactData.live_risk?.live_risk_score * 100).toFixed(1)}%</div>
                                  </div>
                                </div>
                                
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 16, borderTop: '1px solid var(--border-default)', paddingTop: 16 }}>
                                  <div>
                                    <h5 style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 8 }}>Weather Conditions ({impactData.live_intelligence?.weather?.source})</h5>
                                    {impactData.live_intelligence?.weather?.status === 'live' ? (
                                      <ul style={{ margin: 0, padding: 0, listStyle: 'none', fontSize: 12, color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                                        <li>Temp: {impactData.live_intelligence.weather.temperature}°C</li>
                                        <li>Wind: {impactData.live_intelligence.weather.wind_speed} km/h</li>
                                        <li>Precipitation: {impactData.live_intelligence.weather.precipitation} mm</li>
                                        <li>Prob: {impactData.live_intelligence.weather.precipitation_probability}%</li>
                                        <li style={{ color: 'var(--status-risk)' }}>{impactData.live_intelligence.weather.weather_explanation}</li>
                                      </ul>
                                    ) : (
                                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Weather unavailable</div>
                                    )}
                                  </div>
                                  <div>
                                    <h5 style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 8 }}>News & Disruptions</h5>
                                    {impactData.live_intelligence?.news?.status === 'live' ? (
                                      <ul style={{ margin: 0, padding: 0, listStyle: 'none', fontSize: 12, color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 4 }}>
                                        <li style={{ color: 'var(--status-risk)' }}>{impactData.live_intelligence.news.explanation}</li>
                                        {impactData.live_intelligence.news.articles?.slice(0, 2).map((art, idx) => (
                                          <li key={idx} style={{ marginTop: 4 }}>
                                            <a href={art.url} target="_blank" rel="noreferrer" style={{ color: 'var(--text-primary)', textDecoration: 'underline' }}>{art.title}</a>
                                            <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{art.source} · {art.disruption_category}</div>
                                          </li>
                                        ))}
                                      </ul>
                                    ) : (
                                      <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>News unavailable</div>
                                    )}
                                  </div>
                                </div>
                              </div>

                              <div>
                                <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', marginBottom: 12 }}>Inventory Impact</h4>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>Product</span>
                                    <strong style={{ color: 'var(--text-primary)' }}>{impactData.shipment?.product_name || `ID: ${impactData.shipment?.product_id}`}</strong>
                                  </div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>Current Inventory</span>
                                    <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{impactData.inventory_impact?.inventory_level}</span>
                                  </div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>Stockout Probability</span>
                                    <span style={{ fontWeight: 600, color: 'var(--status-critical)' }}>{(impactData.inventory_impact?.stockout_probability * 100).toFixed(1)}%</span>
                                  </div>
                                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <span style={{ color: 'var(--text-secondary)' }}>Expected Shortage</span>
                                    <span style={{ fontWeight: 600, color: 'var(--status-critical)' }}>{impactData.inventory_impact?.expected_shortage} units</span>
                                  </div>
                                </div>
                              </div>
                              
                              <div>
                                <h4 style={{ fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', marginBottom: 12 }}>Recommended Action</h4>
                                <div style={{ 
                                  padding: 16, 
                                  background: 'var(--status-risk-bg)', 
                                  border: '1px solid var(--status-risk-border)', 
                                  borderRadius: 8,
                                  color: 'var(--status-risk)',
                                  fontWeight: 500,
                                  lineHeight: 1.5
                                }}>
                                  {impactData.recommended_action}
                                </div>
                              </div>
                            </div>
                          ) : (
                            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 20 }}>Failed to load impact data.</div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
