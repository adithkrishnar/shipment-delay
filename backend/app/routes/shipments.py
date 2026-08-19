import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.shipment_delay import predict_shipment_risk
from app.models import Company, Shipment, Supplier
from app.schemas.ml import RiskFactorOut, ShipmentListResponse, ShipmentRiskOut
from app.services.model_training_service import get_active_shipment_models
from app.utils.logging_config import get_logger

router = APIRouter(prefix="/api/shipments", tags=["shipments"])
logger = get_logger(__name__)

_SHIPMENT_COLS = [
    "shipment_id", "external_shipment_id", "product_id", "supplier_id", "origin", "destination",
    "carrier", "transport_mode", "distance_km", "weight_kg", "quantity",
    "order_date", "planned_delivery", "actual_delivery",
    "supplier_lead_time_days", "supplier_reliability", "supplier_cost_index",
]


def _row_to_single_df(shipment: Shipment, supplier: Supplier | None) -> pd.DataFrame:
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
        "actual_delivery": None,  # always predict as if not yet delivered
        "supplier_lead_time_days": supplier.lead_time_days if supplier else None,
        "supplier_reliability": supplier.reliability if supplier else None,
        "supplier_cost_index": supplier.cost_index if supplier else None,
    }])


@router.get("/{company_id}", response_model=ShipmentListResponse)
def list_shipment_risk(
    company_id: int,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")

    try:
        classifier, duration_model, clf_entry = get_active_shipment_models(db, company_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    shipments_and_suppliers = (
        db.query(Shipment, Supplier)
        .outerjoin(Supplier, Supplier.id == Shipment.supplier_id)
        .filter(Shipment.company_id == company_id)
        .order_by(Shipment.order_date.desc())
        .limit(limit)
        .all()
    )
    
    if not shipments_and_suppliers:
        raise HTTPException(status_code=404, detail="No shipments found for this company.")

    # Prepare DataFrame for batch prediction
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
            "supplier_cost_index": supplier.cost_index if supplier else None,
        })
    df_batch = pd.DataFrame(rows)

    # Batch Predict
    from app.ml.shipment_delay import predict_shipment_risk_batch
    try:
        batch_risks = predict_shipment_risk_batch(classifier, duration_model, df_batch)
    except Exception:
        logger.exception("Batch risk prediction failed.")
        # Fallback empty list of risks if it somehow fails completely
        batch_risks = [{"delay_probability": 0.0, "risk_tier": "LOW", "expected_delay_days": None, "top_risk_factors": []}] * len(shipments_and_suppliers)

    results = []
    for (shipment, _), risk in zip(shipments_and_suppliers, batch_risks):
        is_completed = shipment.actual_delivery is not None
        actual_was_delayed = None
        actual_delay_days = None
        if is_completed:
            delta = (shipment.actual_delivery - shipment.planned_delivery).days
            actual_was_delayed = delta > 0
            actual_delay_days = float(delta)

        results.append(ShipmentRiskOut(
            shipment_id=shipment.id,
            external_shipment_id=shipment.external_shipment_id,
            product_id=shipment.product_id,
            supplier_id=shipment.supplier_id,
            origin=shipment.origin,
            destination=shipment.destination,
            carrier=shipment.carrier,
            transport_mode=shipment.transport_mode,
            order_date=str(shipment.order_date) if shipment.order_date else None,
            planned_delivery=str(shipment.planned_delivery),
            actual_delivery=str(shipment.actual_delivery) if shipment.actual_delivery else None,
            is_completed=is_completed,
            actual_was_delayed=actual_was_delayed,
            actual_delay_days=actual_delay_days,
            delay_probability=risk["delay_probability"],
            risk_tier=risk["risk_tier"],
            expected_delay_days=risk["expected_delay_days"],
            top_risk_factors=[RiskFactorOut(**f) for f in risk["top_risk_factors"]],
            model_source=clf_entry.model_source,
        ))

    return ShipmentListResponse(company_id=company_id, model_source=clf_entry.model_source, shipments=results)


@router.get("/{company_id}/{shipment_id}", response_model=ShipmentRiskOut)
def get_shipment_risk(company_id: int, shipment_id: int, db: Session = Depends(get_db)):
    shipment = (
        db.query(Shipment)
        .filter(Shipment.company_id == company_id, Shipment.id == shipment_id)
        .first()
    )
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found for this company.")

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

    return ShipmentRiskOut(
        shipment_id=shipment.id,
        external_shipment_id=shipment.external_shipment_id,
        product_id=shipment.product_id,
        supplier_id=shipment.supplier_id,
        origin=shipment.origin,
        destination=shipment.destination,
        carrier=shipment.carrier,
        transport_mode=shipment.transport_mode,
        order_date=str(shipment.order_date) if shipment.order_date else None,
        planned_delivery=str(shipment.planned_delivery),
        actual_delivery=str(shipment.actual_delivery) if shipment.actual_delivery else None,
        is_completed=is_completed,
        actual_was_delayed=actual_was_delayed,
        actual_delay_days=actual_delay_days,
        delay_probability=risk["delay_probability"],
        risk_tier=risk["risk_tier"],
        expected_delay_days=risk["expected_delay_days"],
        top_risk_factors=[RiskFactorOut(**f) for f in risk["top_risk_factors"]],
        model_source=clf_entry.model_source,
    )
