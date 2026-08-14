from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    region = Column(String(120), nullable=True)

    company = relationship("Company", back_populates="warehouses")
    inventory_records = relationship("InventoryRecord", back_populates="warehouse", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Warehouse id={self.id} company_id={self.company_id} name={self.name!r}>"
