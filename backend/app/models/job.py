from datetime import datetime
import uuid

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
import enum

from app.database import Base

class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class JobType(str, enum.Enum):
    DEMAND_RETRAIN = "demand_retrain"
    SHIPMENT_RETRAIN = "shipment_retrain"
    BASE_DEMAND = "base_demand"
    BASE_SHIPMENT = "base_shipment"

class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=True)
    job_type = Column(String, nullable=False) # e.g. JobType
    status = Column(String, default=JobStatus.QUEUED.value, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    
    result = Column(Text, nullable=True) # JSON stored as Text
    error_message = Column(Text, nullable=True)
    
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    company = relationship("Company")
    user = relationship("User")
