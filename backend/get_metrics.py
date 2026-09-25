import json
from app.database import SessionLocal
from app.models import ModelRegistryEntry

db = SessionLocal()
# Get only active models
entries = db.query(ModelRegistryEntry).filter(ModelRegistryEntry.status == 'active').all()

for e in entries:
    metrics = json.loads(e.metrics_json) if e.metrics_json else {}
    selected = metrics.get("selected_model", "N/A")
    comp = metrics.get("comparison", {})
    
    print(f"\n{'='*50}")
    print(f"Model: {e.model_type.upper()} | Source: {e.model_source} | Version: {e.version}")
    print(f"Selected Algorithm: {selected}")
    print(f"{'-'*50}")
    
    if e.model_type == "demand_forecast":
        baseline = comp.get("naive_seasonal_baseline", {})
        actual = comp.get(selected, {})
        print(f"Metric: MAE (Lower is better)")
        print(f"  - Baseline: {baseline.get('mae', 'N/A'):.2f}")
        print(f"  - Actual:   {actual.get('mae', 'N/A'):.2f}")
        print(f"Metric: RMSE (Lower is better)")
        print(f"  - Baseline: {baseline.get('rmse', 'N/A'):.2f}")
        print(f"  - Actual:   {actual.get('rmse', 'N/A'):.2f}")
        
    elif e.model_type == "delay_classifier":
        baseline = comp.get("majority_class_baseline", {})
        actual = comp.get(selected, {})
        if not actual and e.model_source == "dataco_v2_leakage_free":
             # Special case for dataco pre-trained if metrics are structured differently
             print("  - Accuracy:", metrics.get("accuracy", "N/A"))
             print("  - ROC AUC:", metrics.get("roc_auc", "N/A"))
        else:
             print(f"Metric: Accuracy (Higher is better)")
             print(f"  - Baseline: {baseline.get('accuracy', 0)*100:.2f}%")
             print(f"  - Actual:   {actual.get('accuracy', 0)*100:.2f}%")
             print(f"Metric: F1 Score (Higher is better)")
             print(f"  - Baseline: {baseline.get('f1', 0):.3f}")
             print(f"  - Actual:   {actual.get('f1', 0):.3f}")
             print(f"Metric: ROC AUC (Higher is better)")
             print(f"  - Actual:   {actual.get('roc_auc', 'N/A')}")
             
    elif e.model_type == "delay_duration":
        baseline = comp.get("mean_baseline", {})
        actual = comp.get(selected, {})
        print(f"Metric: MAE (Lower is better, measured in days)")
        print(f"  - Baseline: {baseline.get('mae', 'N/A')}")
        print(f"  - Actual:   {actual.get('mae', 'N/A')}")
        print(f"Metric: R2 Score (Higher is better)")
        print(f"  - Baseline: {baseline.get('r2', 'N/A')}")
        print(f"  - Actual:   {actual.get('r2', 'N/A')}")
