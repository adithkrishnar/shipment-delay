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

    # 3. If DataCo (company 1) has fewer than 10 sales records, auto-import master dataset
    dataco = db.query(Company).filter(Company.name == "DataCo Global Supply Chain").first()
    if dataco:
        sales_count = db.query(Sale).filter(Sale.company_id == dataco.id).count()
        if sales_count < 10:
            logger.info("DataCo has %d sales records. Auto-seeding from Master Enterprise Dataset...", sales_count)
            from app.config import settings
            import pandas as pd
            from app.services.column_mapping import suggest_column_mapping
            from app.services.data_import import apply_mapping, import_dataset
            
            p = settings.BASE_DIR / "data" / "SupplyIQ_Master_Enterprise_Dataset.csv"
            if not p.exists():
                p = settings.BASE_DIR.parent / "data" / "SupplyIQ_Master_Enterprise_Dataset.csv"
            if p.exists():
                try:
                    df = pd.read_csv(p)
                    mapping = suggest_column_mapping("unified", list(df.columns))
                    mapped = apply_mapping(df, mapping)
                    imp, skp, upd = import_dataset(db, dataco.id, "unified", mapped)
                    logger.info("Auto-seeded Master Enterprise Dataset for DataCo: imported=%d, updated=%d", imp, upd)
                except Exception as e:
                    logger.warning("Could not auto-seed master dataset for DataCo: %s", e)

