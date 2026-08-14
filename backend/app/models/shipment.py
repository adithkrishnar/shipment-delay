from sqlalchemy import Column, Date, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Shipment(Base):
    __tablename__ = "shipments"
    __table_args__ = (
        Index("ix_shipments_company_product", "company_id", "product_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True, index=True)

    external_shipment_id = Column(String(120), nullable=False, index=True)
    origin = Column(String(255), nullable=True)
    destination = Column(String(255), nullable=True)
    carrier = Column(String(120), nullable=True)
    transport_mode = Column(String(50), nullable=True)  # road/rail/air/sea

    distance_km = Column(Float, nullable=True)
    weight_kg = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True)

    order_date = Column(Date, nullable=True)
    planned_delivery = Column(Date, nullable=False)
    actual_delivery = Column(Date, nullable=True)  # null = not yet delivered / in-flight

    company = relationship("Company", back_populates="shipments")
    product = relationship("Product", back_populates="shipments")
    supplier = relationship("Supplier", back_populates="shipments")

    def __repr__(self) -> str:
        return f"<Shipment id={self.external_shipment_id} product_id={self.product_id}>"
