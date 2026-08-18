import json
import asyncio
from datetime import datetime

from arq import Worker
from arq.connections import RedisSettings

from app.config import settings
from app.database import SessionLocal
from app.models.job import TrainingJob, JobStatus
from app.utils.logging_config import get_logger
from app.services.model_training_service import (
    train_company_demand_model,
    train_company_shipment_models,
    train_base_demand_model,
    train_base_shipment_models,
)

logger = get_logger(__name__)


def _update_job_status(db, job_id, status: JobStatus, result_dict=None, error_msg=None):
    job = db.query(TrainingJob).filter(TrainingJob.id == job_id).first()
    if not job:
        logger.error(f"Job {job_id} not found to update status to {status}")
        return

    job.status = status.value
    if status == JobStatus.RUNNING:
        job.started_at = datetime.utcnow()
    elif status in (JobStatus.COMPLETED, JobStatus.FAILED):
        job.finished_at = datetime.utcnow()
        if result_dict:
            job.result = json.dumps(result_dict)
        if error_msg:
            job.error_message = error_msg
    db.commit()


async def train_demand_for_company(ctx, job_id: str, company_id: int):
    logger.info(f"Starting demand retrain for company {company_id} in job {job_id}")
    db = SessionLocal()
    try:
        _update_job_status(db, job_id, JobStatus.RUNNING)
        # Call synchronous function using asyncio.to_thread
        entry, reason = await asyncio.to_thread(train_company_demand_model, db, company_id)
        
        result_dict = {
            "trained": entry is not None,
            "reason": reason,
            "metrics": json.loads(entry.metrics_json) if entry else None,
            "version": entry.version if entry else None
        }
        _update_job_status(db, job_id, JobStatus.COMPLETED, result_dict=result_dict)
    except Exception as exc:
        logger.exception(f"Job {job_id} failed")
        _update_job_status(db, job_id, JobStatus.FAILED, error_msg=str(exc))
    finally:
        db.close()


async def train_shipment_for_company(ctx, job_id: str, company_id: int):
    logger.info(f"Starting shipment retrain for company {company_id} in job {job_id}")
    db = SessionLocal()
    try:
        _update_job_status(db, job_id, JobStatus.RUNNING)
        entry, dur_entry, reason = await asyncio.to_thread(train_company_shipment_models, db, company_id)
        
        result_dict = {
            "trained": entry is not None,
            "reason": reason,
            "classifier_metrics": json.loads(entry.metrics_json) if entry else None,
            "duration_metrics": json.loads(dur_entry.metrics_json) if dur_entry else None
        }
        _update_job_status(db, job_id, JobStatus.COMPLETED, result_dict=result_dict)
    except Exception as exc:
        logger.exception(f"Job {job_id} failed")
        _update_job_status(db, job_id, JobStatus.FAILED, error_msg=str(exc))
    finally:
        db.close()


async def train_base_demand(ctx, job_id: str):
    logger.info(f"Starting base demand train in job {job_id}")
    db = SessionLocal()
    try:
        _update_job_status(db, job_id, JobStatus.RUNNING)
        entry = await asyncio.to_thread(train_base_demand_model, db)
        result_dict = {
            "trained": True,
            "metrics": json.loads(entry.metrics_json),
            "version": entry.version
        }
        _update_job_status(db, job_id, JobStatus.COMPLETED, result_dict=result_dict)
    except Exception as exc:
        logger.exception(f"Job {job_id} failed")
        _update_job_status(db, job_id, JobStatus.FAILED, error_msg=str(exc))
    finally:
        db.close()


async def train_base_shipment(ctx, job_id: str):
    logger.info(f"Starting base shipment train in job {job_id}")
    db = SessionLocal()
    try:
        _update_job_status(db, job_id, JobStatus.RUNNING)
        clf_entry, dur_entry = await asyncio.to_thread(train_base_shipment_models, db)
        result_dict = {
            "trained": True,
            "classifier_metrics": json.loads(clf_entry.metrics_json),
            "duration_metrics": json.loads(dur_entry.metrics_json) if dur_entry else None
        }
        _update_job_status(db, job_id, JobStatus.COMPLETED, result_dict=result_dict)
    except Exception as exc:
        logger.exception(f"Job {job_id} failed")
        _update_job_status(db, job_id, JobStatus.FAILED, error_msg=str(exc))
    finally:
        db.close()


class WorkerSettings:
    functions = [
        train_demand_for_company,
        train_shipment_for_company,
        train_base_demand,
        train_base_shipment
    ]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
