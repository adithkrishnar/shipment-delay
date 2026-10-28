from app.database import SessionLocal
from app.services.replenishment_service import compute_replenishment_plan

def main():
    db = SessionLocal()
    plan = compute_replenishment_plan(db, 5)
    print(f"Summary: {plan['summary']}")
    print("\nAll 8 SKUs Replenishment Policy Details:")
    for r in plan['recommendations']:
        print(
            f"SKU: {r['name']} ({r['sku']})\n"
            f"  On-Hand: {r['on_hand']}, On-Order: {r['on_order']}\n"
            f"  Daily Demand: {r['daily_demand']} u/d, Lead Time: {r['lead_time_days']} days\n"
            f"  Safety Stock: {r['safety_stock']} units, Reorder Point (ROP): {r['reorder_point']} units\n"
            f"  Approaching Threshold (ROP + 2*d): {r['reorder_point'] + (r['daily_demand']*2):.1f} units\n"
            f"  Needs Reorder: {r['needs_reorder']}, Urgency: {r['urgency']}\n"
            f"  Suggested Order Qty: {r['suggested_order_qty']} units\n"
            f"  Unit Cost: ${r['unit_cost']:.2f} (Explicit: {r['has_explicit_cost']})\n"
            f"  Estimated Order Cost: ${r['estimated_order_cost']:,.2f}\n"
        )

if __name__ == "__main__":
    main()
