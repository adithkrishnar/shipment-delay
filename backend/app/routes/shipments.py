from app.auth.deps import get_current_user
from app.models.user import User
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.ml.shipment_delay import predict_shipment_risk
from app.models import Company, Shipment, Supplier, Product
from app.schemas.ml import RiskFactorOut, ShipmentListResponse, ShipmentRiskOut
from app.services.model_training_service import get_active_shipment_models
from app.utils.logging_config import get_logger
router = APIRouter(prefix='/api/shipments', tags=['shipments'])
logger = get_logger(__name__)
_SHIPMENT_COLS = ['shipment_id', 'external_shipment_id', 'product_id', 'supplier_id', 'origin', 'destination', 'carrier', 'transport_mode', 'distance_km', 'weight_kg', 'quantity', 'order_date', 'planned_delivery', 'actual_delivery', 'supplier_lead_time_days', 'supplier_reliability', 'supplier_cost_index']

def _row_to_single_df(shipment: Shipment, supplier: Supplier | None) -> pd.DataFrame:
    return pd.DataFrame([{'shipment_id': shipment.id, 'external_shipment_id': shipment.external_shipment_id, 'product_id': shipment.product_id, 'supplier_id': shipment.supplier_id, 'origin': shipment.origin, 'destination': shipment.destination, 'carrier': shipment.carrier, 'transport_mode': shipment.transport_mode, 'distance_km': shipment.distance_km, 'weight_kg': shipment.weight_kg, 'quantity': shipment.quantity, 'order_date': shipment.order_date, 'planned_delivery': shipment.planned_delivery, 'actual_delivery': None, 'supplier_lead_time_days': supplier.lead_time_days if supplier else None, 'supplier_reliability': supplier.reliability if supplier else None, 'supplier_cost_index': supplier.cost_index if supplier else None}])

@router.get('/{company_id}', response_model=ShipmentListResponse)
def list_shipment_risk(company_id: int, limit: int=Query(100, ge=1, le=1000), db: Session=Depends(get_db), *, current_user: User=Depends(get_current_user)):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's data")
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail='Company not found.')
    try:
        classifier, duration_model, clf_entry = get_active_shipment_models(db, company_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    shipments_and_suppliers = db.query(Shipment, Supplier).outerjoin(Supplier, Supplier.id == Shipment.supplier_id).filter(Shipment.company_id == company_id).order_by(Shipment.order_date.desc()).limit(limit).all()
    if not shipments_and_suppliers:
        raise HTTPException(status_code=404, detail='No shipments found for this company.')
    rows = []
    for shipment, supplier in shipments_and_suppliers:
        rows.append({'shipment_id': shipment.id, 'external_shipment_id': shipment.external_shipment_id, 'product_id': shipment.product_id, 'supplier_id': shipment.supplier_id, 'origin': shipment.origin, 'destination': shipment.destination, 'carrier': shipment.carrier, 'transport_mode': shipment.transport_mode, 'distance_km': shipment.distance_km, 'weight_kg': shipment.weight_kg, 'quantity': shipment.quantity, 'order_date': shipment.order_date, 'planned_delivery': shipment.planned_delivery, 'actual_delivery': None, 'supplier_lead_time_days': supplier.lead_time_days if supplier else None, 'supplier_reliability': supplier.reliability if supplier else None, 'supplier_cost_index': supplier.cost_index if supplier else None})
    df_batch = pd.DataFrame(rows)
    from app.ml.shipment_delay import predict_shipment_risk_batch
    try:
        batch_risks = predict_shipment_risk_batch(classifier, duration_model, df_batch)
    except Exception:
        logger.exception('Batch risk prediction failed.')
        batch_risks = [{'delay_probability': 0.0, 'risk_tier': 'LOW', 'expected_delay_days': None, 'top_risk_factors': []}] * len(shipments_and_suppliers)
    results = []
    for (shipment, _), risk in zip(shipments_and_suppliers, batch_risks):
        is_completed = shipment.actual_delivery is not None
        actual_was_delayed = None
        actual_delay_days = None
        if is_completed:
            delta = (shipment.actual_delivery - shipment.planned_delivery).days
            actual_was_delayed = delta > 0
            actual_delay_days = float(delta)
        results.append(ShipmentRiskOut(shipment_id=shipment.id, external_shipment_id=shipment.external_shipment_id, product_id=shipment.product_id, supplier_id=shipment.supplier_id, origin=shipment.origin, destination=shipment.destination, carrier=shipment.carrier, transport_mode=shipment.transport_mode, order_date=str(shipment.order_date) if shipment.order_date else None, planned_delivery=str(shipment.planned_delivery), actual_delivery=str(shipment.actual_delivery) if shipment.actual_delivery else None, is_completed=is_completed, actual_was_delayed=actual_was_delayed, actual_delay_days=actual_delay_days, delay_probability=risk['delay_probability'], risk_tier=risk['risk_tier'], expected_delay_days=risk['expected_delay_days'], top_risk_factors=[RiskFactorOut(**f) for f in risk['top_risk_factors']], model_source=clf_entry.model_source))
    return ShipmentListResponse(company_id=company_id, model_source=clf_entry.model_source, shipments=results)

@router.get('/{company_id}/{shipment_id}', response_model=ShipmentRiskOut)
def get_shipment_risk(company_id: int, shipment_id: int, db: Session=Depends(get_db), *, current_user: User=Depends(get_current_user)):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's data")
    shipment = db.query(Shipment).filter(Shipment.company_id == company_id, Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail='Shipment not found for this company.')
    try:
        classifier, duration_model, clf_entry = get_active_shipment_models(db, company_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    supplier = db.query(Supplier).filter(Supplier.id == shipment.supplier_id).first()
    row_df = _row_to_single_df(shipment, supplier)
    risk = predict_shipment_risk(classifier, duration_model, row_df)
    is_completed = shipment.actual_delivery is not None
    actual_was_delayed = None
    actual_delay_days = None
    if is_completed:
        delta = (shipment.actual_delivery - shipment.planned_delivery).days
        actual_was_delayed = delta > 0
        actual_delay_days = float(delta)
    return ShipmentRiskOut(shipment_id=shipment.id, external_shipment_id=shipment.external_shipment_id, product_id=shipment.product_id, supplier_id=shipment.supplier_id, origin=shipment.origin, destination=shipment.destination, carrier=shipment.carrier, transport_mode=shipment.transport_mode, order_date=str(shipment.order_date) if shipment.order_date else None, planned_delivery=str(shipment.planned_delivery), actual_delivery=str(shipment.actual_delivery) if shipment.actual_delivery else None, is_completed=is_completed, actual_was_delayed=actual_was_delayed, actual_delay_days=actual_delay_days, delay_probability=risk['delay_probability'], risk_tier=risk['risk_tier'], expected_delay_days=risk['expected_delay_days'], top_risk_factors=[RiskFactorOut(**f) for f in risk['top_risk_factors']], model_source=clf_entry.model_source)
@router.get('/{company_id}/multi-leg/{shipment_id}')
def get_multi_leg_shipment(company_id: int, shipment_id: int, scenario: int = 1, db: Session=Depends(get_db), current_user: User=Depends(get_current_user)):
    from app.services.multi_leg_service import analyze_multi_leg_shipment
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's data")
    try:
        return analyze_multi_leg_shipment(db, company_id, shipment_id, scenario)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post('/{company_id}', status_code=201)
def create_shipment(
    company_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Company Admin creates a new shipment and assigns an eligible transporter organization.
    """
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to create shipments for this company")

    from app.models.transporter_org import TransporterOrganization
    from app.services.collaborative_disruption_service import ensure_shipment_legs
    from datetime import datetime, date

    # Validate product
    product_id = payload.get("product_id")
    product = db.query(Product).filter(Product.id == product_id, Product.company_id == company_id).first()
    if not product:
        raise HTTPException(400, "Valid product_id belonging to this company is required")

    # Resolve transporter organization if provided
    transporter_org_id = payload.get("transporter_org_id")
    carrier_name = payload.get("carrier")
    if transporter_org_id:
        t_org = db.query(TransporterOrganization).filter(TransporterOrganization.id == transporter_org_id).first()
        if not t_org:
            raise HTTPException(400, "Specified transporter organization does not exist")
        carrier_name = t_org.name

    planned_del_val = payload.get("planned_delivery")
    if isinstance(planned_del_val, str):
        planned_del = datetime.strptime(planned_del_val, "%Y-%m-%d").date()
    else:
        planned_del = planned_del_val or date.today()

    order_date_val = payload.get("order_date")
    if isinstance(order_date_val, str):
        order_date = datetime.strptime(order_date_val, "%Y-%m-%d").date()
    else:
        order_date = order_date_val or date.today()

    shipment = Shipment(
        company_id=company_id,
        product_id=product.id,
        supplier_id=payload.get("supplier_id"),
        external_shipment_id=payload.get("external_shipment_id") or f"SHP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
        origin=payload.get("origin") or "Primary Manufacturing Hub",
        destination=payload.get("destination") or "Central Distribution Center",
        carrier=carrier_name,
        transporter_org_id=transporter_org_id,
        assignment_status="ACCEPTED" if transporter_org_id else "PENDING",
        transport_mode=(payload.get("transport_mode") or "ROAD").upper(),
        distance_km=float(payload.get("distance_km") or 650.0),
        weight_kg=float(payload.get("weight_kg") or 250.0),
        quantity=float(payload.get("quantity") or 100.0),
        order_date=order_date,
        planned_delivery=planned_del,
        current_eta=planned_del,
    )
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    # Provision multi-modal legs
    legs = ensure_shipment_legs(db, shipment)

    return {
        "id": shipment.id,
        "external_shipment_id": shipment.external_shipment_id,
        "company_id": shipment.company_id,
        "carrier": shipment.carrier,
        "transporter_org_id": shipment.transporter_org_id,
        "assignment_status": shipment.assignment_status,
        "origin": shipment.origin,
        "destination": shipment.destination,
        "planned_delivery": str(shipment.planned_delivery),
        "legs_count": len(legs)
    }

