from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.auth.deps import get_current_user
from app.models.user import User
from app.database import get_db
from app.models import Company
from app.models.action_approval import ActionApproval
from app.services.recommendation_engine import generate_recommendations

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


class ActionApprovalRequest(BaseModel):
    action_id: str
    action_type: str = "RECOMMENDATION_APPROVAL"
    title: Optional[str] = None
    notes: Optional[str] = None


@router.get("/{company_id}")
def recommendations(
    company_id: int,
    db: Session = Depends(get_db),
    *,
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's data")
    if not db.query(Company).filter(Company.id == company_id).first():
        raise HTTPException(404, "Company not found")

    recs = generate_recommendations(db, company_id)

    # Fetch existing approvals for this company to persist approval status across refreshes
    approvals = (
        db.query(ActionApproval)
        .filter(ActionApproval.company_id == company_id)
        .all()
    )
    approval_map = {a.action_id: a for a in approvals}

    # Annotate recommendations with persistent approval status
    for r in recs:
        key = r.get("sku") or r.get("target_id")
        approval = approval_map.get(key) or approval_map.get(r.get("target_id"))
        if approval:
            r["is_approved"] = True
            r["approved_at"] = str(approval.created_at)
            r["approved_by_user_id"] = approval.user_id
        else:
            r["is_approved"] = False

    approved_ids = list(approval_map.keys())
    return {
        "company_id": company_id,
        "recommendations": recs,
        "approved_action_ids": approved_ids,
        "approved_count": len(approved_ids),
    }


@router.post("/{company_id}/approve")
def approve_action(
    company_id: int,
    payload: ActionApprovalRequest,
    db: Session = Depends(get_db),
    *,
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to approve actions for this company")
    if not db.query(Company).filter(Company.id == company_id).first():
        raise HTTPException(404, "Company not found")

    # Check for existing approval (prevent duplicate creation)
    existing = (
        db.query(ActionApproval)
        .filter(
            ActionApproval.company_id == company_id,
            ActionApproval.action_id == payload.action_id,
        )
        .first()
    )
    if existing:
        return {
            "status": "APPROVED",
            "message": "Action was already approved",
            "action_id": existing.action_id,
            "company_id": existing.company_id,
            "approved_at": str(existing.created_at),
            "approved_by_user_id": existing.user_id,
        }

    approval = ActionApproval(
        company_id=company_id,
        action_id=payload.action_id,
        action_type=payload.action_type,
        title=payload.title,
        notes=payload.notes,
        status="APPROVED",
        user_id=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)

    return {
        "status": "APPROVED",
        "message": "Action successfully approved and audited",
        "action_id": approval.action_id,
        "company_id": approval.company_id,
        "approved_at": str(approval.created_at),
        "approved_by_user_id": approval.user_id,
    }


@router.get("/{company_id}/approvals")
def get_action_approvals(
    company_id: int,
    db: Session = Depends(get_db),
    *,
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's approvals")

    approvals = (
        db.query(ActionApproval)
        .filter(ActionApproval.company_id == company_id)
        .order_by(ActionApproval.created_at.desc())
        .all()
    )
    return [
        {
            "id": a.id,
            "action_id": a.action_id,
            "action_type": a.action_type,
            "title": a.title,
            "status": a.status,
            "notes": a.notes,
            "user_id": a.user_id,
            "created_at": str(a.created_at),
        }
        for a in approvals
    ]