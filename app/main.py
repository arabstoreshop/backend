import logging
import subprocess

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import admin, config, health, orders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def run_migrations():
    logger.info("Running Alembic migrations...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        logger.error("Migration failed: %s", result.stderr)
        raise RuntimeError("Alembic migration failed")
    logger.info("Migrations complete: %s", result.stdout)


app = FastAPI(
    title="Naseem API",
    description="نسيم — Saudi DTC ecommerce API",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "https://naseem.beauty",
        "https://www.naseem.beauty",
        "http://localhost:3000",
        "http://localhost:3005",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3005",
    ],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(config.router)
app.include_router(orders.router)
app.include_router(admin.router)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    logger.warning("422 %s %s", request.url.path, exc.errors())
    msgs = []
    for err in exc.errors():
        msg = str(err.get("msg") or "")
        msg = msg.replace("Value error, ", "").replace("Value error,", "")
        if msg:
            msgs.append(msg)
    return JSONResponse(
        status_code=422,
        content={"detail": " — ".join(msgs) or "بيانات الطلب غير صحيحة"},
    )


@app.on_event("startup")
async def startup_event():
    if settings.database_url.startswith("sqlite"):
        from app.database import Base, engine
        from app.models import Order, OrderItem  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info("SQLite tables created/verified")
    elif settings.run_migrations_on_start:
        run_migrations()
    logger.info("Naseem API started in %s mode", settings.environment)
