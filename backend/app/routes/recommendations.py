from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.auth.deps import get_current_user
from app.models.user import User
from app.database import get_db
from app.models import Company, Warehouse, Product, InventoryRecord
from app.models.warehouse_transfer import WarehouseTransfer
from app.models.action_approval import ActionApproval
from app.services.recommendation_engine import generate_recommendations

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


class ActionApprovalRequest(BaseModel):
    action_id: str
    action_type: str = "RECOMMENDATION_APPROVAL"
    title: Optional[str] = None
    notes: Optional[str] = None
    source_warehouse_id: Optional[int] = None
    destination_warehouse_id: Optional[int] = None
    product_id: Optional[int] = None
    sku: Optional[str] = None
    quantity: Optional[float] = None


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

    from app.models import Product, Warehouse
    total_skus = db.query(Product).filter(Product.company_id == company_id).count()
    wh_count = db.query(Warehouse).filter(Warehouse.company_id == company_id).count()

    approved_ids = list(approval_map.keys())
    return {
        "company_id": company_id,
        "recommendations": recs,
        "total_skus_evaluated": total_skus,
        "facilities_evaluated": wh_count,
        "audit_summary": f"Evaluated {total_skus} SKUs across {wh_count} distribution facilities against dynamic ROP and safety-stock thresholds.",
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
            "status": existing.status,
            "message": "Action was already approved",
            "action_id": existing.action_id,
            "company_id": existing.company_id,
            "approved_at": str(existing.created_at),
            "approved_by_user_id": existing.user_id,
        }

    status_val = "APPROVED"
    notes = payload.notes or ""
    message = "Action successfully approved and audited"

    is_transfer = (
        payload.action_type in ("STOCK_TRANSFER", "DISRUPTION_MITIGATION")
        or "transfer" in (payload.title or "").lower()
        or "transfer" in (payload.notes or "").lower()
    )

    if is_transfer:
        warehouses = db.query(Warehouse).filter(Warehouse.company_id == company_id).all()
        wh_count = len(warehouses)
        if wh_count == 1:
            # Single-facility company (e.g. Company 21 / Chennai Central DC)
            status_val = "PENDING_EXTERNAL_DISPATCH"
            wh_name = warehouses[0].name
            notes = (
                f"{notes} [Operational Guidance: Company has only 1 facility ({wh_name}). "
                f"Internal warehouse transfer not applicable. Dispatched operational guidance for upstream supplier shipment.]"
            ).strip()
            message = (
                "Approval recorded. Note: Internal facility transfer not possible for single-warehouse tenant; "
                "dispatched operational guidance for upstream supplier shipment."
            )
        elif wh_count >= 2:
            # Multi-warehouse company
            if (
                payload.source_warehouse_id is not None
                and payload.destination_warehouse_id is not None
                and payload.quantity is not None
                and payload.quantity > 0
                and (payload.product_id is not None or payload.sku is not None)
            ):
                if payload.source_warehouse_id == payload.destination_warehouse_id:
                    raise HTTPException(400, "Source and destination warehouses must be different.")

                source_wh = next((w for w in warehouses if w.id == payload.source_warehouse_id), None)
                dest_wh = next((w for w in warehouses if w.id == payload.destination_warehouse_id), None)
                if not source_wh or not dest_wh:
                    raise HTTPException(404, "Specified source or destination warehouse not found for this company.")

                prod_query = db.query(Product).filter(Product.company_id == company_id)
                if payload.product_id:
                    product = prod_query.filter(Product.id == payload.product_id).first()
                else:
                    product = prod_query.filter(Product.external_product_id == payload.sku).first()
                if not product:
                    raise HTTPException(404, "Product not found for this company.")

                source_inv = (
                    db.query(InventoryRecord)
                    .filter(
                        InventoryRecord.company_id == company_id,
                        InventoryRecord.product_id == product.id,
                        InventoryRecord.warehouse_id == payload.source_warehouse_id,
                    )
                    .order_by(InventoryRecord.date.desc())
                    .first()
                )
                avail = float(source_inv.inventory_level) if source_inv else 0.0
                if avail < payload.quantity:
                    raise HTTPException(
                        400,
                        f"Insufficient stock at {source_wh.name}. Available: {avail:.1f} units, Requested: {payload.quantity:.1f} units.",
                    )

                today = date.today()
                source_inv.inventory_level = avail - payload.quantity

                dest_inv = (
                    db.query(InventoryRecord)
                    .filter(
                        InventoryRecord.company_id == company_id,
                        InventoryRecord.product_id == product.id,
                        InventoryRecord.warehouse_id == payload.destination_warehouse_id,
                    )
                    .order_by(InventoryRecord.date.desc())
                    .first()
                )
                if dest_inv:
                    dest_before = float(dest_inv.inventory_level)
                    dest_inv.inventory_level = dest_before + payload.quantity
                else:
                    dest_before = 0.0
                    dest_inv = InventoryRecord(
                        company_id=company_id,
                        product_id=product.id,
                        warehouse_id=payload.destination_warehouse_id,
                        date=today,
                        inventory_level=payload.quantity,
                        safety_stock=0.0,
                    )
                    db.add(dest_inv)

                transfer_log = WarehouseTransfer(
                    company_id=company_id,
                    product_id=product.id,
                    source_warehouse_id=payload.source_warehouse_id,
                    destination_warehouse_id=payload.destination_warehouse_id,
                    quantity=payload.quantity,
                    status="COMPLETED",
                    executed_by_user_id=current_user.id,
                    created_at=datetime.utcnow(),
                    notes=f"Auto-executed on action approval {payload.action_id} (source before: {avail:.1f}, dest before: {dest_before:.1f})",
                )
                db.add(transfer_log)

                status_val = "EXECUTED"
                notes = (
                    f"{notes} [Executed: {payload.quantity} units transferred from {source_wh.name} to {dest_wh.name}]"
                ).strip()
                message = f"Action approved and transfer of {payload.quantity} units executed successfully."
            else:
                status_val = "PENDING_ALLOCATION"
                notes = (
                    f"{notes} [Multi-warehouse network verified ({wh_count} facilities); awaiting facility allocation]"
                ).strip()
                message = f"Action approved for multi-facility network ({wh_count} warehouses); pending warehouse allocation."

    approval = ActionApproval(
        company_id=company_id,
        action_id=payload.action_id,
        action_type=payload.action_type,
        title=payload.title,
        notes=notes,
        status=status_val,
        user_id=current_user.id,
        created_at=datetime.utcnow(),
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)

    return {
        "status": approval.status,
        "message": message,
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