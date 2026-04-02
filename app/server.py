
from fastapi import FastAPI
from app.routes import router

def create_app() -> FastAPI:
    app = FastAPI(
        title="TrackSense",
        description="RFID-based horse race finish-line engine",
        version="1.0.0",
    )
    app.include_router(router)
    return app

app = create_app()