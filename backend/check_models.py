import json
from app.database import SessionLocal
from app.models import ModelRegistryEntry

db = SessionLocal()
entries = db.query(ModelRegistryEntry).all()

for e in entries:
    metrics = json.loads(e.metrics_json) if e.metrics_json else {}
    selected = metrics.get("selected_model", "N/A")
    print(f"Type: {e.model_type:<18} | Source: {e.model_source:<16} | Version: {e.version:<4} | Status: {e.status:<8} | Selected Model: {selected}")
