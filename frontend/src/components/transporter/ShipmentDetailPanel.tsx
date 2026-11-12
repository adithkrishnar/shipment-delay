import React from "react";
import { Shipment, ShipmentLeg } from "../../types/transporter";
import { StatusBadge, RiskBadge, TransportModeBadge, ServiceLevelBadge } from "./TransporterBadges";
import { RouteTimeline } from "./RouteTimeline";
import { formatDateTime } from "../../utils/delayPropagation";
import { AlertTriangle, Clock, MapPin, Building, ShieldCheck, ChevronRight, Bell, History } from "lucide-react";

interface ShipmentDetailPanelProps {
  shipment: Shipment;
  onOpenReportModal: (legId?: string) => void;
  onOpenDelayModal?: () => void;
  onClose?: () => void;
}

export function ShipmentDetailPanel({
  shipment,
  onOpenReportModal,
  onOpenDelayModal,
  onClose,
}: ShipmentDetailPanelProps) {
  const activeLeg = shipment.legs.find((l) => l.status !== "on_schedule") || shipment.legs[0];
  const hasExceptions = shipment.exceptions && shipment.exceptions.length > 0;

  return (
    <div
      className="shipment-detail-panel"
      style={{
        background: "var(--bg-surface-1, #151C24)",
        border: "1px solid var(--border-subtle, #26313D)",
        borderRadius: "var(--r-xl, 10px)",
        padding: "24px",
        boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
      }}
    >
      {/* Panel Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          paddingBottom: "18px",
          borderBottom: "1px solid var(--border-subtle, #26313D)",
          marginBottom: "20px",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
            <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-tertiary, #6F7C8C)", textTransform: "uppercase" }}>
              Shipment Dossier
            </span>
            <span style={{ fontSize: "11px", color: "var(--text-muted, #6F7C8C)" }}>•</span>
            <span style={{ fontSize: "12px", color: "var(--text-secondary, #A8B3C2)", fontWeight: 600 }}>
              Destination: {shipment.destinationFacility}
            </span>
          </div>

          <h2 style={{ fontSize: "22px", fontWeight: 700, color: "var(--text-primary, #F3F6FA)", margin: "0 0 6px 0", letterSpacing: "-0.01em" }}>
            {shipment.reference}
          </h2>

          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <StatusBadge status={shipment.status} />
            <RiskBadge risk={shipment.inventoryRisk} />
            <ServiceLevelBadge level={shipment.serviceLevel} />
          </div>
        </div>

        {/* Action Button */}
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          {onOpenDelayModal && (
            <button
              onClick={onOpenDelayModal}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "10px 18px",
                fontSize: "13px",
                fontWeight: 700,
                borderRadius: "6px",
                border: "none",
                cursor: "pointer",
                backgroundColor: "#FF8C42",
                color: "#0B0E14",
                boxShadow: "0 2px 10px rgba(255, 140, 66, 0.4)",
              }}
            >
              <Clock size={16} />
              Report Delay
            </button>
          )}

          <button
            onClick={() => onOpenReportModal(activeLeg?.id)}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 16px",
              fontSize: "13px",
              fontWeight: 600,
              borderRadius: "6px",
              border: "1px solid var(--border-color, #232E3C)",
              backgroundColor: "rgba(25, 34, 45, 0.6)",
              color: "var(--text-secondary, #A0AEC0)",
              cursor: "pointer",
            }}
          >
            <AlertTriangle size={15} />
            Report Disruption Event
          </button>
        </div>
      </div>

      {/* Corridor Overview 4-Card Summary */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "12px",
          marginBottom: "24px",
        }}
      >
        <div style={{ background: "var(--bg-surface-2, #19222D)", padding: "12px 14px", borderRadius: "8px", border: "1px solid var(--border-subtle, #26313D)" }}>
          <span style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>PLANNED DELIVERY</span>
          <strong style={{ fontSize: "14px", color: "var(--text-primary, #F3F6FA)" }}>
            {formatDateTime(shipment.plannedDelivery)}
          </strong>
          <div style={{ fontSize: "11px", color: "var(--text-secondary, #A8B3C2)", marginTop: "2px" }}>
            Contractual SLA Target
          </div>
        </div>

        <div style={{ background: "var(--bg-surface-2, #19222D)", padding: "12px 14px", borderRadius: "8px", border: "1px solid var(--border-subtle, #26313D)" }}>
          <span style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>CURRENT ETA</span>
          <strong
            style={{
              fontSize: "14px",
              color: shipment.currentEta !== shipment.plannedDelivery ? "#FF8C42" : "var(--status-healthy, #2DD4A7)",
            }}
          >
            {formatDateTime(shipment.currentEta)}
          </strong>
          <div style={{ fontSize: "11px", color: "var(--text-secondary, #A8B3C2)", marginTop: "2px" }}>
            Dynamic schedule recalculation
          </div>
        </div>

        <div style={{ background: "var(--bg-surface-2, #19222D)", padding: "12px 14px", borderRadius: "8px", border: "1px solid var(--border-subtle, #26313D)" }}>
          <span style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>DESTINATION FACILITY RISK</span>
          <strong
            style={{
              fontSize: "14px",
              color:
                shipment.inventoryRisk === "critical"
                  ? "#FF4D5F"
                  : shipment.inventoryRisk === "high"
                  ? "#FF8C42"
                  : shipment.inventoryRisk === "medium"
                  ? "#F5B942"
                  : "#2DD4A7",
            }}
          >
            {shipment.inventoryRisk.toUpperCase()} STOCK RISK
          </strong>
          <div style={{ fontSize: "11px", color: "var(--text-secondary, #A8B3C2)", marginTop: "2px" }}>
            Destination: {shipment.destinationFacility}
          </div>
        </div>

        <div style={{ background: "var(--bg-surface-2, #19222D)", padding: "12px 14px", borderRadius: "8px", border: "1px solid var(--border-subtle, #26313D)" }}>
          <span style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>CURRENT TELEMATICS CHECKPOINT</span>
          <strong style={{ fontSize: "13px", color: "var(--text-primary, #F3F6FA)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", display: "block" }}>
            {shipment.currentCheckpoint || activeLeg?.currentLocation || "In transit corridor"}
          </strong>
          <div style={{ fontSize: "11px", color: "var(--text-secondary, #A8B3C2)", marginTop: "2px" }}>
            Leg #{activeLeg?.sequence} ({activeLeg?.mode.toUpperCase()})
          </div>
        </div>
      </div>

      {/* Control Tower Alerts (if any) */}
      {shipment.notifications && shipment.notifications.length > 0 && (
        <div
          style={{
            background: "rgba(79, 140, 255, 0.08)",
            border: "1px solid rgba(79, 140, 255, 0.3)",
            borderRadius: "8px",
            padding: "14px 18px",
            marginBottom: "24px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
            <Bell size={16} color="var(--accent-primary, #4F8CFF)" />
            <strong style={{ fontSize: "13px", color: "var(--text-primary, #F3F6FA)", textTransform: "uppercase" }}>
              Active Control Tower Directive
            </strong>
          </div>
          {shipment.notifications.map((n) => (
            <div key={n.id} style={{ fontSize: "13px", color: "var(--text-secondary, #A8B3C2)", lineHeight: 1.5 }}>
              <p style={{ margin: "0 0 4px 0" }}>{n.message}</p>
              <div style={{ fontSize: "12px", color: "var(--accent-primary, #4F8CFF)", fontWeight: 600 }}>
                ↳ Control Tower Action: {n.prescribedAction}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Multimodal Route Timeline */}
      <div style={{ marginBottom: "28px" }}>
        <h3 style={{ fontSize: "16px", fontWeight: 700, color: "var(--text-primary, #F3F6FA)", marginBottom: "14px", display: "flex", alignItems: "center", gap: "8px" }}>
          Multimodal Intermodal Corridor ({shipment.legs?.length || 0} Connected Legs)
        </h3>
        <RouteTimeline
          shipment={shipment}
          onReportLeg={(leg) => onOpenReportModal(leg.id)}
        />
      </div>

      {/* Exception Telematics Audit Trail */}
      {hasExceptions && (
        <div style={{ marginTop: "24px", paddingTop: "20px", borderTop: "1px solid var(--border-subtle, #26313D)" }}>
          <h3 style={{ fontSize: "15px", fontWeight: 700, color: "var(--text-primary, #F3F6FA)", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
            <History size={16} color="var(--text-tertiary, #6F7C8C)" />
            Exception Telematics Log & Audit History ({shipment.exceptions.length})
          </h3>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {shipment.exceptions.map((ex) => (
              <div
                key={ex.id}
                style={{
                  background: "var(--bg-surface-2, #19222D)",
                  border: "1px solid var(--border-subtle, #26313D)",
                  borderRadius: "6px",
                  padding: "12px 16px",
                  fontSize: "12px",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "4px", flexWrap: "wrap", gap: "6px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <span style={{ fontSize: "11px", fontWeight: 700, padding: "2px 6px", borderRadius: "3px", background: "#FF8C42", color: "#fff" }}>
                      {ex.disruptionType}
                    </span>
                    <strong style={{ color: "var(--text-primary, #F3F6FA)" }}>
                      Reported by {ex.reportedBy}
                    </strong>
                    <span style={{ color: "var(--text-tertiary, #6F7C8C)" }}>•</span>
                    <span style={{ color: "var(--text-secondary, #A8B3C2)" }}>
                      {formatDateTime(ex.reportedAt)}
                    </span>
                  </div>

                  <span style={{ color: "#FF4D5F", fontWeight: 700 }}>
                    +{ex.delayHours}h delay duration
                  </span>
                </div>

                <p style={{ margin: "4px 0", color: "var(--text-secondary, #A8B3C2)", lineHeight: 1.4 }}>
                  <strong>Cause:</strong> {ex.reason}
                </p>

                {ex.notes && (
                  <div style={{ color: "var(--text-tertiary, #6F7C8C)", fontStyle: "italic", marginTop: "2px" }}>
                    "{ex.notes}"
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

