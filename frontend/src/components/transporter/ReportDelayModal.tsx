import React, { useState, useEffect } from "react";
import { Shipment } from "../../types/transporter";
import { X, Clock, AlertTriangle, Calendar, FileText, CheckCircle2, ShieldAlert } from "lucide-react";
import { reportShipmentDelay } from "../../services/api";

interface ReportDelayModalProps {
  shipment: Shipment | null;
  isOpen: boolean;
  onClose: () => void;
  onDelayReported: (data: {
    shipmentId: string;
    newEta: string;
    delayHours: number;
    reason: string;
    notes?: string;
    reportedBy: string;
    reportedAt: string;
  }) => void;
}

const DELAY_REASONS = [
  { value: "TRAFFIC_CONGESTION", label: "Traffic congestion" },
  { value: "WEATHER", label: "Weather / Environmental" },
  { value: "VEHICLE_BREAKDOWN", label: "Vehicle breakdown / Mechanical" },
  { value: "LOADING_UNLOADING_DELAY", label: "Loading / Unloading delay" },
  { value: "DOCK_APPOINTMENT_DELAY", label: "Dock or appointment delay" },
  { value: "CUSTOMS_BORDER_DELAY", label: "Customs / Border inspection hold" },
  { value: "PORT_CONGESTION", label: "Port congestion" },
  { value: "DRIVER_AVAILABILITY", label: "Driver availability / HOS compliance" },
  { value: "OTHER", label: "Other" },
];

export function ReportDelayModal({
  shipment,
  isOpen,
  onClose,
  onDelayReported,
}: ReportDelayModalProps) {
  if (!isOpen || !shipment) return null;

  // Form State
  const [selectedLegId, setSelectedLegId] = useState<string>("");
  const [inputMode, setInputMode] = useState<"hours" | "datetime">("hours");
  const [delayHours, setDelayHours] = useState<string>("4");
  const [newEtaDatetime, setNewEtaDatetime] = useState<string>("");
  const [reason, setReason] = useState<string>("TRAFFIC_CONGESTION");
  const [notes, setNotes] = useState<string>("");
  const [attachmentName, setAttachmentName] = useState<string>("");

  // UI state
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [successMsg, setSuccessMsg] = useState<string>("");

  // Baseline dates
  const currentEtaDate = new Date(shipment.currentEta || shipment.plannedDelivery);

  // Initialize newEtaDatetime default on open
  useEffect(() => {
    if (shipment) {
      const defaultEta = new Date(currentEtaDate.getTime() + 4 * 3600 * 1000);
      const iso = defaultEta.toISOString().slice(0, 16);
      setNewEtaDatetime(iso);
      setDelayHours("4");
      // Pick first active or uncompleted leg by default
      const defaultLeg = shipment.legs?.find((l) => l.status !== "on_schedule") || shipment.legs?.[0];
      setSelectedLegId(defaultLeg?.id || "");
      setErrorMsg("");
      setSuccessMsg("");
    }
  }, [shipment]);

  // Derived Preview calculation
  const computedPreview = () => {
    let previewEta = new Date(currentEtaDate);
    let hoursDiff = 0;

    if (inputMode === "hours") {
      const h = parseFloat(delayHours) || 0;
      hoursDiff = h;
      previewEta = new Date(currentEtaDate.getTime() + h * 3600 * 1000);
    } else {
      if (newEtaDatetime) {
        const selectedDate = new Date(newEtaDatetime);
        hoursDiff = Math.max(0, Math.round(((selectedDate.getTime() - currentEtaDate.getTime()) / (3600 * 1000)) * 10) / 10);
        previewEta = selectedDate;
      }
    }

    return {
      previewEta,
      hoursDiff,
      isValidFuture: previewEta.getTime() > Date.now(),
    };
  };

  const preview = computedPreview();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg("");

    // Validate
    if (inputMode === "hours") {
      const h = parseFloat(delayHours);
      if (isNaN(h) || h <= 0) {
        setErrorMsg("Delay hours must be greater than 0.");
        return;
      }
    } else {
      if (!newEtaDatetime) {
        setErrorMsg("Please select a revised date and time.");
        return;
      }
      const selected = new Date(newEtaDatetime);
      if (selected.getTime() <= Date.now()) {
        setErrorMsg("Revised ETA must be in the future.");
        return;
      }
    }

    if (!reason) {
      setErrorMsg("Please select a delay reason.");
      return;
    }

    setIsSubmitting(true);
    const idempotencyKey = `delay-${shipment.id}-${Date.now()}`;

    try {
      const numericId = parseInt(shipment.id.replace(/\D/g, ""), 10);
      const numericLegId = selectedLegId ? parseInt(selectedLegId.replace(/\D/g, ""), 10) : undefined;
      const finalDelayHours = preview.hoursDiff;
      const finalEtaIso = preview.previewEta.toISOString();

      if (!isNaN(numericId)) {
        await reportShipmentDelay(numericId, {
          delay_hours: finalDelayHours,
          new_eta: finalEtaIso,
          leg_id: !isNaN(Number(numericLegId)) ? numericLegId : undefined,
          reason,
          notes: notes.trim() || undefined,
          idempotency_key: idempotencyKey,
        });
      }

      setSuccessMsg("Delay reported. ETA updated. Control Tower has been notified.");

      setTimeout(() => {
        onDelayReported({
          shipmentId: shipment.id,
          newEta: finalEtaIso,
          delayHours: finalDelayHours,
          reason,
          notes,
          reportedBy: "Carrier Fleet Dispatch",
          reportedAt: new Date().toISOString(),
        });
        setIsSubmitting(false);
        onClose();
      }, 1200);
    } catch (err: any) {
      setIsSubmitting(false);
      const detail = err?.response?.data?.detail || err?.message || "Failed to submit delay report.";
      setErrorMsg(`Error: ${detail}`);
    }
  };

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(7, 10, 15, 0.78)",
        backdropFilter: "blur(5px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
        padding: "16px",
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="report-delay-title"
    >
      <div
        className="animate-fade"
        style={{
          width: "100%",
          maxWidth: "560px",
          backgroundColor: "var(--bg-surface-1, #121820)",
          border: "1px solid var(--border-color, #232E3C)",
          borderRadius: "10px",
          boxShadow: "0 20px 45px rgba(0,0,0,0.5)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid var(--border-color, #232E3C)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "linear-gradient(180deg, rgba(255, 140, 66, 0.08) 0%, transparent 100%)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "36px",
                height: "36px",
                borderRadius: "8px",
                backgroundColor: "rgba(255, 140, 66, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#FF8C42",
              }}
            >
              <Clock size={20} />
            </div>
            <div>
              <h3 id="report-delay-title" style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "#F3F6FA" }}>
                Report Transit Delay
              </h3>
              <p style={{ margin: "2px 0 0", fontSize: "12px", color: "var(--text-tertiary, #6F7C8C)" }}>
                Fast-track operational ETA revision & Control Tower broadcast
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--text-secondary, #A0AEC0)",
              cursor: "pointer",
              padding: "6px",
              borderRadius: "4px",
            }}
            aria-label="Close modal"
          >
            <X size={18} />
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "16px" }}>
          {/* Read-Only Shipment Context */}
          <div
            style={{
              padding: "12px 14px",
              borderRadius: "6px",
              backgroundColor: "rgba(25, 34, 45, 0.7)",
              border: "1px solid var(--border-color, #232E3C)",
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "10px",
              fontSize: "12px",
            }}
          >
            <div>
              <span style={{ color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>Shipment Reference:</span>
              <strong style={{ color: "#F3F6FA", fontSize: "13px" }}>{shipment.reference}</strong>
            </div>
            <div>
              <span style={{ color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>Current Status:</span>
              <span
                style={{
                  display: "inline-block",
                  padding: "2px 8px",
                  borderRadius: "4px",
                  fontSize: "11px",
                  fontWeight: 600,
                  backgroundColor: shipment.status === "critical" ? "rgba(255, 77, 95, 0.2)" : "rgba(255, 140, 66, 0.2)",
                  color: shipment.status === "critical" ? "#FF4D5F" : "#FF8C42",
                  textTransform: "uppercase",
                }}
              >
                {shipment.status.replace("_", " ")}
              </span>
            </div>
            <div>
              <span style={{ color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>Baseline Planned ETA:</span>
              <span style={{ color: "#A0AEC0" }}>{new Date(shipment.plannedDelivery).toLocaleString()}</span>
            </div>
            <div>
              <span style={{ color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>Current ETA:</span>
              <span style={{ color: "#FFB074", fontWeight: 600 }}>{currentEtaDate.toLocaleString()}</span>
            </div>
          </div>

          {/* Multi-Leg Selection (if shipment has multiple legs) */}
          {shipment.legs && shipment.legs.length > 1 && (
            <div>
              <label htmlFor="delay-leg-select" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#F3F6FA", marginBottom: "4px" }}>
                Affected Transit Leg / Milestone *
              </label>
              <select
                id="delay-leg-select"
                value={selectedLegId}
                onChange={(e) => setSelectedLegId(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-surface-2, #19222D)",
                  border: "1px solid var(--border-color, #232E3C)",
                  color: "#F3F6FA",
                  fontSize: "12px",
                }}
              >
                {shipment.legs.map((leg) => (
                  <option key={leg.id} value={leg.id}>
                    Leg #{leg.sequence} ({leg.mode.toUpperCase()}): {leg.origin} → {leg.destination} {leg.carrierName ? `[${leg.carrierName}]` : ""}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Input Method Toggle */}
          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#F3F6FA", marginBottom: "6px" }}>
              How would you like to specify the delay?
            </label>
            <div style={{ display: "flex", gap: "8px" }}>
              <button
                type="button"
                onClick={() => setInputMode("hours")}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: 600,
                  border: inputMode === "hours" ? "1px solid #FF8C42" : "1px solid var(--border-color, #232E3C)",
                  backgroundColor: inputMode === "hours" ? "rgba(255, 140, 66, 0.15)" : "transparent",
                  color: inputMode === "hours" ? "#FF8C42" : "var(--text-secondary, #A0AEC0)",
                  cursor: "pointer",
                }}
              >
                + Delay in Hours
              </button>
              <button
                type="button"
                onClick={() => setInputMode("datetime")}
                style={{
                  flex: 1,
                  padding: "8px 12px",
                  borderRadius: "6px",
                  fontSize: "12px",
                  fontWeight: 600,
                  border: inputMode === "datetime" ? "1px solid #FF8C42" : "1px solid var(--border-color, #232E3C)",
                  backgroundColor: inputMode === "datetime" ? "rgba(255, 140, 66, 0.15)" : "transparent",
                  color: inputMode === "datetime" ? "#FF8C42" : "var(--text-secondary, #A0AEC0)",
                  cursor: "pointer",
                }}
              >
                Specific New Date / Time
              </button>
            </div>
          </div>

          {/* Delay Specification Input */}
          {inputMode === "hours" ? (
            <div>
              <label htmlFor="delay-hours-input" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#F3F6FA", marginBottom: "4px" }}>
                Estimated Delay Duration (Hours) *
              </label>
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <input
                  id="delay-hours-input"
                  type="number"
                  min="0.5"
                  step="0.5"
                  max="720"
                  value={delayHours}
                  onChange={(e) => setDelayHours(e.target.value)}
                  style={{
                    width: "120px",
                    padding: "8px 12px",
                    borderRadius: "6px",
                    backgroundColor: "var(--bg-surface-2, #19222D)",
                    border: "1px solid var(--border-color, #232E3C)",
                    color: "#F3F6FA",
                    fontSize: "14px",
                  }}
                  required
                />
                <div style={{ display: "flex", gap: "4px" }}>
                  {[2, 4, 8, 12, 24].map((h) => (
                    <button
                      key={h}
                      type="button"
                      onClick={() => setDelayHours(h.toString())}
                      style={{
                        padding: "5px 9px",
                        borderRadius: "4px",
                        fontSize: "11px",
                        border: "1px solid var(--border-color, #232E3C)",
                        backgroundColor: delayHours === h.toString() ? "rgba(255, 140, 66, 0.2)" : "rgba(25, 34, 45, 0.5)",
                        color: delayHours === h.toString() ? "#FF8C42" : "var(--text-secondary, #A0AEC0)",
                        cursor: "pointer",
                      }}
                    >
                      +{h}h
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div>
              <label htmlFor="new-eta-input" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#F3F6FA", marginBottom: "4px" }}>
                New Estimated Arrival (Date & Time) *
              </label>
              <input
                id="new-eta-input"
                type="datetime-local"
                value={newEtaDatetime}
                onChange={(e) => setNewEtaDatetime(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  backgroundColor: "var(--bg-surface-2, #19222D)",
                  border: "1px solid var(--border-color, #232E3C)",
                  color: "#F3F6FA",
                  fontSize: "13px",
                }}
                required
              />
            </div>
          )}

          {/* Delay Reason Dropdown */}
          <div>
            <label htmlFor="delay-reason-select" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#F3F6FA", marginBottom: "4px" }}>
              Delay Reason *
            </label>
            <select
              id="delay-reason-select"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "6px",
                backgroundColor: "var(--bg-surface-2, #19222D)",
                border: "1px solid var(--border-color, #232E3C)",
                color: "#F3F6FA",
                fontSize: "13px",
              }}
              required
            >
              {DELAY_REASONS.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          {/* Optional Notes */}
          <div>
            <label htmlFor="delay-notes-input" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#F3F6FA", marginBottom: "4px" }}>
              Carrier Operational Notes (Optional)
            </label>
            <textarea
              id="delay-notes-input"
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="e.g. Traffic backlog extending 15km on interstate corridor; backup unit dispatched."
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "6px",
                backgroundColor: "var(--bg-surface-2, #19222D)",
                border: "1px solid var(--border-color, #232E3C)",
                color: "#F3F6FA",
                fontSize: "12px",
                resize: "vertical",
              }}
            />
          </div>

          {/* Optional Attachment Upload */}
          <div>
            <label style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "#F3F6FA", marginBottom: "4px" }}>
              Supporting Proof / Documentation (Optional)
            </label>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
              <input
                type="file"
                id="delay-attachment"
                style={{ display: "none" }}
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    setAttachmentName(e.target.files[0].name);
                  }
                }}
              />
              <button
                type="button"
                onClick={() => document.getElementById("delay-attachment")?.click()}
                style={{
                  padding: "6px 12px",
                  borderRadius: "6px",
                  border: "1px dashed var(--border-color, #232E3C)",
                  backgroundColor: "rgba(25, 34, 45, 0.5)",
                  color: "var(--text-secondary, #A0AEC0)",
                  fontSize: "12px",
                  cursor: "pointer",
                }}
              >
                Choose File...
              </button>
              <span style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)" }}>
                {attachmentName || "No file chosen (e.g. gate slip, BOL, photo)"}
              </span>
            </div>
          </div>

          {/* Live Preview Callout */}
          <div
            style={{
              padding: "10px 14px",
              borderRadius: "6px",
              backgroundColor: "rgba(255, 140, 66, 0.08)",
              border: "1px solid rgba(255, 140, 66, 0.3)",
              fontSize: "12px",
              color: "#F3F6FA",
            }}
          >
            <div style={{ fontWeight: 600, color: "#FF8C42", marginBottom: "2px" }}>
              Timeline Impact Preview:
            </div>
            <div>
              Current ETA: <strong>{currentEtaDate.toLocaleString()}</strong> → New ETA:{" "}
              <strong style={{ color: "#2DD4A7" }}>{preview.previewEta.toLocaleString()}</strong>{" "}
              <span style={{ color: "#FF8C42", fontWeight: 700 }}>(+{preview.hoursDiff} hours)</span>
            </div>
          </div>

          {/* Error Message */}
          {errorMsg && (
            <div
              style={{
                padding: "8px 12px",
                borderRadius: "6px",
                backgroundColor: "rgba(255, 77, 95, 0.15)",
                border: "1px solid rgba(255, 77, 95, 0.4)",
                color: "#FF4D5F",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <ShieldAlert size={16} />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Success Message */}
          {successMsg && (
            <div
              style={{
                padding: "8px 12px",
                borderRadius: "6px",
                backgroundColor: "rgba(45, 212, 167, 0.15)",
                border: "1px solid rgba(45, 212, 167, 0.4)",
                color: "#2DD4A7",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <CheckCircle2 size={16} />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "10px", marginTop: "4px" }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isSubmitting}
              className="btn-secondary"
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                fontSize: "12px",
                cursor: isSubmitting ? "not-allowed" : "pointer",
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !preview.isValidFuture}
              style={{
                padding: "8px 20px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 700,
                backgroundColor: "#FF8C42",
                color: "#0B0E14",
                border: "none",
                cursor: isSubmitting || !preview.isValidFuture ? "not-allowed" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                boxShadow: "0 4px 14px rgba(255, 140, 66, 0.35)",
              }}
            >
              {isSubmitting ? "Broadcasting..." : "Submit Delay Report"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

