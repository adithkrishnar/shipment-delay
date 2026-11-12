// ── Core Domain Types for Collaborative Multi-Leg Transporter Portal ──────────

export type TransportMode = "road" | "rail" | "sea" | "air";

export type ServiceLevel = "standard" | "express" | "expedited" | "economy";

export type ShipmentStatus =
  | "on_schedule"
  | "monitoring"
  | "at_risk"
  | "disrupted"
  | "delayed"
  | "critical";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type DisruptionCategory =
  | "Vehicle breakdown"
  | "Traffic"
  | "Weather"
  | "Accident"
  | "Port congestion"
  | "Customs inspection"
  | "Missed connection"
  | "Labor shortage"
  | "Documentation issue"
  | "Other";

export interface ConnectionInfo {
  type: "port_cutoff" | "rail_slot" | "vessel" | "flight" | "cross_dock";
  cutoffTime: string;          // ISO string or formatted timestamp
  nextAvailableSlot?: string;   // ISO string or formatted timestamp
  penaltyHours?: number;       // Explicit cycle penalty e.g. 72h for weekly vessel
  missed?: boolean;
  name?: string;               // e.g. "Vessel Cutoff (MSC Gulsun)"
}

export interface ShipmentLeg {
  id: string;
  sequence: number;
  mode: TransportMode;
  carrierId: string;
  carrierName: string;
  origin: string;
  destination: string;
  plannedDeparture: string;
  plannedArrival: string;
  revisedArrival?: string;
  status: ShipmentStatus;
  delayHours?: number;
  currentLocation?: string;
  connection?: ConnectionInfo;
  isCarrierAssigned?: boolean; // Indicates if the logged in carrier is responsible for this leg
}

export interface DisruptionReport {
  id: string;
  shipmentId: string;
  legId: string;
  reportedBy: string;
  reportedAt: string;
  disruptionType: DisruptionCategory | string;
  location?: string;
  delayHours: number;
  expectedRecoveryTime?: string;
  reason: string;
  notes?: string;
  status: "submitted" | "acknowledged" | "resolved";
}

export interface ControlTowerNotification {
  id: string;
  timestamp: string;
  type: "DISRUPTION_ALERT" | "ETA_RECALCULATION" | "MITIGATION_REQUESTED" | "CRITICAL_STOCKOUT_RISK";
  message: string;
  prescribedAction: string;
}

export interface Shipment {
  id: string;
  reference: string;
  origin: string;
  destination: string;
  customer?: string;
  destinationFacility: string;
  carrierId: string;
  carrierName: string;
  serviceLevel: ServiceLevel;
  transportModes: TransportMode[];
  legs: ShipmentLeg[];
  plannedDelivery: string;
  currentEta: string;
  status: ShipmentStatus;
  inventoryRisk: RiskLevel;
  requiresCarrierAction: boolean;
  exceptions: DisruptionReport[];
  notifications?: ControlTowerNotification[];
  currentCheckpoint?: string;
}

export interface DelayCalculationResult {
  legDelayHours: number;
  missedConnectionPenaltyHours: number;
  totalDownstreamDelayHours: number;
  totalDownstreamDelayDays: number;
  originalEta: string;
  revisedEta: string;
  missedConnection?: {
    type: string;
    cutoffTime: string;
    nextAvailableSlot: string;
    penaltyHours: number;
    explanation: string;
  };
  inventoryRisk: RiskLevel;
  inventoryRiskExplanation: string;
  recommendedControlTowerAction: string;
  plainLanguageExplanation: string;
}

