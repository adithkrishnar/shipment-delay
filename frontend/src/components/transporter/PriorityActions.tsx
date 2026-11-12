import React from "react";
import { AlertCircle, Clock, Flame, ChevronRight } from "lucide-react";
import { Shipment } from "../../types/transporter";

interface PriorityActionsProps {
  shipments: Shipment[];
  onSelectShipment: (shipment: Shipment) => void;
}

export function PriorityActions({ shipments, onSelectShipment }: PriorityActionsProps) {
  const requiresImmediateAction = shipments.filter((s) => s.requiresCarrierAction);
  const deliveryWindowRisk = shipments.filter(
    (s) => s.status === "critical" || s.status === "disrupted" || s.status === "at_risk"
  );
  const stockoutRiskShipments = shipments.filter(
    (s) => s.inventoryRisk === "critical" || s.inventoryRisk === "high"
  );

  if (requiresImmediateAction.length === 0 && deliveryWindowRisk.length === 0 && stockoutRiskShipments.length === 0) {
    return null;
  }

  return (
    <section
      aria-label="Priority Operational Actions"
      style={{
        background: "linear-gradient(135deg, rgba(255, 77, 95, 0.08) 0%, rgba(245, 185, 66, 0.04) 100%)",
        border: "1px solid rgba(255, 77, 95, 0.25)",
        borderRadius: "var(--r-xl, 10px)",
        padding: "14px 20px",
        marginBottom: "20px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px", flexWrap: "wrap", gap: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#FF4D5F", animation: "pulse 1.5s infinite" }} />
          <h2 style={{ fontSize: "14px", fontWeight: 700, color: "var(--text-primary, #F3F6FA)", margin: 0, textTransform: "uppercase", letterSpacing: "0.03em" }}>
            Priority Action Desk (Exceptions Requiring Attention)
          </h2>
        </div>
        <span style={{ fontSize: "12px", color: "var(--text-secondary, #A8B3C2)" }}>
          Direct carrier telematics needed to update downstream control tower
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: "10px",
        }}
      >
        {/* Item 1: Requiring Immediate Action */}
        {requiresImmediateAction.length > 0 && (
          <button
            onClick={() => onSelectShipment(requiresImmediateAction[0])}
            className="priority-alert-btn"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 14px",
              background: "var(--bg-surface-1, #151C24)",
              border: "1px solid rgba(255, 140, 66, 0.3)",
              borderRadius: "6px",
              cursor: "pointer",
              textAlign: "left",
              color: "inherit",
              width: "100%",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <AlertCircle size={16} color="#FF8C42" aria-hidden="true" />
              <div>
                <strong style={{ fontSize: "13px", color: "var(--text-primary, #F3F6FA)", display: "block" }}>
                  {requiresImmediateAction.length} shipment(s) require immediate action
                </strong>
                <span style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)" }}>
                  e.g. {requiresImmediateAction[0].reference} ({requiresImmediateAction[0].destinationFacility})
                </span>
              </div>
            </div>
            <ChevronRight size={15} color="var(--text-tertiary, #6F7C8C)" />
          </button>
        )}

        {/* Item 2: Risk Missing Delivery Window */}
        {deliveryWindowRisk.length > 0 && (
          <button
            onClick={() => onSelectShipment(deliveryWindowRisk[0])}
            className="priority-alert-btn"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 14px",
              background: "var(--bg-surface-1, #151C24)",
              border: "1px solid rgba(245, 185, 66, 0.3)",
              borderRadius: "6px",
              cursor: "pointer",
              textAlign: "left",
              color: "inherit",
              width: "100%",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Clock size={16} color="#F5B942" aria-hidden="true" />
              <div>
                <strong style={{ fontSize: "13px", color: "var(--text-primary, #F3F6FA)", display: "block" }}>
                  {deliveryWindowRisk.length} shipment(s) risk missing delivery window
                </strong>
                <span style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)" }}>
                  Lead exception: {deliveryWindowRisk[0].reference} ({deliveryWindowRisk[0].currentCheckpoint || "Corridor"})
                </span>
              </div>
            </div>
            <ChevronRight size={15} color="var(--text-tertiary, #6F7C8C)" />
          </button>
        )}

        {/* Item 3: May cause inventory stockout */}
        {stockoutRiskShipments.length > 0 && (
          <button
            onClick={() => onSelectShipment(stockoutRiskShipments[0])}
            className="priority-alert-btn"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "10px 14px",
              background: "var(--bg-surface-1, #151C24)",
              border: "1px solid rgba(255, 77, 95, 0.35)",
              borderRadius: "6px",
              cursor: "pointer",
              textAlign: "left",
              color: "inherit",
              width: "100%",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
              <Flame size={16} color="#FF4D5F" aria-hidden="true" />
              <div>
                <strong style={{ fontSize: "13px", color: "#FF4D5F", display: "block" }}>
                  {stockoutRiskShipments.length} shipment(s) threaten destination stockout
                </strong>
                <span style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)" }}>
                  Target: {stockoutRiskShipments[0].destinationFacility}
                </span>
              </div>
            </div>
            <ChevronRight size={15} color="var(--text-tertiary, #6F7C8C)" />
          </button>
        )}
      </div>
    </section>
  );
}

