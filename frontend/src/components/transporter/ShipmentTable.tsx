import React from "react";
import { Shipment, TransportMode } from "../../types/transporter";
import { StatusBadge, RiskBadge, TransportModeBadge, ServiceLevelBadge } from "./TransporterBadges";
import { formatDateTime } from "../../utils/delayPropagation";
import { ArrowRight, MapPin, AlertTriangle, Eye, Flame, ChevronRight, Clock } from "lucide-react";

interface ShipmentTableProps {
  shipments: Shipment[];
  selectedShipmentId?: string;
  onSelectShipment: (shipment: Shipment) => void;
  onOpenReportModal: (shipment: Shipment) => void;
  onOpenDelayModal: (shipment: Shipment) => void;
}

export function ShipmentTable({
  shipments,
  selectedShipmentId,
  onSelectShipment,
  onOpenReportModal,
  onOpenDelayModal,
}: ShipmentTableProps) {
  if (shipments.length === 0) {
    return (
      <div
        style={{
          background: "var(--bg-surface-1, #151C24)",
          border: "1px solid var(--border-subtle, #26313D)",
          borderRadius: "var(--r-lg, 8px)",
          padding: "48px 24px",
          textAlign: "center",
          color: "var(--text-secondary, #A8B3C2)",
        }}
      >
        <MapPin size={32} color="var(--text-tertiary, #6F7C8C)" style={{ margin: "0 auto 12px" }} />
        <h3 style={{ fontSize: "16px", fontWeight: 600, color: "var(--text-primary, #F3F6FA)", marginBottom: "6px" }}>
          No Assigned Shipments Match Your Filter Criteria
        </h3>
        <p style={{ fontSize: "13px", maxWidth: "420px", margin: "0 auto" }}>
          Try clearing your search query or adjusting status and mode filters to view all assigned corridors.
        </p>
      </div>
    );
  }

  return (
    <div
      className="shipment-table-container"
      style={{
        background: "var(--bg-surface-1, #151C24)",
        border: "1px solid var(--border-subtle, #26313D)",
        borderRadius: "var(--r-lg, 8px)",
        overflowX: "auto",
        boxShadow: "0 2px 6px rgba(0,0,0,0.15)",
      }}
    >
      <table
        className="shipment-table"
        style={{
          width: "100%",
          borderCollapse: "collapse",
          textAlign: "left",
          fontSize: "13px",
        }}
      >
        <thead>
          <tr
            style={{
              background: "var(--bg-surface-2, #19222D)",
              borderBottom: "1px solid var(--border-default, #26313D)",
              color: "var(--text-secondary, #A8B3C2)",
              fontSize: "11px",
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            }}
          >
            <th style={{ padding: "12px 16px" }}>Shipment ID / Ref</th>
            <th style={{ padding: "12px 16px" }}>Corridor Route</th>
            <th style={{ padding: "12px 14px" }}>Status / Risk</th>
            <th style={{ padding: "12px 14px" }}>Active Leg</th>
            <th style={{ padding: "12px 14px" }}>Mode Sequence</th>
            <th style={{ padding: "12px 16px" }}>ETA vs Baseline</th>
            <th style={{ padding: "12px 14px" }}>Destination DC</th>
            <th style={{ padding: "12px 16px", textAlign: "right" }}>Operational Action</th>
          </tr>
        </thead>
        <tbody>
          {shipments.map((s) => {
            const isSelected = s.id === selectedShipmentId;
            const activeLeg = s.legs.find((l) => l.status !== "on_schedule") || s.legs[0];
            const hasDelay = (activeLeg?.delayHours || 0) > 0;
            const isCritical = s.status === "critical" || s.inventoryRisk === "critical";
            const isAtRisk = s.status === "at_risk" || s.status === "disrupted" || s.inventoryRisk === "high";

            return (
              <tr
                key={s.id}
                onClick={() => onSelectShipment(s)}
                style={{
                  borderBottom: "1px solid var(--border-subtle, #26313D)",
                  background: isSelected
                    ? "rgba(79, 140, 255, 0.08)"
                    : isCritical
                    ? "rgba(255, 77, 95, 0.03)"
                    : "transparent",
                  cursor: "pointer",
                  transition: "background 0.15s ease",
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) e.currentTarget.style.backgroundColor = "var(--bg-surface-2, #19222D)";
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.backgroundColor = isCritical
                      ? "rgba(255, 77, 95, 0.03)"
                      : "transparent";
                  }
                }}
              >
                {/* 1. Shipment ID & Ref */}
                <td style={{ padding: "12px 16px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <div
                      style={{
                        width: "6px",
                        height: "6px",
                        borderRadius: "50%",
                        background:
                          s.status === "critical"
                            ? "#FF4D5F"
                            : s.status === "disrupted"
                            ? "#FF8C42"
                            : s.status === "at_risk"
                            ? "#F5B942"
                            : "#2DD4A7",
                      }}
                    />
                    <div>
                      <strong style={{ color: "var(--text-primary, #F3F6FA)", fontSize: "13px", display: "block" }}>
                        {s.reference}
                      </strong>
                      <span style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)" }}>
                        ID: {s.id}
                      </span>
                    </div>
                  </div>
                </td>

                {/* 2. Corridor Route */}
                <td style={{ padding: "12px 16px", maxWidth: "240px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "12px", color: "var(--text-primary, #F3F6FA)" }}>
                    <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "105px" }} title={s.origin}>
                      {s.origin.split(",")[0]}
                    </span>
                    <ArrowRight size={11} color="var(--text-tertiary, #6F7C8C)" style={{ flexShrink: 0 }} />
                    <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "105px" }} title={s.destination}>
                      {s.destination.split(",")[0]}
                    </span>
                  </div>
                  {s.customer && (
                    <div style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)", marginTop: "2px" }}>
                      Consignee: {s.customer}
                    </div>
                  )}
                </td>

                {/* 3. Status & Risk */}
                <td style={{ padding: "12px 14px" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px", alignItems: "flex-start" }}>
                    <StatusBadge status={s.status} />
                    <RiskBadge risk={s.inventoryRisk} />
                  </div>
                </td>

                {/* 4. Active Leg */}
                <td style={{ padding: "12px 14px" }}>
                  <div>
                    <span style={{ fontSize: "11px", fontWeight: 700, color: "var(--text-secondary, #A8B3C2)", textTransform: "uppercase" }}>
                      Leg #{activeLeg.sequence} ({activeLeg.mode})
                    </span>
                    <div style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", maxWidth: "130px" }} title={activeLeg.carrierName}>
                      {activeLeg.carrierName}
                    </div>
                    {hasDelay && (
                      <span style={{ fontSize: "11px", color: "#FF4D5F", fontWeight: 600 }}>
                        +{activeLeg.delayHours}h lag
                      </span>
                    )}
                  </div>
                </td>

                {/* 5. Mode Sequence */}
                <td style={{ padding: "12px 14px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "4px", flexWrap: "wrap" }}>
                    {s.transportModes.map((m, idx) => (
                      <React.Fragment key={idx}>
                        <TransportModeBadge mode={m} />
                        {idx < s.transportModes.length - 1 && (
                          <span style={{ fontSize: "9px", color: "var(--text-tertiary, #6F7C8C)" }}>→</span>
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                  <div style={{ marginTop: "4px" }}>
                    <ServiceLevelBadge level={s.serviceLevel} />
                  </div>
                </td>

                {/* 6. Current ETA vs Baseline */}
                <td style={{ padding: "12px 16px" }}>
                  <div>
                    <strong style={{ fontSize: "12px", color: hasDelay ? "#FF8C42" : "var(--text-primary, #F3F6FA)" }}>
                      {formatDateTime(s.currentEta)}
                    </strong>
                    <div style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)" }}>
                      Plan: {formatDateTime(s.plannedDelivery)}
                    </div>
                  </div>
                </td>

                {/* 7. Destination Facility */}
                <td style={{ padding: "12px 14px" }}>
                  <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-primary, #F3F6FA)" }}>
                    {s.destinationFacility}
                  </span>
                </td>

                {/* 8. Actions */}
                <td style={{ padding: "12px 16px", textAlign: "right" }}>
                  <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: "6px" }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectShipment(s);
                      }}
                      className="btn-secondary"
                      style={{
                        padding: "5px 8px",
                        fontSize: "11px",
                        borderRadius: "4px",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                      title="Inspect full route and delay propagation timeline"
                    >
                      <Eye size={12} /> Route
                    </button>

                    {/* Primary Report Delay button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenDelayModal(s);
                      }}
                      style={{
                        padding: "5px 10px",
                        fontSize: "11px",
                        fontWeight: 700,
                        borderRadius: "4px",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        border: "none",
                        cursor: "pointer",
                        backgroundColor: (isCritical || isAtRisk || s.status === "delayed") ? "#FF8C42" : "#2A3644",
                        color: (isCritical || isAtRisk || s.status === "delayed") ? "#0B0E14" : "#F3F6FA",
                        boxShadow: (isCritical || isAtRisk || s.status === "delayed") ? "0 2px 8px rgba(255, 140, 66, 0.4)" : "none",
                      }}
                      title="Report routine delay and revise ETA"
                    >
                      <Clock size={12} /> Report Delay
                    </button>

                    {/* Secondary Report Disruption button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onOpenReportModal(s);
                      }}
                      style={{
                        padding: "5px 8px",
                        fontSize: "11px",
                        borderRadius: "4px",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        border: "1px solid var(--border-color, #232E3C)",
                        backgroundColor: "transparent",
                        color: "var(--text-secondary, #A0AEC0)",
                        cursor: "pointer",
                      }}
                      title="Report serious exceptional disruption event"
                    >
                      <AlertTriangle size={11} /> Disruption
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

