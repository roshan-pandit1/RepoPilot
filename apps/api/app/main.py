import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.routes import router
from app.core.config import get_settings
from app.infra.database import get_engine

logging.basicConfig(level=logging.INFO, format='{"level":"%(levelname)s","event":"%(message)s"}')
logger = logging.getLogger("repopilot")
@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings()  # Fail closed before serving traffic if configuration is unsafe.
    yield


app = FastAPI(title="RepoPilot", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError):
    logger.error("database_operation_failed")
    return JSONResponse({"detail": "Service temporarily unavailable"}, status_code=503)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    return JSONResponse({"detail": "Invalid request"}, status_code=422)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1 FROM outbox_events LIMIT 1"))
        with Redis.from_url(get_settings().redis_url, socket_connect_timeout=2,
                            socket_timeout=2) as redis:
            redis.ping()
    except Exception:
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ready"}
