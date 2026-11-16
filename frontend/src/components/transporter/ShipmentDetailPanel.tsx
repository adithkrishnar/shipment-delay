import React from "react";
import { Shipment, ShipmentLeg } from "../../types/transporter";
import { StatusBadge, RiskBadge, TransportModeBadge, ServiceLevelBadge } from "./TransporterBadges";
import { RouteTimeline } from "./RouteTimeline";
import { formatDateTime } from "../../utils/delayPropagation";
import { AlertTriangle, Clock, MapPin, Building, ShieldCheck, ChevronRight, Bell, History, CheckCircle2 } from "lucide-react";

interface ShipmentDetailPanelProps {
  shipment: Shipment;
  onOpenReportModal: (legId?: string) => void;
  onOpenDelayModal?: () => void;
  onClose?: () => void;
  isApproved?: boolean;
}

export function ShipmentDetailPanel({
  shipment,
  onOpenReportModal,
  onOpenDelayModal,
  onClose,
  isApproved,
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
            {isApproved ? (
              <>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "5px",
                    padding: "3px 8px",
                    borderRadius: "4px",
                    fontSize: "11px",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    background: "rgba(45, 212, 167, 0.16)",
                    color: "#2DD4A7",
                    border: "1px solid rgba(45, 212, 167, 0.4)",
                  }}
                >
                  <CheckCircle2 size={12} /> Mitigated / Approved
                </span>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "5px",
                    padding: "3px 8px",
                    borderRadius: "4px",
                    fontSize: "11px",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.04em",
                    background: "rgba(45, 212, 167, 0.12)",
                    color: "#2DD4A7",
                    border: "1px solid rgba(45, 212, 167, 0.3)",
                  }}
                >
                  Stock Risk Resolved
                </span>
              </>
            ) : (
              <>
                <StatusBadge status={shipment.status} />
                <RiskBadge risk={shipment.inventoryRisk} />
              </>
            )}
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

        <div style={{ background: "var(--bg-surface-2, #19222D)", padding: "12px 14px", borderRadius: "8px", border: isApproved ? "1px solid rgba(45, 212, 167, 0.4)" : "1px solid var(--border-subtle, #26313D)" }}>
          <span style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>DESTINATION FACILITY RISK</span>
          <strong
            style={{
              fontSize: "14px",
              color: isApproved ? "#2DD4A7" : shipment.inventoryRisk === "critical" ? "#FF4D5F" : shipment.inventoryRisk === "high" ? "#FF8C42" : "#2DD4A7",
            }}
          >
            {isApproved ? "STOCK RISK RESOLVED" : `${shipment.inventoryRisk.toUpperCase()} STOCK RISK`}
          </strong>
          <div style={{ fontSize: "11px", color: isApproved ? "#2DD4A7" : "var(--text-secondary, #A8B3C2)", marginTop: "2px" }}>
            {isApproved ? "Emergency stock transfer approved by Control Tower" : `Destination: ${shipment.destinationFacility}`}
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

      {/* Control Tower Directives (Pending vs Approved by Control Tower) */}
      {isApproved ? (
        <div
          style={{
            background: "linear-gradient(135deg, rgba(45, 212, 167, 0.12), rgba(79, 140, 255, 0.08))",
            border: "1px solid rgba(45, 212, 167, 0.4)",
            borderRadius: "8px",
            padding: "16px 20px",
            marginBottom: "24px",
            boxShadow: "0 4px 16px rgba(45, 212, 167, 0.08)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px", flexWrap: "wrap", gap: "8px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <CheckCircle2 size={18} color="#2DD4A7" />
              <strong style={{ fontSize: "14px", color: "#2DD4A7", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                Control Tower Directive Authorized &amp; Dispatched
              </strong>
            </div>
            <span style={{ fontSize: "11px", fontWeight: 700, padding: "3px 8px", borderRadius: "4px", background: "rgba(45, 212, 167, 0.2)", color: "#2DD4A7" }}>
              ACTION APPROVED
            </span>
          </div>
          <div style={{ fontSize: "13px", color: "var(--text-primary, #F3F6FA)", lineHeight: 1.6 }}>
            <p style={{ margin: "0 0 6px 0" }}>
              The Company Control Tower has officially approved the <strong>Emergency Inter-Warehouse Stock Transfer (32 units)</strong> to bridge the delay gap at <strong>{shipment.destinationFacility}</strong>.
            </p>
            <div style={{ fontSize: "12px", color: "#2DD4A7", fontWeight: 600 }}>
              ✓ Downstream inventory stockout risk is neutralized. Carrier transit schedule updated.
            </div>
          </div>
        </div>
      ) : (
        shipment.notifications && shipment.notifications.length > 0 && (
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
        )
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

