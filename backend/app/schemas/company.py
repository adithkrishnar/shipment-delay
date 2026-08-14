from datetime import datetime

from pydantic import BaseModel, Field


class CompanyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    industry: str | None = None
    default_currency: str = "INR"
    notes: str | None = None


class CompanyOut(BaseModel):
    id: int
    name: str
    industry: str | None
    is_demo: int
    default_currency: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanySummaryOut(CompanyOut):
    product_count: int = 0
    supplier_count: int = 0
    sales_record_count: int = 0
    shipment_count: int = 0
    date_range_start: str | None = None
    date_range_end: str | None = None
