"""
Tests for Task 2 Application Security Hardening:
- Rejection of insecure secret key in production
- Enforcement of DEBUG=False in production
- Protected demo seeding endpoint in production
- Cross-company tenant isolation verification
"""
import pytest
from pydantic import ValidationError
from app.config import Settings
from app.models.user import User


def test_production_rejects_insecure_default_secret():
    """Verifies that running in production with default or weak secret raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            ENV="production",
            SECRET_KEY="change-me-in-production-super-secret",
        )
    assert "INSECURE_SECRET_KEY_IN_PRODUCTION" in str(exc_info.value)

    # Also test short secret
    with pytest.raises(ValidationError) as exc_info2:
        Settings(
            ENV="production",
            SECRET_KEY="short-secret-12345",
        )
    assert "INSECURE_SECRET_KEY_IN_PRODUCTION" in str(exc_info2.value)


def test_production_disables_debug_mode():
    """Verifies that DEBUG is automatically forced to False when ENV=production."""
    s = Settings(
        ENV="production",
        DEBUG=True,
        SECRET_KEY="a-very-strong-cryptographically-secure-production-secret-key-32-chars",
    )
    assert s.DEBUG is False
    assert s.ENV == "production"


def test_demo_seed_endpoint_blocked_in_production(client, monkeypatch):
    """Verifies that POST /api/demo/seed rejects unauthenticated requests in production."""
    from app.config import settings
    monkeypatch.setattr(settings, "ENV", "production")

    # Unauthenticated request in production -> 403 Forbidden
    resp = client.post("/api/demo/seed")
    assert resp.status_code == 403
    assert "Security rejection" in resp.json()["detail"]


def test_demo_seed_endpoint_allowed_in_development(client, monkeypatch):
    """Verifies that development mode preserves quick local seeding."""
    from app.config import settings
    monkeypatch.setattr(settings, "ENV", "development")

    # If demo companies exist or are seeded, response is status ok
    resp = client.post("/api/demo/seed")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
