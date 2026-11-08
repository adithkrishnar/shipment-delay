from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from app.database import Base

class ShipmentLeg(Base):
    __tablename__ = "shipment_legs"
    __table_args__ = (
        Index("ix_shipment_legs_shipment_seq", "shipment_id", "sequence"),
    )

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    sequence = Column(Integer, nullable=False, default=1)  # 1, 2, 3...
    mode = Column(String(50), nullable=False)  # ROAD, RAIL, AIR, SEA
    origin = Column(String(255), nullable=False)
    destination = Column(String(255), nullable=False)
    carrier_name = Column(String(120), nullable=True)  # carrier operating this leg
    
    distance_km = Column(Float, nullable=True, default=0.0)
    expected_duration_hrs = Column(Float, nullable=False, default=0.0)
    delay_hours = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="SCHEDULED")  # SCHEDULED, IN_TRANSIT, DELAYED, COMPLETED
    
    # Connection / Dwell buffer to next leg (e.g. port gate cutoff or freight train departure)
    scheduled_departure = Column(DateTime, nullable=True)
    scheduled_arrival = Column(DateTime, nullable=True)
    next_leg_cutoff = Column(DateTime, nullable=True)  # Port/depot gate cutoff
    missed_connection_dwell_hrs = Column(Float, nullable=False, default=0.0)

    shipment = relationship("Shipment", back_populates="legs")
    disruptions = relationship("DisruptionReport", back_populates="leg", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ShipmentLeg id={self.id} shipment_id={self.shipment_id} seq={self.sequence} mode={self.mode}>"


class DisruptionReport(Base):
    __tablename__ = "disruption_reports"

    id = Column(Integer, primary_key=True, index=True)
    leg_id = Column(Integer, ForeignKey("shipment_legs.id", ondelete="CASCADE"), nullable=False, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    delay_hours = Column(Float, nullable=False)
    disruption_reason = Column(String(120), nullable=False)  # e.g., "Vehicle Breakdown", "Customs Hold", "Adverse Weather", "Port Congestion"
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Simulated impact cached on report
    total_impact_delay_days = Column(Float, nullable=True)
    stockout_predicted = Column(Integer, default=0)  # 0 or 1
    unmet_demand_units = Column(Float, default=0.0)
    estimated_cost_loss = Column(Float, default=0.0)
    prescribed_mitigation = Column(Text, nullable=True)
    impact_details_json = Column(Text, nullable=True)

    leg = relationship("ShipmentLeg", back_populates="disruptions")
    shipment = relationship("Shipment")
    reporter = relationship("User")

    def __repr__(self) -> str:
        return f"<DisruptionReport id={self.id} leg_id={self.leg_id} delay={self.delay_hours}hrs reason={self.disruption_reason}>"

