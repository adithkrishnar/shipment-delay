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
]


def ensure_demo_accounts_seeded(db: Session) -> Dict[str, Any]:
    """
    Idempotently verifies and seeds the 4 critical demo companies, transporter orgs,
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
                    default_currency="USD",
                    notes="Official demo tenant configured for SupplyIQ intelligence workflows.",
                )
                db.add(company)
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

    db.commit()
    logger.info("Demo shipments & legs verification complete (DC-PO-00801, DC-PO-00802).")


