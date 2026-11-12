import React from "react";
import { Search, Filter, ArrowUpDown } from "lucide-react";
import { ShipmentStatus, RiskLevel, TransportMode, ServiceLevel } from "../../types/transporter";

interface ShipmentFiltersProps {
  searchQuery: string;
  onSearchChange: (q: string) => void;
  statusFilter: string;
  onStatusChange: (status: string) => void;
  riskFilter: string;
  onRiskChange: (risk: string) => void;
  modeFilter: string;
  onModeChange: (mode: string) => void;
  serviceFilter: string;
  onServiceChange: (service: string) => void;
  facilityFilter: string;
  onFacilityChange: (fac: string) => void;
  facilityOptions: string[];
  sortBy: string;
  onSortChange: (sort: string) => void;
  totalFiltered: number;
  totalCount: number;
}

export function ShipmentFilters({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusChange,
  riskFilter,
  onRiskChange,
  modeFilter,
  onModeChange,
  serviceFilter,
  onServiceChange,
  facilityFilter,
  onFacilityChange,
  facilityOptions,
  sortBy,
  onSortChange,
  totalFiltered,
  totalCount,
}: ShipmentFiltersProps) {
  return (
    <div
      className="shipment-filters-bar"
      style={{
        background: "var(--bg-surface-1, #151C24)",
        border: "1px solid var(--border-subtle, #26313D)",
        borderRadius: "var(--r-lg, 8px)",
        padding: "14px 18px",
        marginBottom: "16px",
        display: "flex",
        flexDirection: "column",
        gap: "12px",
      }}
    >
      {/* Row 1: Search and Primary Controls */}
      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between" }}>
        {/* Search input */}
        <div style={{ position: "relative", flex: "1 1 260px", minWidth: "220px" }}>
          <Search
            size={16}
            color="var(--text-tertiary, #6F7C8C)"
            style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)" }}
            aria-hidden="true"
          />
          <input
            type="text"
            placeholder="Search by Shipment ID, reference, customer, or destination..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search shipments"
            className="input"
            style={{
              width: "100%",
              paddingLeft: "36px",
              paddingRight: "12px",
              height: "38px",
              fontSize: "13px",
              borderRadius: "6px",
              border: "1px solid var(--border-default, #26313D)",
              background: "var(--bg-base, #0B0F14)",
              color: "var(--text-primary, #F3F6FA)",
            }}
          />
        </div>

        {/* Sort selector */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <ArrowUpDown size={15} color="var(--text-tertiary, #6F7C8C)" aria-hidden="true" />
          <label htmlFor="shipment-sort" style={{ fontSize: "12px", color: "var(--text-secondary, #A8B3C2)", fontWeight: 500 }}>
            Sort:
          </label>
          <select
            id="shipment-sort"
            value={sortBy}
            onChange={(e) => onSortChange(e.target.value)}
            className="input"
            style={{
              height: "38px",
              padding: "0 10px",
              fontSize: "13px",
              borderRadius: "6px",
              border: "1px solid var(--border-default, #26313D)",
              background: "var(--bg-base, #0B0F14)",
              color: "var(--text-primary, #F3F6FA)",
            }}
          >
            <option value="highest_risk">Highest Risk First</option>
            <option value="largest_delay">Largest Delay</option>
            <option value="nearest_deadline">Nearest Delivery Window</option>
            <option value="reference_asc">Shipment ID (A-Z)</option>
          </select>
        </div>

        <div style={{ fontSize: "12px", color: "var(--text-tertiary, #6F7C8C)" }}>
          Showing <strong>{totalFiltered}</strong> of {totalCount} assigned shipments
        </div>
      </div>

      {/* Row 2: Filter dropdown pills */}
      <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "var(--text-secondary, #A8B3C2)", fontWeight: 600 }}>
          <Filter size={13} /> Filters:
        </div>

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => onStatusChange(e.target.value)}
          aria-label="Filter by Shipment Status"
          className="input"
          style={{
            height: "32px",
            fontSize: "12px",
            padding: "0 8px",
            borderRadius: "6px",
            border: "1px solid var(--border-subtle, #26313D)",
            background: statusFilter !== "ALL" ? "rgba(79, 140, 255, 0.15)" : "var(--bg-base, #0B0F14)",
            color: "var(--text-primary, #F3F6FA)",
          }}
        >
          <option value="ALL">All Statuses</option>
          <option value="delayed">Delayed</option>
          <option value="critical">Critical</option>
          <option value="disrupted">Disrupted</option>
          <option value="at_risk">At Risk</option>
          <option value="monitoring">Monitoring</option>
          <option value="on_schedule">On Schedule</option>
        </select>

        {/* Inventory Risk Filter */}
        <select
          value={riskFilter}
          onChange={(e) => onRiskChange(e.target.value)}
          aria-label="Filter by Inventory Risk"
          className="input"
          style={{
            height: "32px",
            fontSize: "12px",
            padding: "0 8px",
            borderRadius: "6px",
            border: "1px solid var(--border-subtle, #26313D)",
            background: riskFilter !== "ALL" ? "rgba(79, 140, 255, 0.15)" : "var(--bg-base, #0B0F14)",
            color: "var(--text-primary, #F3F6FA)",
          }}
        >
          <option value="ALL">All Inventory Risks</option>
          <option value="critical">Critical Risk</option>
          <option value="high">High Risk</option>
          <option value="medium">Medium Risk</option>
          <option value="low">Low Risk</option>
        </select>

        {/* Transport Mode Filter */}
        <select
          value={modeFilter}
          onChange={(e) => onModeChange(e.target.value)}
          aria-label="Filter by Primary Transport Mode"
          className="input"
          style={{
            height: "32px",
            fontSize: "12px",
            padding: "0 8px",
            borderRadius: "6px",
            border: "1px solid var(--border-subtle, #26313D)",
            background: modeFilter !== "ALL" ? "rgba(79, 140, 255, 0.15)" : "var(--bg-base, #0B0F14)",
            color: "var(--text-primary, #F3F6FA)",
          }}
        >
          <option value="ALL">All Transport Modes</option>
          <option value="road">Road</option>
          <option value="rail">Rail</option>
          <option value="sea">Sea / Ocean</option>
          <option value="air">Air Cargo</option>
        </select>

        {/* Service Level Filter */}
        <select
          value={serviceFilter}
          onChange={(e) => onServiceChange(e.target.value)}
          aria-label="Filter by Service Level"
          className="input"
          style={{
            height: "32px",
            fontSize: "12px",
            padding: "0 8px",
            borderRadius: "6px",
            border: "1px solid var(--border-subtle, #26313D)",
            background: serviceFilter !== "ALL" ? "rgba(79, 140, 255, 0.15)" : "var(--bg-base, #0B0F14)",
            color: "var(--text-primary, #F3F6FA)",
          }}
        >
          <option value="ALL">All Service Levels</option>
          <option value="standard">Standard</option>
          <option value="express">Express</option>
          <option value="expedited">Expedited</option>
          <option value="economy">Economy</option>
        </select>

        {/* Destination Facility Filter */}
        <select
          value={facilityFilter}
          onChange={(e) => onFacilityChange(e.target.value)}
          aria-label="Filter by Destination Facility"
          className="input"
          style={{
            height: "32px",
            fontSize: "12px",
            padding: "0 8px",
            borderRadius: "6px",
            border: "1px solid var(--border-subtle, #26313D)",
            background: facilityFilter !== "ALL" ? "rgba(79, 140, 255, 0.15)" : "var(--bg-base, #0B0F14)",
            color: "var(--text-primary, #F3F6FA)",
          }}
        >
          <option value="ALL">All Destination Facilities</option>
          {facilityOptions.map((fac) => (
            <option key={fac} value={fac}>
              {fac}
            </option>
          ))}
        </select>

        {/* Reset button if any filter is active */}
        {(searchQuery || statusFilter !== "ALL" || riskFilter !== "ALL" || modeFilter !== "ALL" || serviceFilter !== "ALL" || facilityFilter !== "ALL") && (
          <button
            onClick={() => {
              onSearchChange("");
              onStatusChange("ALL");
              onRiskChange("ALL");
              onModeChange("ALL");
              onServiceChange("ALL");
              onFacilityChange("ALL");
            }}
            style={{
              background: "none",
              border: "none",
              fontSize: "12px",
              color: "var(--accent-primary, #4F8CFF)",
              cursor: "pointer",
              padding: "4px 8px",
              textDecoration: "underline",
            }}
          >
            Reset Filters
          </button>
        )}
      </div>
    </div>
  );
}

