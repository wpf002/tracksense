
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

    try:
        from app.database import SessionLocal
        from app.models import User
        from app import crud

        db = SessionLocal()
        try:
            if db.query(User).count() == 0:
                crud.create_user(db, "admin", "tracksense", "admin", "TrackSense Admin")
                print("[startup] Default admin created: admin / tracksense")
                print("[startup] CHANGE THIS PASSWORD before production use.")
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Admin user creation skipped — %s", exc)

    try:
        from app.database import SessionLocal
        from app.models import GateRecord, VenueRecord
        from app.gate_registry import registry

        db = SessionLocal()
        try:
            venues = db.query(VenueRecord).all()
            for venue in venues:
                registry.create_venue(venue.venue_id, venue.name, venue.total_distance_m)
                gates = db.query(GateRecord).filter_by(venue_id=venue.venue_id).all()
                for gate in gates:
                    registry.add_gate(
                        venue.venue_id, gate.reader_id, gate.name,
                        gate.distance_m, gate.is_finish,
                    )
            if venues:
                logger.info("GateRegistry hydrated — %d venue(s) loaded.", len(venues))
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("GateRegistry hydration skipped — %s", exc)

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