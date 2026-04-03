
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routes import router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("TRACKSENSE_INIT_DB"):
        try:
            from app.database import init_db
            init_db()
            logger.info("Database tables initialised.")
        except Exception as exc:  # noqa: BLE001
            logger.warning("DB init skipped — %s", exc)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="TrackSense",
        description="RFID-based horse racing intelligence platform",
        version="3.0.0",
        lifespan=lifespan,
    )
    app.include_router(router)
    return app


app = create_app()