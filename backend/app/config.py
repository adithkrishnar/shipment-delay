"""
Application configuration.

All external services (AI API, weather API, news API) are OPTIONAL.
The application must run completely with defaults and no keys set.
"""
from pathlib import Path
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
    TRAINED_MODELS_DIR: Path = BASE_DIR / "trained_models"

    # JWT Authentication
    SECRET_KEY: str = "change-me-in-production-super-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    FRONTEND_ORIGINS: list[str] | str = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    from pydantic import field_validator
    @field_validator("FRONTEND_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return v

    # Optional external services - app must work with these unset
    AI_API_KEY: str | None = None
    WEATHER_API_KEY: str | None = None
    NEWS_API_KEY: str | None = None

    # Data sufficiency threshold for company-specific model training
    MIN_RECORDS_FOR_COMPANY_MODEL: int = 3000
    MIN_HISTORY_DAYS_FOR_COMPANY_MODEL: int = 180
    # Shipment volumes are naturally much smaller than daily sales volumes,
    # so shipment-based models (delay classifier, delay duration) use their
    # own, lower record threshold. History-days threshold is shared.
    MIN_SHIPMENT_RECORDS_FOR_COMPANY_MODEL: int = 300

    # Upload limits
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_UPLOAD_EXTENSIONS: tuple[str, ...] = (".csv", ".xlsx", ".xls")


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.TRAINED_MODELS_DIR.mkdir(parents=True, exist_ok=True)
