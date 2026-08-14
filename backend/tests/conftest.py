import os
import tempfile
from pathlib import Path

import pytest

# IMPORTANT: set the test DB before any `app.*` module is imported anywhere,
# so app.config.Settings() picks it up instead of the dev database.
TEST_DB_PATH = Path(tempfile.gettempdir()) / "supplyiq_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def client():
    """A TestClient with a freshly reset schema for each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    """A raw SQLAlchemy session against the same fresh test schema."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
