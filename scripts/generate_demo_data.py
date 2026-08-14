"""
Standalone CLI to (re)generate the demo companies without going through the API.

Usage (from backend/):
    ./venv/bin/python ../scripts/generate_demo_data.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.database import SessionLocal, init_db  # noqa: E402
from app.services.demo_data_generator import generate_demo_companies  # noqa: E402


def main():
    init_db()
    db = SessionLocal()
    try:
        print("Generating demo companies (this replaces any existing demo data)...")
        results = generate_demo_companies(db, reset=True)
        for r in results:
            print(
                f"  - {r['name']}: {r['products']} products, {r['suppliers']} suppliers, "
                f"{r['sales_rows']} sales rows, {r['shipment_rows']} shipments, "
                f"{r['history_days']} days of history"
            )
        print("Done.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
