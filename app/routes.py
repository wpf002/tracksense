
import asyncio
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from app.gate_registry import registry
from app.race_tracker import (
    RaceTracker, HorseEntry,
    get_tracker, set_tracker,
)
from app.websocket_manager import ws_manager
from app.database import get_db
from app import crud

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


# ------------------------------------------------------------------ #
# Phase 3 request models
# ------------------------------------------------------------------ #

class CreateHorseRequest(BaseModel):
    epc: str = Field(..., description="UHF chip EPC — permanent identity key")
    name: str
    breed: Optional[str] = None
    date_of_birth: Optional[str] = Field(None, description="ISO date e.g. '2018-09-14'")
    implant_date: Optional[str] = Field(None, description="ISO date of implant procedure")
    implant_vet: Optional[str] = None


class AddOwnerRequest(BaseModel):
    owner_name: str
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class AddTrainerRequest(BaseModel):
    trainer_name: str
    from_date: Optional[str] = None
    to_date: Optional[str] = None


class CreateRaceRequest(BaseModel):
    venue_id: str
    race_date: str = Field(..., description="ISO datetime e.g. '2026-04-02T14:30:00'")
    distance_m: float
    surface: str = "turf"
    conditions: Optional[str] = None


class AddVetRecordRequest(BaseModel):
    event_date: str = Field(..., description="ISO date e.g. '2026-04-02'")
    event_type: str = Field(..., description="e.g. 'implant', 'clearance', 'treatment'")
    notes: Optional[str] = None
    vet_name: Optional[str] = None


# ------------------------------------------------------------------ #
# Phase 3 — Horse identity platform
# ------------------------------------------------------------------ #

@router.post("/horses")
def create_horse(req: CreateHorseRequest, db: Session = Depends(get_db)):
    result = crud.create_horse(
        db,
        epc=req.epc.strip().upper(),
        name=req.name,
        breed=req.breed,
        date_of_birth=req.date_of_birth,
        implant_date=req.implant_date,
        implant_vet=req.implant_vet,
    )
    if not result["ok"]:
        raise HTTPException(409, result["error"])
    return result


@router.get("/horses")
def list_horses(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    horses = crud.list_horses(db, skip=skip, limit=limit)
    return {
        "horses": [
            {
                "epc": h.epc,
                "name": h.name,
                "breed": h.breed,
                "date_of_birth": h.date_of_birth,
                "implant_date": h.implant_date,
                "implant_vet": h.implant_vet,
            }
            for h in horses
        ]
    }


# Note: /horses/compare/{epc1}/vs/{epc2} is defined before /horses/{epc}
# to prevent FastAPI from matching "compare" as an EPC value.
@router.get("/horses/compare/{epc1}/vs/{epc2}")
def compare_horses(epc1: str, epc2: str, db: Session = Depends(get_db)):
    epc1 = epc1.strip().upper()
    epc2 = epc2.strip().upper()
    if not crud.get_horse(db, epc1):
        raise HTTPException(404, f"Horse '{epc1}' not found")
    if not crud.get_horse(db, epc2):
        raise HTTPException(404, f"Horse '{epc2}' not found")
    return crud.get_head_to_head(db, epc1, epc2)


@router.get("/horses/{epc}")
def get_horse(epc: str, db: Session = Depends(get_db)):
    horse = crud.get_horse(db, epc.strip().upper())
    if not horse:
        raise HTTPException(404, f"Horse '{epc}' not found")
    return {
        "epc": horse.epc,
        "name": horse.name,
        "breed": horse.breed,
        "date_of_birth": horse.date_of_birth,
        "implant_date": horse.implant_date,
        "implant_vet": horse.implant_vet,
        "created_at": horse.created_at.isoformat() if horse.created_at else None,
        "owners": [
            {"owner_name": o.owner_name, "from_date": o.from_date, "to_date": o.to_date}
            for o in horse.owners
        ],
        "trainers": [
            {"trainer_name": t.trainer_name, "from_date": t.from_date, "to_date": t.to_date}
            for t in horse.trainers
        ],
    }


@router.get("/horses/{epc}/career")
def horse_career(epc: str, db: Session = Depends(get_db)):
    epc = epc.strip().upper()
    if not crud.get_horse(db, epc):
        raise HTTPException(404, f"Horse '{epc}' not found")
    return {"epc": epc, "career": crud.get_career_history(db, epc)}


@router.get("/horses/{epc}/form")
def horse_form(epc: str, n: int = 5, db: Session = Depends(get_db)):
    epc = epc.strip().upper()
    if not crud.get_horse(db, epc):
        raise HTTPException(404, f"Horse '{epc}' not found")
    return {"epc": epc, "form": crud.get_form_guide(db, epc, n=n)}


@router.get("/horses/{epc}/sectionals")
def horse_sectionals(epc: str, db: Session = Depends(get_db)):
    epc = epc.strip().upper()
    if not crud.get_horse(db, epc):
        raise HTTPException(404, f"Horse '{epc}' not found")
    return {"epc": epc, "sectional_averages": crud.get_sectional_averages(db, epc)}


@router.get("/horses/{epc}/vet")
def get_vet_records(epc: str, db: Session = Depends(get_db)):
    epc = epc.strip().upper()
    if not crud.get_horse(db, epc):
        raise HTTPException(404, f"Horse '{epc}' not found")
    records = crud.get_vet_records(db, epc)
    return {
        "epc": epc,
        "vet_records": [
            {
                "id": r.id,
                "event_date": r.event_date,
                "event_type": r.event_type,
                "notes": r.notes,
                "vet_name": r.vet_name,
            }
            for r in records
        ],
    }


@router.post("/horses/{epc}/vet")
def add_vet_record(epc: str, req: AddVetRecordRequest, db: Session = Depends(get_db)):
    result = crud.add_vet_record(
        db,
        epc=epc.strip().upper(),
        event_date=req.event_date,
        event_type=req.event_type,
        notes=req.notes,
        vet_name=req.vet_name,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


# ------------------------------------------------------------------ #
# Phase 3 — Race persistence
# ------------------------------------------------------------------ #

@router.post("/races")
def create_race(req: CreateRaceRequest, db: Session = Depends(get_db)):
    try:
        race_date = datetime.fromisoformat(req.race_date)
    except ValueError:
        raise HTTPException(400, f"Invalid race_date format: '{req.race_date}'. Use ISO 8601.")
    result = crud.create_race(
        db,
        venue_id=req.venue_id.strip().upper(),
        race_date=race_date,
        distance_m=req.distance_m,
        surface=req.surface,
        conditions=req.conditions,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.get("/races")
def list_races(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    races = crud.list_races(db, skip=skip, limit=limit)
    return {
        "races": [
            {
                "race_id": r.id,
                "venue_id": r.venue_id,
                "race_date": r.race_date.isoformat() if r.race_date else None,
                "distance_m": r.distance_m,
                "surface": r.surface,
                "status": r.status,
            }
            for r in races
        ]
    }


@router.get("/races/{race_id}")
def get_race(race_id: int, db: Session = Depends(get_db)):
    race = crud.get_race(db, race_id)
    if not race:
        raise HTTPException(404, f"Race {race_id} not found")
    return {
        "race_id": race.id,
        "venue_id": race.venue_id,
        "race_date": race.race_date.isoformat() if race.race_date else None,
        "distance_m": race.distance_m,
        "surface": race.surface,
        "conditions": race.conditions,
        "status": race.status,
        "entries": [
            {"horse_epc": e.horse_epc, "saddle_cloth": e.saddle_cloth}
            for e in race.entries
        ],
        "results": [
            {
                "horse_epc": r.horse_epc,
                "finish_position": r.finish_position,
                "elapsed_ms": r.elapsed_ms,
            }
            for r in sorted(race.results, key=lambda r: r.finish_position)
        ],
    }


@router.post("/races/{race_id}/persist")
def persist_race(race_id: int, db: Session = Depends(get_db)):
    """
    Persist the active in-memory tracker's results to the database race record.
    The race record must already exist (created via POST /races).
    Horses must already exist in the horses table (POST /horses).
    This operation is idempotent — safe to call multiple times.
    """
    t = get_tracker()
    if not t:
        raise HTTPException(400, "No active race tracker. Register a race first.")
    tracker_state = t.get_race_state()
    result = crud.persist_race_results(db, race_id, tracker_state)
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result