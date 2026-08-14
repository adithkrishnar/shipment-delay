from sqlalchemy import Column, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("company_id", "external_product_id", name="uq_product_company_external_id"),)

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    # external_product_id is the ID as it appears in the company's own source data
    # (e.g. their "SKU" column) - kept distinct from our internal surrogate `id`.
    external_product_id = Column(String(120), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(120), nullable=True)
    unit_cost = Column(Float, nullable=True)
    unit_price = Column(Float, nullable=True)

    company = relationship("Company", back_populates="products")
    sales = relationship("Sale", back_populates="product", cascade="all, delete-orphan")
    inventory_records = relationship("InventoryRecord", back_populates="product", cascade="all, delete-orphan")
    shipments = relationship("Shipment", back_populates="product", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Product id={self.id} company_id={self.company_id} external_id={self.external_product_id!r}>"
