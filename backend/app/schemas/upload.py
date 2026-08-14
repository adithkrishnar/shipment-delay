from typing import Any, Literal

from pydantic import BaseModel

DatasetType = Literal["sales", "inventory", "shipments", "suppliers"]


class UploadResponse(BaseModel):
    upload_id: int
    company_id: int
    dataset_type: DatasetType
    original_filename: str
    row_count: int
    columns: list[str]
    preview_rows: list[dict[str, Any]]
    suggested_mapping: dict[str, str | None]
    status: str


class ValidationIssue(BaseModel):
    field: str | None = None
    row: int | None = None
    message: str
    severity: Literal["error", "warning"]


class ValidationReport(BaseModel):
    upload_id: int
    data_quality_score: int
    row_count: int
    valid_row_count: int
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    missing_required_fields: list[str]


class ValidateRequest(BaseModel):
    upload_id: int
    column_mapping: dict[str, str | None]


class MapRequest(BaseModel):
    upload_id: int
    column_mapping: dict[str, str | None]  # {source_column: standard_field_or_None}


class MapResponse(BaseModel):
    upload_id: int
    column_mapping: dict[str, str | None]
    unmapped_required_fields: list[str]
    status: str


class ImportRequest(BaseModel):
    upload_id: int


class ImportResponse(BaseModel):
    upload_id: int
    company_id: int
    dataset_type: DatasetType
    imported_row_count: int
    skipped_row_count: int
    status: str
