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
        return {"status": "success", "created": created_users, "updated": updated_users}
    except Exception as exc:
        db.rollback()
        logger.error("Failed to seed demo accounts: %s", exc)
        return {"status": "error", "message": str(exc)}

