import React, { useState, useEffect } from 'react';
import { 
  Truck, AlertTriangle, Clock, MapPin, CheckCircle2, ChevronRight, 
  ArrowRight, ShieldAlert, Sparkles, Send, RefreshCw, Layers, DollarSign 
} from 'lucide-react';
import { getAssignedShipments, reportLegDisruption, getRecentDisruptions } from '../services/api';
import { useAuth } from '../auth/AuthContext';

export default function TransporterPortal() {
  const { user } = useAuth();
  const [shipments, setShipments] = useState([]);
  const [selectedShipment, setSelectedShipment] = useState(null);
  const [selectedLeg, setSelectedLeg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [recentDisruptions, setRecentDisruptions] = useState([]);

  // Form inputs
  const [delayValue, setDelayValue] = useState(1);
  const [delayUnit, setDelayUnit] = useState('days'); // 'days' or 'hours'
  const [reason, setReason] = useState('Vehicle Breakdown');
  const [notes, setNotes] = useState('');
  
  // Real-time calculated simulation feedback
  const [simulationResult, setSimulationResult] = useState(null);
  const [successMsg, setSuccessMsg] = useState('');
  const [errMsg, setErrMsg] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      const [shipmentsData, disruptionsData] = await Promise.all([
        getAssignedShipments(),
        getRecentDisruptions()
      ]);
      setShipments(shipmentsData);
      setRecentDisruptions(disruptionsData);
      if (shipmentsData.length > 0 && !selectedShipment) {
        setSelectedShipment(shipmentsData[0]);
        if (shipmentsData[0].legs?.length > 0) {
          setSelectedLeg(shipmentsData[0].legs[0]);
        }
      }
    } catch (err) {
      setErrMsg(err.response?.data?.detail || err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSelectShipment = (s) => {
    setSelectedShipment(s);
    setSimulationResult(null);
    setSuccessMsg('');
    setErrMsg('');
    if (s.legs?.length > 0) {
      setSelectedLeg(s.legs[0]);
    }
  };

  const handleSubmitDisruption = async (e) => {
    e.preventDefault();
    if (!selectedShipment || !selectedLeg) return;

    try {
      setSubmitting(true);
      setErrMsg('');
      setSuccessMsg('');
      const calculatedHours = delayUnit === 'days' ? Number(delayValue) * 24 : Number(delayValue);
      const res = await reportLegDisruption(selectedShipment.id, selectedLeg.id, {
        delay_hours: calculatedHours,
        disruption_reason: reason,
        notes: notes || undefined
      });

      setSimulationResult(res);
      setSuccessMsg(`Disruption logged! Simulated cumulative delay: +${res.total_delay_days} days (${res.total_delay_hours} hrs) across downstream legs.`);
      
      // Refresh list to update status indicators
      const updatedShipments = await getAssignedShipments();
      setShipments(updatedShipments);
      const found = updatedShipments.find(x => x.id === selectedShipment.id);
      if (found) {
        setSelectedShipment(found);
        const lFound = found.legs.find(l => l.id === selectedLeg.id);
        if (lFound) setSelectedLeg(lFound);
      }

      const disruptionsData = await getRecentDisruptions();
      setRecentDisruptions(disruptionsData);
    } catch (err) {
      setErrMsg(err.response?.data?.detail || err.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="page" style={{ padding: '32px', textAlign: 'center' }}>
        <div className="spinner" style={{ margin: '40px auto' }} />
        <p style={{ color: 'var(--text-secondary)' }}>Loading Transporter Operations Control Tower...</p>
      </div>
    );
  }

  return (
    <div className="page" style={{ padding: '24px 32px' }}>
      {/* Header Banner */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
            <div style={{ 
              background: 'linear-gradient(135deg, #2563eb, #1d4ed8)', 
              color: '#fff', 
              padding: '6px 10px', 
              borderRadius: '8px', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '6px',
              fontSize: '12px',
              fontWeight: 600,
              letterSpacing: '0.04em'
            }}>
              <Truck size={14} /> CARRIER COLLABORATIVE PORTAL
            </div>
            {user?.carrier_name && (
              <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                {user.carrier_name}
              </span>
            )}
          </div>
          <h1 style={{ fontSize: '26px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
            Multi-Leg Transit & Exception Reporting
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginTop: '4px' }}>
            Log transit disruptions across Road, Rail, Sea, or Air legs. SupplyIQ automatically propagates compounding schedule delays and calculates real-time inventory risk.
          </p>
        </div>

        <button 
          onClick={loadData} 
          className="btn-secondary" 
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <RefreshCw size={14} /> Refresh Corridors
        </button>
      </div>

      {errMsg && (
        <div style={{ 
          background: 'rgba(239, 68, 68, 0.1)', 
          border: '1px solid rgba(239, 68, 68, 0.3)', 
          color: '#ef4444', 
          padding: '12px 16px', 
          borderRadius: '8px', 
          marginBottom: '20px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px'
        }}>
          <AlertTriangle size={18} /> {errMsg}
        </div>
      )}

      {/* Main Grid: Shipments List (Left) + Detail & Exception Form (Right) */}
      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '24px' }}>
        
        {/* Left Column: Assigned Shipments */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', margin: '0 0 4px 0' }}>
            Assigned Intermodal Shipments ({shipments.length})
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '720px', overflowY: 'auto' }}>
            {shipments.map(s => {
              const isSelected = selectedShipment?.id === s.id;
              const hasDelayedLeg = s.legs?.some(l => l.delay_hours > 0);

              return (
                <div
                  key={s.id}
                  onClick={() => handleSelectShipment(s)}
                  style={{
                    background: isSelected ? 'var(--bg-surface-2)' : 'var(--bg-surface)',
                    border: isSelected ? '2px solid var(--accent-primary, #2563eb)' : '1px solid var(--border-subtle)',
                    borderRadius: '10px',
                    padding: '14px 16px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)' }}>
                      {s.external_shipment_id}
                    </span>
                    <span style={{ 
                      fontSize: '11px', 
                      fontWeight: 600, 
                      padding: '2px 8px', 
                      borderRadius: '12px',
                      background: hasDelayedLeg ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                      color: hasDelayedLeg ? '#ef4444' : '#10b981'
                    }}>
                      {hasDelayedLeg ? 'DISRUPTED' : 'ON SCHEDULE'}
                    </span>
                  </div>

                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <MapPin size={12} /> {s.origin || 'Origin'} <ArrowRight size={10} /> {s.destination || 'Destination'}
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '10px', fontSize: '11px', color: 'var(--text-tertiary)' }}>
                    <span>Primary Mode: <strong>{s.transport_mode || 'ROAD'}</strong></span>
                    <span>Legs: <strong>{s.legs?.length || 3}</strong></span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Leg Details, Exception Submission & Live Simulation */}
        {selectedShipment ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            
            {/* Shipment Overview Card */}
            <div style={{ 
              background: 'var(--bg-surface)', 
              border: '1px solid var(--border-subtle)', 
              borderRadius: '12px', 
              padding: '20px' 
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div>
                  <h3 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                    Intermodal Route: {selectedShipment.external_shipment_id}
                  </h3>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                    Carrier: {selectedShipment.carrier || 'Assigned Logistics'} | Mode: {selectedShipment.transport_mode} | Planned Delivery: {selectedShipment.planned_delivery}
                  </p>
                </div>
              </div>

              {/* Multimodal Legs Visual Stepper */}
              <div style={{ display: 'grid', gridTemplateColumns: `repeat(${selectedShipment.legs?.length || 3}, 1fr)`, gap: '12px' }}>
                {selectedShipment.legs?.map((leg) => {
                  const isLegSelected = selectedLeg?.id === leg.id;
                  const isDelayed = leg.delay_hours > 0;

                  return (
                    <div
                      key={leg.id}
                      onClick={() => { setSelectedLeg(leg); setSimulationResult(null); }}
                      style={{
                        padding: '12px',
                        borderRadius: '8px',
                        border: isLegSelected ? '2px solid #2563eb' : '1px solid var(--border-subtle)',
                        background: isLegSelected ? 'rgba(37, 99, 235, 0.05)' : 'var(--bg-surface-2)',
                        cursor: 'pointer',
                        position: 'relative'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                        <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-tertiary)' }}>
                          LEG #{leg.sequence}
                        </span>
                        <span style={{ 
                          fontSize: '10px', 
                          fontWeight: 700, 
                          padding: '1px 6px', 
                          borderRadius: '4px',
                          background: isDelayed ? '#ef4444' : '#10b981',
                          color: '#fff'
                        }}>
                          {leg.mode}
                        </span>
                      </div>

                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
                        {leg.carrier_name || 'Carrier Fleet'}
                      </div>

                      <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        {leg.origin?.split('(')[0]} <br />↳ {leg.destination?.split('(')[0]}
                      </div>

                      <div style={{ marginTop: '8px', fontSize: '11px', fontWeight: 600, color: isDelayed ? '#ef4444' : 'var(--text-tertiary)' }}>
                        {isDelayed ? `⚠️ +${leg.delay_hours}h delay` : `⏱️ ${leg.expected_duration_hrs}h scheduled`}
                      </div>

                      {leg.missed_connection_dwell_hrs > 0 && (
                        <div style={{ fontSize: '10px', color: '#f59e0b', marginTop: '4px', fontWeight: 600 }}>
                          🛑 Missed cut-off (+{leg.missed_connection_dwell_hrs}h)
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Disruption Form */}
            {selectedLeg && (
              <div style={{ 
                background: 'var(--bg-surface)', 
                border: '1px solid var(--border-subtle)', 
                borderRadius: '12px', 
                padding: '20px' 
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                  <AlertTriangle size={18} color="#f59e0b" />
                  <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>
                    Report Disruption on Leg #{selectedLeg.sequence} ({selectedLeg.mode} - {selectedLeg.carrier_name})
                  </h3>
                </div>

                <form onSubmit={handleSubmitDisruption}>
                  <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '16px', marginBottom: '16px' }}>
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                        Delay Duration
                      </label>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <input
                          type="number"
                          step="0.5"
                          min="0.5"
                          max="365"
                          value={delayValue}
                          onChange={(e) => setDelayValue(e.target.value)}
                          required
                          className="input"
                          style={{ flex: 1, padding: '8px 12px', borderRadius: '6px' }}
                        />
                        <select
                          value={delayUnit}
                          onChange={(e) => setDelayUnit(e.target.value)}
                          className="input"
                          style={{ width: '100px', padding: '8px 10px', borderRadius: '6px', background: 'var(--bg-surface-2)', fontWeight: 600 }}
                        >
                          <option value="days">Days</option>
                          <option value="hours">Hours</option>
                        </select>
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-tertiary)', marginTop: '4px' }}>
                        {delayUnit === 'days' ? `≈ ${(Number(delayValue) * 24).toFixed(0)} hours transit disruption` : `≈ ${(Number(delayValue) / 24).toFixed(1)} days`}
                      </div>
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                        Primary Disruption Reason
                      </label>
                      <select
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        className="input"
                        style={{ width: '100%', padding: '8px 12px', borderRadius: '6px' }}
                      >
                        <option value="Vehicle Breakdown">Vehicle Breakdown / Engine Fault</option>
                        <option value="Port Congestion / Berth Waiting">Port Congestion / Berth Waiting</option>
                        <option value="Customs Clearance Hold">Customs Clearance / Inspection Hold</option>
                        <option value="Severe Weather / Fog / Storm">Severe Weather / Fog / Storm</option>
                        <option value="Highway Route Blockage / Accident">Highway Route Blockage / Accident</option>
                        <option value="Rail Track Maintenance / Signal Failure">Rail Track Maintenance / Signal Failure</option>
                      </select>
                    </div>
                  </div>

                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px', color: 'var(--text-secondary)' }}>
                      Field Notes / Driver Telematics
                    </label>
                    <textarea
                      rows={2}
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                      placeholder="e.g. Broken axle on highway NH-48. Mechanic vehicle deployed, estimated repair by 18:00 hrs."
                      className="input"
                      style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', resize: 'vertical' }}
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={submitting}
                    className="btn-primary"
                    style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 18px', fontWeight: 600 }}
                  >
                    <Send size={15} /> {submitting ? 'Transmitting Exception Telematics...' : 'Broadcast Delay to Company Control Tower'}
                  </button>
                </form>

                {/* Transporter confirmation toast */}
                {successMsg && (
                  <div style={{
                    marginTop: '16px',
                    background: 'rgba(16, 185, 129, 0.1)',
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    color: '#10b981',
                    padding: '14px 18px',
                    borderRadius: '8px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px'
                  }}>
                    <CheckCircle2 size={18} />
                    <div>
                      <strong>Exception Broadcasted Successfully:</strong>
                      <div style={{ fontSize: '13px', marginTop: '2px', color: 'var(--text-secondary)' }}>
                        {successMsg} The company's operations dashboard has received real-time inventory risk calculations and mitigation options.
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Note: The Transporter Portal ONLY submits transit exceptions. Downstream stockout loss and business mitigations are sent directly to the Company Dashboard. */}
          </div>
        ) : (
          <div style={{ background: 'var(--bg-surface)', borderRadius: '12px', padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            Select a shipment on the left to view multimodal legs and log transit telemetry.
          </div>
        )}

      </div>
    </div>
  );
}

