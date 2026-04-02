
import asyncio
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from typing import Optional

from app.gate_registry import registry
from app.race_tracker import (
    RaceTracker, HorseEntry,
    get_tracker, set_tracker,
)
from app.websocket_manager import ws_manager

router = APIRouter()


# ------------------------------------------------------------------ #
# Request models
# ------------------------------------------------------------------ #

class CreateVenueRequest(BaseModel):
    venue_id: str = Field(..., description="Short unique ID e.g. 'FLEMINGTON'")
    name: str = Field(..., description="Human-readable name e.g. 'Flemington Racecourse'")
    total_distance_m: float = Field(..., description="Track distance in metres e.g. 1609")


class AddGateRequest(BaseModel):
    reader_id: str = Field(..., description="Must match reader_id sent in tag submissions e.g. 'GATE-START'")
    name: str = Field(..., description="Human-readable e.g. 'Start', 'Furlong 3', 'Finish'")
    distance_m: float = Field(..., description="Distance from start in metres")
    is_finish: bool = Field(False, description="True for the finish line gate")


class HorseRegistration(BaseModel):
    horse_id: str = Field(..., description="UHF chip EPC")
    display_name: str
    saddle_cloth: str


class RegisterRequest(BaseModel):
    venue_id: str = Field(..., description="Which venue this race is at")
    horses: list[HorseRegistration]


class TagSubmitRequest(BaseModel):
    tag_id: str = Field(..., description="UHF chip EPC")
    reader_id: str = Field(..., description="Which gate fired this read")


# ------------------------------------------------------------------ #
# Health
# ------------------------------------------------------------------ #

@router.get("/health")
def health():
    return {
        "ok": True,
        "service": "tracksense",
        "version": "2.0.0",
        "ws_connections": ws_manager.connection_count(),
    }


# ------------------------------------------------------------------ #
# Venue management
# ------------------------------------------------------------------ #

@router.post("/venues")
def create_venue(req: CreateVenueRequest):
    result = registry.create_venue(
        venue_id=req.venue_id.strip().upper(),
        name=req.name,
        total_distance_m=req.total_distance_m,
    )
    if not result["ok"]:
        raise HTTPException(409, result["error"])
    return result


@router.get("/venues")
def list_venues():
    return {"venues": registry.list_venues()}


@router.get("/venues/{venue_id}")
def get_venue(venue_id: str):
    venue_id = venue_id.upper()
    result = registry.list_gates(venue_id)
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    v = registry.get_venue(venue_id)
    assert v is not None  # list_gates already confirmed it exists
    return {
        "venue_id": v.venue_id,
        "name": v.name,
        "total_distance_m": v.total_distance_m,
        "gates": result["gates"],
    }


@router.delete("/venues/{venue_id}")
def delete_venue(venue_id: str):
    result = registry.delete_venue(venue_id.upper())
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.post("/venues/{venue_id}/gates")
def add_gate(venue_id: str, req: AddGateRequest):
    result = registry.add_gate(
        venue_id=venue_id.upper(),
        reader_id=req.reader_id.strip().upper(),
        name=req.name,
        distance_m=req.distance_m,
        is_finish=req.is_finish,
    )
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.delete("/venues/{venue_id}/gates/{reader_id}")
def remove_gate(venue_id: str, reader_id: str):
    result = registry.remove_gate(venue_id.upper(), reader_id.upper())
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


# ------------------------------------------------------------------ #
# Race management
# ------------------------------------------------------------------ #

@router.post("/race/register")
def register_horses(req: RegisterRequest):
    if not req.horses:
        raise HTTPException(400, "Must provide at least one horse")

    ids = [h.horse_id.strip().upper() for h in req.horses]
    if len(ids) != len(set(ids)):
        raise HTTPException(400, "Duplicate horse_id values in registration")

    venue_id = req.venue_id.strip().upper()
    if not registry.get_venue(venue_id):
        raise HTTPException(404, f"Venue '{venue_id}' not found. Create it first via POST /venues")

    entries = [
        HorseEntry(
            horse_id=h.horse_id.strip().upper(),
            display_name=h.display_name,
            saddle_cloth=h.saddle_cloth,
        )
        for h in req.horses
    ]

    t = RaceTracker(
        venue_id=venue_id,
        on_gate_event=ws_manager.broadcast_gate_event,
    )
    result = t.register_horses(entries)
    if not result["ok"]:
        raise HTTPException(400, result["error"])

    set_tracker(t)
    return result


@router.post("/race/arm")
def arm_race():
    t = get_tracker()
    if not t:
        raise HTTPException(400, "No race registered. POST /race/register first.")
    result = t.arm()
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.post("/race/reset")
def reset_race():
    set_tracker(None)
    return {"ok": True, "reset": True}


# ------------------------------------------------------------------ #
# Tag submission — hot path
# ------------------------------------------------------------------ #

@router.post("/tags/submit")
def submit_tag(req: TagSubmitRequest):
    t = get_tracker()
    if not t:
        return {"ok": False, "reason": "no_active_race"}
    return t.submit_tag(req.tag_id, req.reader_id)


# ------------------------------------------------------------------ #
# Race reads
# ------------------------------------------------------------------ #

@router.get("/race/status")
def race_status():
    t = get_tracker()
    if not t:
        return {"status": "idle", "message": "No active race"}
    return t.get_status()


@router.get("/race/finish-order")
def finish_order():
    t = get_tracker()
    if not t:
        return {"status": "idle", "results": []}
    return t.get_finish_order()


@router.get("/race/state")
def race_state():
    """
    Full race state — all horses, all gate events, all sectional times and speeds.
    Primary data endpoint for Phase 2.
    """
    t = get_tracker()
    if not t:
        return {"status": "idle", "message": "No active race"}
    return t.get_race_state()


# ------------------------------------------------------------------ #
# WebSocket — live race feed
# ------------------------------------------------------------------ #

@router.websocket("/ws/race")
async def race_feed(websocket: WebSocket):
    """
    Connect to receive live gate events as horses pass through each gate.

    Message format:
    {
      "type": "gate_event",
      "data": {
        "tag_id": "...",
        "display_name": "Thunderstrike",
        "gate_name": "Furlong 3",
        "distance_m": 603.0,
        "elapsed_ms": 34521,
        "elapsed_str": "0:34.521",
        "is_finish": false,
        ...
      }
    }
    """
    ws_manager.set_loop(asyncio.get_event_loop())
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)