from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class ModelRegistryEntry(Base):
    """
    One row per trained model artifact.

    company_id may be NULL for a global base model that isn't tied to any
    single company (e.g. the initial base model trained on aggregate demo data).
    """

    __tablename__ = "model_registry"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)

    model_type = Column(String(80), nullable=False)  # demand_forecast | delay_classifier | delay_duration | anomaly
    model_source = Column(String(20), nullable=False, default="base")  # "base" | "company_specific"
    version = Column(String(40), nullable=False)

    training_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    dataset_size = Column(Integer, nullable=True)
    history_days = Column(Integer, nullable=True)

    metrics_json = Column(Text, nullable=True)  # JSON-encoded metrics dict (MAE, RMSE, F1, etc.)
    model_path = Column(String(500), nullable=False)
    status = Column(String(20), nullable=False, default="active")  # active | archived | training | failed

    company = relationship("Company", back_populates="models")

    def __repr__(self) -> str:
        return f"<ModelRegistryEntry {self.model_type} company_id={self.company_id} v={self.version}>"
