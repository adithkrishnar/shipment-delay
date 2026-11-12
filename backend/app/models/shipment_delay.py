import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from app.database import Base


class DelayReasonEnum(str, enum.Enum):
    TRAFFIC_CONGESTION = "TRAFFIC_CONGESTION"
    WEATHER = "WEATHER"
    VEHICLE_BREAKDOWN = "VEHICLE_BREAKDOWN"
    LOADING_UNLOADING_DELAY = "LOADING_UNLOADING_DELAY"
    DOCK_APPOINTMENT_DELAY = "DOCK_APPOINTMENT_DELAY"
    CUSTOMS_BORDER_DELAY = "CUSTOMS_BORDER_DELAY"
    PORT_CONGESTION = "PORT_CONGESTION"
    DRIVER_AVAILABILITY = "DRIVER_AVAILABILITY"
    OTHER = "OTHER"


class ShipmentDelay(Base):
    __tablename__ = "shipment_delays"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    transporter_org_id = Column(Integer, ForeignKey("transporter_organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    reported_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    previous_eta = Column(DateTime, nullable=True)
    new_eta = Column(DateTime, nullable=False)
    delay_hours = Column(Float, nullable=False)
    reason = Column(String(100), nullable=False)
    notes = Column(Text, nullable=True)
    attachment_url = Column(String(500), nullable=True)

    idempotency_key = Column(String(120), nullable=True, unique=True, index=True)
    payload_hash = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    shipment = relationship("Shipment", backref="delays")
    transporter_org = relationship("TransporterOrganization")
    reporter = relationship("User")

    def __repr__(self) -> str:
        return f"<ShipmentDelay id={self.id} shipment_id={self.shipment_id} delay={self.delay_hours}h reason={self.reason}>"
