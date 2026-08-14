from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class DatasetUpload(Base):
    """
    Tracks every file uploaded through the Data Upload & Mapping flow,
    from raw upload through validation, mapping, and import.
    """

    __tablename__ = "dataset_uploads"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    dataset_type = Column(String(30), nullable=False)  # sales | inventory | shipments | suppliers
    original_filename = Column(String(500), nullable=False)
    stored_path = Column(String(500), nullable=False)

    status = Column(String(30), nullable=False, default="uploaded")
    # uploaded -> validated -> mapped -> imported  (or failed at any stage)

    row_count = Column(Integer, nullable=True)
    data_quality_score = Column(Integer, nullable=True)  # 0-100

    column_mapping_json = Column(Text, nullable=True)   # {"Qty_Sold": "quantity", ...}
    validation_report_json = Column(Text, nullable=True)  # {"errors": [...], "warnings": [...]}

    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    imported_at = Column(DateTime, nullable=True)

    company = relationship("Company", back_populates="uploads")

    def __repr__(self) -> str:
        return f"<DatasetUpload id={self.id} type={self.dataset_type} status={self.status}>"
