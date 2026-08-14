from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    alert_type = Column(String(50), nullable=False)  # anomaly | stockout | delay | overstock | data_quality
    severity = Column(String(20), nullable=False, default="medium")  # low | medium | high | critical
    entity_type = Column(String(50), nullable=True)  # product | shipment | supplier
    entity_id = Column(Integer, nullable=True)

    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_resolved = Column(Integer, default=0, nullable=False)

    company = relationship("Company", back_populates="alerts")

    def __repr__(self) -> str:
        return f"<Alert id={self.id} type={self.alert_type} severity={self.severity}>"
