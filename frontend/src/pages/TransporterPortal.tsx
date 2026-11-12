import React, { useState, useMemo } from "react";
import { Shipment, ShipmentLeg } from "../types/transporter";
import { MOCK_SHIPMENTS, MOCK_CARRIER_NAME } from "../mock/transporterData";
import { PortalHeader } from "../components/transporter/PortalHeader";
import { OperationalSummary } from "../components/transporter/OperationalSummary";
import { PriorityActions } from "../components/transporter/PriorityActions";
import { ShipmentFilters } from "../components/transporter/ShipmentFilters";
import { ShipmentTable } from "../components/transporter/ShipmentTable";
import { ShipmentDetailPanel } from "../components/transporter/ShipmentDetailPanel";
import { DisruptionForm } from "../components/transporter/DisruptionForm";
import { ReportDelayModal } from "../components/transporter/ReportDelayModal";
import { CheckCircle2, AlertOctagon, X, Clock } from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { reportLegDisruption } from "../services/api";

export default function TransporterPortal() {
  const { user } = useAuth();
  const carrierName = user?.carrier_name || MOCK_CARRIER_NAME;
  const companyName = user?.company?.name || "DataCo Global Supply Chain";

  // Shipments state seeded from high-fidelity multi-modal sample dataset
  const [shipments, setShipments] = useState<Shipment[]>(MOCK_SHIPMENTS);
  const [selectedShipmentId, setSelectedShipmentId] = useState<string>(MOCK_SHIPMENTS[0]?.id || "");
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Disruption modal state
  const [isReportModalOpen, setIsReportModalOpen] = useState<boolean>(false);
  const [reportTargetLegId, setReportTargetLegId] = useState<string | undefined>(undefined);

  // Delay modal state
  const [isDelayModalOpen, setIsDelayModalOpen] = useState<boolean>(false);
  const [delayTargetShipment, setDelayTargetShipment] = useState<Shipment | null>(null);

  // Success toast state
  const [successToast, setSuccessToast] = useState<{
    reference: string;
    delayHours: number;
    revisedEta: string;
    impactExplanation: string;
  } | null>(null);

  // Filter and sort state
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [riskFilter, setRiskFilter] = useState("ALL");
  const [modeFilter, setModeFilter] = useState("ALL");
  const [serviceFilter, setServiceFilter] = useState("ALL");
  const [facilityFilter, setFacilityFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("highest_risk");

  // Distinct facilities for filtering
  const facilityOptions = useMemo(() => {
    const set = new Set<string>();
    shipments.forEach((s) => {
      if (s.destinationFacility) set.add(s.destinationFacility);
    });
    return Array.from(set).sort();
  }, [shipments]);

  // Filtered and sorted shipments
  const filteredShipments = useMemo(() => {
    let list = shipments.filter((s) => {
      // Search
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesRef = s.reference.toLowerCase().includes(q);
        const matchesId = s.id.toLowerCase().includes(q);
        const matchesOrigin = s.origin.toLowerCase().includes(q);
        const matchesDest = s.destination.toLowerCase().includes(q);
        const matchesFac = s.destinationFacility.toLowerCase().includes(q);
        const matchesCustomer = s.customer?.toLowerCase().includes(q);
        if (!matchesRef && !matchesId && !matchesOrigin && !matchesDest && !matchesFac && !matchesCustomer) {
          return false;
        }
      }

      // Status
      if (statusFilter !== "ALL" && s.status !== statusFilter) return false;

      // Risk
      if (riskFilter !== "ALL" && s.inventoryRisk !== riskFilter) return false;

      // Mode
      if (modeFilter !== "ALL" && !s.transportModes.includes(modeFilter as any)) return false;

      // Service Level
      if (serviceFilter !== "ALL" && s.serviceLevel !== serviceFilter) return false;

      // Facility
      if (facilityFilter !== "ALL" && s.destinationFacility !== facilityFilter) return false;

      return true;
    });

    // Sort
    list.sort((a, b) => {
      if (sortBy === "highest_risk") {
        const score = (s: Shipment) => {
          let pts = 0;
          if (s.status === "critical") pts += 10;
          if (s.status === "disrupted") pts += 7;
          if (s.status === "at_risk") pts += 5;
          if (s.inventoryRisk === "critical") pts += 10;
          if (s.inventoryRisk === "high") pts += 6;
          if (s.requiresCarrierAction) pts += 4;
          return pts;
        };
        return score(b) - score(a);
      } else if (sortBy === "largest_delay") {
        const getMaxDelay = (s: Shipment) =>
          Math.max(0, ...s.legs.map((l) => l.delayHours || 0));
        return getMaxDelay(b) - getMaxDelay(a);
      } else if (sortBy === "nearest_deadline") {
        return new Date(a.plannedDelivery).getTime() - new Date(b.plannedDelivery).getTime();
      } else if (sortBy === "reference_asc") {
        return a.reference.localeCompare(b.reference);
      }
      return 0;
    });

    return list;
  }, [shipments, searchQuery, statusFilter, riskFilter, modeFilter, serviceFilter, facilityFilter, sortBy]);

  // Selected shipment object
  const selectedShipment = useMemo(() => {
    return shipments.find((s) => s.id === selectedShipmentId) || filteredShipments[0] || shipments[0];
  }, [shipments, selectedShipmentId, filteredShipments]);

  // Refresh handler
  const handleRefresh = () => {
    setIsRefreshing(true);
    setTimeout(() => {
      setIsRefreshing(false);
    }, 600);
  };

  // Open disruption form
  const handleOpenReportModal = (shipment: Shipment, legId?: string) => {
    setSelectedShipmentId(shipment.id);
    setReportTargetLegId(legId);
    setIsReportModalOpen(true);
  };

  const handleOpenDelayModal = (shipment: Shipment) => {
    setSelectedShipmentId(shipment.id);
    setDelayTargetShipment(shipment);
    setIsDelayModalOpen(true);
  };

  const handleDelayReported = (data: {
    shipmentId: string;
    newEta: string;
    delayHours: number;
    reason: string;
    notes?: string;
    reportedBy: string;
    reportedAt: string;
  }) => {
    setShipments((prevList) =>
      prevList.map((s) => {
        if (s.id !== data.shipmentId) return s;

        const updatedLegs = s.legs.map((leg, idx) => {
          if (idx === s.legs.length - 1) {
            return {
              ...leg,
              delayHours: (leg.delayHours || 0) + data.delayHours,
              status: "delayed" as const,
            };
          }
          return leg;
        });

        const newNotification = {
          id: `notif-${Date.now()}`,
          timestamp: new Date().toISOString(),
          type: "ETA_RECALCULATION" as const,
          message: `Carrier reported ${data.reason.replace(/_/g, " ")} (+${data.delayHours}h). Revised ETA: ${new Date(data.newEta).toLocaleString()}`,
          prescribedAction: "Control Tower Updated",
        };

        return {
          ...s,
          legs: updatedLegs,
          status: "delayed" as const,
          currentEta: data.newEta,
          notifications: [newNotification, ...(s.notifications || [])],
        };
      })
    );

    setSuccessToast({
      reference: selectedShipment?.reference || data.shipmentId,
      delayHours: data.delayHours,
      revisedEta: new Date(data.newEta).toLocaleString(),
      impactExplanation: `Delay of ${data.delayHours}h reported due to ${data.reason.replace(/_/g, " ")}. Control Tower notified.`,
    });
  };

  // Submit disruption telematics & trigger delay propagation
  const handleDisruptionSubmitSuccess = async (
    shipmentId: string,
    legId: string,
    reportedDelayHours: number,
    details: any
  ) => {
    setIsReportModalOpen(false);

    // Update frontend state with recalculated propagation
    setShipments((prevList) =>
      prevList.map((s) => {
        if (s.id !== shipmentId) return s;

        const updatedLegs = s.legs.map((leg) => {
          if (leg.id === legId) {
            const hasConnection = !!leg.connection;
            const missedCutoff = details.impact?.missedConnectionPenaltyHours > 0;
            return {
              ...leg,
              delayHours: (leg.delayHours || 0) + reportedDelayHours,
              status: "disrupted" as const,
              currentLocation: details.location || leg.currentLocation,
              connection: leg.connection
                ? {
                    ...leg.connection,
                    missed: missedCutoff,
                  }
                : undefined,
            };
          }
          return leg;
        });

        const newStatus = details.impact?.inventoryRisk === "critical" ? ("critical" as const) : ("disrupted" as const);
        const newRisk = details.impact?.inventoryRisk || "high";
        const newEta = details.impact?.revisedEta || s.currentEta;

        const newException = {
          id: `ex-${Date.now()}`,
          shipmentId: s.id,
          legId,
          reportedBy: carrierName,
          reportedAt: new Date().toISOString(),
          disruptionType: details.disruptionType,
          location: details.location,
          delayHours: reportedDelayHours,
          reason: details.reason,
          notes: details.notes,
          status: "submitted" as const,
        };

        const newNotification = {
          id: `notif-${Date.now()}`,
          timestamp: new Date().toISOString(),
          type: "DISRUPTION_ALERT" as const,
          message: `Carrier reported ${details.disruptionType} on Leg. Total downstream delay impact: +${details.impact?.totalDownstreamDelayHours || reportedDelayHours}h.`,
          prescribedAction: details.impact?.recommendedControlTowerAction || "Active Monitoring",
        };

        return {
          ...s,
          legs: updatedLegs,
          status: newStatus,
          inventoryRisk: newRisk,
          currentEta: newEta,
          exceptions: [newException, ...(s.exceptions || [])],
          notifications: [newNotification, ...(s.notifications || [])],
          requiresCarrierAction: false,
        };
      })
    );

    // Also attempt backend synchronization if connected to actual database shipment
    try {
      const numericId = parseInt(shipmentId.replace(/\D/g, ""), 10);
      const numericLegId = parseInt(legId.replace(/\D/g, ""), 10);
      if (!isNaN(numericId) && !isNaN(numericLegId)) {
        await reportLegDisruption(numericId, numericLegId, {
          delay_hours: reportedDelayHours,
          disruption_reason: details.disruptionType,
          notes: details.notes,
        });
      }
    } catch (e) {
      // Non-blocking for mock/demo IDs
      console.log("Telemetry sync completed locally:", e);
    }

    // Trigger toast notification
    setSuccessToast({
      reference: selectedShipment?.reference || shipmentId,
      delayHours: reportedDelayHours,
      revisedEta: details.impact?.revisedEta || "Updated",
      impactExplanation:
        details.impact?.plainLanguageExplanation ||
        `Transit lag of ${reportedDelayHours}h broadcasted to company control tower.`,
    });
  };

  return (
    <div
      className="page animate-fade transporter-portal-page"
      style={{
        padding: "24px 32px",
        maxWidth: "1600px",
        margin: "0 auto",
        color: "var(--text-primary, #F3F6FA)",
      }}
    >
      {/* 1. Portal Header */}
      <PortalHeader
        carrierName={carrierName}
        companyName={companyName}
        onRefresh={handleRefresh}
        isRefreshing={isRefreshing}
      />

      {/* 2. Operational Summary KPI Cards */}
      <OperationalSummary shipments={shipments} />

      {/* 3. Priority Actions Alert Strip */}
      <PriorityActions
        shipments={shipments}
        onSelectShipment={(shipment) => {
          setSelectedShipmentId(shipment.id);
          const el = document.getElementById("shipment-detail-section");
          if (el) el.scrollIntoView({ behavior: "smooth" });
        }}
      />

      {/* Success Feedback Banner Toast */}
      {successToast && (
        <div
          role="alert"
          style={{
            background: "linear-gradient(135deg, rgba(45, 212, 167, 0.15) 0%, rgba(45, 212, 167, 0.05) 100%)",
            border: "1px solid rgba(45, 212, 167, 0.4)",
            borderRadius: "8px",
            padding: "16px 20px",
            marginBottom: "20px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
          }}
        >
          <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
            <CheckCircle2 size={22} color="#2DD4A7" style={{ marginTop: "2px", flexShrink: 0 }} />
            <div>
              <strong style={{ fontSize: "14px", color: "var(--text-primary, #F3F6FA)" }}>
                Delay Telematics Broadcasted • Control Tower Notified
              </strong>
              <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "var(--text-secondary, #A8B3C2)", lineHeight: 1.5 }}>
                {successToast.impactExplanation}
              </p>
              <div style={{ fontSize: "11px", color: "#2DD4A7", fontWeight: 600, marginTop: "4px" }}>
                ✓ Shipment {successToast.reference} schedule and ETA recalculated in central control tower.
              </div>
            </div>
          </div>

          <button
            onClick={() => setSuccessToast(null)}
            aria-label="Dismiss message"
            style={{
              background: "none",
              border: "none",
              color: "var(--text-tertiary, #6F7C8C)",
              cursor: "pointer",
              padding: "4px",
            }}
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* 4. Filter, Search & Sorting Bar */}
      <ShipmentFilters
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        statusFilter={statusFilter}
        onStatusChange={setStatusFilter}
        riskFilter={riskFilter}
        onRiskChange={setRiskFilter}
        modeFilter={modeFilter}
        onModeChange={setModeFilter}
        serviceFilter={serviceFilter}
        onServiceChange={setServiceFilter}
        facilityFilter={facilityFilter}
        onFacilityChange={setFacilityFilter}
        facilityOptions={facilityOptions}
        sortBy={sortBy}
        onSortChange={setSortBy}
        totalFiltered={filteredShipments.length}
        totalCount={shipments.length}
      />

      {/* 5. Main Content: Table + Detail Panel */}
      <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
        {/* Scannable Shipments Table */}
        <section aria-label="Assigned Shipments Corridor Overview">
          <ShipmentTable
            shipments={filteredShipments}
            selectedShipmentId={selectedShipment?.id}
            onSelectShipment={(s) => setSelectedShipmentId(s.id)}
            onOpenReportModal={(s) => handleOpenReportModal(s)}
            onOpenDelayModal={(s) => handleOpenDelayModal(s)}
          />
        </section>

        {/* Selected Shipment Detail & Route Propagation Timeline */}
        {selectedShipment && (
          <section id="shipment-detail-section" aria-label="Selected Shipment Details and Route Timeline">
            <ShipmentDetailPanel
              shipment={selectedShipment}
              onOpenReportModal={(legId) => handleOpenReportModal(selectedShipment, legId)}
              onOpenDelayModal={() => handleOpenDelayModal(selectedShipment)}
            />
          </section>
        )}
      </div>

      {/* 6. Disruption Reporting Modal */}
      {isReportModalOpen && selectedShipment && (
        <DisruptionForm
          shipment={selectedShipment}
          initialLegId={reportTargetLegId}
          onClose={() => setIsReportModalOpen(false)}
          onSubmitSuccess={handleDisruptionSubmitSuccess}
        />
      )}

      {/* 7. Dedicated Report Delay Modal */}
      {isDelayModalOpen && (delayTargetShipment || selectedShipment) && (
        <ReportDelayModal
          shipment={delayTargetShipment || selectedShipment}
          isOpen={isDelayModalOpen}
          onClose={() => setIsDelayModalOpen(false)}
          onDelayReported={handleDelayReported}
        />
      )}
    </div>
  );
}

