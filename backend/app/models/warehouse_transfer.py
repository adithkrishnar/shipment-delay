from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class WarehouseTransfer(Base):
    __tablename__ = "warehouse_transfers"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    source_warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)
    destination_warehouse_id = Column(Integer, ForeignKey("warehouses.id"), nullable=False, index=True)

    quantity = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default="COMPLETED")
    executed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)

    company = relationship("Company")
    product = relationship("Product")
    source_warehouse = relationship("Warehouse", foreign_keys=[source_warehouse_id])
    destination_warehouse = relationship("Warehouse", foreign_keys=[destination_warehouse_id])
    executed_by = relationship("User", foreign_keys=[executed_by_user_id])

    def __repr__(self) -> str:
        return (
            f"<WarehouseTransfer id={self.id} product_id={self.product_id} "
            f"source={self.source_warehouse_id} dest={self.destination_warehouse_id} qty={self.quantity}>"
        )
