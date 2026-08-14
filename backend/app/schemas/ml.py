from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ModelRegistryOut(BaseModel):
    model_config = {"from_attributes": True, "protected_namespaces": ()}

    id: int
    company_id: int | None
    model_type: str
    model_source: str
    version: str
    training_date: datetime
    dataset_size: int | None
    history_days: int | None
    status: str
    metrics: dict[str, Any] | None = None


class BaseModelTrainError(BaseModel):
    model_config = {"protected_namespaces": ()}

    model_type: str
    error: str


class TrainBaseModelsResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    trained: list[ModelRegistryOut]
    errors: list[BaseModelTrainError]


class ModelTrainOutcome(BaseModel):
    model_config = {"protected_namespaces": ()}

    trained_company_specific: bool
    reason: str
    active_model_source: str | None
    registry_entry: ModelRegistryOut | None


class RetrainResponse(BaseModel):
    company_id: int
    demand: ModelTrainOutcome
    shipments: ModelTrainOutcome


class ForecastPoint(BaseModel):
    date: str
    predicted_quantity: float


class ProductForecast(BaseModel):
    model_config = {"protected_namespaces": ()}

    product_id: int
    external_product_id: str
    product_name: str
    last_actual_date: str | None
    last_actual_quantity: float | None
    horizon_days: int
    model_source: str
    forecast: list[ForecastPoint]


class DemandForecastResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    company_id: int
    horizon_days: int
    model_source: str
    model_version: str
    products: list[ProductForecast]


class RiskFactorOut(BaseModel):
    factor: str
    importance: float
    value: float


class ShipmentRiskOut(BaseModel):
    model_config = {"protected_namespaces": ()}

    shipment_id: int
    external_shipment_id: str
    product_id: int
    supplier_id: int | None
    origin: str | None
    destination: str | None
    carrier: str | None
    transport_mode: str | None
    order_date: str | None
    planned_delivery: str
    actual_delivery: str | None
    is_completed: bool
    actual_was_delayed: bool | None       # ground truth, only for completed shipments
    actual_delay_days: float | None
    delay_probability: float
    risk_tier: str
    expected_delay_days: float | None
    top_risk_factors: list[RiskFactorOut]
    model_source: str


class ShipmentListResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    company_id: int
    model_source: str
    shipments: list[ShipmentRiskOut]
