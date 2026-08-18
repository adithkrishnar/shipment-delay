import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from arq.connections import ArqRedis

from app.database import get_db
from app.models import Company, ModelRegistryEntry
from app.models.job import TrainingJob, JobType, JobStatus
from app.schemas.ml import ModelRegistryOut, JobStatusResponse
from app.deps.arq import get_redis_pool
from app.utils.logging_config import get_logger

router = APIRouter(prefix="/api/models", tags=["models"])
logger = get_logger(__name__)


def _to_registry_out(entry: ModelRegistryEntry) -> ModelRegistryOut:
    return ModelRegistryOut(
        id=entry.id, company_id=entry.company_id, model_type=entry.model_type,
        model_source=entry.model_source, version=entry.version, training_date=entry.training_date,
        dataset_size=entry.dataset_size, history_days=entry.history_days, status=entry.status,
        metrics=json.loads(entry.metrics_json) if entry.metrics_json else None,
    )


@router.post("/train/base")
async def train_base_model(
    db: Session = Depends(get_db),
    redis: ArqRedis = Depends(get_redis_pool)
):
    """
    Enqueue background jobs to train base demand and shipment models.
    """
    demand_job = TrainingJob(job_type=JobType.BASE_DEMAND.value)
    shipment_job = TrainingJob(job_type=JobType.BASE_SHIPMENT.value)
    db.add(demand_job)
    db.add(shipment_job)
    db.commit()

    await redis.enqueue_job('train_base_demand', demand_job.id)
    await redis.enqueue_job('train_base_shipment', shipment_job.id)

    return {
        "message": "Base model training jobs queued",
        "jobs": [
            {"job_id": demand_job.id, "type": demand_job.job_type, "status": demand_job.status},
            {"job_id": shipment_job.id, "type": shipment_job.job_type, "status": shipment_job.status}
        ]
    }


@router.post("/retrain/{company_id}")
async def retrain_company_model(
    company_id: int, 
    db: Session = Depends(get_db),
    redis: ArqRedis = Depends(get_redis_pool)
):
    """
    Enqueue background jobs to train company-specific demand and shipment models.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    demand_job = TrainingJob(company_id=company_id, job_type=JobType.DEMAND_RETRAIN.value)
    shipment_job = TrainingJob(company_id=company_id, job_type=JobType.SHIPMENT_RETRAIN.value)
    db.add(demand_job)
    db.add(shipment_job)
    db.commit()

    await redis.enqueue_job('train_demand_for_company', demand_job.id, company_id)
    await redis.enqueue_job('train_shipment_for_company', shipment_job.id, company_id)

    return {
        "message": "Company model retraining jobs queued",
        "jobs": [
            {"job_id": demand_job.id, "type": demand_job.job_type, "status": demand_job.status},
            {"job_id": shipment_job.id, "type": shipment_job.job_type, "status": shipment_job.status}
        ]
    }


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """
    Check the status of a specific background training job.
    """
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        result=json.loads(job.result) if job.result else None,
        error=job.error_message
    )


@router.get("/{company_id}/jobs")
def list_company_jobs(company_id: int, db: Session = Depends(get_db)):
    """
    List recent jobs for a company.
    """
    jobs = (
        db.query(TrainingJob)
        .filter(TrainingJob.company_id == company_id)
        .order_by(TrainingJob.created_at.desc())
        .limit(10)
        .all()
    )
    return [
        {
            "job_id": j.id,
            "type": j.job_type,
            "status": j.status,
            "created_at": j.created_at,
            "finished_at": j.finished_at
        }
        for j in jobs
    ]


@router.get("/{company_id}", response_model=list[ModelRegistryOut])
def list_models_for_company(company_id: int, db: Session = Depends(get_db)):
    """
    Lists every model relevant to a company: its own company-specific
    registry entries plus the current base model (which may be what's
    actually serving it).
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    own_entries = (
        db.query(ModelRegistryEntry)
        .filter(ModelRegistryEntry.company_id == company_id)
        .order_by(ModelRegistryEntry.training_date.desc())
        .all()
    )
    base_entries = (
        db.query(ModelRegistryEntry)
        .filter(ModelRegistryEntry.company_id.is_(None))
        .order_by(ModelRegistryEntry.training_date.desc())
        .all()
    )
    return [_to_registry_out(e) for e in (own_entries + base_entries)]
