import React from "react";
import { RefreshCw, LogOut, Shield, Truck } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";

interface PortalHeaderProps {
  carrierName: string;
  companyName: string;
  onRefresh: () => void;
  isRefreshing?: boolean;
  onOpenMap?: () => void;
}

export function PortalHeader({
  carrierName,
  companyName,
  onRefresh,
  isRefreshing = false,
  onOpenMap,
}: PortalHeaderProps) {
  const { logout } = useAuth();

  return (
    <header
      className="portal-header portal-header-container"
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: "16px",
        padding: "16px 24px",
        background: "var(--bg-surface-1, #151C24)",
        borderBottom: "1px solid var(--border-subtle, #26313D)",
        borderRadius: "var(--r-xl, 10px)",
        marginBottom: "20px",
      }}
    >
      {/* Brand & Carrier Identity */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <div
          style={{
            width: "42px",
            height: "42px",
            borderRadius: "10px",
            background: "linear-gradient(135deg, #4F8CFF 0%, #2A5ACC 100%)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "0 2px 8px rgba(79, 140, 255, 0.3)",
          }}
        >
          <Truck size={22} color="#ffffff" aria-hidden="true" />
        </div>

        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
            <h1 style={{ fontSize: "20px", fontWeight: 700, color: "var(--text-primary, #F3F6FA)", margin: 0, letterSpacing: "-0.01em" }}>
              SupplyIQ Carrier Portal
            </h1>
            <span
              style={{
                fontSize: "11px",
                fontWeight: 600,
                textTransform: "uppercase",
                padding: "2px 8px",
                borderRadius: "4px",
                background: "rgba(79, 140, 255, 0.12)",
                color: "var(--accent-primary, #4F8CFF)",
                border: "1px solid rgba(79, 140, 255, 0.25)",
              }}
            >
              Carrier / Fleet Operator
            </span>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "12px", marginTop: "4px", fontSize: "12px", color: "var(--text-secondary, #A8B3C2)" }}>
            <span>
              Partner Carrier: <strong style={{ color: "var(--text-primary, #F3F6FA)" }}>{carrierName}</strong>
            </span>
            <span>•</span>
            <span>
              Shipper / Partner: <strong style={{ color: "var(--text-primary, #F3F6FA)" }}>{companyName}</strong>
            </span>
            <span>•</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", color: "var(--status-healthy, #2DD4A7)" }}>
              <Shield size={12} /> Scoped Operational View (RBAC Active)
            </span>
          </div>
        </div>
      </div>

      {/* Action Controls */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {onOpenMap && (
          <button
            onClick={onOpenMap}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 16px",
              fontSize: "13px",
              fontWeight: 700,
              cursor: "pointer",
              borderRadius: "var(--r-md, 6px)",
              background: "linear-gradient(135deg, #1d4ed8 0%, #0284c7 100%)",
              color: "#ffffff",
              border: "1px solid #38bdf8",
              boxShadow: "0 2px 10px rgba(56, 189, 248, 0.35)",
            }}
          >
            <span style={{ fontSize: "14px" }}>🌐</span>
            Live Global Corridor Map
          </button>
        )}

        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="btn-secondary"
          aria-label="Refresh assigned shipments list"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "8px 14px",
            fontSize: "13px",
            fontWeight: 600,
            cursor: "pointer",
            borderRadius: "var(--r-md, 6px)",
          }}
        >
          <RefreshCw
            size={14}
            className={isRefreshing ? "spin-animation" : ""}
            aria-hidden="true"
          />
          {isRefreshing ? "Refreshing..." : "Refresh shipments"}
        </button>

        <button
          onClick={logout}
          className="btn-secondary"
          aria-label="Log out of Carrier Portal"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "8px 14px",
            fontSize: "13px",
            fontWeight: 500,
            color: "var(--text-tertiary, #6F7C8C)",
            cursor: "pointer",
            borderRadius: "var(--r-md, 6px)",
          }}
        >
          <LogOut size={14} aria-hidden="true" />
          Logout
        </button>
      </div>
    </header>
  );
}

