"""
SupplyIQ - Benchmark Corridor Reset Script for Live Demonstrations
Resets:
- Benchmark Corridor: SH-BLR-2026-0001 (IN_TRANSIT, Leg 1 COMPLETED, Leg 2 IN_TRANSIT, Leg 3 SCHEDULED)
- Chennai Central DC Stock: exactly 85.0 units
- Clears disruption reports, active alerts, and action approvals for SH-BLR-2026-0001
"""
import sys
import os
import subprocess
from pathlib import Path

# Auto-detect and switch to backend virtual environment if running in global python
try:
    import sqlalchemy
except ImportError:
    candidates = [
        Path(__file__).resolve().parent / "venv" / "Scripts" / "python.exe",
        Path(__file__).resolve().parent.parent / "backend" / "venv" / "Scripts" / "python.exe"
    ]
    venv_py = next((p for p in candidates if p.exists()), None)
    if venv_py:
        res = subprocess.run([str(venv_py), __file__] + sys.argv[1:])
        sys.exit(res.returncode)
    else:
        print("ERROR: SQLAlchemy not found and backend venv not found.")
        sys.exit(1)

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.database import SessionLocal
from app.services.demo_seeder import reset_benchmark_corridor

def main():
    print("Resetting SupplyIQ benchmark corridor for live demonstration...")
    db = SessionLocal()
    try:
        result = reset_benchmark_corridor(db)
        print("\n" + "="*65)
        print("  DEMO RESET SUCCESSFUL!")
        print("="*65)
        print(f"  Shipment ID       : {result.get('shipment_id')}")
        print(f"  Corridor          : {result.get('corridor')}")
        print(f"  Initial Stock     : {result.get('initial_inventory')} units (Chennai Central DC)")
        print(f"  Shipment Quantity : {result.get('shipment_quantity')} units")
        print(f"  Daily Demand      : {result.get('daily_demand')} units/day")
        print(f"  Currency          : {result.get('currency')}")
        print("="*65)
        print("  Ready for evaluator demonstration across 3 laptops/tabs.\n")
    except Exception as e:
        print(f"ERROR: Failed to reset benchmark corridor: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
