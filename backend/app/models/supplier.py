from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    external_supplier_id = Column(String(120), nullable=False, index=True)
    name = Column(String(255), nullable=False)

    lead_time_days = Column(Float, nullable=True)      # average promised lead time
    reliability = Column(Float, nullable=True)          # 0-1, historical on-time rate
    cost_index = Column(Float, nullable=True)            # relative cost score
    defect_rate = Column(Float, nullable=True)           # 0-1, optional

    company = relationship("Company", back_populates="suppliers")
    shipments = relationship("Shipment", back_populates="supplier", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Supplier id={self.id} company_id={self.company_id} name={self.name!r}>"
