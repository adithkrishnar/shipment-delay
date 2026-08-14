from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    industry = Column(String(120), nullable=True)  # e.g. Electronics, Automotive Parts, FMCG
    is_demo = Column(Integer, default=0, nullable=False)  # 1 = seeded demo company
    default_currency = Column(String(8), default="INR", nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    products = relationship("Product", back_populates="company", cascade="all, delete-orphan")
    warehouses = relationship("Warehouse", back_populates="company", cascade="all, delete-orphan")
    suppliers = relationship("Supplier", back_populates="company", cascade="all, delete-orphan")
    sales = relationship("Sale", back_populates="company", cascade="all, delete-orphan")
    inventory_records = relationship("InventoryRecord", back_populates="company", cascade="all, delete-orphan")
    shipments = relationship("Shipment", back_populates="company", cascade="all, delete-orphan")
    models = relationship("ModelRegistryEntry", back_populates="company", cascade="all, delete-orphan")
    recommendations = relationship("Recommendation", back_populates="company", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="company", cascade="all, delete-orphan")
    uploads = relationship("DatasetUpload", back_populates="company", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Company id={self.id} name={self.name!r}>"
