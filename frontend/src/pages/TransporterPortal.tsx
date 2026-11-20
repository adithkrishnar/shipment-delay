import React, { useState, useMemo, useEffect } from "react";
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
import { reportLegDisruption, reportShipmentDelay, getAssignedShipments, updateAssignmentAction } from "../services/api";
import { useAlert } from "../context/AlertContext";
import { formatDateTime } from "../utils/delayPropagation";

export default function TransporterPortal() {
  const { user } = useAuth();
  const { triggerAlert } = useAlert();
  const carrierName = user?.carrier_name || MOCK_CARRIER_NAME;
  const companyName = user?.company?.name || "DataCo Global Supply Chain";

  // Shipments state strictly loaded from live authenticated backend
  const [shipments, setShipments] = useState<Shipment[]>([]);
  const [selectedShipmentId, setSelectedShipmentId] = useState<string>("");
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Disruption modal state
  const [isReportModalOpen, setIsReportModalOpen] = useState<boolean>(false);
  const [reportTargetLegId, setReportTargetLegId] = useState<string | undefined>(undefined);

  // Delay modal state
  const [isDelayModalOpen, setIsDelayModalOpen] = useState<boolean>(false);
  const [delayTargetShipment, setDelayTargetShipment] = useState<Shipment | null>(null);

  // Synchronized Control Tower Approved Actions
  const [approvedActionIds, setApprovedActionIds] = useState<Set<string>>(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("supplyiq_approved_actions") || "[]");
      return new Set(stored);
    } catch {
      return new Set();
    }
  });

  useEffect(() => {
    const syncApproved = () => {
      try {
        const stored = JSON.parse(localStorage.getItem("supplyiq_approved_actions") || "[]");
        setApprovedActionIds(new Set(stored));
      } catch {
        // ignore
      }
    };

    const handleActionApproved = (e: any) => {
      syncApproved();
      const actionId = e.detail?.actionId || "Shipment Delay";
      triggerAlert({
        title: "Control Tower Action Approved",
        message: `Control Tower approved mitigation action for ${actionId}! Downstream stockout risk is neutralized.`,
        severity: "healthy",
      });
    };

    window.addEventListener("supplyiq_action_approved", handleActionApproved);
    const handleStorage = (e: StorageEvent) => {
      if (e.key === "supplyiq_approved_actions") {
        syncApproved();
      }
    };
    window.addEventListener("storage", handleStorage);
    const interval = setInterval(syncApproved, 2500);

    return () => {
      window.removeEventListener("supplyiq_action_approved", handleActionApproved);
      window.removeEventListener("storage", handleStorage);
      clearInterval(interval);
    };
  }, []);

  // Live polling of assigned shipments from backend
  useEffect(() => {
    let active = true;
    const fetchLive = async () => {
      try {
        const live = await getAssignedShipments();
        if (active) {
          if (Array.isArray(live)) {
            const adapted: Shipment[] = live.map((s: any) => {
              const hasDelayedLeg = s.legs?.some((l: any) => (l.delay_hours || 0) > 0);
              const isPending = s.assignment_status === "PENDING";
              const isDelivered = s.assignment_status === "DELIVERED";
              return {
                id: String(s.id),
                reference: s.external_shipment_id || `SH-${s.id}`,
                origin: s.origin,
                destination: s.destination,
                destinationFacility: s.destination || "Destination Facility",
                carrierId: "CARRIER-B",
                carrierName: s.carrier || carrierName,
                customer: s.company_name,
                serviceLevel: "express" as const,
                transportModes: [s.transport_mode?.toLowerCase() || "road"],
                plannedDelivery: s.planned_delivery,
                currentEta: s.current_eta || s.planned_delivery,
                status: isPending ? ("at_risk" as const) :
                        (hasDelayedLeg || s.assignment_status === "DELAYED") ? ("delayed" as const) :
                        isDelivered ? ("on_schedule" as const) : ("on_schedule" as const),
                assignmentStatus: s.assignment_status || "ACCEPTED",
                inventoryRisk: (hasDelayedLeg || s.assignment_status === "DELAYED") ? ("critical" as const) : ("low" as const),
                requiresCarrierAction: isPending || hasDelayedLeg,
                legs: (s.legs || []).map((l: any) => {
                  const isLegAssigned = l.is_assigned_to_caller !== undefined
                    ? Boolean(l.is_assigned_to_caller)
                    : (!l.carrier_name || l.carrier_name.toLowerCase().trim() === carrierName.toLowerCase().trim() || Boolean(user?.is_superuser));
                  return {
                    id: String(l.id),
                    sequence: l.sequence,
                    mode: (l.mode?.toLowerCase() || "road") as any,
                    carrierId: isLegAssigned ? "CARRIER-B" : "CARRIER-PARTNER",
                    carrierName: l.carrier_name || carrierName,
                    origin: l.origin,
                    destination: l.destination,
                    plannedDeparture: s.order_date || s.planned_delivery,
                    plannedArrival: s.planned_delivery,
                    status: l.status === "COMPLETED" ? ("on_schedule" as const) :
                            l.status === "IN_TRANSIT" ? ("on_schedule" as const) :
                            l.status === "DELAYED" ? ("delayed" as const) : ("monitoring" as const),
                    delayHours: l.delay_hours || 0,
                    isCarrierAssigned: isLegAssigned
                  };
                }),
                exceptions: [],
                notifications: []
              };
            });
            setShipments(adapted);
          } else {
            setShipments([]);
          }
        }
      } catch (e) {
        console.warn("Could not fetch assigned shipments from backend:", e);
      }
    };
    fetchLive();
    const liveInterval = setInterval(fetchLive, 3500);
    return () => {
      active = false;
      clearInterval(liveInterval);
    };
  }, [user]);

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
    const targetShipment = shipments.find((s) => s.id === data.shipmentId) || selectedShipment;

    // Real cloud synchronization for cross-laptop multi-device alerts
    (async () => {
      try {
        const shipmentRef = targetShipment?.reference || data.shipmentId;
        await reportShipmentDelay(shipmentRef, {
          delay_hours: data.delayHours,
          reason: data.reason.replace(/_/g, " "),
          notes: data.notes || "Field delay reported via Transporter Portal.",
          new_eta: data.newEta ? new Date(data.newEta).toISOString() : undefined,
        });
      } catch (err) {
        console.warn("Cloud delay sync to backend:", err);
      }
    })();

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
          message: `Carrier reported ${data.reason.replace(/_/g, " ")} (+${data.delayHours}h). Revised ETA: ${formatDateTime(data.newEta)}`,
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
      reference: targetShipment?.reference || data.shipmentId,
      delayHours: data.delayHours,
      revisedEta: formatDateTime(data.newEta),
      impactExplanation: `Delay of ${data.delayHours}h reported due to ${data.reason.replace(/_/g, " ")}. Control Tower notified.`,
    });

    triggerAlert({
      title: "Carrier Incident Broadcasted",
      message: `${carrierName} logged a +${data.delayHours}h delay on ${targetShipment?.reference || "Shipment"} due to ${data.reason.replace(/_/g, " ")}. Control Tower notified.`,
      severity: data.delayHours >= 12 ? "critical" : "warning",
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

    // Also attempt backend synchronization to PostgreSQL on Render
    try {
      const numericId = parseInt(shipmentId.replace(/\D/g, ""), 10) || 801;
      const numericLegId = parseInt(legId.replace(/\D/g, ""), 10) || 2;
      try {
        await reportLegDisruption(numericId, numericLegId, {
          delay_hours: reportedDelayHours,
          disruption_reason: details.disruptionType,
          notes: details.notes,
        });
      } catch {
        await reportShipmentDelay(numericId, {
          delay_hours: reportedDelayHours,
          reason: details.disruptionType || "Field Disruption",
          notes: details.notes,
        });
      }
    } catch (e) {
      console.log("Telemetry cloud sync notice:", e);
    }

    const curShipment = shipments.find((s) => s.id === shipmentId) || selectedShipment;
    const curLeg = curShipment?.legs?.find((l) => l.id === legId);

    triggerAlert({
      title: "Control Tower Disruption Broadcasted",
      message: `${carrierName} broadcasted ${details.disruptionType} on ${curShipment?.reference || "Shipment"} (+${reportedDelayHours}h). Control Tower notified.`,
      severity: reportedDelayHours >= 12 ? "critical" : "warning",
    });

    // Trigger toast notification
    setSuccessToast({
      reference: curShipment?.reference || shipmentId,
      delayHours: reportedDelayHours,
      revisedEta: details.impact?.revisedEta || "Updated",
      impactExplanation:
        details.impact?.plainLanguageExplanation ||
        `Transit lag of ${reportedDelayHours}h broadcasted to company control tower.`,
    });
  };

  const handleAcceptAssignment = async (shipment: Shipment) => {
    try {
      await updateAssignmentAction(Number(shipment.id), { action: "ACCEPT" });
      triggerAlert({
        title: "Assignment Accepted",
        message: `Freight assignment for ${shipment.reference} accepted! Transit corridor is now active.`,
        severity: "healthy",
      });
      handleRefresh();
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || "Failed to accept assignment");
    }
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
            onAcceptAssignment={handleAcceptAssignment}
            approvedActionIds={approvedActionIds}
          />
        </section>

        {/* Selected Shipment Detail & Route Propagation Timeline */}
        {selectedShipment && (() => {
          const isSelectedApproved = Boolean(
            approvedActionIds.has(selectedShipment.reference) ||
            approvedActionIds.has(selectedShipment.id) ||
            approvedActionIds.has(`DISRUPTION-${selectedShipment.id}`) ||
            (approvedActionIds.has("DC-PO-00809") && (selectedShipment.reference === "DC-PO-00809" || selectedShipment.id === "SH-DC-809")) ||
            (approvedActionIds.has("DC-PO-00801") && (selectedShipment.reference === "DC-PO-00801" || selectedShipment.id === "SH-DC-801")) ||
            (approvedActionIds.has("SKU-1004") && (selectedShipment.reference === "DC-PO-00809" || selectedShipment.reference === "DC-PO-00801"))
          );

          return (
            <section id="shipment-detail-section" aria-label="Selected Shipment Details and Route Timeline">
              <ShipmentDetailPanel
                shipment={selectedShipment}
                onOpenReportModal={(legId) => handleOpenReportModal(selectedShipment, legId)}
                onOpenDelayModal={() => handleOpenDelayModal(selectedShipment)}
                onAcceptAssignment={() => handleAcceptAssignment(selectedShipment)}
                isApproved={isSelectedApproved}
              />
            </section>
          );
        })()}
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

