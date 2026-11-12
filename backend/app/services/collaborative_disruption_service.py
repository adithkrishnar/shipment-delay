from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import Company, Shipment, Product, Supplier, User, Sale, InventoryRecord, Warehouse
from app.models.shipment_leg import ShipmentLeg, DisruptionReport
from app.services.inventory_intelligence import analyze_product

# Standard realistic transit profiles for multi-leg generation
DEFAULT_MULTIMODAL_TEMPLATES = {
    "AIR": [
        {"seq": 1, "mode": "ROAD", "name": "First-Mile Drayage", "carrier": "Express Drayage Co", "pct_dist": 0.05, "speed_kmh": 40.0, "buffer_hrs": 3.0},
        {"seq": 2, "mode": "AIR", "name": "Air Cargo Linehaul", "carrier": "SkyFreight Global", "pct_dist": 0.90, "speed_kmh": 650.0, "buffer_hrs": 4.0},
        {"seq": 3, "mode": "ROAD", "name": "Last-Mile Distribution", "carrier": "Regional Logistics Fleet", "pct_dist": 0.05, "speed_kmh": 35.0, "buffer_hrs": 0.0},
    ],
    "SEA": [
        {"seq": 1, "mode": "ROAD", "name": "Inland Port Drayage", "carrier": "Container Drayage LLC", "pct_dist": 0.08, "speed_kmh": 45.0, "buffer_hrs": 24.0},
        {"seq": 2, "mode": "SEA", "name": "Ocean Container Transit", "carrier": "Oceanic Line Corp", "pct_dist": 0.84, "speed_kmh": 35.0, "buffer_hrs": 48.0},
        {"seq": 3, "mode": "ROAD", "name": "Depot to Warehouse Delivery", "carrier": "Inland Haulage", "pct_dist": 0.08, "speed_kmh": 40.0, "buffer_hrs": 0.0},
    ],
    "RAIL": [
        {"seq": 1, "mode": "ROAD", "name": "Factory to Railhead", "carrier": "Intermodal Cartage", "pct_dist": 0.10, "speed_kmh": 40.0, "buffer_hrs": 12.0},
        {"seq": 2, "mode": "RAIL", "name": "Intermodal Freight Corridor", "carrier": "National Rail Freight", "pct_dist": 0.80, "speed_kmh": 60.0, "buffer_hrs": 18.0},
        {"seq": 3, "mode": "ROAD", "name": "ICD to Final Plant", "carrier": "Local Transport Fleet", "pct_dist": 0.10, "speed_kmh": 35.0, "buffer_hrs": 0.0},
    ],
    "ROAD": [
        {"seq": 1, "mode": "ROAD", "name": "First-Mile Pickup & Consolidation", "carrier": "Apex Logistics Express", "pct_dist": 0.20, "speed_kmh": 45.0, "buffer_hrs": 4.0},
        {"seq": 2, "mode": "ROAD", "name": "Long-Haul Highway Corridor", "carrier": "Blue Dart Express", "pct_dist": 0.65, "speed_kmh": 60.0, "buffer_hrs": 6.0},
        {"seq": 3, "mode": "ROAD", "name": "Last-Mile Delivery to Plant", "carrier": "City Delivery Couriers", "pct_dist": 0.15, "speed_kmh": 30.0, "buffer_hrs": 0.0},
    ]
}

def ensure_shipment_legs(db: Session, shipment: Shipment) -> List[ShipmentLeg]:
    """
    Ensures that a shipment has persisted multi-modal legs.
    If none exist yet, automatically provisions realistic multimodal legs
    based on origin, destination, distance, and primary transport mode.
    """
    existing_legs = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == shipment.id).order_by(ShipmentLeg.sequence).all()
    if existing_legs:
        return existing_legs

    # Generate legs based on transport_mode template
    mode_key = (shipment.transport_mode or "ROAD").upper()
    if mode_key not in DEFAULT_MULTIMODAL_TEMPLATES:
        mode_key = "ROAD"
    template = DEFAULT_MULTIMODAL_TEMPLATES[mode_key]

    total_dist = float(shipment.distance_km or 850.0)
    origin_name = shipment.origin or "Origin Facility"
    dest_name = shipment.destination or "Destination Hub"
    order_dt = datetime.combine(shipment.order_date, datetime.min.time()) if shipment.order_date else (datetime.utcnow() - timedelta(days=2))

    current_start = order_dt
    created_legs = []

    carrier_name = shipment.carrier or "National Logistics"

    for step in template:
        leg_dist = max(10.0, round(total_dist * step["pct_dist"], 1))
        # duration = dist / speed
        duration_hrs = max(1.5, round(leg_dist / step["speed_kmh"], 1))
        
        # Origin / Dest names
        if step["seq"] == 1:
            l_origin = origin_name
            l_dest = f"Intermediate Terminal ({step['name']})"
        elif step["seq"] == len(template):
            l_origin = f"Terminal Hub ({step['name']})"
            l_dest = dest_name
        else:
            l_origin = f"Origin Hub ({step['mode']})"
            l_dest = f"Destination Hub ({step['mode']})"

        leg_carrier = step["carrier"]
        if step["seq"] == 2 and shipment.carrier:
            leg_carrier = shipment.carrier

        sched_dep = current_start
        sched_arr = sched_dep + timedelta(hours=duration_hrs)
        gate_cutoff = sched_arr + timedelta(hours=step["buffer_hrs"]) if step["buffer_hrs"] > 0 else None

        leg = ShipmentLeg(
            shipment_id=shipment.id,
            sequence=step["seq"],
            mode=step["mode"],
            origin=l_origin,
            destination=l_dest,
            carrier_name=leg_carrier,
            distance_km=leg_dist,
            expected_duration_hrs=duration_hrs,
            delay_hours=0.0,
            status="IN_TRANSIT" if step["seq"] == 1 else "SCHEDULED",
            scheduled_departure=sched_dep,
            scheduled_arrival=sched_arr,
            next_leg_cutoff=gate_cutoff,
            missed_connection_dwell_hrs=0.0,
        )
        db.add(leg)
        created_legs.append(leg)

        # advance time including transfer buffer
        current_start = sched_arr + timedelta(hours=step["buffer_hrs"])

    db.commit()
    for l in created_legs:
        db.refresh(l)
    return created_legs


def simulate_downstream_impact(
    db: Session,
    shipment: Shipment,
    leg_id: int,
    reported_delay_hrs: float,
    reason: str,
    notes: Optional[str] = None,
    reporter_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Processes a disruption reported by a carrier on a specific leg.
    1. Updates the target leg with reported delay.
    2. Checks for missed connections (e.g., missed vessel cut-off, train slot departure).
    3. Calculates total compounding delay across all remaining downstream legs.
    4. Triggers the inventory intelligence simulation for the product.
    5. Calculates unmet demand units, financial loss ($), and prescribes 3 mitigations.
    6. Persists DisruptionReport and returns full telemetry to UI.
    """
    legs = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == shipment.id).order_by(ShipmentLeg.sequence).all()
    if not legs:
        legs = ensure_shipment_legs(db, shipment)

    target_leg = next((l for l in legs if l.id == leg_id), None)
    if not target_leg:
        raise ValueError(f"Leg {leg_id} does not belong to shipment {shipment.id}")

    # Update target leg
    target_leg.delay_hours = max(0.0, float(reported_delay_hrs))
    target_leg.status = "DELAYED" if target_leg.delay_hours > 0 else "IN_TRANSIT"

    # Compound Delay & Missed Connection calculation
    total_compounding_delay_hrs = 0.0
    missed_connection_notes = []

    for l in legs:
        total_compounding_delay_hrs += l.delay_hours
        
        # If this leg was delayed, check if it violated next_leg_cutoff
        if l.delay_hours > 0 and l.next_leg_cutoff and l.scheduled_arrival:
            actual_arrival = l.scheduled_arrival + timedelta(hours=l.delay_hours)
            if actual_arrival > l.next_leg_cutoff:
                # Missed gate cutoff! Add intermodal schedule cycle delay
                # Ocean: +72-120 hrs (next vessel), Rail: +24-48 hrs, Road: +12 hrs
                cycle_penalty = 72.0 if l.mode == "SEA" else (24.0 if l.mode == "RAIL" else 12.0)
                l.missed_connection_dwell_hrs = cycle_penalty
                total_compounding_delay_hrs += cycle_penalty
                missed_connection_notes.append(
                    f"Leg {l.sequence} ({l.mode}) missed scheduled cutoff by {(actual_arrival - l.next_leg_cutoff).total_seconds()/3600:.1f} hrs. "
                    f"Compounded waiting penalty for next departure slot: +{cycle_penalty:.0f} hrs."
                )

    total_delay_days = round(total_compounding_delay_hrs / 24.0, 2)

    # 4. Run Inventory Intelligence Simulation
    # Check if this shipment targets a specific destination warehouse
    from app.models import Warehouse, InventoryRecord
    dest_wh = db.query(Warehouse).filter(Warehouse.company_id == shipment.company_id, Warehouse.name == shipment.destination).first() if shipment.destination else None
    
    # Check if inventory and sales data exist for this product/company
    has_inventory_data = bool(db.query(InventoryRecord).filter(
        InventoryRecord.company_id == shipment.company_id,
        InventoryRecord.product_id == shipment.product_id
    ).first())
    has_sales_data = bool(db.query(Sale).filter(
        Sale.company_id == shipment.company_id,
        Sale.product_id == shipment.product_id
    ).first())

    inventory_assessment_available = has_inventory_data and has_sales_data

    if inventory_assessment_available:
        inv_analysis = analyze_product(db, shipment.company_id, shipment.product_id, delay_days=total_delay_days)
    else:
        inv_analysis = {
            "inventory_level": None,
            "daily_demand": None,
            "safety_stock": None,
            "stockout_risk": "DATA_UNAVAILABLE",
            "expected_shortage": None
        }

    product = db.query(Product).filter(Product.id == shipment.product_id).first()
    unit_price = float(product.unit_price if (product and product.unit_price) else 85.0)

    # Check warehouse-level stock if destination warehouse is known
    wh_stock = None
    if dest_wh and inventory_assessment_available:
        wh_rec = db.query(InventoryRecord).filter(
            InventoryRecord.company_id == shipment.company_id,
            InventoryRecord.product_id == shipment.product_id,
            InventoryRecord.warehouse_id == dest_wh.id
        ).order_by(InventoryRecord.date.desc()).first()
        if wh_rec:
            wh_stock = float(wh_rec.inventory_level or 0.0)

    if inventory_assessment_available:
        daily_rate = float(inv_analysis.get("daily_demand") or 10.0)
        daily_facility_demand = round(daily_rate / 5.0, 2) if dest_wh else daily_rate

        if wh_stock is not None:
            local_lead = float(inv_analysis.get("effective_lead_time_days") or 14.0)
            facility_needed = daily_facility_demand * local_lead
            expected_shortage_units = round(max(0.0, facility_needed - wh_stock), 1)
            stockout_predicted = 1 if (wh_stock < facility_needed or wh_stock <= 25.0) else 0
        else:
            expected_shortage_units = float(inv_analysis.get("expected_shortage") or 0.0)
            stockout_predicted = 1 if inv_analysis.get("stockout_risk") in ["HIGH", "CRITICAL"] or expected_shortage_units > 0 else 0

        revenue_loss = expected_shortage_units * unit_price
        sla_penalty = 1500.0 if expected_shortage_units > 0 else 0.0
        total_cost_loss = round(revenue_loss + sla_penalty, 2)
    else:
        # DATA LIMITATION HONORED: Do NOT invent stockouts or loss without inventory/sales records
        daily_facility_demand = None
        expected_shortage_units = None
        stockout_predicted = 0
        revenue_loss = 0.0
        sla_penalty = 0.0
        total_cost_loss = 0.0

    # 5. Formulate Prescriptive AI Mitigations
    mitigations = []
    if not inventory_assessment_available:
        mitigations.append({
            "option_id": "INSUFFICIENT_INVENTORY_DATA",
            "title": "Insufficient Inventory Baseline Data",
            "description": "Historical sales demand or warehouse inventory records are not yet linked to this SKU. Transit delay is logged without simulated stockout.",
            "estimated_cost": 0.0,
            "net_savings": 0.0,
            "priority": "INFO",
            "why_best": "SUPPLYIQ preserves data integrity by withholding stockout predictions until verified warehouse stock records are provided."
        })
    elif stockout_predicted:
        mitigations.append({
            "option_id": "INTER_HUB_TRANSFER",
            "title": "Emergency Inter-Warehouse Stock Transfer",
            "description": f"Transfer {min(int(expected_shortage_units) + 10, int(wh_stock if wh_stock else 100))} units from neighboring regional DC with surplus stock.",
            "estimated_cost": 450.0,
            "net_savings": round(max(0.0, total_cost_loss - 450.0), 2),
            "priority": "RECOMMENDED",
            "why_best": f"Immediate execution (transit time < 12 hrs). Solves the {expected_shortage_units:.0f}-unit shortage at destination DC without buying new stock, delivering a net ROI saving of ${max(0.0, total_cost_loss - 450.0):,.2f}."
        })
        mitigations.append({
            "option_id": "EXPEDITE_FINAL_LEG",
            "title": "Expedite Downstream Leg via Dedicated Courier / Hot-Shot Van",
            "description": f"Bypass remaining standard transit legs with an expedited direct charter. Cuts lead time by {min(total_delay_days, 3.0):.1f} days.",
            "estimated_cost": round(min(1200.0, total_cost_loss * 0.35), 2),
            "net_savings": round(max(0.0, total_cost_loss - min(1200.0, total_cost_loss * 0.35)), 2),
            "priority": "HIGH",
            "why_best": "Recovers 2-3 days directly from the transportation schedule, bringing the cargo to destination before the existing safety buffer is fully depleted."
        })
        mitigations.append({
            "option_id": "RESCHEDULE_PRODUCTION",
            "title": "Reschedule Manufacturing / Client Order Allocation",
            "description": "Shift assembly schedule to alternative product variants and notify Tier-2 customers of a 48-hr delay buffer.",
            "estimated_cost": 0.0,
            "net_savings": 0.0,
            "priority": "CONTINGENCY",
            "why_best": "Zero upfront capital expense. Prevents customer contract breach by proactively agreeing to an adjusted delivery window."
        })
    else:
        mitigations.append({
            "option_id": "MONITOR_BUFFER",
            "title": "Buffer Stock Sufficient — Active Monitoring",
            "description": f"Existing on-hand safety stock ({inv_analysis.get('safety_stock', 0)} units) absorbs this {total_delay_days}-day delay without stockout.",
            "estimated_cost": 0.0,
            "net_savings": 0.0,
            "priority": "INFO",
            "why_best": "Current on-hand inventory coverage is healthy enough to absorb this transit disruption without risking order fulfillment or incurring expediting fees."
        })

    import json
    details_payload = {
        "destination_warehouse": dest_wh.name if dest_wh else shipment.destination,
        "facility_stock": wh_stock,
        "product_name": product.name if product else f"Product #{shipment.product_id}",
        "unit_price": unit_price,
        "revenue_loss": revenue_loss,
        "sla_penalty": sla_penalty,
        "daily_demand": daily_facility_demand,
        "missed_connections": missed_connection_notes,
        "mitigations": mitigations
    }

    # Save Disruption Report record
    report = DisruptionReport(
        leg_id=target_leg.id,
        shipment_id=shipment.id,
        reporter_id=reporter_id,
        delay_hours=reported_delay_hrs,
        disruption_reason=reason,
        notes=notes,
        total_impact_delay_days=total_delay_days,
        stockout_predicted=stockout_predicted,
        unmet_demand_units=expected_shortage_units,
        estimated_cost_loss=total_cost_loss,
        prescribed_mitigation=mitigations[0]["title"] if mitigations else "No action required",
        impact_details_json=json.dumps(details_payload)
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {
        "report_id": report.id,
        "shipment_id": shipment.id,
        "external_shipment_id": shipment.external_shipment_id,
        "product_name": product.name if product else f"Product #{shipment.product_id}",
        "reported_leg": {
            "id": target_leg.id,
            "sequence": target_leg.sequence,
            "mode": target_leg.mode,
            "carrier_name": target_leg.carrier_name,
            "delay_hours": target_leg.delay_hours,
            "status": target_leg.status
        },
        "all_legs": [
            {
                "id": l.id,
                "sequence": l.sequence,
                "mode": l.mode,
                "origin": l.origin,
                "destination": l.destination,
                "carrier_name": l.carrier_name,
                "expected_duration_hrs": l.expected_duration_hrs,
                "delay_hours": l.delay_hours,
                "missed_connection_dwell_hrs": l.missed_connection_dwell_hrs,
                "status": l.status
            }
            for l in legs
        ],
        "missed_connection_alerts": missed_connection_notes,
        "total_delay_hours": total_compounding_delay_hrs,
        "total_delay_days": total_delay_days,
        "inventory_simulation": {
            "current_stock": inv_analysis.get("inventory_level", 0.0),
            "daily_demand": inv_analysis.get("daily_demand", 0.0),
            "safety_stock": inv_analysis.get("safety_stock", 0.0),
            "coverage_days": inv_analysis.get("inventory_coverage_days"),
            "stockout_risk": inv_analysis.get("stockout_risk"),
            "expected_shortage_units": expected_shortage_units,
            "stockout_predicted": bool(stockout_predicted)
        },
        "financial_impact": {
            "unit_price": unit_price,
            "revenue_loss": revenue_loss,
            "sla_penalty": sla_penalty,
            "total_cost_loss": total_cost_loss
        },
        "prescriptive_mitigations": mitigations
    }

