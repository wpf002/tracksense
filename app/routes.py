"""
routes.py

REST API for TrackSense.

Endpoints:
  POST /race/register      - Register horse field for a race
  POST /race/arm           - Arm (re-use registered horses, clear results)
  POST /race/reset         - Full reset
  POST /tags/submit        - Submit a tag read (core hot path)
  GET  /race/status        - Quick status check
  GET  /race/finish-order  - Full results with splits
  GET  /health             - Liveness check
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.race_state import race, HorseEntry

router = APIRouter()


# ------------------------------------------------------------------ #
# Request / Response models
# ------------------------------------------------------------------ #

class HorseRegistration(BaseModel):
    horse_id: str = Field(..., description="Must match the RFID tag ID exactly")
    display_name: str
    saddle_cloth: str = Field(..., description="Race number on saddle cloth, e.g. '7'")


class RegisterRequest(BaseModel):
    horses: list[HorseRegistration]


class TagSubmitRequest(BaseModel):
    tag_id: str = Field(..., description="Raw tag ID from reader")
    reader_id: Optional[str] = Field(None, description="Which reader submitted this (future multi-reader support)")


# ------------------------------------------------------------------ #
# Routes
# ------------------------------------------------------------------ #

@router.get("/health")
def health():
    return {"ok": True, "service": "tracksense"}


@router.post("/race/register")
def register_horses(req: RegisterRequest):
    """
    Register the field. Call this before arming.
    Wipes any existing state including previous results.
    """
    if not req.horses:
        raise HTTPException(400, "Must provide at least one horse")

    entries = [
        HorseEntry(
            horse_id=h.horse_id.strip().upper(),
            display_name=h.display_name,
            saddle_cloth=h.saddle_cloth,
        )
        for h in req.horses
    ]

    # Check for duplicate horse IDs
    ids = [e.horse_id for e in entries]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Duplicate horse_id values in registration")

    result = race.register_horses(entries)
    if not result["ok"]:
        raise HTTPException(409, result["error"])
    return result


@router.post("/race/arm")
def arm_race():
    """
    Arm the race. Clears previous results but keeps horse registration.
    Use this to re-run the same field without re-registering.
    """
    result = race.arm()
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.post("/race/reset")
def reset_race():
    """Full wipe. Clears horses, results, everything."""
    return race.reset()


@router.post("/tags/submit")
def submit_tag(req: TagSubmitRequest):
    """
    Hot path. Called by the mock reader and will be called by hardware readers.
    Returns immediately with position info or rejection reason.
    """
    result = race.submit_tag(req.tag_id)

    if not result["ok"] and result.get("reason") == "unknown_tag":
        # Don't 400 here — unknown tags happen with real hardware (adjacent tags,
        # stray reads). Log and return 200 so the reader keeps going.
        return {"ok": False, "reason": "unknown_tag", "tag_id": req.tag_id}

    return result


@router.get("/race/status")
def race_status():
    return race.get_status()


@router.get("/race/finish-order")
def finish_order():
    return race.get_finish_order()
