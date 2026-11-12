import React, { useState, useEffect } from 'react';
import { 
  MapContainer, 
  TileLayer, 
  Marker, 
  Popup, 
  Polyline, 
  Tooltip,
  CircleMarker
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix default leaflet icons
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

// Custom Node Icon Generators
const createPillIcon = (label: string, color: string, iconChar: string) => {
  return L.divIcon({
    className: 'custom-map-node',
    html: `
      <div style="
        background: #0f172a;
        border: 2px solid ${color};
        box-shadow: 0 0 10px ${color};
        color: #f8fafc;
        padding: 4px 8px;
        border-radius: 6px;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        font-size: 11px;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 5px;
        white-space: nowrap;
        position: absolute;
        transform: translate(-50%, -50%);
        pointer-events: auto;
      ">
        <span>${iconChar}</span>
        <span>${label}</span>
      </div>
    `,
    iconSize: [120, 26],
    iconAnchor: [60, 13]
  });
};

interface NetworkMapModalProps {
  isOpen: boolean;
  onClose: () => void;
  companyId?: number;
  highlightShipmentRef?: string;
}

export default function NetworkMapModal({ isOpen, onClose, companyId = 17, highlightShipmentRef }: NetworkMapModalProps) {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'all' | 'shipments' | 'rebalance'>('all');
  const [selectedRoute, setSelectedRoute] = useState<any>(null);

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    const token = localStorage.getItem('token');
    fetch(`http://127.0.0.1:8000/api/network-map/${companyId}`, {
      headers: {
        'Authorization': token ? `Bearer ${token}` : ''
      }
    })
      .then(res => res.json())
      .then(json => {
        setData(json);
        setLoading(false);
        if (highlightShipmentRef && json.shipment_routes) {
          const match = json.shipment_routes.find((r: any) => r.reference === highlightShipmentRef);
          if (match) setSelectedRoute(match);
        }
      })
      .catch(err => {
        console.error('Failed to load network map data:', err);
        setLoading(false);
      });
  }, [isOpen, companyId, highlightShipmentRef]);

  if (!isOpen) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 9999,
      background: 'rgba(5, 10, 20, 0.88)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px'
    }}>
      <div style={{
        width: '95vw',
        maxWidth: '1440px',
        height: '88vh',
        background: '#0d131f',
        border: '1px solid #1e293b',
        borderRadius: '16px',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.8)',
        overflow: 'hidden'
      }}>
        {/* Header Bar */}
        <div style={{
          padding: '16px 24px',
          background: '#090e17',
          borderBottom: '1px solid #1e293b',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{
              width: '36px',
              height: '36px',
              borderRadius: '10px',
              background: '#2563eb',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '18px'
            }}>
              🌐
            </div>
            <div>
              <div style={{ fontSize: '17px', fontWeight: 700, color: '#f8fafc', letterSpacing: '-0.01em' }}>
                Global Multimodal Corridor & Warehouse Mesh
              </div>
              <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                Real-time satellite & intermodal telemetry • Live Open-Meteo weather • Autonomous stock rebalancing
              </div>
            </div>
          </div>

          {/* Layer Filter Pills */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => setActiveTab('all')}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 600,
                border: '1px solid',
                borderColor: activeTab === 'all' ? '#3b82f6' : '#1e293b',
                background: activeTab === 'all' ? '#1d4ed8' : '#0f172a',
                color: '#fff',
                cursor: 'pointer'
              }}
            >
              All Layers
            </button>
            <button
              onClick={() => setActiveTab('shipments')}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 600,
                border: '1px solid',
                borderColor: activeTab === 'shipments' ? '#06b6d4' : '#1e293b',
                background: activeTab === 'shipments' ? '#0891b2' : '#0f172a',
                color: '#fff',
                cursor: 'pointer'
              }}
            >
              Multimodal Shipments
            </button>
            <button
              onClick={() => setActiveTab('rebalance')}
              style={{
                padding: '6px 14px',
                borderRadius: '8px',
                fontSize: '12px',
                fontWeight: 600,
                border: '1px solid',
                borderColor: activeTab === 'rebalance' ? '#eab308' : '#1e293b',
                background: activeTab === 'rebalance' ? '#ca8a04' : '#0f172a',
                color: '#fff',
                cursor: 'pointer'
              }}
            >
              ⚡ Rebalance Transfers ({data?.rebalancing_links?.length || 0})
            </button>
            <button
              onClick={onClose}
              style={{
                marginLeft: '12px',
                background: '#1e293b',
                border: 'none',
                color: '#94a3b8',
                borderRadius: '8px',
                width: '32px',
                height: '32px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                fontSize: '16px'
              }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Map Container Body */}
        <div style={{ flex: 1, position: 'relative' }}>
          {loading ? (
            <div style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#94a3b8',
              gap: '12px'
            }}>
              <div style={{ fontSize: '24px' }}>📡</div>
              <div>Acquiring global telemetry & resolving satellite corridors...</div>
            </div>
          ) : (
            <MapContainer
              center={[32.0, 10.0]}
              zoom={2.5}
              minZoom={2}
              maxZoom={8}
              style={{ height: '100%', width: '100%', background: '#090d16' }}
            >
              {/* Truly Free OpenStreetMap Dark Matter / Standard Tiles with No API Key */}
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                className="dark-map-tiles"
              />

              {/* 1. Warehouse Nodes */}
              {data?.warehouses?.map((wh: any) => (
                <React.Fragment key={`wh-grp-${wh.id}`}>
                  <CircleMarker
                    center={[wh.lat, wh.lon]}
                    radius={8}
                    pathOptions={{
                      color: wh.health_color || '#3b82f6',
                      fillColor: wh.health_color || '#3b82f6',
                      fillOpacity: 0.9,
                      weight: 2
                    }}
                  />
                  <Marker
                    position={[wh.lat, wh.lon]}
                    icon={createPillIcon(wh.name, wh.health_color, '🏢')}
                  >
                    <Popup className="dark-popup">
                      <div style={{ padding: '8px', color: '#0f172a', minWidth: '220px' }}>
                        <div style={{ fontSize: '13px', fontWeight: 700, marginBottom: '4px' }}>{wh.name}</div>
                        <div style={{ fontSize: '11px', color: '#64748b', marginBottom: '8px' }}>Region: {wh.region} • {wh.country}</div>
                        
                        <div style={{ background: '#f8fafc', padding: '8px', borderRadius: '6px', marginBottom: '8px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '4px' }}>
                            <span>Current Stock:</span>
                            <strong>{wh.total_stock_units} units</strong>
                          </div>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
                            <span>Target Safety Stock:</span>
                            <strong>{wh.safety_stock_units} units</strong>
                          </div>
                        </div>

                        {wh.weather && (
                          <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: '6px', padding: '6px', fontSize: '11px' }}>
                            <div><strong>🌦️ Live Weather:</strong> {wh.weather.condition} ({wh.weather.temperature_c}°C)</div>
                            <div style={{ color: '#1e40af', marginTop: '2px' }}>Wind: {wh.weather.windspeed_kmh} km/h • <em>{wh.weather.risk_factor}</em></div>
                          </div>
                        )}
                      </div>
                    </Popup>
                  </Marker>
                </React.Fragment>
              ))}

              {/* 2. Supplier Nodes */}
              {data?.suppliers?.map((sup: any) => (
                <React.Fragment key={`sup-grp-${sup.id}`}>
                  <CircleMarker
                    center={[sup.lat, sup.lon]}
                    radius={6}
                    pathOptions={{
                      color: '#8b5cf6',
                      fillColor: '#8b5cf6',
                      fillOpacity: 0.9,
                      weight: 2
                    }}
                  />
                  <Marker
                    position={[sup.lat, sup.lon]}
                    icon={createPillIcon(sup.name, '#8b5cf6', '🏭')}
                  >
                    <Popup>
                      <div style={{ padding: '6px', color: '#0f172a' }}>
                        <div style={{ fontWeight: 700 }}>{sup.name}</div>
                        <div style={{ fontSize: '11px', color: '#64748b' }}>Tier-1 Component Manufacturer</div>
                        <div style={{ fontSize: '11px', marginTop: '4px' }}>Reliability Rating: <strong>{(sup.reliability * 100).toFixed(0)}%</strong></div>
                        <div style={{ fontSize: '11px' }}>Lead Time: <strong>{sup.lead_time_days} days</strong></div>
                      </div>
                    </Popup>
                  </Marker>
                </React.Fragment>
              ))}

              {/* 3. Inter-Warehouse Rebalancing Links (Network Self-Healing) */}
              {(activeTab === 'all' || activeTab === 'rebalance') && data?.rebalancing_links?.map((link: any) => (
                <React.Fragment key={link.link_id}>
                  <Polyline
                    positions={[
                      [link.source_lat, link.source_lon],
                      [link.dest_lat, link.dest_lon]
                    ]}
                    pathOptions={{
                      color: '#eab308',
                      weight: 4,
                      dashArray: '10, 10',
                      opacity: 0.85
                    }}
                  >
                    <Tooltip sticky>
                      <div style={{ padding: '6px' }}>
                        <div style={{ fontWeight: 700, color: '#ca8a04' }}>⚡ Autonomous Rebalance Link</div>
                        <div style={{ fontSize: '11px' }}>Transfer: <strong>{link.transfer_units} units</strong></div>
                        <div style={{ fontSize: '11px' }}>From: {link.source_name} ➔ {link.dest_name}</div>
                        <div style={{ fontSize: '11px', color: '#16a34a' }}>Est Savings: <strong>${link.estimated_savings_usd.toLocaleString()}</strong></div>
                      </div>
                    </Tooltip>
                  </Polyline>
                </React.Fragment>
              ))}

              {/* 4. Multimodal Shipment Legs */}
              {(activeTab === 'all' || activeTab === 'shipments') && data?.shipment_routes?.map((shp: any) => (
                shp.legs?.map((leg: any) => {
                  const isAir = leg.mode === 'AIR';
                  const isSea = leg.mode === 'SEA';
                  const isRail = leg.mode === 'RAIL';
                  
                  let strokeColor = '#10b981'; // Green on schedule
                  if (leg.is_delayed) strokeColor = '#ef4444'; // Red delayed
                  else if (isAir) strokeColor = '#06b6d4'; // Cyan Air
                  else if (isSea) strokeColor = '#3b82f6'; // Blue Sea
                  else if (isRail) strokeColor = '#f97316'; // Orange Rail

                  return (
                    <Polyline
                      key={`leg-${leg.leg_id}`}
                      positions={[
                        [leg.origin_lat, leg.origin_lon],
                        [leg.dest_lat, leg.dest_lon]
                      ]}
                      pathOptions={{
                        color: strokeColor,
                        weight: leg.is_delayed ? 4 : 2.5,
                        dashArray: isAir ? '6, 8' : (isSea ? '4, 4' : undefined),
                        opacity: leg.is_delayed ? 0.95 : 0.65
                      }}
                    >
                      <Tooltip sticky>
                        <div style={{ padding: '4px' }}>
                          <div><strong>Shipment:</strong> {shp.reference}</div>
                          <div><strong>Leg #{leg.sequence}:</strong> {leg.mode} ({leg.origin_name} ➔ {leg.destination_name})</div>
                          <div><strong>Status:</strong> {leg.is_delayed ? `⚠️ DELAYED (+${leg.delay_hours}h)` : 'ON SCHEDULE'}</div>
                          <div><strong>Distance:</strong> {leg.distance_km} km</div>
                        </div>
                      </Tooltip>
                    </Polyline>
                  );
                })
              ))}
            </MapContainer>
          )}

          {/* Floating Map Legend */}
          <div style={{
            position: 'absolute',
            bottom: '24px',
            left: '24px',
            background: 'rgba(15, 23, 42, 0.92)',
            border: '1px solid #1e293b',
            borderRadius: '10px',
            padding: '12px 16px',
            fontSize: '11px',
            color: '#cbd5e1',
            zIndex: 1000,
            boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            <div style={{ fontWeight: 700, color: '#f8fafc', marginBottom: '2px' }}>NETWORK TOPOLOGY LEGEND</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#ef4444' }}></span>
              <span>Warehouse: Critical Deficit (Stockout Risk)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: '#10b981' }}></span>
              <span>Warehouse: Healthy Surplus Stock</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '18px', height: '3px', background: '#eab308', borderBottom: '2px dashed #ca8a04' }}></span>
              <span>Autonomous Rebalance Transfer (Surplus ➔ Deficit)</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '18px', height: '3px', background: '#06b6d4', borderBottom: '2px dashed #0891b2' }}></span>
              <span>✈️ Air Cargo Linehaul</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '18px', height: '3px', background: '#3b82f6' }}></span>
              <span>🚢 Maritime Ocean Freight</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '18px', height: '3px', background: '#f97316' }}></span>
              <span>🚆 Intermodal Rail</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ width: '18px', height: '3px', background: '#10b981' }}></span>
              <span>🚛 Highway Drayage</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

