from app.auth.deps import get_current_user
from app.models.user import User
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
router = APIRouter(prefix='/api/models', tags=['models'])
logger = get_logger(__name__)

def _to_registry_out(entry: ModelRegistryEntry) -> ModelRegistryOut:
    return ModelRegistryOut(id=entry.id, company_id=entry.company_id, model_type=entry.model_type, model_source=entry.model_source, version=entry.version, training_date=entry.training_date, dataset_size=entry.dataset_size, history_days=entry.history_days, status=entry.status, metrics=json.loads(entry.metrics_json) if entry.metrics_json else None)

@router.post('/train/base')
async def train_base_model(db: Session=Depends(get_db), redis: ArqRedis=Depends(get_redis_pool), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser: raise HTTPException(403, "Only superusers can trigger base model training")
    """
    Enqueue background jobs to train base demand and shipment models.
    """
    demand_job = TrainingJob(job_type=JobType.BASE_DEMAND.value)
    shipment_job = TrainingJob(job_type=JobType.BASE_SHIPMENT.value)
    db.add(demand_job)
    db.add(shipment_job)
    db.commit()
    trained_sync = False
    if redis is not None:
        try:
            await redis.enqueue_job('train_base_demand', demand_job.id)
            await redis.enqueue_job('train_base_shipment', shipment_job.id)
        except Exception as exc:
            logger.warning("Redis worker queue unreachable (%s). Training base models synchronously...", exc)
            trained_sync = True
    else:
        trained_sync = True

    if trained_sync:
        from app.services.model_training_service import train_base_demand_model, train_base_shipment_models
        try:
            train_base_demand_model(db)
            demand_job.status = JobStatus.COMPLETED.value
        except Exception as e_d:
            logger.exception("Base demand model training failed: %s", e_d)
            demand_job.status = JobStatus.FAILED.value
        try:
            train_base_shipment_models(db)
            shipment_job.status = JobStatus.COMPLETED.value
        except Exception as e_s:
            logger.exception("Base shipment model training failed: %s", e_s)
            shipment_job.status = JobStatus.FAILED.value
        db.commit()
    return {'message': 'Base model training executed/queued', 'jobs': [{'job_id': demand_job.id, 'type': demand_job.job_type, 'status': demand_job.status}, {'job_id': shipment_job.id, 'type': shipment_job.job_type, 'status': shipment_job.status}]}

@router.post('/retrain/{company_id}')
async def retrain_company_model(company_id: int, db: Session=Depends(get_db), redis: ArqRedis=Depends(get_redis_pool), current_user: User = Depends(get_current_user)):
    if not current_user.is_superuser and current_user.company_id != company_id: raise HTTPException(403, "Not authorized to access this company's data")
    """
    Enqueue background jobs to train company-specific demand and shipment models.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail='Company not found.')
    demand_job = TrainingJob(company_id=company_id, job_type=JobType.DEMAND_RETRAIN.value)
    shipment_job = TrainingJob(company_id=company_id, job_type=JobType.SHIPMENT_RETRAIN.value)
    db.add(demand_job)
    db.add(shipment_job)
    db.commit()
    trained_sync = False
    if redis is not None:
        try:
            await redis.enqueue_job('train_demand_for_company', demand_job.id, company_id)
            await redis.enqueue_job('train_shipment_for_company', shipment_job.id, company_id)
        except Exception as exc:
            logger.warning("Redis worker queue unreachable (%s). Executing model training synchronously as fallback...", exc)
            trained_sync = True
    else:
        trained_sync = True

    if trained_sync:
        from app.services.model_training_service import train_company_demand_model, train_company_shipment_models, ensure_company_has_a_model
        try:
            entry_d, reason_d = train_company_demand_model(db, company_id)
            if not entry_d:
                try:
                    entry_d = ensure_company_has_a_model(db, company_id)
                    reason_d = f"Baseline demand model active ({reason_d})"
                except Exception as e_base:
                    logger.warning("Could not train base demand model fallback: %s", e_base)
            demand_job.status = JobStatus.COMPLETED.value
            demand_job.result = json.dumps({"reason": reason_d, "version": entry_d.version if entry_d else None})
        except Exception as e_d:
            logger.exception("Synchronous demand model training failed: %s", e_d)
            demand_job.status = JobStatus.FAILED.value
            demand_job.error_message = str(e_d)

        try:
            clf_e, dur_e, reason_s = train_company_shipment_models(db, company_id)
            shipment_job.status = JobStatus.COMPLETED.value
            shipment_job.result = json.dumps({"reason": reason_s})
        except Exception as e_s:
            logger.exception("Synchronous shipment model training failed: %s", e_s)
            shipment_job.status = JobStatus.FAILED.value
            shipment_job.error_message = str(e_s)

        db.commit()
    return {'message': 'Company model retraining executed/queued', 'jobs': [{'job_id': demand_job.id, 'type': demand_job.job_type, 'status': demand_job.status}, {'job_id': shipment_job.id, 'type': shipment_job.job_type, 'status': shipment_job.status}]}

@router.get('/jobs/{job_id}', response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session=Depends(get_db), *, current_user: User=Depends(get_current_user)):
    """
    Check the status of a specific background training job.
    """
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    if job.company_id is not None and not current_user.is_superuser and current_user.company_id != job.company_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this company's job")
    return JobStatusResponse(job_id=job.id, status=job.status, result=json.loads(job.result) if job.result else None, error=job.error_message)

@router.get('/{company_id}/jobs')
def list_company_jobs(company_id: int, db: Session=Depends(get_db), *, current_user: User=Depends(get_current_user)):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's data")
    '\n    List recent jobs for a company.\n    '
    jobs = db.query(TrainingJob).filter(TrainingJob.company_id == company_id).order_by(TrainingJob.created_at.desc()).limit(10).all()
    return [{'job_id': j.id, 'type': j.job_type, 'status': j.status, 'created_at': j.created_at, 'finished_at': j.finished_at} for j in jobs]

@router.get('/{company_id}', response_model=list[ModelRegistryOut])
def list_models_for_company(company_id: int, db: Session=Depends(get_db), *, current_user: User=Depends(get_current_user)):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's data")
    "\n    Lists every model relevant to a company: its own company-specific\n    registry entries plus the current base model (which may be what's\n    actually serving it).\n    "
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail='Company not found.')
    own_entries = db.query(ModelRegistryEntry).filter(ModelRegistryEntry.company_id == company_id).order_by(ModelRegistryEntry.training_date.desc()).all()
    base_entries = db.query(ModelRegistryEntry).filter(ModelRegistryEntry.company_id.is_(None)).order_by(ModelRegistryEntry.training_date.desc()).all()
    all_entries = list(own_entries) + list(base_entries)
    
    # Ensure there is always a registered demand forecasting model available
    has_demand = any(e.model_type == 'demand_forecast' for e in all_entries)
    if not has_demand:
        from app.services.model_training_service import ensure_company_has_a_model
        try:
            entry = ensure_company_has_a_model(db, company_id)
            if entry:
                all_entries.insert(0, entry)
        except Exception as exc:
            logger.warning("Could not auto-ensure demand model on list_models_for_company: %s", exc)
    return [_to_registry_out(e) for e in all_entries]