from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

class DisruptionReportRequest(BaseModel):
    delay_hours: float
    disruption_reason: str
    notes: Optional[str] = None

class TransporterRegisterRequest(BaseModel):
    email: str
    password: str
    carrier_name: str
    company_id: int  # company partner they transport for

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

    class Config:
        orm_mode = True

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

