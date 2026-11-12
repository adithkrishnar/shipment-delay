import React from "react";
import { Package, AlertOctagon, Flame, ShieldCheck, AlertTriangle, UserCheck } from "lucide-react";
import { Shipment } from "../../types/transporter";

interface OperationalSummaryProps {
  shipments: Shipment[];
}

export function OperationalSummary({ shipments }: OperationalSummaryProps) {
  const total = shipments.length;
  const activeDisruptions = shipments.filter((s) => s.status === "disrupted").length;
  const atRisk = shipments.filter((s) => s.status === "at_risk").length;
  const onSchedule = shipments.filter((s) => s.status === "on_schedule").length;
  const critical = shipments.filter((s) => s.status === "critical").length;
  const requiresAction = shipments.filter((s) => s.requiresCarrierAction).length;

  const kpis = [
    {
      label: "Assigned Shipments",
      value: total,
      subtext: "In active transit corridors",
      icon: Package,
      color: "var(--accent-primary, #4F8CFF)",
      bg: "rgba(79, 140, 255, 0.08)",
      border: "rgba(79, 140, 255, 0.2)",
    },
    {
      label: "Active Disruptions",
      value: activeDisruptions,
      subtext: "Reported route exceptions",
      icon: AlertOctagon,
      color: "#FF8C42",
      bg: "rgba(255, 140, 66, 0.08)",
      border: "rgba(255, 140, 66, 0.25)",
    },
    {
      label: "At-Risk Shipments",
      value: atRisk,
      subtext: "Connection window tight",
      icon: AlertTriangle,
      color: "#F5B942",
      bg: "rgba(245, 185, 66, 0.08)",
      border: "rgba(245, 185, 66, 0.25)",
    },
    {
      label: "On Schedule",
      value: onSchedule,
      subtext: "Within baseline ETA",
      icon: ShieldCheck,
      color: "var(--status-healthy, #2DD4A7)",
      bg: "rgba(45, 212, 167, 0.08)",
      border: "rgba(45, 212, 167, 0.2)",
    },
    {
      label: "Critical Exceptions",
      value: critical,
      subtext: "Missed cutoffs or stockout risk",
      icon: Flame,
      color: "var(--status-critical, #FF4D5F)",
      bg: "rgba(255, 77, 95, 0.1)",
      border: "rgba(255, 77, 95, 0.3)",
    },
    {
      label: "Requires Action",
      value: requiresAction,
      subtext: "Awaiting telematics report",
      icon: UserCheck,
      color: "#8B5CF6",
      bg: "rgba(139, 92, 246, 0.08)",
      border: "rgba(139, 92, 246, 0.25)",
    },
  ];

  return (
    <section aria-label="Operational KPI Summary" style={{ marginBottom: "20px" }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
          gap: "12px",
        }}
      >
        {kpis.map((kpi, idx) => {
          const Icon = kpi.icon;
          return (
            <div
              key={idx}
              style={{
                background: "var(--bg-surface-1, #151C24)",
                border: `1px solid ${kpi.border}`,
                borderRadius: "var(--r-lg, 8px)",
                padding: "14px 16px",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "8px" }}>
                <span style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #A8B3C2)" }}>
                  {kpi.label}
                </span>
                <div
                  style={{
                    width: "28px",
                    height: "28px",
                    borderRadius: "6px",
                    background: kpi.bg,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Icon size={15} color={kpi.color} aria-hidden="true" />
                </div>
              </div>

              <div>
                <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--text-primary, #F3F6FA)", letterSpacing: "-0.02em" }}>
                  {kpi.value}
                </div>
                <div style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)", marginTop: "2px" }}>
                  {kpi.subtext}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

