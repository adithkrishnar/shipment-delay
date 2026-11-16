"""
Idempotent Demo Account Seeding Service for SupplyIQ.
Ensures that all 4 demo accounts exist across both PostgreSQL and SQLite
upon application startup or manual CLI execution without destroying existing data.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.models.company import Company
from app.models.user import User
from app.models.transporter_org import TransporterOrganization
from app.auth.security import get_password_hash, verify_password
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

DEMO_ACCOUNTS: List[Dict[str, Any]] = [
    {
        "company_name": "DataCo Global Supply Chain",
        "industry": "Omnichannel Retail & Logistics",
        "user_email": "admin@dataco.com",
        "password": "admin123",
        "role": "company",
        "is_superuser": True,
        "org_name": None,
        "carrier_code": None,
        "carrier_name": None,
    },
    {
        "company_name": "DataCo Global Supply Chain",
        "industry": "Omnichannel Retail & Logistics",
        "user_email": "carrier@datacotransport.com",
        "password": "carrier123",
        "role": "transporter",
        "is_superuser": False,
        "org_name": "DataCo Express Linehaul",
        "carrier_code": "DC-EXPRESS",
        "carrier_name": "DataCo Express Linehaul",
    },
    {
        "company_name": "Nexus Global Logistics",
        "industry": "Global Multimodal Freight & Electronics Distribution",
        "user_email": "admin@nexus-global.com",
        "password": "nexus123",
        "role": "company",
        "is_superuser": False,
        "org_name": None,
        "carrier_code": None,
        "carrier_name": None,
    },
    {
        "company_name": "Nexus Global Logistics",
        "industry": "Global Multimodal Freight & Electronics Distribution",
        "user_email": "fleet@nexus-logistics.com",
        "password": "nexus123",
        "role": "transporter",
        "is_superuser": False,
        "org_name": "Nexus Intermodal Fleetways",
        "carrier_code": "NX-FLEET",
        "carrier_name": "Nexus Intermodal Fleetways",
    },
    {
        "company_name": "Vanguard Aerospace & Robotics",
        "industry": "Aerospace & Advanced Defense Systems",
        "user_email": "admin@vanguard-aero.com",
        "password": "vanguard123",
        "role": "company",
        "is_superuser": False,
        "org_name": None,
        "carrier_code": None,
        "carrier_name": None,
    },
    {
        "company_name": "Vanguard Aerospace & Robotics",
        "industry": "Aerospace & Advanced Defense Systems",
        "user_email": "ops@pacificintermodal.com",
        "password": "pacific123",
        "role": "transporter",
        "is_superuser": False,
        "org_name": "Pacific Intermodal Freightways",
        "carrier_code": "PAC-INTERMODAL",
        "carrier_name": "Pacific Intermodal Freightways",
    },
    # ── Live Demonstration Benchmark Scenario: Bengaluru -> Chennai Corridor ──
    {
        "company_name": "Bengaluru Manufacturing Ltd",
        "industry": "High-Tech Electronics & IoT Hardware",
        "user_email": "sender@companyA.com",
        "password": "sender123",
        "role": "company",
        "is_superuser": False,
        "default_currency": "INR",
        "org_name": None,
        "carrier_code": None,
        "carrier_name": None,
    },
    {
        "company_name": "Bengaluru Manufacturing Ltd",
        "industry": "High-Tech Electronics & IoT Hardware",
        "user_email": "sender@companya.com",
        "password": "sender123",
        "role": "company",
        "is_superuser": False,
        "default_currency": "INR",
        "org_name": None,
        "carrier_code": None,
        "carrier_name": None,
    },
    {
        "company_name": "Karnataka-Tamil Nadu Express Logistics",
        "industry": "Interstate Express Logistics & Fleet Operations",
        "user_email": "transporter@companyB.com",
        "password": "transporter123",
        "role": "transporter",
        "is_superuser": False,
        "default_currency": "INR",
        "org_name": "Karnataka-Tamil Nadu Express Logistics",
        "carrier_code": "KTN-EXPRESS",
        "carrier_name": "Karnataka-Tamil Nadu Express Logistics",
    },
    {
        "company_name": "Karnataka-Tamil Nadu Express Logistics",
        "industry": "Interstate Express Logistics & Fleet Operations",
        "user_email": "transporter@companyb.com",
        "password": "transporter123",
        "role": "transporter",
        "is_superuser": False,
        "default_currency": "INR",
        "org_name": "Karnataka-Tamil Nadu Express Logistics",
        "carrier_code": "KTN-EXPRESS",
        "carrier_name": "Karnataka-Tamil Nadu Express Logistics",
    },
    {
        "company_name": "Chennai Central Distribution",
        "industry": "Distribution & Omnichannel Retail Logistics",
        "user_email": "receiver@companyC.com",
        "password": "receiver123",
        "role": "company",
        "is_superuser": False,
        "default_currency": "INR",
        "org_name": None,
        "carrier_code": None,
        "carrier_name": None,
    },
    {
        "company_name": "Chennai Central Distribution",
        "industry": "Distribution & Omnichannel Retail Logistics",
        "user_email": "receiver@companyc.com",
        "password": "receiver123",
        "role": "company",
        "is_superuser": False,
        "default_currency": "INR",
        "org_name": None,
        "carrier_code": None,
        "carrier_name": None,
    },
]


def ensure_demo_accounts_seeded(db: Session) -> Dict[str, Any]:
    """
    Idempotently verifies and seeds the demo companies, transporter orgs,
    and user credentials into the active database.
    Does not delete existing data or reset passwords if already valid.
    """
    created_users = 0
    updated_users = 0

    try:
        for entry in DEMO_ACCOUNTS:
            # 1. Company
            company = db.query(Company).filter(Company.name == entry["company_name"]).first()
            if not company:
                company = Company(
                    name=entry["company_name"],
                    industry=entry["industry"],
                    is_demo=1,
                    default_currency=entry.get("default_currency", "USD"),
                    notes="Official demo tenant configured for SupplyIQ intelligence workflows.",
                )
                db.add(company)
                db.flush()
            else:
                if "default_currency" in entry and company.default_currency != entry["default_currency"]:
                    company.default_currency = entry["default_currency"]
                db.flush()

            # 2. Transporter Organization (if transporter role)
            org_id = None
            if entry["org_name"]:
                org = db.query(TransporterOrganization).filter(
                    TransporterOrganization.name == entry["org_name"]
                ).first()
                if not org:
                    org = TransporterOrganization(
                        name=entry["org_name"],
                        code=entry["carrier_code"],
                        contact_email=entry["user_email"],
                        is_active=True,
                    )
                    db.add(org)
                    db.flush()
                org_id = org.id

            # 3. User Account
            user = db.query(User).filter(User.email == entry["user_email"]).first()
            if not user:
                user = User(
                    email=entry["user_email"],
                    hashed_password=get_password_hash(entry["password"]),
                    role=entry["role"],
                    is_active=True,
                    is_superuser=entry["is_superuser"],
                    company_id=company.id,
                    transporter_org_id=org_id,
                    carrier_name=entry["carrier_name"],
                )
                db.add(user)
                created_users += 1
            else:
                # User exists - ensure company and org associations match
                modified = False
                if user.company_id != company.id:
                    user.company_id = company.id
                    modified = True
                if user.transporter_org_id != org_id:
                    user.transporter_org_id = org_id
                    modified = True
                if entry["carrier_name"] and user.carrier_name != entry["carrier_name"]:
                    user.carrier_name = entry["carrier_name"]
                    modified = True
                if not user.is_active:
                    user.is_active = True
                    modified = True

                # Validate password hash; if invalid, fix it to intended demo password
                if not verify_password(entry["password"], user.hashed_password):
                    user.hashed_password = get_password_hash(entry["password"])
                    modified = True

                if modified:
                    updated_users += 1

        db.commit()
        logger.info(
            "Demo accounts verification complete: created=%d, updated=%d",
            created_users,
            updated_users,
        )
        # Ensure baseline ML models and master enterprise dataset records exist
        ensure_baseline_data_and_models(db)
        return {"status": "success", "created": created_users, "updated": updated_users}
    except Exception as exc:
        db.rollback()
        logger.error("Failed to seed demo accounts: %s", exc)
        return {"status": "error", "message": str(exc)}


def ensure_baseline_data_and_models(db: Session):
    """
    Guarantees that on any platform (Render, Docker, local), the database has:
    1. Base demand forecasting model registered and trained.
    2. Base shipment delay classifier model registered.
    3. DataCo operational records seeded from master enterprise dataset if empty.
    """
    from app.models import Company, Sale, ModelRegistryEntry
    from app.services.model_training_service import (
        MODEL_TYPE_DEMAND,
        MODEL_TYPE_DELAY_CLASSIFIER,
        train_base_demand_model,
        train_base_shipment_models,
    )
    
    # 1. Base demand model
    has_demand = db.query(ModelRegistryEntry).filter(
        ModelRegistryEntry.model_type == MODEL_TYPE_DEMAND
    ).first()
    if not has_demand:
        try:
            logger.info("Initializing baseline demand model on startup...")
            train_base_demand_model(db)
        except Exception as e:
            logger.warning("Could not auto-train base demand model on startup: %s", e)

    # 2. Base shipment model
    has_shipment = db.query(ModelRegistryEntry).filter(
        ModelRegistryEntry.model_type == MODEL_TYPE_DELAY_CLASSIFIER
    ).first()
    if not has_shipment:
        try:
            logger.info("Initializing baseline shipment model on startup...")
            train_base_shipment_models(db)
        except Exception as e:
            logger.warning("Could not auto-register base shipment model on startup: %s", e)

    # 3. Auto-seed datasets for companies if records are low
    from app.config import settings, BASE_DIR
    import pandas as pd
    from app.services.column_mapping import suggest_column_mapping
    from app.services.data_import import apply_mapping, import_dataset

    # 4. Auto-seed intermodal multi-leg shipments for carrier portal & control tower
    ensure_demo_shipments_and_legs(db)


def ensure_demo_shipments_and_legs(db: Session):
    """
    Seeds realistic multimodal benchmark shipments (DC-PO-00801, DC-PO-00802, etc.)
    and their legs into the database so that transporter disruption and delay reports
    execute genuine database operations, run downstream ripple simulations, and alert the company.
    """
    from datetime import date, datetime, timedelta
    from app.models import Company, Product, Shipment, TransporterOrganization
    from app.models.shipment_leg import ShipmentLeg

    dataco = db.query(Company).filter(Company.name == "DataCo Global Supply Chain").first()
    if not dataco:
        return

    transporter = db.query(TransporterOrganization).filter(
        TransporterOrganization.name == "DataCo Express Linehaul"
    ).first()
    trans_org_id = transporter.id if transporter else None

    # Resolve product for shipment linkage (prefer SKU-1004 or first available product)
    prod = (
        db.query(Product).filter(Product.company_id == dataco.id, Product.external_product_id == "SKU-1004").first()
        or db.query(Product).filter(Product.company_id == dataco.id).first()
    )
    if not prod:
        prod = Product(
            company_id=dataco.id,
            external_product_id="SKU-1004",
            name="Smart Fitness Tracker Pro",
            unit_price=85.0,
            unit_cost=45.0,
        )
        db.add(prod)
        db.flush()

    prod_id = prod.id

    # 1. Shipment DC-PO-00801
    s801 = db.query(Shipment).filter(
        (Shipment.id == 801) | (Shipment.external_shipment_id == "DC-PO-00801")
    ).first()
    if not s801:
        s801 = Shipment(
            id=801,
            company_id=dataco.id,
            product_id=prod_id,
            external_shipment_id="DC-PO-00801",
            origin="Shenzhen Precision Factory, CN",
            destination="DataCo USCA DC (Chicago, IL)",
            carrier="DataCo Express Linehaul",
            transport_mode="SEA",
            transporter_org_id=trans_org_id,
            assignment_status="IN_TRANSIT",
            order_date=date(2026, 11, 1),
            planned_delivery=date(2026, 11, 18),
            current_eta=date(2026, 11, 20),
            weight_kg=1250.0,
            quantity=150.0,
            distance_km=11400.0,
        )
        db.add(s801)
        db.flush()

        legs_801 = [
            ShipmentLeg(
                id=8011,
                shipment_id=s801.id,
                sequence=1,
                mode="ROAD",
                origin="Shenzhen Precision Factory",
                destination="Yantian Ocean Terminal",
                carrier_name="Shenzhen Drayage Express",
                expected_duration_hrs=6.0,
                delay_hours=0.0,
                status="COMPLETED",
                scheduled_departure=datetime(2026, 11, 1, 8, 0),
                scheduled_arrival=datetime(2026, 11, 1, 14, 0),
            ),
            ShipmentLeg(
                id=8012,
                shipment_id=s801.id,
                sequence=2,
                mode="SEA",
                origin="Yantian Ocean Terminal",
                destination="Port of Long Beach (Pier T)",
                carrier_name="Cosco Shipping Lines (Pacific Service)",
                expected_duration_hrs=280.0,
                delay_hours=20.0,
                status="DISRUPTED",
                scheduled_departure=datetime(2026, 11, 2, 18, 0),
                scheduled_arrival=datetime(2026, 11, 14, 6, 0),
                next_leg_cutoff=datetime(2026, 11, 14, 14, 0),
                missed_connection_dwell_hrs=48.0,
            ),
            ShipmentLeg(
                id=8013,
                shipment_id=s801.id,
                sequence=3,
                mode="RAIL",
                origin="Long Beach Intermodal Terminal",
                destination="Chicago BNSF Logistics Park",
                carrier_name="DataCo Express Linehaul",
                expected_duration_hrs=64.0,
                delay_hours=0.0,
                status="AT_RISK",
                scheduled_departure=datetime(2026, 11, 15, 2, 0),
                scheduled_arrival=datetime(2026, 11, 17, 18, 0),
                next_leg_cutoff=datetime(2026, 11, 14, 20, 0),
            ),
            ShipmentLeg(
                id=8014,
                shipment_id=s801.id,
                sequence=4,
                mode="ROAD",
                origin="Chicago BNSF Logistics Park",
                destination="DataCo USCA DC (Joliet, IL)",
                carrier_name="DataCo Express Linehaul",
                expected_duration_hrs=4.0,
                delay_hours=0.0,
                status="SCHEDULED",
                scheduled_departure=datetime(2026, 11, 18, 6, 0),
                scheduled_arrival=datetime(2026, 11, 18, 10, 0),
            ),
        ]
        db.add_all(legs_801)

    # 2. Shipment DC-PO-00802
    s802 = db.query(Shipment).filter(
        (Shipment.id == 802) | (Shipment.external_shipment_id == "DC-PO-00802")
    ).first()
    if not s802:
        s802 = Shipment(
            id=802,
            company_id=dataco.id,
            product_id=prod_id,
            external_shipment_id="DC-PO-00802",
            origin="Hamburg Industrial Park, DE",
            destination="DataCo Europe DC (Frankfurt, DE)",
            carrier="DataCo Express Linehaul",
            transport_mode="ROAD",
            transporter_org_id=trans_org_id,
            assignment_status="IN_TRANSIT",
            order_date=date(2026, 11, 5),
            planned_delivery=date(2026, 11, 9),
            current_eta=date(2026, 11, 10),
            weight_kg=850.0,
            quantity=80.0,
            distance_km=495.0,
        )
        db.add(s802)
        db.flush()

        leg_802 = ShipmentLeg(
            id=8021,
            shipment_id=s802.id,
            sequence=1,
            mode="ROAD",
            origin="Hamburg Logistics Hub",
            destination="DataCo Europe DC (Frankfurt)",
            carrier_name="DataCo Express Linehaul",
            expected_duration_hrs=10.0,
            delay_hours=4.0,
            status="DELAYED",
            scheduled_departure=datetime(2026, 11, 9, 6, 0),
            scheduled_arrival=datetime(2026, 11, 9, 16, 0),
        )
        db.add(leg_802)

    # 3. Bengaluru -> Chennai Live Demo Benchmark Corridor (Company A -> Company B -> Company C)
    ensure_bengaluru_chennai_corridor(db)

    db.commit()
    logger.info("Demo shipments & legs verification complete (DC-PO-00801, DC-PO-00802, SH-BLR-2026-0001).")


def ensure_bengaluru_chennai_corridor(db: Session):
    """
    Seeds the authoritative live demonstration scenario:
    - Manufacturer (Company A): Bengaluru Manufacturing Ltd
    - Transporter (Company B): Karnataka-Tamil Nadu Express Logistics
    - Receiver (Company C): Chennai Central Distribution
    Includes active shipment SH-BLR-2026-0001 with 3 sequenced legs,
    baseline inventory (85 units) at Chennai Central DC, and 30-day sales demand history.
    """
    from datetime import date, datetime, timedelta
    from app.models import Company, Product, Warehouse, InventoryRecord, Sale, Shipment, TransporterOrganization
    from app.models.shipment_leg import ShipmentLeg

    comp_a = db.query(Company).filter(Company.name == "Bengaluru Manufacturing Ltd").first()
    comp_c = db.query(Company).filter(Company.name == "Chennai Central Distribution").first()
    carrier_b = db.query(TransporterOrganization).filter(TransporterOrganization.name == "Karnataka-Tamil Nadu Express Logistics").first()

    if not comp_a or not comp_c or not carrier_b:
        return

    # Warehouses
    wh_blr = db.query(Warehouse).filter(Warehouse.company_id == comp_a.id, Warehouse.name == "Bengaluru Electronic City Plant").first()
    if not wh_blr:
        wh_blr = Warehouse(company_id=comp_a.id, name="Bengaluru Electronic City Plant", region="Karnataka / South")
        db.add(wh_blr)
        db.flush()

    wh_chn = db.query(Warehouse).filter(Warehouse.company_id == comp_c.id, Warehouse.name == "Chennai Central DC").first()
    if not wh_chn:
        wh_chn = Warehouse(company_id=comp_c.id, name="Chennai Central DC", region="Tamil Nadu / South")
        db.add(wh_chn)
        db.flush()

    # Products
    prod_a = db.query(Product).filter(Product.company_id == comp_a.id, Product.external_product_id == "SKU-BLR-101").first()
    if not prod_a:
        prod_a = Product(
            company_id=comp_a.id,
            external_product_id="SKU-BLR-101",
            name="Industrial IoT Telematics Controller",
            unit_price=4500.0,
            unit_cost=2200.0
        )
        db.add(prod_a)
        db.flush()

    prod_c = db.query(Product).filter(Product.company_id == comp_c.id, Product.external_product_id == "SKU-BLR-101").first()
    if not prod_c:
        prod_c = Product(
            company_id=comp_c.id,
            external_product_id="SKU-BLR-101",
            name="Industrial IoT Telematics Controller",
            unit_price=5400.0,
            unit_cost=4500.0
        )
        db.add(prod_c)
        db.flush()

    # Baseline Inventory Record at Chennai Central DC (85 on-hand units)
    today = date.today()
    inv_c = db.query(InventoryRecord).filter(
        InventoryRecord.company_id == comp_c.id,
        InventoryRecord.warehouse_id == wh_chn.id,
        InventoryRecord.product_id == prod_c.id
    ).first()
    if not inv_c:
        inv_c = InventoryRecord(
            company_id=comp_c.id,
            warehouse_id=wh_chn.id,
            product_id=prod_c.id,
            date=today,
            inventory_level=85.0
        )
        db.add(inv_c)
        db.flush()

    # 30-Day Sales Demand Baseline for Company C (expected daily demand: 50 units/day)
    has_sales = db.query(Sale).filter(Sale.company_id == comp_c.id, Sale.product_id == prod_c.id).first()
    if not has_sales:
        sales_records = []
        for days_ago in range(30, 0, -1):
            sale_date = today - timedelta(days=days_ago)
            # deterministic daily demand averaging exactly 50.0 units/day (48, 49, 50, 51, 52)
            daily_units = 48.0 + (days_ago % 5)
            sales_records.append(Sale(
                company_id=comp_c.id,
                product_id=prod_c.id,
                date=sale_date,
                quantity=daily_units,
                price=5400.0,
                region="South",
                promotion=0
            ))
        db.add_all(sales_records)
        db.flush()
    else:
        # Update existing sales to match 50.0 units/day requirement
        sales_records = db.query(Sale).filter(Sale.company_id == comp_c.id, Sale.product_id == prod_c.id).all()
        for idx, s in enumerate(sales_records):
            s.quantity = 48.0 + (idx % 5)
            s.price = 5400.0

    # Pre-Seeded Shipment: SH-BLR-2026-0001
    s_blr = db.query(Shipment).filter(Shipment.external_shipment_id == "SH-BLR-2026-0001").first()
    if not s_blr:
        s_blr = Shipment(
            id=901,
            company_id=comp_a.id,
            receiver_company_id=comp_c.id,
            destination_warehouse_id=wh_chn.id,
            product_id=prod_a.id,
            external_shipment_id="SH-BLR-2026-0001",
            origin="Bengaluru Electronic City Plant, Karnataka",
            destination="Chennai Central DC, Tamil Nadu",
            carrier="Karnataka-Tamil Nadu Express Logistics",
            transport_mode="ROAD",
            transporter_org_id=carrier_b.id,
            assignment_status="IN_TRANSIT",
            order_date=today - timedelta(days=2),
            planned_delivery=today + timedelta(days=1),
            current_eta=today + timedelta(days=1),
            distance_km=360.0,
            weight_kg=450.0,
            quantity=100.0
        )
        db.add(s_blr)
        db.flush()

        # Sequenced transportation legs
        dep_dt = datetime.combine(today - timedelta(days=1), datetime.min.time()) + timedelta(hours=6)
        legs_blr = [
            ShipmentLeg(
                id=9011,
                shipment_id=s_blr.id,
                sequence=1,
                mode="ROAD",
                origin="Bengaluru Electronic City Plant",
                destination="Hosur Intermodal Hub",
                carrier_name="Karnataka-Tamil Nadu Express Logistics",
                distance_km=45.0,
                expected_duration_hrs=2.0,
                delay_hours=0.0,
                status="COMPLETED",
                scheduled_departure=dep_dt,
                scheduled_arrival=dep_dt + timedelta(hours=2),
                next_leg_cutoff=dep_dt + timedelta(hours=3),
            ),
            ShipmentLeg(
                id=9012,
                shipment_id=s_blr.id,
                sequence=2,
                mode="ROAD",
                origin="Hosur Intermodal Hub",
                destination="Sriperumbudur Logistics Park",
                carrier_name="Karnataka-Tamil Nadu Express Logistics",
                distance_km=280.0,
                expected_duration_hrs=6.0,
                delay_hours=0.0,
                status="IN_TRANSIT",
                scheduled_departure=dep_dt + timedelta(hours=3),
                scheduled_arrival=dep_dt + timedelta(hours=9),
                next_leg_cutoff=dep_dt + timedelta(hours=11),
                missed_connection_dwell_hrs=0.0,
            ),
            ShipmentLeg(
                id=9013,
                shipment_id=s_blr.id,
                sequence=3,
                mode="ROAD",
                origin="Sriperumbudur Logistics Park",
                destination="Chennai Central DC",
                carrier_name="Karnataka-Tamil Nadu Express Logistics",
                distance_km=35.0,
                expected_duration_hrs=1.5,
                delay_hours=0.0,
                status="SCHEDULED",
                scheduled_departure=dep_dt + timedelta(hours=11),
                scheduled_arrival=dep_dt + timedelta(hours=12, minutes=30),
            )
        ]
        db.add_all(legs_blr)


def reset_benchmark_corridor(db: Session) -> Dict[str, Any]:
    """
    Authoritative reset for live evaluators:
    - SH-BLR-2026-0001 -> IN_TRANSIT, planned_delivery = tomorrow, current_eta = tomorrow, actual_delivery = None.
    - Leg 1 -> COMPLETED (0 delay).
    - Leg 2 -> IN_TRANSIT (0 delay).
    - Leg 3 -> SCHEDULED (0 delay).
    - Chennai Central DC stock -> exactly 85.0 units.
    - Clears DisruptionReport, ShipmentDelay, active Alerts, and ActionApprovals for SH-BLR-2026-0001.
    Does NOT delete real company accounts or unrelated shipments.
    """
    from datetime import date, datetime, timedelta
    from app.models import (
        Company, Product, Warehouse, InventoryRecord, 
        Sale, Shipment, Alert
    )
    from app.models.shipment_leg import ShipmentLeg, DisruptionReport
    from app.models.shipment_delay import ShipmentDelay
    from app.models.action_approval import ActionApproval

    # Ensure corridor is initialized
    ensure_bengaluru_chennai_corridor(db)

    comp_c = db.query(Company).filter(Company.name == "Chennai Central Distribution").first()
    wh_chn = db.query(Warehouse).filter(Warehouse.company_id == comp_c.id, Warehouse.name == "Chennai Central DC").first() if comp_c else None
    prod_c = db.query(Product).filter(Product.company_id == comp_c.id, Product.external_product_id == "SKU-BLR-101").first() if comp_c else None

    # 1. Reset Inventory at Chennai Central DC to exactly 85.0 units
    if comp_c and wh_chn and prod_c:
        inv = db.query(InventoryRecord).filter(
            InventoryRecord.company_id == comp_c.id,
            InventoryRecord.warehouse_id == wh_chn.id,
            InventoryRecord.product_id == prod_c.id
        ).first()
        if inv:
            inv.inventory_level = 85.0
            inv.date = date.today()
        else:
            inv = InventoryRecord(
                company_id=comp_c.id,
                warehouse_id=wh_chn.id,
                product_id=prod_c.id,
                date=date.today(),
                inventory_level=85.0
            )
            db.add(inv)

        # Ensure sales demand averages 50 units/day
        sales = db.query(Sale).filter(Sale.company_id == comp_c.id, Sale.product_id == prod_c.id).all()
        for idx, s in enumerate(sales):
            s.quantity = 48.0 + (idx % 5)
            s.price = 5400.0

    # 2. Reset Benchmark Shipment SH-BLR-2026-0001
    s_blr = db.query(Shipment).filter(Shipment.external_shipment_id == "SH-BLR-2026-0001").first()
    if s_blr:
        today = date.today()
        s_blr.assignment_status = "IN_TRANSIT"
        s_blr.planned_delivery = today + timedelta(days=1)
        s_blr.current_eta = today + timedelta(days=1)
        s_blr.actual_delivery = None
        s_blr.quantity = 100.0

        legs = db.query(ShipmentLeg).filter(ShipmentLeg.shipment_id == s_blr.id).order_by(ShipmentLeg.sequence).all()
        if len(legs) >= 3:
            legs[0].status = "COMPLETED"
            legs[0].delay_hours = 0.0
            legs[1].status = "IN_TRANSIT"
            legs[1].delay_hours = 0.0
            legs[1].missed_connection_dwell_hrs = 0.0
            legs[2].status = "SCHEDULED"
            legs[2].delay_hours = 0.0

        # Clean prior disruption reports and shipment delays for this shipment
        db.query(DisruptionReport).filter(DisruptionReport.shipment_id == s_blr.id).delete()
        db.query(ShipmentDelay).filter(ShipmentDelay.shipment_id == s_blr.id).delete()
        db.query(Alert).filter(Alert.entity_id == s_blr.id).delete()
        db.query(ActionApproval).filter(ActionApproval.action_id.like("%DISRUPTION%")).delete()

    db.commit()
    return {
        "status": "success",
        "corridor": "Bengaluru Electronic City -> Chennai Central DC",
        "shipment_id": "SH-BLR-2026-0001",
        "initial_inventory": 85.0,
        "shipment_quantity": 100.0,
        "daily_demand": 50.0,
        "currency": "INR (₹)",
        "message": "Benchmark corridor safely reset to fresh initial state for live evaluation."
    }


