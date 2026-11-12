import React, { useState, useMemo } from "react";
import { Shipment, ShipmentLeg, DisruptionCategory } from "../../types/transporter";
import { calculateDelayPropagation, formatDateTime } from "../../utils/delayPropagation";
import { AlertTriangle, Clock, MapPin, Send, AlertOctagon, Sparkles, X, ShieldAlert, CheckCircle2 } from "lucide-react";

interface DisruptionFormProps {
  shipment: Shipment;
  initialLegId?: string;
  onClose: () => void;
  onSubmitSuccess: (shipmentId: string, legId: string, reportedDelayHours: number, details: any) => void;
}

const DISRUPTION_TYPES: DisruptionCategory[] = [
  "Vehicle breakdown",
  "Traffic",
  "Weather",
  "Accident",
  "Port congestion",
  "Customs inspection",
  "Missed connection",
  "Labor shortage",
  "Documentation issue",
  "Other",
];

export function DisruptionForm({
  shipment,
  initialLegId,
  onClose,
  onSubmitSuccess,
}: DisruptionFormProps) {
  // Only permit reporting against assigned, uncompleted legs
  const availableLegs = useMemo(() => {
    return (shipment.legs || []).filter((l) => l.isCarrierAssigned !== false);
  }, [shipment]);

  const [selectedLegId, setSelectedLegId] = useState<string>(
    initialLegId || (availableLegs[0]?.id || shipment.legs[0]?.id || "")
  );

  const [disruptionType, setDisruptionType] = useState<DisruptionCategory>("Vehicle breakdown");
  const [delayValue, setDelayValue] = useState<number>(12);
  const [delayUnit, setDelayUnit] = useState<"hours" | "days">("hours");
  const [location, setLocation] = useState<string>(shipment.currentCheckpoint || "");
  const [expectedRecoveryTime, setExpectedRecoveryTime] = useState<string>("");
  const [reason, setReason] = useState<string>("");
  const [notes, setNotes] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");

  const [submitting, setSubmitting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  // Compute total reported delay hours
  const calculatedDelayHours = useMemo(() => {
    const val = Number(delayValue) || 0;
    return delayUnit === "days" ? val * 24 : val;
  }, [delayValue, delayUnit]);

  // Live impact preview calculation
  const impactPreview = useMemo(() => {
    if (calculatedDelayHours <= 0) return null;
    return calculateDelayPropagation(shipment, selectedLegId, calculatedDelayHours);
  }, [shipment, selectedLegId, calculatedDelayHours]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (calculatedDelayHours <= 0) {
      setValidationError("Delay duration must be greater than 0.");
      return;
    }

    if (!selectedLegId) {
      setValidationError("Please select an active leg under your operational responsibility.");
      return;
    }

    if (!reason.trim()) {
      setValidationError("Please provide a concise root cause explanation for the control tower.");
      return;
    }

    if (calculatedDelayHours > 336) { // 14 days
      setValidationError("Warning: Entered delay exceeds 14 days. Please verify telematics data.");
      return;
    }

    setSubmitting(true);

    // Prepare simulated telematics report
    const reportPayload = {
      disruptionType,
      delayHours: calculatedDelayHours,
      location: location.trim() || undefined,
      expectedRecoveryTime: expectedRecoveryTime || undefined,
      reason: reason.trim(),
      notes: notes.trim() || undefined,
      fileName: fileName || undefined,
      impact: impactPreview,
    };

    setTimeout(() => {
      setSubmitting(false);
      onSubmitSuccess(shipment.id, selectedLegId, calculatedDelayHours, reportPayload);
    }, 600);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="disruption-form-title"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(4px)",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        zIndex: 1100,
        padding: "16px",
      }}
    >
      <div
        style={{
          background: "var(--bg-surface-1, #151C24)",
          border: "1px solid var(--border-default, #26313D)",
          borderRadius: "var(--r-xl, 10px)",
          width: "100%",
          maxWidth: "760px",
          maxHeight: "90vh",
          overflowY: "auto",
          padding: "24px 28px",
          boxShadow: "0 20px 40px rgba(0,0,0,0.5)",
          color: "var(--text-primary, #F3F6FA)",
        }}
      >
        {/* Modal Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "18px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  padding: "2px 8px",
                  borderRadius: "4px",
                  background: "#FF8C42",
                  color: "#fff",
                  textTransform: "uppercase",
                }}
              >
                Carrier Field Exception
              </span>
              <span style={{ fontSize: "13px", color: "var(--text-secondary, #A8B3C2)", fontWeight: 600 }}>
                {shipment.reference} ({shipment.destinationFacility})
              </span>
            </div>
            <h2 id="disruption-form-title" style={{ fontSize: "20px", fontWeight: 700, margin: 0, letterSpacing: "-0.01em" }}>
              Broadcast Transit Disruption to Control Tower
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close disruption form"
            style={{
              background: "none",
              border: "none",
              color: "var(--text-tertiary, #6F7C8C)",
              cursor: "pointer",
              padding: "4px",
            }}
          >
            <X size={20} />
          </button>
        </div>

        {validationError && (
          <div
            role="alert"
            style={{
              background: "rgba(255, 77, 95, 0.12)",
              border: "1px solid rgba(255, 77, 95, 0.4)",
              borderRadius: "6px",
              padding: "10px 14px",
              marginBottom: "16px",
              fontSize: "13px",
              color: "#FF4D5F",
              display: "flex",
              alignItems: "center",
              gap: "8px",
            }}
          >
            <AlertOctagon size={16} />
            {validationError}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Section 1: Target Leg & Disruption Type */}
          <div className="disruption-modal-grid-2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "16px" }}>
            <div>
              <label htmlFor="target-leg-select" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #A8B3C2)", marginBottom: "6px" }}>
                Affected Leg (Assigned Scope) *
              </label>
              <select
                id="target-leg-select"
                value={selectedLegId}
                onChange={(e) => setSelectedLegId(e.target.value)}
                required
                className="input"
                style={{
                  width: "100%",
                  height: "38px",
                  padding: "0 10px",
                  fontSize: "13px",
                  borderRadius: "6px",
                  background: "var(--bg-base, #0B0F14)",
                  color: "var(--text-primary, #F3F6FA)",
                  border: "1px solid var(--border-default, #26313D)",
                }}
              >
                {shipment.legs.map((leg) => (
                  <option key={leg.id} value={leg.id}>
                    Leg #{leg.sequence} ({leg.mode.toUpperCase()}) — {leg.carrierName} {leg.isCarrierAssigned ? "★ (Your Fleet)" : ""}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="disruption-type-select" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #A8B3C2)", marginBottom: "6px" }}>
                Disruption Category *
              </label>
              <select
                id="disruption-type-select"
                value={disruptionType}
                onChange={(e) => setDisruptionType(e.target.value as DisruptionCategory)}
                required
                className="input"
                style={{
                  width: "100%",
                  height: "38px",
                  padding: "0 10px",
                  fontSize: "13px",
                  borderRadius: "6px",
                  background: "var(--bg-base, #0B0F14)",
                  color: "var(--text-primary, #F3F6FA)",
                  border: "1px solid var(--border-default, #26313D)",
                }}
              >
                {DISRUPTION_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Section 2: Delay Value, Unit & Location */}
          <div className="disruption-modal-grid-2" style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: "16px", marginBottom: "16px" }}>
            <div>
              <label htmlFor="delay-val-input" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #A8B3C2)", marginBottom: "6px" }}>
                Delay Duration *
              </label>
              <div style={{ display: "flex", gap: "8px" }}>
                <input
                  id="delay-val-input"
                  type="number"
                  min="0.5"
                  step="0.5"
                  max="336"
                  value={delayValue}
                  onChange={(e) => setDelayValue(Number(e.target.value))}
                  required
                  className="input"
                  style={{
                    flex: 1,
                    height: "38px",
                    padding: "0 10px",
                    fontSize: "13px",
                    borderRadius: "6px",
                    background: "var(--bg-base, #0B0F14)",
                    color: "var(--text-primary, #F3F6FA)",
                    border: "1px solid var(--border-default, #26313D)",
                  }}
                />
                <select
                  value={delayUnit}
                  onChange={(e) => setDelayUnit(e.target.value as "hours" | "days")}
                  aria-label="Select delay unit"
                  className="input"
                  style={{
                    width: "90px",
                    height: "38px",
                    fontSize: "12px",
                    fontWeight: 600,
                    borderRadius: "6px",
                    background: "var(--bg-surface-2, #19222D)",
                    color: "var(--text-primary, #F3F6FA)",
                    border: "1px solid var(--border-default, #26313D)",
                  }}
                >
                  <option value="hours">Hours</option>
                  <option value="days">Days</option>
                </select>
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-tertiary, #6F7C8C)", marginTop: "4px" }}>
                Equivalent: <strong>{calculatedDelayHours} hours</strong> ({ (calculatedDelayHours / 24).toFixed(1) } days)
              </div>
            </div>

            <div>
              <label htmlFor="location-input" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #A8B3C2)", marginBottom: "6px" }}>
                Current Checkpoint / Location
              </label>
              <input
                id="location-input"
                type="text"
                placeholder="e.g. Milepost 45, Interstate 94"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                className="input"
                style={{
                  width: "100%",
                  height: "38px",
                  padding: "0 10px",
                  fontSize: "13px",
                  borderRadius: "6px",
                  background: "var(--bg-base, #0B0F14)",
                  color: "var(--text-primary, #F3F6FA)",
                  border: "1px solid var(--border-default, #26313D)",
                }}
              />
            </div>
          </div>

          {/* Section 3: Root Cause & Recovery Time */}
          <div className="disruption-modal-grid-2" style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: "16px", marginBottom: "16px" }}>
            <div>
              <label htmlFor="reason-input" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #A8B3C2)", marginBottom: "6px" }}>
                Root Cause / Incident Summary *
              </label>
              <input
                id="reason-input"
                type="text"
                placeholder="e.g. Broken alternator belt and cooling system fault"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
                className="input"
                style={{
                  width: "100%",
                  height: "38px",
                  padding: "0 10px",
                  fontSize: "13px",
                  borderRadius: "6px",
                  background: "var(--bg-base, #0B0F14)",
                  color: "var(--text-primary, #F3F6FA)",
                  border: "1px solid var(--border-default, #26313D)",
                }}
              />
            </div>

            <div>
              <label htmlFor="recovery-input" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #A8B3C2)", marginBottom: "6px" }}>
                Expected Recovery Time
              </label>
              <input
                id="recovery-input"
                type="text"
                placeholder="e.g. Today by 19:30 hrs"
                value={expectedRecoveryTime}
                onChange={(e) => setExpectedRecoveryTime(e.target.value)}
                className="input"
                style={{
                  width: "100%",
                  height: "38px",
                  padding: "0 10px",
                  fontSize: "13px",
                  borderRadius: "6px",
                  background: "var(--bg-base, #0B0F14)",
                  color: "var(--text-primary, #F3F6FA)",
                  border: "1px solid var(--border-default, #26313D)",
                }}
              />
            </div>
          </div>

          {/* Optional Driver Notes */}
          <div style={{ marginBottom: "18px" }}>
            <label htmlFor="driver-notes" style={{ display: "block", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary, #A8B3C2)", marginBottom: "6px" }}>
              Field Notes / Telematics Remarks (Optional)
            </label>
            <textarea
              id="driver-notes"
              rows={2}
              placeholder="e.g. Mechanic dispatch confirmed; replacement tractor unit mobilized from regional depot."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="input"
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: "13px",
                borderRadius: "6px",
                background: "var(--bg-base, #0B0F14)",
                color: "var(--text-primary, #F3F6FA)",
                border: "1px solid var(--border-default, #26313D)",
                resize: "vertical",
              }}
            />
          </div>

          {/* Live Impact Preview Card */}
          {impactPreview && (
            <div
              className="live-impact-preview-card"
              style={{
                background: "linear-gradient(135deg, rgba(79, 140, 255, 0.08) 0%, rgba(245, 185, 66, 0.05) 100%)",
                border: "1px solid rgba(79, 140, 255, 0.3)",
                borderRadius: "8px",
                padding: "16px",
                marginBottom: "20px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                <Sparkles size={16} color="var(--accent-primary, #4F8CFF)" />
                <strong style={{ fontSize: "13px", color: "var(--text-primary, #F3F6FA)", textTransform: "uppercase", letterSpacing: "0.03em" }}>
                  Live Impact Preview & Propagation Calculation
                </strong>
              </div>

              {/* Plain language explanation banner */}
              <p style={{ fontSize: "13px", color: "var(--text-primary, #F3F6FA)", margin: "0 0 10px 0", lineHeight: 1.5 }}>
                {impactPreview.plainLanguageExplanation}
              </p>

              {/* Metrics pill summary */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "8px" }}>
                <div style={{ background: "var(--bg-surface-2, #19222D)", padding: "8px 10px", borderRadius: "6px", border: "1px solid var(--border-subtle, #26313D)" }}>
                  <span style={{ fontSize: "10px", color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>LEG DELAY</span>
                  <strong style={{ fontSize: "14px", color: "#FF8C42" }}>+{impactPreview.legDelayHours}h</strong>
                </div>

                <div style={{ background: "var(--bg-surface-2, #19222D)", padding: "8px 10px", borderRadius: "6px", border: "1px solid var(--border-subtle, #26313D)" }}>
                  <span style={{ fontSize: "10px", color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>MISSED CUTOFF PENALTY</span>
                  <strong style={{ fontSize: "14px", color: impactPreview.missedConnectionPenaltyHours > 0 ? "#FF4D5F" : "var(--status-healthy, #2DD4A7)" }}>
                    {impactPreview.missedConnectionPenaltyHours > 0 ? `+${impactPreview.missedConnectionPenaltyHours}h` : "None (0h)"}
                  </strong>
                </div>

                <div style={{ background: "var(--bg-surface-2, #19222D)", padding: "8px 10px", borderRadius: "6px", border: "1px solid var(--border-subtle, #26313D)" }}>
                  <span style={{ fontSize: "10px", color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>DESTINATION INVENTORY RISK</span>
                  <strong
                    style={{
                      fontSize: "13px",
                      color:
                        impactPreview.inventoryRisk === "critical"
                          ? "#FF4D5F"
                          : impactPreview.inventoryRisk === "high"
                          ? "#FF8C42"
                          : impactPreview.inventoryRisk === "medium"
                          ? "#F5B942"
                          : "#2DD4A7",
                    }}
                  >
                    {impactPreview.inventoryRisk.toUpperCase()} RISK
                  </strong>
                </div>

                <div style={{ background: "var(--bg-surface-2, #19222D)", padding: "8px 10px", borderRadius: "6px", border: "1px solid var(--border-subtle, #26313D)" }}>
                  <span style={{ fontSize: "10px", color: "var(--text-tertiary, #6F7C8C)", display: "block" }}>REVISED ETA</span>
                  <strong style={{ fontSize: "12px", color: "var(--text-primary, #F3F6FA)" }}>
                    {formatDateTime(impactPreview.revisedEta)}
                  </strong>
                </div>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px" }}>
            <button
              type="button"
              onClick={onClose}
              className="btn-secondary"
              style={{ padding: "10px 18px", fontSize: "13px" }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="btn-primary"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                padding: "10px 22px",
                fontSize: "13px",
                fontWeight: 600,
                background: "linear-gradient(135deg, #FF8C42 0%, #D4541B 100%)",
                boxShadow: "0 2px 8px rgba(255, 140, 66, 0.3)",
              }}
            >
              <Send size={15} />
              {submitting ? "Broadcasting to Control Tower..." : "Submit Exception & Notify Control Tower"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

