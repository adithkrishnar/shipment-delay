import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Company, DatasetUpload
from app.schemas.upload import (
    ImportResponse,
    MapRequest,
    MapResponse,
    UploadResponse,
    ValidateRequest,
    ValidationIssue,
    ValidationReport,
)
from app.services.column_mapping import suggest_column_mapping, unmapped_required_fields
from app.services.data_import import apply_mapping, import_dataset, revalidate_after_mapping
from app.services.file_io import preview_rows, read_tabular_file
from app.services.model_training_service import ensure_company_has_a_model, ensure_company_has_shipment_models
from app.services.schema_registry import STANDARD_SCHEMA
from app.utils.logging_config import get_logger

router = APIRouter(prefix="/api", tags=["data"])
logger = get_logger(__name__)

VALID_DATASET_TYPES = set(STANDARD_SCHEMA.keys())


def _require_company(db: Session, company_id: int) -> Company:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    return company


def _require_upload(db: Session, upload_id: int) -> DatasetUpload:
    upload = db.query(DatasetUpload).filter(DatasetUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found.")
    return upload


@router.post("/upload", response_model=UploadResponse)
async def upload_dataset(
    company_id: int = Form(...),
    dataset_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _require_company(db, company_id)

    if dataset_type not in VALID_DATASET_TYPES:
        raise HTTPException(status_code=400, detail=f"dataset_type must be one of {sorted(VALID_DATASET_TYPES)}")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{suffix}'. Use CSV or Excel.")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.")

    upload_record = DatasetUpload(
        company_id=company_id,
        dataset_type=dataset_type,
        original_filename=file.filename or "upload",
        stored_path="",  # filled in below once we know the ID
        status="uploaded",
    )
    db.add(upload_record)
    db.flush()  # get an ID without a full commit yet

    company_dir = settings.UPLOAD_DIR / f"company_{company_id}"
    company_dir.mkdir(parents=True, exist_ok=True)
    stored_path = company_dir / f"upload_{upload_record.id}{suffix}"
    stored_path.write_bytes(contents)
    upload_record.stored_path = str(stored_path)

    try:
        df = read_tabular_file(stored_path)
    except Exception as exc:  # noqa: BLE001 - surface a clean 400 to the client
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    if df.empty:
        db.rollback()
        raise HTTPException(status_code=400, detail="Uploaded file has no data rows.")

    suggested_mapping = suggest_column_mapping(dataset_type, list(df.columns))
    upload_record.row_count = len(df)
    db.commit()
    db.refresh(upload_record)

    logger.info(
        "Uploaded dataset id=%s company=%s type=%s rows=%s file=%s",
        upload_record.id, company_id, dataset_type, len(df), file.filename,
    )

    return UploadResponse(
        upload_id=upload_record.id,
        company_id=company_id,
        dataset_type=dataset_type,
        original_filename=upload_record.original_filename,
        row_count=len(df),
        columns=list(df.columns),
        preview_rows=preview_rows(df),
        suggested_mapping=suggested_mapping,
        status=upload_record.status,
    )


@router.post("/data/validate", response_model=ValidationReport)
def validate_upload(payload: ValidateRequest, db: Session = Depends(get_db)):
    upload = _require_upload(db, payload.upload_id)
    df = read_tabular_file(Path(upload.stored_path))
    mapped_df = apply_mapping(df, payload.column_mapping)

    report = revalidate_after_mapping(upload.dataset_type, mapped_df)

    upload.status = "validated"
    upload.data_quality_score = report["data_quality_score"]
    upload.validation_report_json = json.dumps({
        "errors": report["errors"], "warnings": report["warnings"],
        "missing_required_fields": report["missing_required_fields"],
    })
    db.commit()

    return ValidationReport(
        upload_id=upload.id,
        data_quality_score=report["data_quality_score"],
        row_count=report["row_count"],
        valid_row_count=report["valid_row_count"],
        errors=[ValidationIssue(**e) for e in report["errors"]],
        warnings=[ValidationIssue(**w) for w in report["warnings"]],
        missing_required_fields=report["missing_required_fields"],
    )


@router.post("/data/map", response_model=MapResponse)
def map_upload(payload: MapRequest, db: Session = Depends(get_db)):
    upload = _require_upload(db, payload.upload_id)

    missing = unmapped_required_fields(upload.dataset_type, payload.column_mapping)

    upload.column_mapping_json = json.dumps(payload.column_mapping)
    upload.status = "mapped" if not missing else "mapped_incomplete"
    db.commit()

    return MapResponse(
        upload_id=upload.id,
        column_mapping=payload.column_mapping,
        unmapped_required_fields=missing,
        status=upload.status,
    )


@router.post("/data/import", response_model=ImportResponse)
def import_upload(company_id: int, upload_id: int, db: Session = Depends(get_db)):
    upload = _require_upload(db, upload_id)
    if upload.company_id != company_id:
        raise HTTPException(status_code=400, detail="upload_id does not belong to this company_id.")
    if not upload.column_mapping_json:
        raise HTTPException(status_code=400, detail="Upload has not been mapped yet. Call /api/data/map first.")

    column_mapping = json.loads(upload.column_mapping_json)
    missing = unmapped_required_fields(upload.dataset_type, column_mapping)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot import: required fields not mapped: {missing}",
        )

    df = read_tabular_file(Path(upload.stored_path))
    mapped_df = apply_mapping(df, column_mapping)

    imported, skipped = import_dataset(db, company_id, upload.dataset_type, mapped_df)

    upload.status = "imported"
    upload.imported_at = datetime.utcnow()
    db.commit()

    logger.info(
        "Imported dataset upload_id=%s company=%s type=%s imported=%s skipped=%s",
        upload_id, company_id, upload.dataset_type, imported, skipped,
    )

    if upload.dataset_type == "sales" and imported > 0:
        try:
            ensure_company_has_a_model(db, company_id)
        except Exception:  # noqa: BLE001 - training failure must never fail the import itself
            logger.exception("Post-import demand model training failed for company_id=%s", company_id)

    if upload.dataset_type == "shipments" and imported > 0:
        try:
            ensure_company_has_shipment_models(db, company_id)
        except Exception:  # noqa: BLE001
            logger.exception("Post-import shipment model training failed for company_id=%s", company_id)

    return ImportResponse(
        upload_id=upload_id,
        company_id=company_id,
        dataset_type=upload.dataset_type,
        imported_row_count=imported,
        skipped_row_count=skipped,
        status=upload.status,
    )


@router.get("/data/uploads/{company_id}")
def list_uploads(company_id: int, db: Session = Depends(get_db)):
    _require_company(db, company_id)
    uploads = (
        db.query(DatasetUpload)
        .filter(DatasetUpload.company_id == company_id)
        .order_by(DatasetUpload.uploaded_at.desc())
        .all()
    )
    return [
        {
            "upload_id": u.id,
            "dataset_type": u.dataset_type,
            "original_filename": u.original_filename,
            "status": u.status,
            "row_count": u.row_count,
            "data_quality_score": u.data_quality_score,
            "uploaded_at": u.uploaded_at.isoformat(),
            "imported_at": u.imported_at.isoformat() if u.imported_at else None,
        }
        for u in uploads
    ]
