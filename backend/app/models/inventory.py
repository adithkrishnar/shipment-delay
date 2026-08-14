from sqlalchemy import Column, Date, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship

from app.database import Base


class InventoryRecord(Base):
    __tablename__ = "inventory_records"
    __table_args__ = (
        Index("ix_inventory_company_product_date", "company_id", "product_id", "date"),
    )

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=True, index=True)

    date = Column(Date, nullable=False, index=True)
    inventory_level = Column(Float, nullable=False)
    safety_stock = Column(Float, nullable=True)

    company = relationship("Company", back_populates="inventory_records")
    product = relationship("Product", back_populates="inventory_records")
    warehouse = relationship("Warehouse", back_populates="inventory_records")

    def __repr__(self) -> str:
        return f"<InventoryRecord product_id={self.product_id} date={self.date} level={self.inventory_level}>"
