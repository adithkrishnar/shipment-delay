"""
Interactive Network Map API endpoints.
Provides full global topology:
- Warehouses with live inventory health pins
- Suppliers
- Active Multimodal Shipments with sequenced legs & coordinates
- Inter-warehouse surplus-to-deficit rebalancing transfer links
- Real-time weather at route nodes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from app.database import get_db
from app.auth.deps import get_current_user
from app.models import Company, Warehouse, Supplier, Shipment, Product, InventoryRecord, User
from app.models.shipment_leg import ShipmentLeg
from app.services.weather_service import resolve_coordinates, get_live_weather
from app.services.inventory_intelligence import _latest_inventory, calculate_safety_stock

router = APIRouter(prefix="/network-map", tags=["network-map"])

@router.get("/{company_id}")
def get_network_map_data(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Returns complete geospatial topology for the company:
    1. Warehouse nodes with coordinates and surplus/deficit inventory status.
    2. Supplier nodes with coordinates.
    3. Multimodal shipment routes with atomic legs, mode, coordinates, delays.
    4. Inter-warehouse rebalancing transfer links.
    """
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    # 1. Fetch Warehouses and compute inventory health
    warehouses = db.query(Warehouse).filter(Warehouse.company_id == company_id).all()
    warehouse_nodes = []
    
    # Get latest inventory per product
    latest_inv = _latest_inventory(db, company_id)
    
    warehouse_surpluses = {}
    warehouse_deficits = {}

    for wh in warehouses:
        coords = resolve_coordinates(wh.name)
        # Fetch inventory records at this warehouse
        wh_invs = db.query(InventoryRecord).filter(
            InventoryRecord.company_id == company_id,
            InventoryRecord.warehouse_id == wh.id
        ).all()
        
        total_stock = sum(float(i.inventory_level or 0.0) for i in wh_invs)
        total_safety = sum(float(i.safety_stock or 0.0) for i in wh_invs)
        
        if total_safety > 0 and total_stock < total_safety * 0.7:
            status = "CRITICAL_DEFICIT"
            health_color = "#ef4444" # Red
            warehouse_deficits[wh.id] = {"name": wh.name, "coords": coords, "deficit_qty": round(total_safety - total_stock)}
        elif total_safety > 0 and total_stock > total_safety * 1.5:
            status = "HEALTHY_SURPLUS"
            health_color = "#10b981" # Emerald Green
            warehouse_surpluses[wh.id] = {"name": wh.name, "coords": coords, "surplus_qty": round(total_stock - total_safety)}
        else:
            status = "OPTIMAL"
            health_color = "#3b82f6" # Blue
            
        weather = get_live_weather(coords["lat"], coords["lon"])

        warehouse_nodes.append({
            "id": wh.id,
            "name": wh.name,
            "region": wh.region,
            "lat": coords["lat"],
            "lon": coords["lon"],
            "type": coords.get("type", "warehouse"),
            "country": coords.get("country", ""),
            "total_stock_units": round(total_stock),
            "safety_stock_units": round(total_safety),
            "status": status,
            "health_color": health_color,
            "weather": weather
        })

    # 2. Fetch Suppliers
    suppliers = db.query(Supplier).filter(Supplier.company_id == company_id).all()
    supplier_nodes = []
    for sup in suppliers:
        coords = resolve_coordinates(sup.name)
        supplier_nodes.append({
            "id": sup.id,
            "name": sup.name,
            "lat": coords["lat"],
            "lon": coords["lon"],
            "reliability": sup.reliability,
            "lead_time_days": sup.lead_time_days,
            "type": "supplier",
            "country": coords.get("country", "")
        })

    # 3. Active Shipments & Multimodal Legs
    active_shipments = db.query(Shipment).filter(
        Shipment.company_id == company_id,
        Shipment.actual_delivery.is_(None)
    ).limit(35).all()

    shipment_routes = []
    for shp in active_shipments:
        origin_coords = resolve_coordinates(shp.origin)
        dest_coords = resolve_coordinates(shp.destination)
        
        legs = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == shp.id).order_by(ShipmentLeg.sequence).all()
        leg_data = []
        
        for leg in legs:
            l_origin = resolve_coordinates(leg.origin)
            l_dest = resolve_coordinates(leg.destination)
            
            leg_data.append({
                "leg_id": leg.id,
                "sequence": leg.sequence,
                "mode": leg.mode,
                "origin_name": leg.origin,
                "origin_lat": l_origin["lat"],
                "origin_lon": l_origin["lon"],
                "destination_name": leg.destination,
                "dest_lat": l_dest["lat"],
                "dest_lon": l_dest["lon"],
                "distance_km": leg.distance_km,
                "delay_hours": leg.delay_hours,
                "status": leg.status,
                "is_delayed": leg.delay_hours > 0 or leg.status == "DELAYED"
            })
            
        shipment_routes.append({
            "id": shp.id,
            "reference": shp.external_shipment_id,
            "primary_mode": (shp.transport_mode or "ROAD").upper(),
            "origin": shp.origin,
            "destination": shp.destination,
            "origin_coords": origin_coords,
            "dest_coords": dest_coords,
            "status": shp.assignment_status,
            "planned_delivery": str(shp.planned_delivery),
            "current_eta": str(shp.current_eta or shp.planned_delivery),
            "legs": leg_data
        })

    # 4. Computed Inter-Warehouse Rebalancing Transfer Links (Network Self-Healing)
    rebalancing_links = []
    # Pair surplus warehouses with deficit warehouses
    for s_id, s_info in warehouse_surpluses.items():
        for d_id, d_info in warehouse_deficits.items():
            if s_id != d_id and s_info["surplus_qty"] > 20 and d_info["deficit_qty"] > 10:
                transfer_qty = min(s_info["surplus_qty"], d_info["deficit_qty"])
                rebalancing_links.append({
                    "link_id": f"REBALANCE-{s_id}-{d_id}",
                    "source_warehouse_id": s_id,
                    "source_name": s_info["name"],
                    "source_lat": s_info["coords"]["lat"],
                    "source_lon": s_info["coords"]["lon"],
                    "dest_warehouse_id": d_id,
                    "dest_name": d_info["name"],
                    "dest_lat": d_info["coords"]["lat"],
                    "dest_lon": d_info["coords"]["lon"],
                    "transfer_units": transfer_qty,
                    "rationale": f"Move {transfer_qty} units buffer stock from {s_info['name']} to eliminate critical shortage at {d_info['name']}.",
                    "estimated_savings_usd": transfer_qty * 105.0
                })

    return {
        "company_id": company.id,
        "company_name": company.name,
        "warehouses": warehouse_nodes,
        "suppliers": supplier_nodes,
        "shipment_routes": shipment_routes,
        "rebalancing_links": rebalancing_links
    }

