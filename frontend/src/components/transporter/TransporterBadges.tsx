import React from "react";
import { ShipmentStatus, RiskLevel, TransportMode, ServiceLevel } from "../../types/transporter";
import { getStatusLabel, getRiskLabel } from "../../utils/delayPropagation";
import { Truck, Train, Ship, Plane, ShieldCheck, Eye, AlertTriangle, AlertOctagon, Flame } from "lucide-react";

export function StatusBadge({ status }: { status: ShipmentStatus }) {
  const styles: Record<ShipmentStatus, { bg: string; color: string; border: string; icon: any }> = {
    on_schedule: {
      bg: "rgba(45, 212, 167, 0.12)",
      color: "#2DD4A7",
      border: "rgba(45, 212, 167, 0.3)",
      icon: ShieldCheck,
    },
    monitoring: {
      bg: "rgba(79, 140, 255, 0.12)",
      color: "#4F8CFF",
      border: "rgba(79, 140, 255, 0.3)",
      icon: Eye,
    },
    at_risk: {
      bg: "rgba(245, 185, 66, 0.14)",
      color: "#F5B942",
      border: "rgba(245, 185, 66, 0.35)",
      icon: AlertTriangle,
    },
    disrupted: {
      bg: "rgba(255, 140, 66, 0.15)",
      color: "#FF8C42",
      border: "rgba(255, 140, 66, 0.4)",
      icon: AlertOctagon,
    },
    delayed: {
      bg: "rgba(255, 140, 66, 0.2)",
      color: "#FF8C42",
      border: "rgba(255, 140, 66, 0.5)",
      icon: AlertTriangle,
    },
    critical: {
      bg: "rgba(255, 77, 95, 0.16)",
      color: "#FF4D5F",
      border: "rgba(255, 77, 95, 0.45)",
      icon: Flame,
    },
  };

  const current = styles[status] || styles.on_schedule;
  const Icon = current.icon;

  return (
    <span
      role="status"
      aria-label={`Shipment status: ${getStatusLabel(status)}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "5px",
        padding: "3px 8px",
        borderRadius: "4px",
        fontSize: "11px",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.04em",
        background: current.bg,
        color: current.color,
        border: `1px solid ${current.border}`,
        whiteSpace: "nowrap",
      }}
    >
      <Icon size={12} aria-hidden="true" />
      {getStatusLabel(status)}
    </span>
  );
}

export function RiskBadge({ risk }: { risk: RiskLevel }) {
  const styles: Record<RiskLevel, { bg: string; color: string; border: string }> = {
    low: {
      bg: "rgba(45, 212, 167, 0.1)",
      color: "#2DD4A7",
      border: "rgba(45, 212, 167, 0.25)",
    },
    medium: {
      bg: "rgba(245, 185, 66, 0.1)",
      color: "#F5B942",
      border: "rgba(245, 185, 66, 0.25)",
    },
    high: {
      bg: "rgba(255, 140, 66, 0.12)",
      color: "#FF8C42",
      border: "rgba(255, 140, 66, 0.3)",
    },
    critical: {
      bg: "rgba(255, 77, 95, 0.15)",
      color: "#FF4D5F",
      border: "rgba(255, 77, 95, 0.4)",
    },
  };

  const current = styles[risk] || styles.low;

  return (
    <span
      role="status"
      aria-label={`Inventory risk level: ${getRiskLabel(risk)}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 7px",
        borderRadius: "4px",
        fontSize: "11px",
        fontWeight: 600,
        background: current.bg,
        color: current.color,
        border: `1px solid ${current.border}`,
        whiteSpace: "nowrap",
      }}
    >
      {getRiskLabel(risk)}
    </span>
  );
}

export function TransportModeBadge({ mode }: { mode: TransportMode }) {
  const icons: Record<TransportMode, any> = {
    road: Truck,
    rail: Train,
    sea: Ship,
    air: Plane,
  };
  const Icon = icons[mode] || Truck;

  return (
    <span
      title={`Mode: ${mode.toUpperCase()}`}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: "2px 6px",
        borderRadius: "4px",
        background: "var(--bg-surface-3, #111720)",
        color: "var(--text-secondary, #A8B3C2)",
        border: "1px solid var(--border-subtle, #26313D)",
        fontSize: "10px",
        fontWeight: 700,
        textTransform: "uppercase",
      }}
    >
      <Icon size={11} aria-hidden="true" />
      {mode}
    </span>
  );
}

export function ServiceLevelBadge({ level }: { level: ServiceLevel }) {
  const isPriority = level === "express" || level === "expedited";
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 6px",
        borderRadius: "4px",
        fontSize: "10px",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: "0.03em",
        background: isPriority ? "rgba(79, 140, 255, 0.12)" : "var(--bg-surface-3, #111720)",
        color: isPriority ? "var(--accent-primary, #4F8CFF)" : "var(--text-muted, #6F7C8C)",
        border: `1px solid ${isPriority ? "rgba(79, 140, 255, 0.25)" : "var(--border-subtle, #26313D)"}`,
      }}
    >
      {level}
    </span>
  );
}

