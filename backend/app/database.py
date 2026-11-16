"""
SQLAlchemy engine, session, and declarative base.

Uses SQLite for local development. `DATABASE_URL` can be pointed at a
PostgreSQL connection string with no code changes elsewhere in the app.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Safe to call repeatedly (no-op if tables exist)."""
    # Import models so they register on Base.metadata before create_all runs.
    from app import models  # noqa: F401
    from sqlalchemy import inspect, text

    Base.metadata.create_all(bind=engine)

    # Automatic schema evolution for new columns
    try:
        insp = inspect(engine)
        if "shipments" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("shipments")]
            with engine.begin() as conn:
                if "receiver_company_id" not in cols:
                    conn.execute(text("ALTER TABLE shipments ADD COLUMN receiver_company_id INTEGER"))
                if "destination_warehouse_id" not in cols:
                    conn.execute(text("ALTER TABLE shipments ADD COLUMN destination_warehouse_id INTEGER"))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("Schema column check notice: %s", e)
