from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    product_id = Column(Integer, ForeignKey("products.id"), nullable=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=True, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)

    priority = Column(String(20), nullable=False, default="medium")  # low | medium | high | critical
    title = Column(String(255), nullable=False)
    reason = Column(Text, nullable=False)
    expected_impact = Column(Text, nullable=True)
    affected_entity = Column(String(255), nullable=True)

    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_dismissed = Column(Integer, default=0, nullable=False)

    company = relationship("Company", back_populates="recommendations")

    def __repr__(self) -> str:
        return f"<Recommendation id={self.id} priority={self.priority} title={self.title!r}>"
