import React from "react";
import { Shipment, ShipmentLeg } from "../../types/transporter";
import { StatusBadge, TransportModeBadge } from "./TransporterBadges";
import { formatDateTime } from "../../utils/delayPropagation";
import { MapPin, AlertOctagon, Clock, CheckCircle2, ShieldAlert } from "lucide-react";

interface RouteTimelineProps {
  shipment: Shipment;
  onReportLeg: (leg: ShipmentLeg) => void;
}

export function RouteTimeline({ shipment, onReportLeg }: RouteTimelineProps) {
  const legs = shipment.legs || [];

  return (
    <div className="route-timeline-container" style={{ position: "relative" }}>
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {legs.map((leg, index) => {
          const isDelayed = (leg.delayHours || 0) > 0;
          const isAssigned = leg.isCarrierAssigned;
          const hasMissedConnection = leg.connection?.missed;

          return (
            <div
              key={leg.id}
              className="leg-timeline-card"
              style={{
                position: "relative",
                padding: "16px",
                borderRadius: "var(--r-lg, 8px)",
                background: isDelayed
                  ? "rgba(255, 77, 95, 0.04)"
                  : "var(--bg-surface-2, #19222D)",
                border: isDelayed
                  ? "1px solid rgba(255, 77, 95, 0.35)"
                  : "1px solid var(--border-subtle, #26313D)",
                boxShadow: isDelayed ? "0 2px 8px rgba(255, 77, 95, 0.1)" : "none",
              }}
            >
              {/* Header: Leg Sequence, Mode, Status, Carrier Scope Badge */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  flexWrap: "wrap",
                  gap: "8px",
                  marginBottom: "12px",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <span
                    style={{
                      width: "24px",
                      height: "24px",
                      borderRadius: "50%",
                      background: isDelayed ? "#FF4D5F" : "var(--accent-primary, #4F8CFF)",
                      color: "#fff",
                      fontSize: "12px",
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {leg.sequence}
                  </span>
                  <strong style={{ fontSize: "14px", color: "var(--text-primary, #F3F6FA)" }}>
                    Leg #{leg.sequence}: {leg.mode.toUpperCase()} Transit
                  </strong>
                  <TransportModeBadge mode={leg.mode} />

                  {isAssigned && (
                    <span
                      style={{
                        fontSize: "10px",
                        fontWeight: 700,
                        padding: "2px 6px",
                        borderRadius: "4px",
                        background: "rgba(79, 140, 255, 0.15)",
                        color: "var(--accent-primary, #4F8CFF)",
                        border: "1px solid rgba(79, 140, 255, 0.3)",
                      }}
                    >
                      ★ Assigned to Your Fleet
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <StatusBadge status={leg.status} />
                  {isAssigned && leg.status !== "on_schedule" && (
                    <button
                      onClick={() => onReportLeg(leg)}
                      className="btn-secondary"
                      style={{
                        padding: "3px 8px",
                        fontSize: "11px",
                        fontWeight: 600,
                        color: "#FF8C42",
                        border: "1px solid rgba(255, 140, 66, 0.4)",
                      }}
                    >
                      Update Telematics
                    </button>
                  )}
                </div>
              </div>

              {/* Waypoints & Operating Carrier */}
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
                  gap: "12px",
                  fontSize: "12px",
                  marginBottom: "12px",
                  paddingBottom: "12px",
                  borderBottom: "1px solid var(--border-subtle, #26313D)",
                }}
              >
                <div>
                  <span style={{ color: "var(--text-tertiary, #6F7C8C)", fontSize: "11px", display: "block" }}>
                    ORIGIN WAYPOINT
                  </span>
                  <strong style={{ color: "var(--text-primary, #F3F6FA)", fontSize: "13px" }}>
                    {leg.origin}
                  </strong>
                  <div style={{ color: "var(--text-secondary, #A8B3C2)", marginTop: "2px" }}>
                    Dept: {formatDateTime(leg.plannedDeparture)}
                  </div>
                </div>

                <div>
                  <span style={{ color: "var(--text-tertiary, #6F7C8C)", fontSize: "11px", display: "block" }}>
                    DESTINATION WAYPOINT
                  </span>
                  <strong style={{ color: "var(--text-primary, #F3F6FA)", fontSize: "13px" }}>
                    {leg.destination}
                  </strong>
                  <div style={{ color: isDelayed ? "#FF8C42" : "var(--text-secondary, #A8B3C2)", marginTop: "2px", fontWeight: isDelayed ? 600 : 400 }}>
                    Arrival: {formatDateTime(leg.revisedArrival || leg.plannedArrival)}
                    {isDelayed && ` (+${leg.delayHours}h)`}
                  </div>
                </div>

                <div>
                  <span style={{ color: "var(--text-tertiary, #6F7C8C)", fontSize: "11px", display: "block" }}>
                    OPERATING CARRIER
                  </span>
                  <span style={{ color: "var(--text-primary, #F3F6FA)", fontWeight: 600 }}>
                    {leg.carrierName}
                  </span>
                  {leg.currentLocation && (
                    <div style={{ color: "var(--text-secondary, #A8B3C2)", marginTop: "2px", display: "flex", alignItems: "center", gap: "4px" }}>
                      <MapPin size={11} color="var(--accent-primary, #4F8CFF)" />
                      {leg.currentLocation}
                    </div>
                  )}
                </div>
              </div>

              {/* Connection Cutoff / Intermodal Gate Card (if configured) */}
              {leg.connection && (
                <div
                  style={{
                    background: hasMissedConnection
                      ? "rgba(255, 77, 95, 0.08)"
                      : "var(--bg-surface-3, #111720)",
                    border: hasMissedConnection
                      ? "1px solid rgba(255, 77, 95, 0.4)"
                      : "1px solid var(--border-subtle, #26313D)",
                    borderRadius: "6px",
                    padding: "10px 14px",
                    fontSize: "12px",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      {hasMissedConnection ? (
                        <AlertOctagon size={14} color="#FF4D5F" />
                      ) : (
                        <Clock size={14} color="var(--accent-primary, #4F8CFF)" />
                      )}
                      <strong style={{ color: hasMissedConnection ? "#FF4D5F" : "var(--text-primary, #F3F6FA)" }}>
                        {leg.connection.name || `${leg.connection.type.replace("_", " ").toUpperCase()} WINDOW`}
                      </strong>
                    </div>

                    <span
                      style={{
                        fontSize: "11px",
                        fontWeight: 700,
                        padding: "2px 6px",
                        borderRadius: "4px",
                        background: hasMissedConnection ? "#FF4D5F" : "rgba(45, 212, 167, 0.15)",
                        color: hasMissedConnection ? "#fff" : "#2DD4A7",
                      }}
                    >
                      {hasMissedConnection ? "MISSED CONNECTION" : "CONNECTION SECURE"}
                    </span>
                  </div>

                  <div style={{ marginTop: "6px", color: "var(--text-secondary, #A8B3C2)", display: "flex", gap: "16px", flexWrap: "wrap" }}>
                    <span>
                      Cut-off deadline: <strong>{formatDateTime(leg.connection.cutoffTime)}</strong>
                    </span>
                    {hasMissedConnection && leg.connection.nextAvailableSlot && (
                      <span style={{ color: "#FF8C42" }}>
                        Next Departure Slot: <strong>{formatDateTime(leg.connection.nextAvailableSlot)}</strong> (+{leg.connection.penaltyHours}h cycle lag)
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

