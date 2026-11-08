from typing import List, Optional
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.shipment import Shipment
from app.models.shipment_leg import ShipmentLeg, DisruptionReport
from app.auth import security
from app.auth.deps import get_current_user
from app.schemas.transporter import (
    DisruptionReportRequest,
    TransporterRegisterRequest,
    ShipmentLegResponse,
    DisruptionReportResponse
)
from app.services.collaborative_disruption_service import (
    ensure_shipment_legs,
    simulate_downstream_impact
)

router = APIRouter(prefix="/transporter", tags=["Transporter Portal"])

@router.post("/register")
def register_transporter(req: TransporterRegisterRequest, db: Session = Depends(get_db)):
    """
    Registers a new carrier/transporter account linked to a partner company.
    """
    existing_user = db.query(User).filter(User.email == req.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User email already registered")

    company = db.query(Company).filter(Company.id == req.company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Partner company not found")

    user = User(
        email=req.email,
        hashed_password=security.get_password_hash(req.password),
        company_id=req.company_id,
        role="transporter",
        carrier_name=req.carrier_name,
        is_superuser=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token_expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(user.id, expires_delta=access_token_expires),
        "token_type": "bearer",
        "role": user.role,
        "carrier_name": user.carrier_name,
        "company_id": user.company_id
    }


@router.get("/assigned-shipments")
def get_assigned_shipments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns shipments relevant to the transporter's company / carrier identity.
    If transporter has a carrier_name (e.g. 'Blue Dart Express'), prioritizes matching legs/shipments.
    Also ensures legs are provisioned on demand.
    """
    # Fetch shipments for user's associated company
    q = db.query(Shipment).filter(Shipment.company_id == current_user.company_id)
    shipments = q.order_by(Shipment.id.desc()).limit(30).all()

    result = []
    for s in shipments:
        legs = ensure_shipment_legs(db, s)
        result.append({
            "id": s.id,
            "external_shipment_id": s.external_shipment_id,
            "origin": s.origin,
            "destination": s.destination,
            "carrier": s.carrier,
            "transport_mode": s.transport_mode,
            "distance_km": s.distance_km,
            "planned_delivery": str(s.planned_delivery),
            "legs": [
                {
                    "id": l.id,
                    "sequence": l.sequence,
                    "mode": l.mode,
                    "origin": l.origin,
                    "destination": l.destination,
                    "carrier_name": l.carrier_name,
                    "distance_km": l.distance_km,
                    "expected_duration_hrs": l.expected_duration_hrs,
                    "delay_hours": l.delay_hours,
                    "missed_connection_dwell_hrs": l.missed_connection_dwell_hrs,
                    "status": l.status,
                }
                for l in legs
            ]
        })

    return result


@router.get("/shipments/{shipment_id}/legs")
def get_shipment_legs(
    shipment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Fetches all multimodal legs for a specific shipment.
    """
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id,
        Shipment.company_id == current_user.company_id
    ).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    legs = ensure_shipment_legs(db, shipment)
    return {
        "shipment_id": shipment.id,
        "external_shipment_id": shipment.external_shipment_id,
        "legs": legs
    }


@router.post("/shipments/{shipment_id}/legs/{leg_id}/report-disruption")
def report_leg_disruption(
    shipment_id: int,
    leg_id: int,
    req: DisruptionReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Core Collaborative Disruption Endpoint:
    Allows transporter or company manager to report an active delay on a specific leg.
    Instantly runs compounding delay propagation & inventory simulation.
    """
    shipment = db.query(Shipment).filter(
        Shipment.id == shipment_id,
        Shipment.company_id == current_user.company_id
    ).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    try:
        impact = simulate_downstream_impact(
            db=db,
            shipment=shipment,
            leg_id=leg_id,
            reported_delay_hrs=req.delay_hours,
            reason=req.disruption_reason,
            notes=req.notes,
            reporter_id=current_user.id
        )
        return impact
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/recent-disruptions")
def get_recent_disruptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Lists recent disruptions reported across all shipments for the company.
    """
    shipments = db.query(Shipment).filter(Shipment.company_id == current_user.company_id).all()
    s_ids = [s.id for s in shipments]
    if not s_ids:
        return []

    reports = (
        db.query(DisruptionReport)
        .filter(DisruptionReport.shipment_id.in_(s_ids))
        .order_by(DisruptionReport.created_at.desc())
        .limit(25)
        .all()
    )

    import json
    res = []
    for r in reports:
        details = {}
        if r.impact_details_json:
            try:
                details = json.loads(r.impact_details_json)
            except Exception:
                details = {}

        res.append({
            "id": r.id,
            "shipment_id": r.shipment_id,
            "external_shipment_id": r.shipment.external_shipment_id if r.shipment else None,
            "leg_id": r.leg_id,
            "leg_sequence": r.leg.sequence if r.leg else 1,
            "leg_mode": r.leg.mode if r.leg else "ROAD",
            "delay_hours": r.delay_hours,
            "disruption_reason": r.disruption_reason,
            "notes": r.notes,
            "total_impact_delay_days": r.total_impact_delay_days,
            "stockout_predicted": bool(r.stockout_predicted),
            "unmet_demand_units": r.unmet_demand_units,
            "estimated_cost_loss": r.estimated_cost_loss,
            "prescribed_mitigation": r.prescribed_mitigation,
            "impact_details": details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return res

