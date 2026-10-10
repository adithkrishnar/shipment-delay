from app.database import SessionLocal
from app.models import Company, Product
from app.services.model_training_service import get_active_demand_model
from app.routes.demand import get_demand_forecast
from app.models.user import User

db = SessionLocal()
company = db.query(Company).filter_by(name="Horizon Electronics").first()
try:
    forecast_resp = get_demand_forecast(company_id=company.id, horizon=7, db=db, current_user=User(is_superuser=True))
    for p in forecast_resp.products:
        print(f"Product: {p.product_name}")
        for f in p.forecast:
            print(f"  {f.date}: {f.predicted_quantity}")
        break
except Exception as e:
    print("Error:", e)
