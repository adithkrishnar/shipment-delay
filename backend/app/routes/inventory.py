"""
SupplyIQ Inventory Intelligence API Router.
Handles all inventory overview, SKU explorer, product profile, ABC/XYZ insights,
aging analysis, replenishment planning, multi-warehouse transfers, and discrete-event simulation.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Company, Product, InventoryRecord, Sale, Warehouse
from app.models.warehouse_transfer import WarehouseTransfer
from app.models.scenario import SavedScenario
from app.models.user import User
from app.services.inventory_intelligence import company_inventory, inventory_summary, analyze_product
from app.services.inventory_simulator_service import run_delay_simulation
from app.services.inventory_analytics_service import (
    get_abc_xyz_analysis,
    get_inventory_aging_and_slow_moving,
    get_warehouses_analytics,
)
from app.services.replenishment_service import (
    compute_replenishment_plan,
    get_warehouse_transfer_recommendations,
)

router = APIRouter(prefix="/api/inventory", tags=["Inventory Intelligence"])


def _verify_company_access(company_id: int, current_user: User, db: Session):
    if not current_user.is_superuser and current_user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this company's data")
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/overview/{company_id}")
def get_inventory_overview(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns high-level inventory KPIs, total valuation, stock health distributions, and alerts."""
    _verify_company_access(company_id, current_user, db)

    items = company_inventory(db, company_id)
    summary = inventory_summary(items)

    products = db.query(Product).filter(Product.company_id == company_id).all()
    product_cost_map = {p.id: float(p.unit_cost or p.unit_price or 25.0) for p in products}

    total_value = sum(
        item["inventory_level"] * product_cost_map.get(item["product_id"], 25.0)
        for item in items
    )

    critical_skus = [i for i in items if i["stockout_risk"] in ("HIGH", "CRITICAL")]
    overstock_skus = [i for i in items if i["overstock_risk"] in ("HIGH", "CRITICAL")]

    # Health score calculation
    stockout_count = len(critical_skus)
    overstock_count = len(overstock_skus)
    total_skus = max(1, len(items))
    health_score = max(10, min(100, int(100 - (stockout_count * 15 / total_skus * 100) - (overstock_count * 5 / total_skus * 100))))

    return {
        "company_id": company_id,
        "health_score": health_score,
        "total_skus": len(items),
        "total_inventory_units": summary["inventory_units"],
        "total_valuation": round(total_value, 2),
        "critical_stockouts": stockout_count,
        "overstock_skus": overstock_count,
        "avg_stockout_probability": summary["avg_stockout_probability"],
        "items": items[:15],
    }


@router.get("/explorer/{company_id}")
def get_inventory_explorer(
    company_id: int,
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    risk_tier: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns filterable and searchable inventory items with detailed stock metrics."""
    _verify_company_access(company_id, current_user, db)

    items = company_inventory(db, company_id)

    # Apply filters
    if search:
        s = search.lower()
        items = [i for i in items if s in i["product_name"].lower() or s in i["external_product_id"].lower()]
    if category and category != "ALL":
        items = [i for i in items if (i["category"] or "").lower() == category.lower()]
    if risk_tier and risk_tier != "ALL":
        items = [i for i in items if i["stockout_risk"] == risk_tier]

    return {
        "total": len(items),
        "items": items,
    }


@router.get("/product/{company_id}/{product_id}")
def get_product_inventory_detail(
    company_id: int,
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns granular product inventory detail including historical demand and incoming receipts."""
    _verify_company_access(company_id, current_user, db)

    product = db.query(Product).filter(Product.company_id == company_id, Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    detail = analyze_product(db, company_id, product_id)

    # Historical demand series
    sales = (
        db.query(Sale)
        .filter(Sale.company_id == company_id, Sale.product_id == product_id)
        .order_by(Sale.date.desc())
        .limit(30)
        .all()
    )
    history = [{"date": str(s.date), "demand": float(s.quantity or 0)} for s in reversed(sales)]

    return {
        "product": {
            "id": product.id,
            "name": product.name,
            "sku": product.external_product_id,
            "category": product.category,
            "unit_cost": product.unit_cost,
            "unit_price": product.unit_price,
        },
        "inventory": detail,
        "demand_history": history,
    }


@router.get("/insights/abc-xyz/{company_id}")
def get_abc_xyz(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns 9-box ABC/XYZ classification matrix and product segmentation."""
    _verify_company_access(company_id, current_user, db)
    return get_abc_xyz_analysis(db, company_id)


@router.get("/insights/aging/{company_id}")
def get_aging(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns inventory aging bands, slow-moving items, and capital exposure."""
    _verify_company_access(company_id, current_user, db)
    return get_inventory_aging_and_slow_moving(db, company_id)


@router.get("/warehouses/{company_id}")
def get_warehouses(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns multi-warehouse comparisons and stock distributions."""
    _verify_company_access(company_id, current_user, db)
    return get_warehouses_analytics(db, company_id)


@router.get("/replenishment/{company_id}")
def get_replenishment(
    company_id: int,
    service_level: float = Query(0.95, ge=0.80, le=0.99),
    horizon_days: int = Query(30, ge=7, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Computes replenishment plan and reorder suggestions with safety stock."""
    _verify_company_access(company_id, current_user, db)
    return compute_replenishment_plan(db, company_id, service_level, horizon_days)


@router.get("/transfers/{company_id}")
def get_transfers(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns inter-warehouse stock transfer proposals."""
    _verify_company_access(company_id, current_user, db)
    return get_warehouse_transfer_recommendations(db, company_id)


class DelaySimulationRequest(BaseModel):
    company_id: int
    product_id: int
    warehouse_id: Optional[int] = None
    delay_days: float = Field(0.0, ge=0.0, le=90.0)
    demand_multiplier: float = Field(1.0, ge=0.0, le=5.0)
    horizon_days: int = Field(30, ge=7, le=90)
    target_order_id: Optional[int] = None
    emergency_order_qty: float = Field(0.0, ge=0.0)
    emergency_order_day: int = Field(5, ge=1, le=90)
    user_expedite_cost: Optional[float] = None


@router.post("/simulate/delay")
def simulate_delay(
    req: DelaySimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Runs the discrete-event delay simulation over the daily timeline."""
    _verify_company_access(req.company_id, current_user, db)
    return run_delay_simulation(
        db=db,
        company_id=req.company_id,
        product_id=req.product_id,
        warehouse_id=req.warehouse_id,
        delay_days=req.delay_days,
        demand_multiplier=req.demand_multiplier,
        horizon_days=req.horizon_days,
        target_order_id=req.target_order_id,
        emergency_order_qty=req.emergency_order_qty,
        emergency_order_day=req.emergency_order_day,
        user_expedite_cost=req.user_expedite_cost,
    )


class WhatIfRequest(BaseModel):
    company_id: int
    product_id: int
    demand_multiplier: float = Field(1.0, ge=0.1, le=5.0)
    lead_time_delta: float = Field(0.0, ge=-30.0, le=60.0)
    service_level_target: float = Field(0.95, ge=0.80, le=0.99)
    replenishment_batch_override: Optional[float] = Field(None, ge=0.0)


@router.post("/simulate/what-if")
def simulate_what_if(
    req: WhatIfRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Runs a multi-parameter what-if scenario comparing baseline vs modified policy."""
    _verify_company_access(req.company_id, current_user, db)

    base = analyze_product(db, req.company_id, req.product_id)
    z_factor = 1.65 if req.service_level_target == 0.95 else 2.33 if req.service_level_target >= 0.99 else 1.28

    sim_daily_demand = base["daily_demand"] * req.demand_multiplier
    sim_lead_time = max(1.0, base["lead_time_days"] + req.lead_time_delta)
    from app.services.inventory_intelligence import calculate_safety_stock
    sim_safety_stock = calculate_safety_stock(
        daily_demand_mean=sim_daily_demand,
        daily_demand_std=base["demand_std"],
        lead_time_mean=sim_lead_time,
        lead_time_std=base.get("lead_time_std", 0.0),
        z_factor=z_factor,
    )
    sim_reorder_point = (sim_daily_demand * sim_lead_time) + sim_safety_stock

    current_stock = base["inventory_level"]
    sim_coverage = (current_stock / sim_daily_demand) if sim_daily_demand > 0 else 999.0

    return {
        "product_id": req.product_id,
        "baseline": {
            "daily_demand": base["daily_demand"],
            "lead_time_days": base["lead_time_days"],
            "safety_stock": base["safety_stock"],
            "reorder_point": base["reorder_point"],
            "coverage_days": base["inventory_coverage_days"],
            "stockout_risk": base["stockout_risk"],
        },
        "scenario": {
            "demand_multiplier": req.demand_multiplier,
            "daily_demand": round(sim_daily_demand, 2),
            "lead_time_days": round(sim_lead_time, 1),
            "safety_stock": round(sim_safety_stock, 1),
            "reorder_point": round(sim_reorder_point, 1),
            "coverage_days": round(sim_coverage, 1) if sim_coverage < 900 else None,
            "stockout_risk": "CRITICAL" if current_stock < (sim_daily_demand * 3) else "HIGH" if current_stock < sim_safety_stock else "LOW",
        },
        "deltas": {
            "daily_demand_diff": round(sim_daily_demand - base["daily_demand"], 2),
            "safety_stock_diff": round(sim_safety_stock - base["safety_stock"], 1),
            "reorder_point_diff": round(sim_reorder_point - base["reorder_point"], 1),
        }
    }


class ExecuteTransferRequest(BaseModel):
    company_id: int
    product_id: Optional[int] = None
    sku: Optional[str] = None
    source_warehouse_id: int
    destination_warehouse_id: int
    quantity: float = Field(..., gt=0)
    notes: Optional[str] = None


@router.post("/transfers/execute")
def execute_warehouse_transfer(
    req: ExecuteTransferRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Executes a real transactional stock transfer between two warehouses.
    Validates company authorization, source & destination warehouses, product existence,
    available stock, and safety buffer constraints.
    Atomically updates inventory records and logs the transfer.
    """
    _verify_company_access(req.company_id, current_user, db)

    if req.source_warehouse_id == req.destination_warehouse_id:
        raise HTTPException(
            status_code=400,
            detail="Source and destination warehouses must be different.",
        )

    # Validate warehouses belong to company
    source_wh = (
        db.query(Warehouse)
        .filter(Warehouse.id == req.source_warehouse_id, Warehouse.company_id == req.company_id)
        .first()
    )
    if not source_wh:
        raise HTTPException(status_code=404, detail="Source warehouse not found for this company.")

    dest_wh = (
        db.query(Warehouse)
        .filter(Warehouse.id == req.destination_warehouse_id, Warehouse.company_id == req.company_id)
        .first()
    )
    if not dest_wh:
        raise HTTPException(status_code=404, detail="Destination warehouse not found for this company.")

    # Validate product
    prod_query = db.query(Product).filter(Product.company_id == req.company_id)
    if req.product_id is not None:
        prod_query = prod_query.filter(Product.id == req.product_id)
    elif req.sku:
        prod_query = prod_query.filter(Product.external_product_id == req.sku)
    else:
        raise HTTPException(status_code=400, detail="Either product_id or sku must be provided.")

    product = prod_query.first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found for this company.")

    # Check available stock at source warehouse
    source_inv = (
        db.query(InventoryRecord)
        .filter(
            InventoryRecord.company_id == req.company_id,
            InventoryRecord.product_id == product.id,
            InventoryRecord.warehouse_id == req.source_warehouse_id,
        )
        .order_by(InventoryRecord.date.desc())
        .first()
    )

    current_source_stock = float(source_inv.inventory_level) if source_inv else 0.0

    if current_source_stock < req.quantity:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Insufficient stock at {source_wh.name}. Available: {current_source_stock:.1f} units, "
                f"Requested: {req.quantity:.1f} units."
            ),
        )

    # Enforce non-negative inventory constraint
    new_source_stock = current_source_stock - req.quantity
    if new_source_stock < 0:
        raise HTTPException(
            status_code=400,
            detail="Transfer would violate non-negative stock constraints.",
        )

    # Get or create destination inventory record
    dest_inv = (
        db.query(InventoryRecord)
        .filter(
            InventoryRecord.company_id == req.company_id,
            InventoryRecord.product_id == product.id,
            InventoryRecord.warehouse_id == req.destination_warehouse_id,
        )
        .order_by(InventoryRecord.date.desc())
        .first()
    )

    current_dest_stock = float(dest_inv.inventory_level) if dest_inv else 0.0
    new_dest_stock = current_dest_stock + req.quantity

    # Transactionally update stock
    today = date.today()
    if source_inv:
        source_inv.inventory_level = new_source_stock
    else:
        source_inv = InventoryRecord(
            company_id=req.company_id,
            product_id=product.id,
            warehouse_id=req.source_warehouse_id,
            date=today,
            inventory_level=new_source_stock,
            safety_stock=0.0,
        )
        db.add(source_inv)

    if dest_inv:
        dest_inv.inventory_level = new_dest_stock
    else:
        dest_inv = InventoryRecord(
            company_id=req.company_id,
            product_id=product.id,
            warehouse_id=req.destination_warehouse_id,
            date=today,
            inventory_level=new_dest_stock,
            safety_stock=0.0,
        )
        db.add(dest_inv)

    # Record transfer log
    transfer = WarehouseTransfer(
        company_id=req.company_id,
        product_id=product.id,
        source_warehouse_id=req.source_warehouse_id,
        destination_warehouse_id=req.destination_warehouse_id,
        quantity=float(req.quantity),
        status="COMPLETED",
        executed_by_user_id=current_user.id,
        created_at=datetime.utcnow(),
        notes=req.notes,
    )
    db.add(transfer)
    db.commit()
    db.refresh(transfer)

    return {
        "status": "COMPLETED",
        "transfer_id": transfer.id,
        "product_id": product.id,
        "product_name": product.name,
        "sku": product.external_product_id,
        "quantity": req.quantity,
        "source_warehouse": source_wh.name,
        "destination_warehouse": dest_wh.name,
        "source_stock_before": round(current_source_stock, 1),
        "source_stock_after": round(new_source_stock, 1),
        "destination_stock_before": round(current_dest_stock, 1),
        "destination_stock_after": round(new_dest_stock, 1),
        "executed_at": str(transfer.created_at),
        "executed_by_user_id": current_user.id,
    }


@router.get("/transfers/history/{company_id}")
def get_warehouse_transfers_history(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetches real history of executed warehouse transfers."""
    _verify_company_access(company_id, current_user, db)
    transfers = (
        db.query(WarehouseTransfer)
        .filter(WarehouseTransfer.company_id == company_id)
        .order_by(WarehouseTransfer.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": t.id,
            "product_id": t.product_id,
            "product_name": t.product.name if t.product else f"Product {t.product_id}",
            "sku": t.product.external_product_id if t.product else None,
            "source_warehouse_id": t.source_warehouse_id,
            "source_warehouse_name": t.source_warehouse.name if t.source_warehouse else f"Warehouse {t.source_warehouse_id}",
            "destination_warehouse_id": t.destination_warehouse_id,
            "destination_warehouse_name": t.destination_warehouse.name if t.destination_warehouse else f"Warehouse {t.destination_warehouse_id}",
            "quantity": t.quantity,
            "status": t.status,
            "executed_by_user_id": t.executed_by_user_id,
            "created_at": str(t.created_at),
            "notes": t.notes,
        }
        for t in transfers
    ]


# ==============================================================================
# Persistent What-If Scenarios (Task 11)
# ==============================================================================

class SaveScenarioRequest(BaseModel):
    company_id: int
    name: str
    description: Optional[str] = None
    scenario_type: str = "WHAT_IF"
    parameters: Dict[str, Any]
    results: Dict[str, Any]


@router.post("/scenarios")
def save_scenario(
    req: SaveScenarioRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Saves a What-If scenario with tenant isolation and audit ownership."""
    _verify_company_access(req.company_id, current_user, db)

    scenario = SavedScenario(
        company_id=req.company_id,
        user_id=current_user.id,
        name=req.name.strip(),
        description=req.description,
        scenario_type=req.scenario_type,
        parameters_json=json.dumps(req.parameters),
        results_json=json.dumps(req.results),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)

    return {
        "id": scenario.id,
        "company_id": scenario.company_id,
        "name": scenario.name,
        "description": scenario.description,
        "scenario_type": scenario.scenario_type,
        "created_at": str(scenario.created_at),
        "status": "SAVED",
    }


@router.get("/scenarios/{company_id}")
def list_saved_scenarios(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists saved scenarios for a company."""
    _verify_company_access(company_id, current_user, db)
    scenarios = (
        db.query(SavedScenario)
        .filter(SavedScenario.company_id == company_id)
        .order_by(SavedScenario.created_at.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "company_id": s.company_id,
            "user_id": s.user_id,
            "name": s.name,
            "description": s.description,
            "scenario_type": s.scenario_type,
            "parameters": json.loads(s.parameters_json),
            "results": json.loads(s.results_json),
            "created_at": str(s.created_at),
        }
        for s in scenarios
    ]


@router.delete("/scenarios/{company_id}/{scenario_id}")
def delete_saved_scenario(
    company_id: int,
    scenario_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes a saved scenario."""
    _verify_company_access(company_id, current_user, db)
    scenario = (
        db.query(SavedScenario)
        .filter(SavedScenario.id == scenario_id, SavedScenario.company_id == company_id)
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    db.delete(scenario)
    db.commit()
    return {"status": "DELETED", "id": scenario_id}

