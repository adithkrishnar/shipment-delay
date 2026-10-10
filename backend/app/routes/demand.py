from app.auth.deps import get_current_user
from app.models.user import User
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.ml.demand_forecasting import forecast_product_demand
from app.models import Company, Product, Sale
from app.schemas.ml import DemandForecastResponse, ForecastPoint, ProductForecast
from app.services.model_training_service import get_active_demand_model
from app.utils.logging_config import get_logger
router = APIRouter(prefix='/api/demand', tags=['demand'])
logger = get_logger(__name__)
ALLOWED_HORIZONS = (7, 30, 90)
MIN_HISTORY_DAYS_FOR_FORECAST = 20

@router.get('/forecast/{company_id}', response_model=DemandForecastResponse)
def get_demand_forecast(company_id: int, product_id: int | None=Query(None, description='Limit to one product (internal id). Omit for all products.'), horizon: int=Query(7, description='Forecast horizon in days: 7, 30, or 90.'), db: Session=Depends(get_db), *, current_user: User=Depends(get_current_user)):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(403, "Not authorized to access this company's data")
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail='Company not found.')
    if horizon not in ALLOWED_HORIZONS:
        raise HTTPException(status_code=400, detail=f'horizon must be one of {ALLOWED_HORIZONS}')
    try:
        trained, model_entry = get_active_demand_model(db, company_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    products_query = db.query(Product).filter(Product.company_id == company_id)
    if product_id is not None:
        products_query = products_query.filter(Product.id == product_id)
    products = products_query.all()
    if not products:
        raise HTTPException(status_code=404, detail='No matching product(s) found for this company.')
    product_forecasts: list[ProductForecast] = []
    for product in products:
        sales = db.query(Sale.date, Sale.quantity, Sale.promotion).filter(Sale.company_id == company_id, Sale.product_id == product.id).order_by(Sale.date.asc()).all()
        if len(sales) < MIN_HISTORY_DAYS_FOR_FORECAST:
            logger.warning('Skipping product_id=%s: only %s sales rows, need >= %s', product.id, len(sales), MIN_HISTORY_DAYS_FOR_FORECAST)
            continue
        history_df = pd.DataFrame(sales, columns=['date', 'quantity', 'promotion'])
        history_df['product_id'] = product.id
        forecast_df = forecast_product_demand(trained, history_df, horizon_days=horizon)
        product_forecasts.append(ProductForecast(product_id=product.id, external_product_id=product.external_product_id, product_name=product.name, last_actual_date=str(history_df['date'].iloc[-1]), last_actual_quantity=float(history_df['quantity'].iloc[-1]), horizon_days=horizon, model_source=model_entry.model_source, forecast=[ForecastPoint(**row) for row in forecast_df.to_dict(orient='records')]))
    # Calculate Historical Metrics
    all_sales = db.query(Sale).join(Product).filter(Sale.company_id == company_id).all()
    historical_metrics = {}
    if all_sales:
        df_all = pd.DataFrame([{"date": s.date, "quantity": s.quantity, "product_id": s.product_id, "product_name": s.product.name, "category": s.product.category} for s in all_sales])
        df_all["date"] = pd.to_datetime(df_all["date"])
        
        # Demand Trend over time (monthly)
        trend = df_all.groupby(df_all["date"].dt.to_period("M"))["quantity"].sum().reset_index()
        historical_metrics["trend"] = [{"date": str(row["date"]), "quantity": int(row["quantity"])} for _, row in trend.iterrows()]
        
        # Top 10 products
        top_products = df_all.groupby("product_name")["quantity"].sum().reset_index().sort_values("quantity", ascending=False).head(10)
        historical_metrics["top_products"] = [{"name": row["product_name"], "volume": int(row["quantity"])} for _, row in top_products.iterrows()]
        
        # Category breakdown
        cats = df_all.groupby("category")["quantity"].sum().reset_index()
        historical_metrics["categories"] = [{"name": row["category"], "value": int(row["quantity"])} for _, row in cats.iterrows()]
    
    if not product_forecasts:
        raise HTTPException(status_code=400, detail='No product had enough sales history to forecast. Upload more sales data first.')
    return DemandForecastResponse(company_id=company_id, horizon_days=horizon, model_source=model_entry.model_source, model_version=model_entry.version, products=product_forecasts, historical_metrics=historical_metrics)