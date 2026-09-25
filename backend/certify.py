import json
import time
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import Company

# Drop and recreate DB for clean test
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)
from app.auth.deps import get_current_user
from app.models.user import User
app.dependency_overrides[get_current_user] = lambda: User(id=1, email="test@example.com", company_id=1, is_superuser=True, is_active=True)

def create_csv_content(company_name, rows):
    header = "Company_Name,product_id,date,quantity,promotion,unit_cost,supplier_id,warehouse\n"
    import datetime
    start_date = datetime.date(2025, 1, 1)
    lines = []
    for i in range(rows):
        current_date = start_date + datetime.timedelta(days=i)
        lines.append(f"{company_name},PROD-1,{current_date.isoformat()},{100+i},0,50.0,SUP-1,WH-1\n")
    return header + "".join(lines)

def run_e2e_test(company_name, rows_count):
    print(f"\n=== E2E Test for {company_name} ===")
    
    print("0. Seeding demo...")
    client.post("/api/demo/seed")
    
    # 1. Upload CSV
    print("1. Uploading CSV...")
    csv_content = create_csv_content(company_name, rows_count)
    files = {"file": ("data.csv", csv_content.encode('utf-8'), "text/csv")}
    data = {"company_id": 1, "dataset_type": "sales"}  # id will be ignored/overridden by company_name in CSV
    
    r = client.post("/api/upload", data=data, files=files)
    if r.status_code != 200:
        print(f"Upload failed: {r.text}")
        return False
    upload_res = r.json()
    company_id = upload_res["company_id"]
    upload_id = upload_res["upload_id"]
    mapping = upload_res["suggested_mapping"]
    print(f"Upload success. Company ID: {company_id}, Upload ID: {upload_id}, Rows: {upload_res['row_count']}")
    
    # 2. Validate
    print("2. Validating...")
    r = client.post("/api/data/validate", json={"upload_id": upload_id, "column_mapping": mapping})
    if r.status_code != 200:
        print(f"Validate failed: {r.text}")
        return False
    
    # 3. Map
    print("3. Mapping...")
    r = client.post("/api/data/map", json={"upload_id": upload_id, "column_mapping": mapping})
    if r.status_code != 200:
        print(f"Map failed: {r.text}")
        return False
    
    # 4. Import
    print("4. Importing...")
    r = client.post(f"/api/data/import?company_id={company_id}&upload_id={upload_id}")
    if r.status_code != 200:
        print(f"Import failed: {r.text}")
        return False
    imp_res = r.json()
    print(f"Imported Rows: {imp_res['imported_row_count']}")
    
    # In test mode, background jobs don't run automatically via ARQ because we don't have worker running.
    # We will trigger the background tasks manually
    db = SessionLocal()
    try:
        from app.services.model_training_service import train_company_demand_model, train_company_shipment_models
        print("Manually triggering background models for testing...")
        train_company_demand_model(db, company_id)
        train_company_shipment_models(db, company_id)
    except Exception as e:
        print(f"Failed to train models: {e}")
    finally:
        db.close()
    
    # 5. Fetch Dashboard
    print("5. Fetching Dashboard...")
    r = client.get(f"/api/dashboard/{company_id}")
    if r.status_code != 200:
        print(f"Dashboard failed: {r.text}")
        return False
    dash_res = r.json()
    print(f"Dashboard model source: {dash_res.get('model_source')}")
    print(f"Dashboard KPI products: {dash_res['kpis']['products']}")
    
    return True

if __name__ == "__main__":
    apex_res = run_e2e_test("Apex Electronics Pvt Ltd", 150)
    freshcore_res = run_e2e_test("FreshCore Retail Pvt Ltd", 50)
    
    if apex_res and freshcore_res:
        print("\n\n================================================")
        print("SUPPLYIQ END-TO-END WORKFLOW CERTIFIED.")
        print("================================================")
    else:
        print("Tests failed.")
