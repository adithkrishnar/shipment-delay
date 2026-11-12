from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date

class DisruptionReportRequest(BaseModel):
    delay_hours: float = Field(..., ge=0.5, le=720, description="Estimated delay in hours (0.5 to 720)")
    disruption_reason: str = Field(..., min_length=2, max_length=120)
    incident_location: Optional[str] = Field(None, max_length=255)
    evidence_url: Optional[str] = Field(None, max_length=500)
    idempotency_key: Optional[str] = Field(None, max_length=120)
    notes: Optional[str] = None

class TransporterRegisterRequest(BaseModel):
    email: str
    password: str
    carrier_name: str
    invite_token: Optional[str] = None

class TransporterInviteRequest(BaseModel):
    email: str
    carrier_name: str
    carrier_code: Optional[str] = None

class ShipmentCreateRequest(BaseModel):
    external_shipment_id: str
    product_id: int
    supplier_id: Optional[int] = None
    origin: str
    destination: str
    transport_mode: str = "ROAD"
    planned_delivery: date
    order_date: Optional[date] = None
    quantity: Optional[float] = 100.0
    distance_km: Optional[float] = 500.0
    transporter_org_id: Optional[int] = None

class AssignmentActionRequest(BaseModel):
    action: str = Field(..., pattern="^(ACCEPT|REJECT|START_TRANSIT|COMPLETE_DELIVERY)$")
    notes: Optional[str] = None

class ShipmentLegResponse(BaseModel):
    id: int
    shipment_id: int
    sequence: int
    mode: str
    origin: str
    destination: str
    carrier_name: Optional[str] = None
    distance_km: Optional[float] = 0.0
    expected_duration_hrs: float
    delay_hours: float
    status: str
    missed_connection_dwell_hrs: float

    model_config = ConfigDict(from_attributes=True)

class DisruptionReportResponse(BaseModel):
    report_id: int
    shipment_id: int
    external_shipment_id: str
    product_name: str
    total_delay_hours: float
    total_delay_days: float
    missed_connection_alerts: List[str]
    inventory_simulation: dict
    financial_impact: dict
    prescriptive_mitigations: List[dict]


class TransporterDelayRequest(BaseModel):
    new_eta: Optional[datetime] = None
    delay_hours: Optional[float] = Field(None, gt=0, le=720)
    leg_id: Optional[int] = None
    reason: str = Field(..., min_length=2, max_length=100)
    notes: Optional[str] = Field(None, max_length=2000)
    attachment_url: Optional[str] = Field(None, max_length=500)
    idempotency_key: Optional[str] = Field(None, max_length=120)


class TransporterDelayResponse(BaseModel):
    shipment_id: int
    external_shipment_id: str
    leg_id: Optional[int] = None
    leg_description: Optional[str] = None
    previous_eta: Optional[str] = None
    new_eta: str
    delay_hours: float
    reason: str
    status: str
    reported_by: str
    reported_at: str
    control_tower_alert_id: Optional[int] = None
    message: Optional[str] = None

