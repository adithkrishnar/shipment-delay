from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routes import companies, demand, demo, health, models, shipments, upload, intelligence, simulator, recommendations, dashboard, live
from app.utils.logging_config import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.ENV)
    init_db()
    logger.info("Database ready at %s", settings.DATABASE_URL)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Multi-company supply chain intelligence platform: demand forecasting, "
        "shipment delay prediction, inventory risk, anomaly detection, what-if "
        "simulation, and AI recommendations - built on real, company-uploaded data."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(companies.router)
app.include_router(demo.router)
app.include_router(upload.router)
app.include_router(demand.router)
app.include_router(models.router)
app.include_router(shipments.router)
app.include_router(intelligence.router)
app.include_router(simulator.router)
app.include_router(recommendations.router)
app.include_router(dashboard.router)
app.include_router(live.router)
