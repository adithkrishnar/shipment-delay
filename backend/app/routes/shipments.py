from typing import Optional
from datetime import datetime, date
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_or_demo
from app.models.user import User
from app.database import get_db
from app.models import Company, Shipment, Supplier, Product, Warehouse, InventoryRecord
from app.models.alert import Alert
from app.models.shipment_leg import ShipmentLeg
from app.schemas.ml import RiskFactorOut, ShipmentListResponse, ShipmentRiskOut
from app.services.model_training_service import get_active_shipment_models
from app.services.collaborative_disruption_service import ensure_shipment_legs
from app.utils.logging_config import get_logger

router = APIRouter(prefix="/api/shipments", tags=["shipments"])
logger = get_logger(__name__)

_SHIPMENT_COLS = [
    "shipment_id", "external_shipment_id", "product_id", "supplier_id",
    "origin", "destination", "carrier", "transport_mode", "distance_km",
    "weight_kg", "quantity", "order_date", "planned_delivery",
    "actual_delivery", "supplier_lead_time_days", "supplier_reliability",
    "supplier_cost_index"
]


def _row_to_single_df(shipment: Shipment, supplier: Optional[Supplier]) -> pd.DataFrame:
    return pd.DataFrame([{
        "shipment_id": shipment.id,
        "external_shipment_id": shipment.external_shipment_id,
        "product_id": shipment.product_id,
        "supplier_id": shipment.supplier_id,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "carrier": shipment.carrier,
        "transport_mode": shipment.transport_mode,
        "distance_km": shipment.distance_km,
        "weight_kg": shipment.weight_kg,
        "quantity": shipment.quantity,
        "order_date": shipment.order_date,
        "planned_delivery": shipment.planned_delivery,
        "actual_delivery": None,
        "supplier_lead_time_days": supplier.lead_time_days if supplier else None,
        "supplier_reliability": supplier.reliability if supplier else None,
        "supplier_cost_index": supplier.cost_index if supplier else None
    }])


@router.get("/{company_id}", response_model=ShipmentListResponse)
def list_shipment_risk(
    company_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo)
):
    """
    Returns both outgoing and inbound shipments for the given company,
    enriched with ML delay probability and live carrier assignment statuses.
    """
    if not current_user.is_superuser:
        if current_user.role == "company" and current_user.company_id != company_id:
            raise HTTPException(status_code=403, detail="Forbidden: Not authorized to view another company's shipments.")

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    limit_val = int(getattr(limit, 'default', limit)) if hasattr(limit, 'default') else int(limit or 100)

    # Model resolution with resilient fallback
    classifier, duration_model, clf_entry = None, None, None
    model_source = "BASE_MODEL"
    try:
        classifier, duration_model, clf_entry = get_active_shipment_models(db, company_id)
        if clf_entry:
            model_source = clf_entry.model_source
    except Exception as exc:
        logger.info("Using baseline risk heuristics for company %d (%s)", company_id, exc)

    # Fetch shipments where this company is either Sender (company_id) or Receiver (receiver_company_id)
    shipments_and_suppliers = (
        db.query(Shipment, Supplier)
        .outerjoin(Supplier, Supplier.id == Shipment.supplier_id)
        .filter(
            (Shipment.company_id == company_id) |
            (Shipment.receiver_company_id == company_id)
        )
        .order_by(Shipment.id.desc())
        .limit(limit_val)
        .all()
    )

    if not shipments_and_suppliers:
        return ShipmentListResponse(
            company_id=company_id,
            model_source=model_source,
            shipments=[]
        )

    # Batch prediction if models are active
    batch_risks = []
    if classifier and duration_model:
        rows = []
        for shipment, supplier in shipments_and_suppliers:
            rows.append({
                "shipment_id": shipment.id,
                "external_shipment_id": shipment.external_shipment_id,
                "product_id": shipment.product_id,
                "supplier_id": shipment.supplier_id,
                "origin": shipment.origin,
                "destination": shipment.destination,
                "carrier": shipment.carrier,
                "transport_mode": shipment.transport_mode,
                "distance_km": shipment.distance_km,
                "weight_kg": shipment.weight_kg,
                "quantity": shipment.quantity,
                "order_date": shipment.order_date,
                "planned_delivery": shipment.planned_delivery,
                "actual_delivery": None,
                "supplier_lead_time_days": supplier.lead_time_days if supplier else None,
                "supplier_reliability": supplier.reliability if supplier else None,
                "supplier_cost_index": supplier.cost_index if supplier else None
            })
        df_batch = pd.DataFrame(rows)
        from app.ml.shipment_delay import predict_shipment_risk_batch
        try:
            batch_risks = predict_shipment_risk_batch(classifier, duration_model, df_batch)
        except Exception:
            logger.exception("Batch risk prediction fallback.")
            batch_risks = [
                {"delay_probability": 0.15, "risk_tier": "LOW", "expected_delay_days": None, "top_risk_factors": []}
            ] * len(shipments_and_suppliers)
    else:
        # Default heuristic based on live assignment status and dates
        batch_risks = [
            {"delay_probability": 0.15, "risk_tier": "LOW", "expected_delay_days": None, "top_risk_factors": []}
        ] * len(shipments_and_suppliers)

    results = []
    for (shipment, _), risk in zip(shipments_and_suppliers, batch_risks):
        is_completed = shipment.actual_delivery is not None
        actual_was_delayed = None
        actual_delay_days = None
        if is_completed:
            delta = (shipment.actual_delivery - shipment.planned_delivery).days
            actual_was_delayed = delta > 0
            actual_delay_days = float(delta)

        # Reconcile risk tier with reported carrier delay
        risk_tier = risk.get("risk_tier", "LOW")
        expected_days = risk.get("expected_delay_days")
        delay_prob = risk.get("delay_probability", 0.15)

        if shipment.assignment_status == "DELAYED":
            risk_tier = "CRITICAL"
            delay_prob = max(delay_prob, 0.88)
            if shipment.current_eta and shipment.planned_delivery:
                day_diff = (shipment.current_eta - shipment.planned_delivery).days
                expected_days = max(1.0, float(day_diff))
            else:
                expected_days = max(1.0, float(expected_days or 1.0))
        elif shipment.assignment_status == "ARRIVED":
            risk_tier = "LOW"
            delay_prob = 0.05
        elif shipment.assignment_status == "DELIVERED":
            risk_tier = "LOW"
            delay_prob = 0.0

        rec_name = shipment.receiver_company.name if shipment.receiver_company else None
        sender_name = shipment.company.name if shipment.company else None

        results.append(ShipmentRiskOut(
            shipment_id=shipment.id,
            external_shipment_id=shipment.external_shipment_id,
            product_id=shipment.product_id,
            supplier_id=shipment.supplier_id,
            origin=shipment.origin,
            destination=shipment.destination,
            carrier=shipment.carrier,
            transport_mode=shipment.transport_mode,
            receiver_company_id=shipment.receiver_company_id,
            receiver_company_name=rec_name,
            sender_company_name=sender_name,
            assignment_status=shipment.assignment_status or "IN_TRANSIT",
            current_eta=str(shipment.current_eta) if shipment.current_eta else str(shipment.planned_delivery),
            order_date=str(shipment.order_date) if shipment.order_date else None,
            planned_delivery=str(shipment.planned_delivery),
            actual_delivery=str(shipment.actual_delivery) if shipment.actual_delivery else None,
            is_completed=is_completed,
            actual_was_delayed=actual_was_delayed,
            actual_delay_days=actual_delay_days,
            delay_probability=delay_prob,
            risk_tier=risk_tier,
            expected_delay_days=expected_days,
            top_risk_factors=[RiskFactorOut(**f) for f in risk.get("top_risk_factors", [])],
            model_source=model_source
        ))

    return ShipmentListResponse(
        company_id=company_id,
        model_source=model_source,
        shipments=results
    )


@router.get("/{company_id}/{shipment_id}", response_model=ShipmentRiskOut)
def get_shipment_risk(
    company_id: int,
    shipment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo)
):
    if not current_user.is_superuser:
        if current_user.role == "company" and current_user.company_id != company_id:
            raise HTTPException(status_code=403, detail="Forbidden: Not authorized to view another company's shipments.")

    shipment = db.query(Shipment).filter(
        ((Shipment.company_id == company_id) | (Shipment.receiver_company_id == company_id)),
        Shipment.id == shipment_id
    ).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found for this company.")

    classifier, duration_model, clf_entry = None, None, None
    model_source = "BASE_MODEL"
    try:
        classifier, duration_model, clf_entry = get_active_shipment_models(db, company_id)
        if clf_entry:
            model_source = clf_entry.model_source
    except Exception:
        pass

    supplier = db.query(Supplier).filter(Supplier.id == shipment.supplier_id).first()
    row_df = _row_to_single_df(shipment, supplier)
    
    if classifier and duration_model:
        from app.ml.shipment_delay import predict_shipment_risk
        risk = predict_shipment_risk(classifier, duration_model, row_df)
    else:
        risk = {"delay_probability": 0.15, "risk_tier": "LOW", "expected_delay_days": None, "top_risk_factors": []}

    is_completed = shipment.actual_delivery is not None
    actual_was_delayed = None
    actual_delay_days = None
    if is_completed:
        delta = (shipment.actual_delivery - shipment.planned_delivery).days
        actual_was_delayed = delta > 0
        actual_delay_days = float(delta)

    risk_tier = risk.get("risk_tier", "LOW")
    expected_days = risk.get("expected_delay_days")
    delay_prob = risk.get("delay_probability", 0.15)

    if shipment.assignment_status == "DELAYED":
        risk_tier = "CRITICAL"
        delay_prob = max(delay_prob, 0.88)
        if shipment.current_eta and shipment.planned_delivery:
            day_diff = (shipment.current_eta - shipment.planned_delivery).days
            expected_days = max(1.0, float(day_diff))
        else:
            expected_days = max(1.0, float(expected_days or 1.0))

    rec_name = shipment.receiver_company.name if shipment.receiver_company else None
    sender_name = shipment.company.name if shipment.company else None

    return ShipmentRiskOut(
        shipment_id=shipment.id,
        external_shipment_id=shipment.external_shipment_id,
        product_id=shipment.product_id,
        supplier_id=shipment.supplier_id,
        origin=shipment.origin,
        destination=shipment.destination,
        carrier=shipment.carrier,
        transport_mode=shipment.transport_mode,
        receiver_company_id=shipment.receiver_company_id,
        receiver_company_name=rec_name,
        sender_company_name=sender_name,
        assignment_status=shipment.assignment_status or "IN_TRANSIT",
        current_eta=str(shipment.current_eta) if shipment.current_eta else str(shipment.planned_delivery),
        order_date=str(shipment.order_date) if shipment.order_date else None,
        planned_delivery=str(shipment.planned_delivery),
        actual_delivery=str(shipment.actual_delivery) if shipment.actual_delivery else None,
        is_completed=is_completed,
        actual_was_delayed=actual_was_delayed,
        actual_delay_days=actual_delay_days,
        delay_probability=delay_prob,
        risk_tier=risk_tier,
        expected_delay_days=expected_days,
        top_risk_factors=[RiskFactorOut(**f) for f in risk.get("top_risk_factors", [])],
        model_source=model_source
    )


@router.get("/{company_id}/multi-leg/{shipment_id}")
def get_multi_leg_shipment(
    company_id: int,
    shipment_id: int,
    scenario: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo)
):
    from app.services.multi_leg_service import analyze_multi_leg_shipment
    try:
        return analyze_multi_leg_shipment(db, company_id, shipment_id, scenario)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{company_id}", status_code=201)
def create_shipment(
    company_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo)
):
    """
    Company Admin creates a new shipment, selects receiver & transporter,
    and provisions sequenced multi-modal transportation legs.
    """
    if not current_user.is_superuser:
        if current_user.role != "company" or current_user.company_id != company_id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Only authorized company managers can dispatch shipments for their enterprise."
            )

    from app.models.transporter_org import TransporterOrganization

    # Validate product
    product_id = payload.get("product_id")
    product = db.query(Product).filter(
        Product.company_id == company_id,
        Product.id == product_id
    ).first()
    if not product:
        product = db.query(Product).filter(Product.company_id == company_id).first()
    if not product:
        # Create default SKU if company has no products yet
        product = Product(
            company_id=company_id,
            external_product_id="SKU-GEN-01",
            name="Manufactured Assembly Unit",
            unit_price=4500.0,
            unit_cost=2200.0
        )
        db.add(product)
        db.flush()

    # Resolve receiver company and destination warehouse
    receiver_company_id = payload.get("receiver_company_id")
    destination_wh_id = payload.get("destination_warehouse_id")

    if not destination_wh_id and receiver_company_id:
        rec_wh = db.query(Warehouse).filter(Warehouse.company_id == receiver_company_id).first()
        if rec_wh:
            destination_wh_id = rec_wh.id

    # Resolve transporter organization
    transporter_org_id = payload.get("transporter_org_id")
    carrier_name = payload.get("carrier")
    if transporter_org_id:
        t_org = db.query(TransporterOrganization).filter(TransporterOrganization.id == transporter_org_id).first()
        if t_org:
            carrier_name = t_org.name

    planned_del_val = payload.get("planned_delivery")
    if isinstance(planned_del_val, str):
        planned_del = datetime.strptime(planned_del_val, "%Y-%m-%d").date()
    else:
        planned_del = planned_del_val or (date.today() + pd.Timedelta(days=2))

    order_date_val = payload.get("order_date")
    if isinstance(order_date_val, str):
        order_date = datetime.strptime(order_date_val, "%Y-%m-%d").date()
    else:
        order_date = order_date_val or date.today()

    # Generate authoritative human-readable reference: SH-BLR-2026-XXXX (collision-free)
    origin_text = payload.get("origin") or "Bengaluru Electronic City Plant"
    prefix = "BLR" if "bengaluru" in origin_text.lower() else "SHP"
    external_ref = payload.get("external_shipment_id")

    if not external_ref:
        import re
        existing_refs = db.query(Shipment.external_shipment_id).filter(
            Shipment.external_shipment_id.like(f"SH-{prefix}-2026-%")
        ).all()
        max_seq = 0
        for (ref,) in existing_refs:
            m = re.search(r"(\d+)$", ref)
            if m:
                val = int(m.group(1))
                if val > max_seq:
                    max_seq = val
        external_ref = f"SH-{prefix}-2026-{max_seq + 1:04d}"
    else:
        existing = db.query(Shipment).filter(Shipment.external_shipment_id == external_ref).first()
        if existing:
            import uuid
            external_ref = f"{external_ref}-{uuid.uuid4().hex[:4].upper()}"

    shipment = Shipment(
        company_id=company_id,
        receiver_company_id=receiver_company_id,
        destination_warehouse_id=destination_wh_id,
        product_id=product.id,
        supplier_id=payload.get("supplier_id"),
        external_shipment_id=external_ref,
        origin=origin_text,
        destination=payload.get("destination") or "Chennai Central DC",
        carrier=carrier_name,
        transporter_org_id=transporter_org_id,
        assignment_status="PENDING" if transporter_org_id else "ACCEPTED",
        transport_mode=(payload.get("transport_mode") or "ROAD").upper(),
        distance_km=float(payload.get("distance_km") or 360.0),
        weight_kg=float(payload.get("weight_kg") or 450.0),
        quantity=float(payload.get("quantity") or 100.0),
        order_date=order_date,
        planned_delivery=planned_del,
        current_eta=planned_del,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    # Provision sequenced multi-modal legs
    legs = ensure_shipment_legs(db, shipment)

    # Create dispatch notification alert
    sender_comp = db.query(Company).filter(Company.id == company_id).first()
    alert_msg = (
        f"Shipment Created [{shipment.external_shipment_id}]: "
        f"{sender_comp.name if sender_comp else 'Sender'} dispatched {shipment.quantity:.0f} units "
        f"from {shipment.origin} to {shipment.destination} via {shipment.carrier or 'Carrier Fleet'}."
    )
    db.add(Alert(
        company_id=company_id,
        alert_type="shipment_created",
        severity="healthy",
        entity_type="shipment",
        entity_id=shipment.id,
        message=alert_msg,
        is_resolved=1,
        created_at=datetime.utcnow()
    ))
    if receiver_company_id:
        db.add(Alert(
            company_id=receiver_company_id,
            alert_type="inbound_shipment",
            severity="healthy",
            entity_type="shipment",
            entity_id=shipment.id,
            message=alert_msg,
            is_resolved=0,
            created_at=datetime.utcnow()
        ))
    db.commit()

    return {
        "id": shipment.id,
        "external_shipment_id": shipment.external_shipment_id,
        "company_id": shipment.company_id,
        "receiver_company_id": shipment.receiver_company_id,
        "carrier": shipment.carrier,
        "transporter_org_id": shipment.transporter_org_id,
        "assignment_status": shipment.assignment_status,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "planned_delivery": str(shipment.planned_delivery),
        "legs_count": len(legs)
    }


@router.post("/{shipment_id}/legs/{leg_id}/complete")
@router.post("/{shipment_id}/legs/{leg_id}/advance")
def complete_shipment_leg(
    shipment_id: int,
    leg_id: int,
    payload: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo)
):
    """
    Advances transportation workflow:
    - Marks Leg N as COMPLETED.
    - Idempotently activates Leg N+1 to IN_TRANSIT.
    - If Leg N was the final leg, transitions shipment to ARRIVED awaiting receiver delivery confirmation.
    """
    shipment = db.query(Shipment).filter(
        (Shipment.id == shipment_id) | (Shipment.external_shipment_id == str(shipment_id))
    ).first()
    if not shipment:
        raise HTTPException(404, "Shipment not found")

    if not current_user.is_superuser:
        if current_user.role == "transporter":
            is_assigned = (
                not shipment.transporter_org_id or
                (shipment.transporter_org_id == current_user.transporter_org_id) or
                (shipment.carrier and current_user.carrier_name and shipment.carrier.strip().lower() in current_user.carrier_name.strip().lower()) or
                (current_user.company_id == shipment.company_id)
            )
            if not is_assigned:
                raise HTTPException(403, "Forbidden: Shipment is not assigned to your transporter fleet.")
        elif current_user.role == "company":
            if current_user.company_id != shipment.company_id:
                raise HTTPException(403, "Forbidden: Only consignor dispatcher or assigned transporter can complete legs.")

    if shipment.assignment_status in ("DELIVERED", "CANCELLED", "REVOKED"):
        raise HTTPException(400, f"Cannot advance legs on a shipment with status '{shipment.assignment_status}'.")

    legs = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == shipment.id).order_by(ShipmentLeg.sequence).all()
    target_leg = next((l for l in legs if l.id == leg_id or l.sequence == leg_id), None)
    if not target_leg:
        raise HTTPException(404, "Specified leg does not belong to this shipment")

    # Idempotent check: if leg already completed, return immediately without re-triggering transitions
    if target_leg.status == "COMPLETED":
        next_leg = next((l for l in legs if l.sequence == target_leg.sequence + 1), None)
        return {
            "shipment_id": shipment.id,
            "external_shipment_id": shipment.external_shipment_id,
            "completed_leg": {
                "id": target_leg.id,
                "sequence": target_leg.sequence,
                "origin": target_leg.origin,
                "destination": target_leg.destination,
                "status": target_leg.status
            },
            "next_leg": {
                "id": next_leg.id,
                "sequence": next_leg.sequence,
                "origin": next_leg.origin,
                "destination": next_leg.destination,
                "status": next_leg.status
            } if next_leg else None,
            "assignment_status": shipment.assignment_status,
            "message": f"Leg #{target_leg.sequence} was already marked COMPLETED previously."
        }

    # Enforce sequential integrity: preceding legs must be COMPLETED
    for l in legs:
        if l.sequence < target_leg.sequence and l.status != "COMPLETED":
            raise HTTPException(
                400,
                f"Preceding Leg #{l.sequence} ({l.origin} → {l.destination}) is not yet completed. "
                f"Legs must progress sequentially."
            )

    now = datetime.utcnow()
    target_leg.status = "COMPLETED"
    target_leg.scheduled_arrival = now

    # Activate next leg if one exists
    next_leg = next((l for l in legs if l.sequence == target_leg.sequence + 1), None)

    if next_leg:
        next_leg.status = "IN_TRANSIT"
        next_leg.scheduled_departure = now
        shipment.assignment_status = "IN_TRANSIT"

        carrier_label = next_leg.carrier_name or shipment.carrier or "Transporter Fleet"
        alert_msg = (
            f"Transit Handover [{shipment.external_shipment_id}]: Leg #{target_leg.sequence} "
            f"({target_leg.origin} → {target_leg.destination}) completed. Cargo handed over to "
            f"Leg #{next_leg.sequence} ({next_leg.origin} → {next_leg.destination}) via {carrier_label}."
        )
        for cid in {shipment.company_id, shipment.receiver_company_id}:
            if cid:
                db.add(Alert(
                    company_id=cid,
                    alert_type="transit_handover",
                    severity="healthy",
                    entity_type="shipment",
                    entity_id=shipment.id,
                    message=alert_msg,
                    is_resolved=1,
                    created_at=now
                ))
    else:
        # All legs completed!
        shipment.assignment_status = "ARRIVED"
        dest_name = shipment.destination_warehouse.name if shipment.destination_warehouse else shipment.destination
        arrived_msg = (
            f"Cargo Arrival [{shipment.external_shipment_id}]: All transit legs completed. "
            f"Cargo has arrived at {dest_name}. Awaiting receiver delivery confirmation and stock receipt."
        )
        for cid in {shipment.company_id, shipment.receiver_company_id}:
            if cid:
                db.add(Alert(
                    company_id=cid,
                    alert_type="shipment_arrived",
                    severity="healthy",
                    entity_type="shipment",
                    entity_id=shipment.id,
                    message=arrived_msg,
                    is_resolved=0,
                    created_at=now
                ))

    db.commit()
    return {
        "shipment_id": shipment.id,
        "external_shipment_id": shipment.external_shipment_id,
        "completed_leg": {
            "id": target_leg.id,
            "sequence": target_leg.sequence,
            "origin": target_leg.origin,
            "destination": target_leg.destination,
            "status": target_leg.status
        },
        "next_leg": {
            "id": next_leg.id,
            "sequence": next_leg.sequence,
            "origin": next_leg.origin,
            "destination": next_leg.destination,
            "status": next_leg.status
        } if next_leg else None,
        "assignment_status": shipment.assignment_status,
        "message": f"Leg #{target_leg.sequence} marked COMPLETED." + (
            f" Leg #{next_leg.sequence} is now IN_TRANSIT." if next_leg else
            " All transit legs completed; cargo arrived at destination warehouse."
        )
    }


@router.post("/{shipment_id}/confirm-delivery")
def confirm_shipment_delivery(
    shipment_id: int,
    payload: dict = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_or_demo)
):
    """
    Receiver / Customer confirms delivery and receives stock.
    Transitions status to DELIVERED, records actual delivery timestamp,
    and updates destination warehouse inventory.
    """
    shipment = db.query(Shipment).filter(
        (Shipment.id == shipment_id) | (Shipment.external_shipment_id == str(shipment_id))
    ).first()
    if not shipment:
        raise HTTPException(404, "Shipment not found")

    target_company_id = shipment.receiver_company_id or shipment.company_id
    if not current_user.is_superuser:
        if current_user.role != "company" or current_user.company_id != target_company_id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: Only the receiving destination company can confirm physical cargo delivery and replenish warehouse stock."
            )

    if shipment.assignment_status == "DELIVERED":
        return {
            "shipment_id": shipment.id,
            "external_shipment_id": shipment.external_shipment_id,
            "status": "DELIVERED",
            "message": "Shipment delivery was already confirmed previously."
        }

    now_dt = datetime.utcnow()
    today_date = now_dt.date()

    # Mark shipment DELIVERED
    shipment.assignment_status = "DELIVERED"
    shipment.actual_delivery = today_date

    # Resolve destination warehouse
    wh = None
    if shipment.destination_warehouse_id:
        wh = db.query(Warehouse).filter(Warehouse.id == shipment.destination_warehouse_id).first()
    if not wh and shipment.destination:
        wh = db.query(Warehouse).filter(
            Warehouse.company_id == target_company_id,
            Warehouse.name.ilike(f"%{shipment.destination}%")
        ).first()
    if not wh:
        wh = db.query(Warehouse).filter(Warehouse.company_id == target_company_id).first()

    # Increment inventory at destination warehouse
    received_qty = float((payload or {}).get("received_quantity") or shipment.quantity or 100.0)
    new_inv_level = received_qty

    # Resolve product matching for target company
    target_product_id = shipment.product_id
    if shipment.product_id:
        source_prod = db.query(Product).filter(Product.id == shipment.product_id).first()
        if source_prod:
            rec_prod = db.query(Product).filter(
                Product.company_id == target_company_id,
                (Product.external_product_id == source_prod.external_product_id) | (Product.name == source_prod.name)
            ).first()
            if rec_prod:
                target_product_id = rec_prod.id

    if wh:
        # Match by resolved product_id, or shipment product_id, or latest record at this warehouse
        inv_rec = None
        if target_product_id:
            inv_rec = db.query(InventoryRecord).filter(
                InventoryRecord.company_id == target_company_id,
                InventoryRecord.warehouse_id == wh.id,
                InventoryRecord.product_id == target_product_id
            ).order_by(InventoryRecord.date.desc()).first()
        if not inv_rec and shipment.product_id:
            inv_rec = db.query(InventoryRecord).filter(
                InventoryRecord.company_id == target_company_id,
                InventoryRecord.warehouse_id == wh.id,
                InventoryRecord.product_id == shipment.product_id
            ).order_by(InventoryRecord.date.desc()).first()
        if not inv_rec:
            inv_rec = db.query(InventoryRecord).filter(
                InventoryRecord.company_id == target_company_id,
                InventoryRecord.warehouse_id == wh.id
            ).order_by(InventoryRecord.date.desc()).first()
            if inv_rec and not target_product_id:
                target_product_id = inv_rec.product_id

        if inv_rec:
            inv_rec.inventory_level = (inv_rec.inventory_level or 0.0) + received_qty
            inv_rec.date = today_date
            new_inv_level = inv_rec.inventory_level
        else:
            inv_rec = InventoryRecord(
                company_id=target_company_id,
                warehouse_id=wh.id,
                product_id=target_product_id or shipment.product_id,
                date=today_date,
                inventory_level=received_qty
            )
            db.add(inv_rec)

    # Resolve prior delay alerts for this shipment
    db.query(Alert).filter(
        Alert.entity_id == shipment.id,
        Alert.alert_type == "delay"
    ).update({"is_resolved": 1})

    # Create delivery confirmation alerts for Sender & Receiver
    wh_name = wh.name if wh else (shipment.destination or "Destination Warehouse")
    conf_msg = (
        f"Delivery Receipt Confirmed [{shipment.external_shipment_id}]: Cargo successfully received "
        f"and inspected at {wh_name}. Inventory replenished by +{received_qty:.0f} units "
        f"(Current on-hand: {new_inv_level:.0f} units)."
    )
    for cid in {shipment.company_id, shipment.receiver_company_id}:
        if cid:
            db.add(Alert(
                company_id=cid,
                alert_type="delivery_confirmed",
                severity="healthy",
                entity_type="shipment",
                entity_id=shipment.id,
                message=conf_msg,
                is_resolved=1,
                created_at=now_dt
            ))

    db.commit()
    return {
        "shipment_id": shipment.id,
        "external_shipment_id": shipment.external_shipment_id,
        "status": "DELIVERED",
        "actual_delivery": str(shipment.actual_delivery),
        "received_quantity": received_qty,
        "warehouse_name": wh_name,
        "new_inventory_level": new_inv_level,
        "message": f"Shipment {shipment.external_shipment_id} successfully received and added to warehouse inventory."
    }
