import secrets
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.company import Company
from app.models.shipment import Shipment
from app.models.shipment_leg import ShipmentLeg, DisruptionReport
from app.models.shipment_delay import ShipmentDelay, DelayReasonEnum
from app.models.transporter_org import TransporterOrganization, TransporterInvitation
from app.models.alert import Alert
from app.auth import security
from app.auth.deps import get_current_user
from app.schemas.transporter import (
    DisruptionReportRequest,
    TransporterRegisterRequest,
    TransporterInviteRequest,
    ShipmentCreateRequest,
    AssignmentActionRequest,
    ShipmentLegResponse,
    DisruptionReportResponse,
    TransporterDelayRequest,
    TransporterDelayResponse
)
from app.services.collaborative_disruption_service import (
    ensure_shipment_legs,
    simulate_downstream_impact
)

router = APIRouter(prefix="/transporter", tags=["Transporter Portal"])


# ─── PART 3: TRANSPORTER ONBOARDING & REGISTRATION ───────────────────────────

@router.post("/invite")
def invite_transporter(
    req: TransporterInviteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Company Admin invites a transporter organization / carrier.
    Generates a secure cryptographically random onboarding token.
    """
    if current_user.role != "company" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only company administrators can invite transporter partners."
        )

    # Resolve or create Transporter Organization
    org = db.query(TransporterOrganization).filter(
        TransporterOrganization.name == req.carrier_name
    ).first()
    if not org:
        org = TransporterOrganization(
            name=req.carrier_name,
            code=req.carrier_code or req.carrier_name[:6].upper().replace(" ", ""),
            contact_email=req.email
        )
        db.add(org)
        db.commit()
        db.refresh(org)

    token = secrets.token_urlsafe(32)
    invitation = TransporterInvitation(
        company_id=current_user.company_id,
        transporter_org_id=org.id,
        invited_email=req.email,
        carrier_name=req.carrier_name,
        invite_token=token,
        status="PENDING",
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    return {
        "invitation_id": invitation.id,
        "invite_token": token,
        "invited_email": invitation.invited_email,
        "carrier_name": invitation.carrier_name,
        "transporter_org_id": org.id,
        "status": invitation.status,
        "expires_at": invitation.expires_at.isoformat()
    }


@router.post("/register")
def register_transporter(req: TransporterRegisterRequest, db: Session = Depends(get_db)):
    """
    Registers a new carrier/transporter account.
    If invite_token is provided, securely resolves and verifies the invited organization.
    """
    existing_user = db.query(User).filter(User.email == req.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User email already registered")

    transporter_org = None
    company_id = None

    if req.invite_token:
        invitation = db.query(TransporterInvitation).filter(
            TransporterInvitation.invite_token == req.invite_token,
            TransporterInvitation.status == "PENDING"
        ).first()
        if not invitation:
            raise HTTPException(status_code=400, detail="Invalid or already used invite token.")
        if invitation.expires_at < datetime.utcnow():
            invitation.status = "EXPIRED"
            db.commit()
            raise HTTPException(status_code=400, detail="Invite token has expired.")

        transporter_org = invitation.transporter_org
        company_id = invitation.company_id
        invitation.status = "ACCEPTED"
        invitation.accepted_at = datetime.utcnow()
    else:
        # Fallback for self-registration or demo mode: find or create organization
        transporter_org = db.query(TransporterOrganization).filter(
            TransporterOrganization.name == req.carrier_name
        ).first()
        if not transporter_org:
            transporter_org = TransporterOrganization(
                name=req.carrier_name,
                code=req.carrier_name[:6].upper().replace(" ", ""),
                contact_email=req.email
            )
            db.add(transporter_org)
            db.commit()
            db.refresh(transporter_org)

    user = User(
        email=req.email,
        hashed_password=security.get_password_hash(req.password),
        company_id=company_id,
        transporter_org_id=transporter_org.id if transporter_org else None,
        role="transporter",
        carrier_name=transporter_org.name if transporter_org else req.carrier_name,
        is_superuser=False,
        is_active=True
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
        "transporter_org_id": user.transporter_org_id,
        "email": user.email
    }


# ─── PART 4 & 5: SHIPMENT ASSIGNMENT & TRANSPORTER DASHBOARD ──────────────────

@router.get("/assigned-shipments")
def get_assigned_shipments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    DATA MINIMIZATION ENFORCED:
    Transporters only receive shipments strictly assigned to their authorized TransporterOrganization.
    Never exposes profit margins, procurement costs, internal inventory, or other companies' data.
    """
    if current_user.role != "transporter" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted to authorized transporter accounts."
        )

    # Authoritative assignment filter
    q = db.query(Shipment)
    if not current_user.is_superuser:
        if current_user.transporter_org_id:
            # Authorized by organization ID or carrier name matching
            q = q.filter(
                (Shipment.transporter_org_id == current_user.transporter_org_id) |
                (Shipment.carrier == current_user.carrier_name)
            )
        elif current_user.carrier_name:
            q = q.filter(Shipment.carrier == current_user.carrier_name)
        else:
            return []

    shipments = q.order_by(Shipment.id.desc()).limit(50).all()

    result = []
    for s in shipments:
        legs = ensure_shipment_legs(db, s)
        result.append({
            "id": s.id,
            "external_shipment_id": s.external_shipment_id,
            "company_name": s.company.name if s.company else "Consignor Enterprise",
            "origin": s.origin,
            "destination": s.destination,
            "carrier": s.carrier,
            "transport_mode": s.transport_mode,
            "distance_km": s.distance_km,
            "quantity": s.quantity,
            "order_date": str(s.order_date) if s.order_date else None,
            "planned_delivery": str(s.planned_delivery),
            "current_eta": str(s.current_eta or s.planned_delivery),
            "assignment_status": s.assignment_status or "ACCEPTED",
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
                    "status": l.status,
                    "is_assigned_to_caller": (
                        l.carrier_name == current_user.carrier_name or
                        (current_user.transporter_org and l.carrier_name == current_user.transporter_org.name)
                    )
                }
                for l in legs
            ]
        })

    return result


@router.get("/shipments/{shipment_id}/legs")
def get_shipment_legs_endpoint(
    shipment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns legs for a specific assigned shipment.
    Enforces authorization: caller must be assigned transporter or owning company.
    """
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    if not current_user.is_superuser:
        if current_user.role == "transporter":
            is_assigned = (
                (shipment.transporter_org_id and shipment.transporter_org_id == current_user.transporter_org_id) or
                (shipment.carrier and shipment.carrier == current_user.carrier_name)
            )
            if not is_assigned:
                raise HTTPException(status_code=403, detail="Forbidden: Shipment is not assigned to your transporter organization.")
        elif current_user.role == "company":
            if shipment.company_id != current_user.company_id:
                raise HTTPException(status_code=403, detail="Forbidden: Shipment belongs to another company.")

    legs = ensure_shipment_legs(db, shipment)
    return [
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
            "status": l.status,
            "is_assigned_to_caller": (
                l.carrier_name == current_user.carrier_name or
                (current_user.transporter_org and l.carrier_name == current_user.transporter_org.name)
            ) if current_user.role == "transporter" else True
        }
        for l in legs
    ]


@router.post("/shipments/{shipment_id}/assignment-action")
def update_assignment_status(
    shipment_id: int,
    req: AssignmentActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Transporter lifecycle action: ACCEPT, REJECT, START_TRANSIT, COMPLETE_DELIVERY.
    """
    if current_user.role != "transporter" and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Transporters only")

    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # Verify authorization
    if not current_user.is_superuser:
        is_assigned = (
            (shipment.transporter_org_id and shipment.transporter_org_id == current_user.transporter_org_id) or
            (shipment.carrier and shipment.carrier == current_user.carrier_name)
        )
        if not is_assigned:
            raise HTTPException(status_code=403, detail="Shipment is not assigned to your organization.")

    status_map = {
        "ACCEPT": "ACCEPTED",
        "REJECT": "REJECTED",
        "START_TRANSIT": "IN_TRANSIT",
        "COMPLETE_DELIVERY": "DELIVERED"
    }
    shipment.assignment_status = status_map[req.action]
    if req.action == "COMPLETE_DELIVERY":
        shipment.actual_delivery = datetime.utcnow().date()

    db.commit()
    return {
        "shipment_id": shipment.id,
        "assignment_status": shipment.assignment_status,
        "message": f"Shipment status successfully transitioned to {shipment.assignment_status}."
    }


# ─── PART 6, 7 & 8: DISRUPTION REPORTING & NOTIFICATION ROUTING ──────────────

@router.post("/shipments/{shipment_id}/legs/{leg_id}/report-disruption")
def report_leg_disruption(
    shipment_id: int,
    leg_id: int,
    req: DisruptionReportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    CRITICAL SECURITY & ROUTING:
    1. Authenticates caller & verifies transporter role.
    2. Resolves shipment by ID.
    3. Verifies shipment is assigned to caller's transporter organization (prevents IDOR/cross-transporter tampering).
    4. Authoritative Owning Company is derived directly from the shipment record — NEVER from user input.
    5. Checks idempotency_key to prevent duplicate submissions on network retries.
    6. Runs AI Impact Assessment on destination inventory & ETAs.
    7. Creates a targeted company-scoped alert in alerts table so ONLY the owning company receives it.
    """
    if current_user.role != "transporter" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated transporters can submit field exception reports."
        )

    # 1. Authoritative Shipment Retrieval
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # 2. Authorization Check (BOLA / IDOR protection)
    if not current_user.is_superuser:
        is_authorized = (
            (shipment.transporter_org_id and shipment.transporter_org_id == current_user.transporter_org_id) or
            (shipment.carrier and shipment.carrier == current_user.carrier_name)
        )
        if not is_authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: This shipment is not assigned to your transporter organization."
            )

    # 3. Idempotency Check
    if req.idempotency_key:
        existing_report = db.query(DisruptionReport).filter(
            DisruptionReport.idempotency_key == req.idempotency_key
        ).first()
        if existing_report:
            # Return cached response to prevent duplicate alerts
            return {
                "report_id": existing_report.id,
                "shipment_id": existing_report.shipment_id,
                "external_shipment_id": shipment.external_shipment_id,
                "status": "DUPLICATE_IDEMPOTENT_IGNORED",
                "message": "Disruption event already recorded and processed."
            }

    # 4. Trigger AI Impact Assessment & Propagation Engine
    from sqlalchemy.exc import IntegrityError
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

        # Update disruption report with incident details & idempotency key
        report = db.query(DisruptionReport).filter(DisruptionReport.id == impact["report_id"]).first()
        if report:
            report.transporter_org_id = current_user.transporter_org_id
            report.idempotency_key = req.idempotency_key
            report.incident_location = req.incident_location
            report.evidence_url = req.evidence_url
            report.status = "SUBMITTED"

        # Update shipment status
        shipment.assignment_status = "DELAYED"
        if impact.get("total_delay_days"):
            new_eta = shipment.planned_delivery + timedelta(days=int(impact["total_delay_days"]))
            shipment.current_eta = new_eta

        # 5. Targeted Notification Routing:
        # Owning Company resolved authoritatively from shipment.company_id
        alert_severity = "critical" if impact.get("inventory_simulation", {}).get("stockout_predicted") else "high"
        carrier_label = current_user.carrier_name or "Transporter"
        loc_suffix = f" at {req.incident_location}" if req.incident_location else ""
        alert_msg = (
            f"Transporter Exception [{carrier_label}]: Reported {req.disruption_reason}{loc_suffix} "
            f"on Shipment {shipment.external_shipment_id} (+{req.delay_hours}h delay). "
            f"Prescribed mitigation: {impact.get('prescriptive_mitigations', [{}])[0].get('title', 'Monitor schedule')}."
        )

        company_alert = Alert(
            company_id=shipment.company_id,  # STRICTLY OWNING COMPANY
            alert_type="delay",
            severity=alert_severity,
            entity_type="shipment",
            entity_id=shipment.id,
            message=alert_msg,
            is_resolved=0
        )
        db.add(company_alert)
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent race won by another thread with same idempotency key
        if req.idempotency_key:
            existing_report = db.query(DisruptionReport).filter(
                DisruptionReport.idempotency_key == req.idempotency_key
            ).first()
            if existing_report:
                return {
                    "report_id": existing_report.id,
                    "shipment_id": existing_report.shipment_id,
                    "external_shipment_id": shipment.external_shipment_id,
                    "status": "DUPLICATE_IDEMPOTENT_IGNORED",
                    "message": "Disruption event already recorded and processed."
                }
        raise HTTPException(status_code=409, detail="Concurrent conflict on disruption submission.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return impact


@router.get("/recent-disruptions")
def get_recent_disruptions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns disruption reports strictly scoped to caller:
    - If Company User: returns reports for shipments owned by their company_id.
    - If Transporter User: returns reports reported by their transporter_org_id or carrier name.
    """
    import json
    q = db.query(DisruptionReport).join(Shipment, Shipment.id == DisruptionReport.shipment_id)

    if current_user.role == "transporter" and not current_user.is_superuser:
        if current_user.transporter_org_id:
            q = q.filter(
                (DisruptionReport.transporter_org_id == current_user.transporter_org_id) |
                (Shipment.carrier == current_user.carrier_name)
            )
        else:
            q = q.filter(Shipment.carrier == current_user.carrier_name)
    elif not current_user.is_superuser:
        # Company user sees all reports for their company's shipments
        q = q.filter(Shipment.company_id == current_user.company_id)

    reports = q.order_by(DisruptionReport.created_at.desc()).limit(30).all()

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
            "incident_location": r.incident_location,
            "status": r.status or "SUBMITTED",
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


@router.get("/organizations")
def list_transporter_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Company Admin lists registered transporter organizations eligible for shipment assignment.
    """
    orgs = db.query(TransporterOrganization).filter(TransporterOrganization.is_active == True).all()
    return [
        {
            "id": o.id,
            "name": o.name,
            "code": o.code,
            "contact_email": o.contact_email
        }
        for o in orgs
    ]


@router.post("/shipments/{shipment_id}/delay", response_model=TransporterDelayResponse, status_code=status.HTTP_201_CREATED)
def report_shipment_delay(
    shipment_id: int,
    req: TransporterDelayRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    First-class dedicated Transporter Delay Report endpoint.
    Allows carrier/transporter to quickly communicate an operational delay,
    recalculating ETA, updating shipment status to DELAYED, and publishing
    an alert to the Company Control Tower.
    """
    import hashlib
    from datetime import date, timezone
    from sqlalchemy.exc import IntegrityError

    # 1. Role validation
    if current_user.role != "transporter" and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Only authenticated transporters may report shipment delays."
        )

    # 2. Shipment retrieval & existence
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")

    # 3. Carrier Isolation & Authorization
    if not current_user.is_superuser:
        is_assigned = (
            (shipment.transporter_org_id is not None and shipment.transporter_org_id == current_user.transporter_org_id) or
            (shipment.carrier is not None and current_user.carrier_name and shipment.carrier.strip().lower() == current_user.carrier_name.strip().lower())
        )
        if not is_assigned:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: This shipment is not assigned to your transporter organization."
            )

    # 4. Status eligibility check
    curr_status = (shipment.assignment_status or "").upper()
    if curr_status in ("REVOKED", "COMPLETED", "CANCELLED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot report delay on a shipment with assignment status '{curr_status}'."
        )

    # 5. Input validation (new_eta or delay_hours required)
    if not req.new_eta and not req.delay_hours:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'new_eta' or 'delay_hours' must be provided."
        )

    # Determine baseline ETA
    baseline_date = shipment.current_eta or shipment.planned_delivery
    if isinstance(baseline_date, date) and not isinstance(baseline_date, datetime):
        baseline_dt = datetime(baseline_date.year, baseline_date.month, baseline_date.day, 18, 0, 0)
    elif isinstance(baseline_date, datetime):
        baseline_dt = baseline_date
    else:
        baseline_dt = datetime.utcnow() + timedelta(days=1)

    # Calculate computed ETA and delay_hours
    computed_new_eta: datetime
    computed_delay_hours: float

    if req.delay_hours is not None and req.new_eta is None:
        computed_delay_hours = float(req.delay_hours)
        computed_new_eta = baseline_dt + timedelta(hours=computed_delay_hours)
    elif req.new_eta is not None and req.delay_hours is None:
        computed_new_eta = req.new_eta
        # Remove tzinfo for uniform comparison
        cmp_eta = computed_new_eta.replace(tzinfo=None) if computed_new_eta.tzinfo else computed_new_eta
        cmp_base = baseline_dt.replace(tzinfo=None) if baseline_dt.tzinfo else baseline_dt
        computed_delay_hours = max(0.5, round((cmp_eta - cmp_base).total_seconds() / 3600.0, 1))
    else:
        computed_new_eta = req.new_eta
        computed_delay_hours = float(req.delay_hours)

    # Ensure new ETA is in the future
    now_utc = datetime.utcnow()
    cmp_new_eta = computed_new_eta.replace(tzinfo=None) if computed_new_eta.tzinfo else computed_new_eta
    if cmp_new_eta <= now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid new_eta: The revised ETA must be set to a future date and time."
        )

    # Validate reason enum
    valid_reasons = {r.value for r in DelayReasonEnum}
    norm_reason = req.reason.strip().upper().replace(" ", "_")
    if norm_reason not in valid_reasons:
        # Match leniently or fall back to OTHER
        matched = next((r for r in valid_reasons if norm_reason in r or r in norm_reason), "OTHER")
        norm_reason = matched

    # 6. Idempotency and Deduplication Check
    payload_str = f"{shipment_id}:{round(computed_delay_hours, 1)}:{norm_reason}:{cmp_new_eta.isoformat()}"
    payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    if req.idempotency_key:
        existing_delay = db.query(ShipmentDelay).filter(
            ShipmentDelay.idempotency_key == req.idempotency_key
        ).first()

        if existing_delay:
            # Check for conflict: different payload submitted with the same idempotency key
            if existing_delay.payload_hash and existing_delay.payload_hash != payload_hash:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency Conflict: The provided idempotency_key was already used with a different delay payload."
                )

            # Replay original response safely
            return TransporterDelayResponse(
                shipment_id=shipment.id,
                external_shipment_id=shipment.external_shipment_id,
                previous_eta=existing_delay.previous_eta.isoformat() if existing_delay.previous_eta else None,
                new_eta=existing_delay.new_eta.isoformat(),
                delay_hours=existing_delay.delay_hours,
                reason=existing_delay.reason,
                status=shipment.assignment_status or "DELAYED",
                reported_by=current_user.email,
                reported_at=existing_delay.created_at.isoformat(),
                control_tower_alert_id=None,
                message="Duplicate request ignored: delay already recorded."
            )

    # 7. Atomic Execution in Database Transaction
    try:
        prev_eta_val = baseline_dt
        new_eta_date = cmp_new_eta.date()

        # Update Shipment
        shipment.assignment_status = "DELAYED"
        shipment.current_eta = new_eta_date

        # Update legs if present
        legs = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == shipment.id).order_by(ShipmentLeg.sequence).all()
        target_leg = None
        if req.leg_id:
            target_leg = next((l for l in legs if l.id == req.leg_id), None)
        
        if target_leg:
            target_leg.delay_hours = (target_leg.delay_hours or 0.0) + computed_delay_hours
            target_leg.status = "DELAYED"
            # Propagate delay to subsequent active legs
            found_target = False
            for leg in legs:
                if leg.id == target_leg.id:
                    found_target = True
                    continue
                if found_target and leg.status in ("SCHEDULED", "PENDING"):
                    leg.delay_hours = (leg.delay_hours or 0.0) + computed_delay_hours
        else:
            for leg in legs:
                if leg.status in ("SCHEDULED", "IN_TRANSIT"):
                    leg.delay_hours = (leg.delay_hours or 0.0) + computed_delay_hours
                    leg.status = "DELAYED"

        # Create ShipmentDelay record
        delay_record = ShipmentDelay(
            shipment_id=shipment.id,
            transporter_org_id=current_user.transporter_org_id or shipment.transporter_org_id,
            reported_by_user_id=current_user.id,
            previous_eta=prev_eta_val,
            new_eta=cmp_new_eta,
            delay_hours=computed_delay_hours,
            reason=norm_reason,
            notes=req.notes,
            attachment_url=req.attachment_url,
            idempotency_key=req.idempotency_key,
            payload_hash=payload_hash,
            created_at=datetime.utcnow()
        )
        db.add(delay_record)
        db.flush()  # obtain delay_record.id

        # Determine severity based on business logic
        severity = "medium"
        if computed_delay_hours >= 24.0 or (shipment.weight_kg and shipment.weight_kg > 1000):
            severity = "critical"
        elif computed_delay_hours >= 6.0:
            severity = "high"

        carrier_label = current_user.carrier_name or "Transporter"
        leg_str = f" on Leg #{target_leg.sequence} ({target_leg.mode}: {target_leg.origin} → {target_leg.destination})" if target_leg else ""
        notes_snippet = f" | Notes: {req.notes}" if req.notes else ""
        alert_msg = (
            f"Carrier Delay Notice [{carrier_label}]: Shipment {shipment.external_shipment_id}{leg_str} "
            f"reported delay (+{computed_delay_hours}h) due to {norm_reason}. "
            f"Revised ETA: {cmp_new_eta.strftime('%Y-%m-%d %H:%M')}{notes_snippet}"
        )

        alert = Alert(
            company_id=shipment.company_id,
            alert_type="delay",
            severity=severity,
            entity_type="shipment",
            entity_id=shipment.id,
            message=alert_msg,
            is_resolved=0,
            created_at=datetime.utcnow()
        )
        db.add(alert)
        db.commit()
        db.refresh(delay_record)
        db.refresh(alert)

        return TransporterDelayResponse(
            shipment_id=shipment.id,
            external_shipment_id=shipment.external_shipment_id,
            leg_id=target_leg.id if target_leg else None,
            leg_description=f"Leg #{target_leg.sequence} ({target_leg.mode}: {target_leg.origin} → {target_leg.destination})" if target_leg else "Entire Transit Route",
            previous_eta=prev_eta_val.isoformat(),
            new_eta=cmp_new_eta.isoformat(),
            delay_hours=computed_delay_hours,
            reason=norm_reason,
            status=shipment.assignment_status,
            reported_by=current_user.email,
            reported_at=delay_record.created_at.isoformat(),
            control_tower_alert_id=alert.id,
            message="Delay successfully reported and propagated to Company Control Tower."
        )

    except IntegrityError:
        db.rollback()
        # Handle concurrent race condition for identical idempotency key
        if req.idempotency_key:
            existing_delay = db.query(ShipmentDelay).filter(
                ShipmentDelay.idempotency_key == req.idempotency_key
            ).first()
            if existing_delay:
                if existing_delay.payload_hash and existing_delay.payload_hash != payload_hash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Idempotency Conflict: The provided idempotency_key was already used with a different delay payload."
                    )
                return TransporterDelayResponse(
                    shipment_id=shipment.id,
                    external_shipment_id=shipment.external_shipment_id,
                    previous_eta=existing_delay.previous_eta.isoformat() if existing_delay.previous_eta else None,
                    new_eta=existing_delay.new_eta.isoformat(),
                    delay_hours=existing_delay.delay_hours,
                    reason=existing_delay.reason,
                    status=shipment.assignment_status or "DELAYED",
                    reported_by=current_user.email,
                    reported_at=existing_delay.created_at.isoformat(),
                    control_tower_alert_id=None,
                    message="Duplicate request ignored: delay already recorded."
                )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict processing delay report."
        )

