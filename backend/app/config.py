"""
Application configuration.

All external services (AI API, weather API, news API) are OPTIONAL.
The application must run completely with defaults and no keys set.
"""
from pathlib import Path
from typing import Any
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "SupplyIQ Intelligence Platform"
    ENV: str = "development"
    DEBUG: bool = True

    # Database - SQLite by default, structured so PostgreSQL can be swapped in later
    DATABASE_URL: str = f"sqlite:///{(BASE_DIR / 'supplyiq.db').as_posix()}"
    REDIS_URL: str = "redis://localhost:6379"

    # Storage locations
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    TRAINED_MODELS_DIR: Path = (BASE_DIR / "trained_models") if (BASE_DIR / "trained_models").exists() else (BASE_DIR.parent / "trained_models")

    # JWT Authentication
    SECRET_KEY: str = "change-me-in-production-super-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    FRONTEND_ORIGINS: Any = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    FRONTEND_ORIGIN_REGEX: str | None = r"https://.*\.vercel\.app"

    from pydantic import field_validator, model_validator

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        if isinstance(v, str):
            # Render PostgreSQL URLs start with postgres:// which SQLAlchemy 1.4+ deprecates in favor of postgresql://
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql://", 1)
            # Ensure standard psycopg2 driver if no specific driver is designated
            if v.startswith("postgresql://") and not v.startswith("postgresql+"):
                v = v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v

    @field_validator("FRONTEND_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                import json
                try:
                    parsed = json.loads(v_str)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed]
                except Exception:
                    pass
            return [i.strip() for i in v_str.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(item).strip() for item in v if str(item).strip()]
        return v

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        is_prod = str(self.ENV).strip().lower() in ("production", "prod")
        if is_prod:
            # Enforce debug is disabled in production
            self.DEBUG = False

            # Reject insecure default secrets in production
            insecure_defaults = {
                "change-me-in-production-super-secret",
                "secret",
                "password",
                "changeme",
                "default",
            }
            if not self.SECRET_KEY or self.SECRET_KEY in insecure_defaults or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "INSECURE_SECRET_KEY_IN_PRODUCTION: In production mode, SECRET_KEY must be "
                    "explicitly set to a cryptographically secure string of at least 32 characters."
                )
        return self

    # Optional external services - app must work with these unset
    AI_API_KEY: str | None = None
    WEATHER_API_KEY: str | None = None
    NEWS_API_KEY: str | None = None

    # Data sufficiency threshold for company-specific model training
    MIN_RECORDS_FOR_COMPANY_MODEL: int = 50
    MIN_HISTORY_DAYS_FOR_COMPANY_MODEL: int = 14
    # Shipment volumes are naturally much smaller than daily sales volumes,
    # so shipment-based models (delay classifier, delay duration) use their
    # own, lower record threshold. History-days threshold is shared.
    MIN_SHIPMENT_RECORDS_FOR_COMPANY_MODEL: int = 20

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_UPLOAD_EXTENSIONS: tuple[str, ...] = (".csv", ".xlsx", ".xls")


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.TRAINED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
