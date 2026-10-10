from app.database import SessionLocal
from app.models import Company, Product, Sale
from app.services.model_training_service import get_active_demand_model
from app.ml.demand_forecasting import forecast_product_demand
import pandas as pd

db = SessionLocal()
company = db.query(Company).filter_by(name="Horizon Electronics").first()
product = db.query(Product).filter_by(company_id=company.id).first()

print(f"Testing forecast for product {product.id} - {product.name}")

trained, model_entry = get_active_demand_model(db, company.id)

sales = db.query(Sale.date, Sale.quantity, Sale.promotion).filter(Sale.company_id == company.id, Sale.product_id == product.id).order_by(Sale.date.asc()).all()

history_df = pd.DataFrame(sales, columns=['date', 'quantity', 'promotion'])
history_df['product_id'] = product.id

print("Recent actuals:")
print(history_df.tail(5))

print(f"\nModel features: {trained.feature_columns}")

forecast_df = forecast_product_demand(trained, history_df, horizon_days=7)

print("\nForecast:")
print(forecast_df)
