
import asyncio
import random
import threading
import time
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from app import gatesmart

from app.gate_registry import registry
from app.race_tracker import (
    RaceTracker, HorseEntry,
    get_tracker, set_tracker,
)
from app.websocket_manager import ws_manager
from app.database import get_db
from app import crud
from app.auth import create_access_token, decode_token
from app.models import User
from app.api_keys_router import require_jwt_or_api_key

router = APIRouter()

# ------------------------------------------------------------------ #
# Auth dependency
# ------------------------------------------------------------------ #

_security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = crud.get_user_by_username(db, username)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


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
        "version": "3.0.0",
        "ws_connections": ws_manager.connection_count(),
    }


# ------------------------------------------------------------------ #
# Auth request models
# ------------------------------------------------------------------ #

class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    full_name: Optional[str] = None


class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    full_name: Optional[str] = None
    active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ------------------------------------------------------------------ #
# Auth helpers
# ------------------------------------------------------------------ #

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return current_user


# ------------------------------------------------------------------ #
# Auth endpoints
# ------------------------------------------------------------------ #

@router.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
    }


@router.post("/auth/refresh")
def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
):
    """
    Exchange a valid (non-expired) Bearer token for a fresh one.
    Returns HTTP 401 if the token is expired or invalid.
    """
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    username = payload.get("sub")
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    new_token = create_access_token({"sub": username})
    return {"access_token": new_token, "token_type": "bearer"}


@router.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "role": current_user.role,
        "full_name": current_user.full_name,
    }


@router.post("/auth/register")
def register_user(
    req: CreateUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    if crud.get_user_by_username(db, req.username):
        raise HTTPException(status_code=409, detail=f"Username '{req.username}' already exists")
    user = crud.create_user(db, req.username, req.password, req.role, req.full_name)
    return {"ok": True, "username": user.username}


@router.post("/auth/change-password")
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    from app.auth import verify_password
    if not verify_password(req.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    crud.reset_password(db, current_user.id, req.new_password)
    return {"ok": True}


# ------------------------------------------------------------------ #
# Admin — user management
# ------------------------------------------------------------------ #

@router.get("/admin/users")
def admin_list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = crud.list_users(db)
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "full_name": u.full_name,
            "active": u.active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.patch("/admin/users/{user_id}")
def admin_update_user(
    user_id: int,
    req: UpdateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        if req.role is not None and req.role != current_user.role:
            raise HTTPException(status_code=400, detail="Cannot change your own role")
        if req.active is False:
            raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    user = crud.update_user(db, user_id, **updates)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    crud.write_audit_log(db, current_user, "update", "user", str(user_id), updates)
    return {"ok": True, "username": user.username, "role": user.role, "active": user.active}


@router.post("/admin/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    req: ResetPasswordRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    ok = crud.reset_password(db, user_id, req.new_password)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True}


@router.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    ok = crud.delete_user(db, user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    crud.write_audit_log(db, current_user, "delete", "user", str(user_id), None)
    return {"ok": True}


@router.get("/admin/audit-log")
def get_audit_log(
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    limit: int = 100,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    limit = min(limit, 500)
    entries = crud.list_audit_log(db, target_type=target_type, target_id=target_id, limit=limit)
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "username": e.username,
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "detail": e.detail,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
        }
        for e in entries
    ]


# ------------------------------------------------------------------ #
# Admin — GateSmart horse mapping
# ------------------------------------------------------------------ #

class MapToGatesmartRequest(BaseModel):
    racing_api_horse_id: str


@router.post("/admin/horses/{epc}/map-to-gatesmart")
async def map_horse_to_gatesmart(
    epc: str,
    req: MapToGatesmartRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    epc = epc.strip().upper()
    horse = crud.get_horse(db, epc)
    if not horse:
        raise HTTPException(404, f"Horse '{epc}' not found")
    ok = await gatesmart.post_horse_mapping(epc, horse.name, req.racing_api_horse_id)
    if ok:
        return {"mapped": True, "epc": epc, "racing_api_horse_id": req.racing_api_horse_id}
    raise HTTPException(502, {"error": "GateSmart mapping failed"})


# ------------------------------------------------------------------ #
# Webhook endpoints
# ------------------------------------------------------------------ #

class CreateWebhookRequest(BaseModel):
    name: str
    url: str
    secret: str
    event_type: str = "race.finished"


class UpdateWebhookRequest(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    secret: Optional[str] = None
    active: Optional[bool] = None


@router.get("/webhooks")
def list_webhooks(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    subs = crud.list_webhooks(db)
    return [
        {
            "id": s.id,
            "name": s.name,
            "url": s.url,
            "event_type": s.event_type,
            "active": s.active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "created_by": s.created_by,
        }
        for s in subs
    ]


@router.post("/webhooks")
def create_webhook(
    req: CreateWebhookRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    sub = crud.create_webhook(
        db,
        name=req.name,
        url=req.url,
        secret=req.secret,
        event_type=req.event_type,
        created_by=current_user.username,
    )
    crud.write_audit_log(db, current_user, "create", "webhook", str(sub.id), {"name": req.name, "url": req.url})
    return {"ok": True, "id": sub.id, "name": sub.name, "url": sub.url}


@router.get("/webhooks/deliveries/failures")
def list_failed_deliveries(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Last 50 failed deliveries across all subscriptions."""
    records = crud.get_failed_deliveries(db)
    return [
        {
            "id": r.id,
            "subscription_id": r.subscription_id,
            "attempted_at": r.attempted_at.isoformat() if r.attempted_at else None,
            "response_code": r.response_code,
            "success": r.success,
            "attempt_number": r.attempt_number,
            "error_message": r.error_message,
        }
        for r in records
    ]


@router.patch("/webhooks/{webhook_id}")
def update_webhook(
    webhook_id: int,
    req: UpdateWebhookRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    sub = crud.update_webhook(db, webhook_id, **updates)
    if not sub:
        raise HTTPException(status_code=404, detail="Webhook not found")
    return {"ok": True}


@router.delete("/webhooks/{webhook_id}")
def delete_webhook(
    webhook_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    ok = crud.delete_webhook(db, webhook_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Webhook not found")
    crud.write_audit_log(db, current_user, "delete", "webhook", str(webhook_id), None)
    return {"ok": True}


@router.post("/webhooks/{webhook_id}/test")
def test_webhook(
    webhook_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.webhooks import deliver_webhook
    sub = crud.get_webhook(db, webhook_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Webhook not found")

    test_payload = {
        "event": "race.finished.test",
        "timestamp": __import__("time").time(),
        "venue_id": "TEST",
        "race_summary": {
            "total_runners": 1,
            "total_finished": 1,
            "elapsed_ms": 60000,
            "elapsed_str": "1:00.000",
        },
        "results": [],
    }

    success = deliver_webhook(sub, test_payload)
    if success:
        return {"ok": True, "status_code": 200}
    return {"ok": False, "error": "Delivery failed — check URL and server logs"}


@router.get("/webhooks/{webhook_id}/deliveries")
def list_webhook_deliveries(
    webhook_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Last 50 delivery records for a subscription, newest first."""
    sub = crud.get_webhook(db, webhook_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Webhook not found")
    records = crud.get_webhook_deliveries(db, webhook_id)
    return [
        {
            "id": r.id,
            "attempted_at": r.attempted_at.isoformat() if r.attempted_at else None,
            "response_code": r.response_code,
            "success": r.success,
            "attempt_number": r.attempt_number,
            "error_message": r.error_message,
        }
        for r in records
    ]


# ------------------------------------------------------------------ #
# Venue management
# ------------------------------------------------------------------ #

@router.post("/venues")
def create_venue(req: CreateVenueRequest, _: User = Depends(get_current_user)):
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
def delete_venue(venue_id: str, _: User = Depends(get_current_user)):
    result = registry.delete_venue(venue_id.upper())
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.post("/venues/{venue_id}/gates")
def add_gate(venue_id: str, req: AddGateRequest, _: User = Depends(get_current_user)):
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
def remove_gate(venue_id: str, reader_id: str, _: User = Depends(get_current_user)):
    result = registry.remove_gate(venue_id.upper(), reader_id.upper())
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


# ------------------------------------------------------------------ #
# Race management
# ------------------------------------------------------------------ #

@router.post("/race/register")
def register_horses(
    req: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
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

    # Fire GateSmart horse mapping for any horse that has a racing_api_horse_id
    for entry in entries:
        horse = crud.get_horse(db, entry.horse_id)
        if horse and horse.racing_api_horse_id:
            background_tasks.add_task(
                gatesmart.post_horse_mapping,
                epc=horse.epc,
                horse_name=horse.name,
                racing_api_horse_id=horse.racing_api_horse_id,
            )

    return result


@router.post("/race/arm")
def arm_race(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = get_tracker()
    if not t:
        raise HTTPException(400, "No race registered. POST /race/register first.")
    result = t.arm()
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    crud.write_audit_log(db, current_user, "arm", "race", t.venue_id, None)
    return result


@router.post("/race/reset")
def reset_race(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    t = get_tracker()
    venue_id = t.venue_id if t else "none"
    set_tracker(None)
    crud.write_audit_log(db, current_user, "reset", "race", venue_id, None)
    return {"ok": True, "reset": True}


@router.post("/race/simulate")
def simulate_race(_: User = Depends(get_current_user)):
    """
    Arm the registered race and run a mock simulation using the registered
    field and venue gates. Horses are assigned speed profiles randomly and
    driven through each gate with realistic timing in background threads.
    """
    t = get_tracker()
    if not t:
        raise HTTPException(400, "No race registered. Use Race Builder first.")
    if t.status not in ("idle", "armed"):
        raise HTTPException(400, f"Cannot simulate in '{t.status}' state. Reset first.")

    arm_result = t.arm()
    if not arm_result["ok"]:
        raise HTTPException(400, arm_result["error"])

    venue = registry.get_venue(t.venue_id)
    if not venue:
        raise HTTPException(400, f"Venue '{t.venue_id}' not found in registry.")

    gates = sorted(venue.gates, key=lambda g: g.distance_m)
    if not gates:
        raise HTTPException(400, "Venue has no gates configured.")

    horses = list(t.registered_horses.values())

    # Speed profiles: multipliers per gate segment
    profiles = {
        "pacer":    [0.92, 0.96, 1.02, 1.08, 1.12],
        "closer":   [1.10, 1.05, 1.00, 0.95, 0.88],
        "midfield": [1.00, 1.00, 1.00, 1.00, 1.00],
    }

    # Base time per segment scales with distance; ~16s per 400m at race speed
    def segment_times(horse_index: int) -> list[float]:
        profile_name = random.choice(list(profiles.keys()))
        mults = profiles[profile_name]
        ability = random.uniform(0.95, 1.05)
        times = [0.0]
        cumulative = 0.0
        for i in range(len(gates) - 1):
            dist = gates[i + 1].distance_m - gates[i].distance_m
            base = dist / 25.0  # ~25 m/s ≈ 90 km/h
            mult = mults[i % len(mults)]
            seg = base * mult * ability + random.uniform(-0.3, 0.3)
            cumulative += max(seg, 0.5)
            times.append(cumulative)
        return times

    pause_ev = t._sim_pause
    stop_ev  = t._sim_stop

    def run_horse(horse, times: list[float], race_start: float):
        for i, gate in enumerate(gates):
            target = race_start + times[i]

            # Sleep toward target in 50 ms slices, honouring pause and stop
            while True:
                if stop_ev.is_set():
                    return
                pause_ev.wait()          # blocks here while paused
                if stop_ev.is_set():     # re-check after unblocking
                    return
                remaining = target - time.time()
                if remaining <= 0:
                    break
                time.sleep(min(0.05, remaining))

            if stop_ev.is_set():
                return

            t.submit_tag(horse.horse_id, gate.reader_id)
            # Simulate 1–3 duplicate reads in the transit window
            for _ in range(random.randint(1, 3)):
                time.sleep(random.uniform(0.001, 0.008))
                t.submit_tag(horse.horse_id, gate.reader_id)

    race_start = time.time() + 0.1  # small buffer so all threads are ready
    threads = []
    for idx, horse in enumerate(horses):
        times = segment_times(idx)
        th = threading.Thread(target=run_horse, args=(horse, times, race_start), daemon=True)
        threads.append(th)

    for th in threads:
        th.start()

    return {"ok": True, "simulating": True, "runners": len(horses), "gates": len(gates)}


@router.post("/race/simulate/pause")
def pause_simulation(_: User = Depends(get_current_user)):
    t = get_tracker()
    if not t:
        raise HTTPException(400, "No active race.")
    result = t.pause()
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


@router.post("/race/simulate/resume")
def resume_simulation(_: User = Depends(get_current_user)):
    t = get_tracker()
    if not t:
        raise HTTPException(400, "No active race.")
    result = t.resume()
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    return result


# ------------------------------------------------------------------ #
# Tag submission — hot path
# ------------------------------------------------------------------ #

@router.post("/tags/submit")
def submit_tag(req: TagSubmitRequest, _: User = Depends(get_current_user)):
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
    racing_api_horse_id: Optional[str] = Field(None, description="GateSmart / racing API horse ID for automatic mapping")


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
    name: Optional[str] = Field(None, description="Human-readable race name e.g. 'The Flemington Cup'")
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
# Phase 5A request models
# ------------------------------------------------------------------ #

class AddWorkoutRequest(BaseModel):
    workout_date: str = Field(..., description="ISO date e.g. '2026-04-01'")
    distance_m: float
    surface: Optional[str] = None
    duration_ms: Optional[int] = None
    track_condition: Optional[str] = None
    trainer_name: Optional[str] = None
    notes: Optional[str] = None


class CheckInRequest(BaseModel):
    scanned_by: Optional[str] = None
    location: Optional[str] = None
    race_id: Optional[int] = None
    notes: Optional[str] = None


class TestBarnCheckInRequest(BaseModel):
    checkin_by: Optional[str] = None
    race_id: Optional[int] = None
    sample_id: Optional[str] = None
    notes: Optional[str] = None


class TestBarnCheckOutRequest(BaseModel):
    checkout_by: Optional[str] = None
    result: str = "Clear"
    notes: Optional[str] = None


# ------------------------------------------------------------------ #
# Phase 3 — Horse identity platform
# ------------------------------------------------------------------ #

@router.post("/horses")
def create_horse(req: CreateHorseRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = crud.create_horse(
        db,
        epc=req.epc.strip().upper(),
        name=req.name,
        breed=req.breed,
        date_of_birth=req.date_of_birth,
        implant_date=req.implant_date,
        implant_vet=req.implant_vet,
        racing_api_horse_id=req.racing_api_horse_id,
    )
    if not result["ok"]:
        raise HTTPException(409, result["error"])
    crud.write_audit_log(db, current_user, "create", "horse", req.epc.strip().upper(), {"name": req.name})
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
def get_horse(epc: str, db: Session = Depends(get_db), _auth=Depends(require_jwt_or_api_key)):
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
        "racing_api_horse_id": horse.racing_api_horse_id,
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
def horse_career(epc: str, db: Session = Depends(get_db), _auth=Depends(require_jwt_or_api_key)):
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
def add_vet_record(epc: str, req: AddVetRecordRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
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
    crud.write_audit_log(db, current_user, "vet_record", "horse", epc.strip().upper(),
                         {"event_type": req.event_type, "event_date": req.event_date})
    return result


# ------------------------------------------------------------------ #
# Phase 3 — Race persistence
# ------------------------------------------------------------------ #

@router.post("/races")
def create_race(req: CreateRaceRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        race_date = datetime.fromisoformat(req.race_date)
    except ValueError:
        raise HTTPException(400, f"Invalid race_date format: '{req.race_date}'. Use ISO 8601.")
    result = crud.create_race(
        db,
        venue_id=req.venue_id.strip().upper(),
        name=req.name,
        race_date=race_date,
        distance_m=req.distance_m,
        surface=req.surface,
        conditions=req.conditions,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    crud.write_audit_log(db, current_user, "create", "race", str(result["race_id"]),
                         {"venue_id": req.venue_id, "name": req.name, "distance_m": req.distance_m})
    return result


@router.get("/races")
def list_races(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    races = crud.list_races(db, skip=skip, limit=limit)
    return {
        "races": [
            {
                "race_id": r.id,
                "name": r.name,
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
        "name": race.name,
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


@router.get("/races/{race_id}/results")
def get_race_results(race_id: int, db: Session = Depends(get_db), _auth=Depends(require_jwt_or_api_key)):
    race = crud.get_race(db, race_id)
    if not race:
        raise HTTPException(404, f"Race {race_id} not found")
    return {
        "race_id": race.id,
        "status": race.status,
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
def persist_race(
    race_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Persist the active in-memory tracker's results to the database race record.
    The race record must already exist (created via POST /races).
    Horses must already exist in the horses table (POST /horses).
    This operation is idempotent — safe to call multiple times.

    After a successful persist, fires the GateSmart race webhook as a
    background task so the HTTP response is not blocked.
    """
    t = get_tracker()
    if not t:
        raise HTTPException(400, "No active race tracker. Register a race first.")
    tracker_state = t.get_race_state()
    result = crud.persist_race_results(db, race_id, tracker_state)
    if not result["ok"]:
        raise HTTPException(404, result["error"])

    # Build and schedule GateSmart webhook without blocking the response
    race = crud.get_race(db, race_id)
    if race:
        venue_name = race.venue.name if race.venue else race.venue_id
        distance_furlongs = round(race.distance_m / 201.168, 4)
    else:
        venue_name = "Unknown"
        distance_furlongs = 0.0

    completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gs_results = gatesmart.build_gatesmart_results(tracker_state)
    payload = gatesmart.build_race_webhook_payload(
        race_id=str(race_id),
        venue_name=venue_name,
        race_name=race.name if race and race.name else f"Race {race_id}",
        distance_furlongs=distance_furlongs,
        completed_at=completed_at,
        results=gs_results,
    )
    background_tasks.add_task(gatesmart.fire_race_webhook, payload)
    crud.write_audit_log(db, current_user, "persist", "race", str(race_id),
                         {"persisted": result.get("persisted")})

    return result


# ------------------------------------------------------------------ #
# Phase 5A — Welfare & operational workflows
# ------------------------------------------------------------------ #

@router.post("/horses/{epc}/workouts")
def add_workout(epc: str, req: AddWorkoutRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    result = crud.add_workout(
        db,
        epc=epc.strip().upper(),
        workout_date=req.workout_date,
        distance_m=req.distance_m,
        surface=req.surface,
        duration_ms=req.duration_ms,
        track_condition=req.track_condition,
        trainer_name=req.trainer_name,
        notes=req.notes,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.get("/horses/{epc}/workouts")
def get_workouts(epc: str, db: Session = Depends(get_db)):
    epc = epc.strip().upper()
    if not crud.get_horse(db, epc):
        raise HTTPException(404, f"Horse '{epc}' not found")
    records = crud.get_workouts(db, epc)
    return {
        "epc": epc,
        "workouts": [
            {
                "id": r.id,
                "workout_date": r.workout_date,
                "distance_m": r.distance_m,
                "surface": r.surface,
                "duration_ms": r.duration_ms,
                "track_condition": r.track_condition,
                "trainer_name": r.trainer_name,
                "notes": r.notes,
            }
            for r in records
        ],
    }


@router.post("/horses/{epc}/checkins")
def add_checkin(epc: str, req: CheckInRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    result = crud.add_checkin(
        db,
        epc=epc.strip().upper(),
        scanned_by=req.scanned_by,
        location=req.location,
        race_id=req.race_id,
        notes=req.notes,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.get("/horses/{epc}/checkins")
def get_checkins(epc: str, race_id: Optional[int] = None, db: Session = Depends(get_db)):
    epc = epc.strip().upper()
    if not crud.get_horse(db, epc):
        raise HTTPException(404, f"Horse '{epc}' not found")
    records = crud.get_checkins(db, epc, race_id=race_id)
    return {
        "epc": epc,
        "checkins": [
            {
                "id": r.id,
                "race_id": r.race_id,
                "scanned_at": r.scanned_at.isoformat() if r.scanned_at else None,
                "scanned_by": r.scanned_by,
                "location": r.location,
                "verified": r.verified,
                "notes": r.notes,
            }
            for r in records
        ],
    }


@router.post("/horses/{epc}/testbarn/checkin")
def test_barn_checkin(epc: str, req: TestBarnCheckInRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    result = crud.test_barn_checkin(
        db,
        epc=epc.strip().upper(),
        checkin_by=req.checkin_by,
        race_id=req.race_id,
        sample_id=req.sample_id,
        notes=req.notes,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.post("/testbarn/{record_id}/checkout")
def test_barn_checkout(record_id: int, req: TestBarnCheckOutRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    result = crud.test_barn_checkout(
        db,
        record_id=record_id,
        checkout_by=req.checkout_by,
        result=req.result,
        notes=req.notes,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.get("/horses/{epc}/testbarn")
def get_test_barn_records(epc: str, db: Session = Depends(get_db)):
    epc = epc.strip().upper()
    if not crud.get_horse(db, epc):
        raise HTTPException(404, f"Horse '{epc}' not found")
    records = crud.get_test_barn_records(db, epc)
    return {
        "epc": epc,
        "test_barn_records": [
            {
                "id": r.id,
                "race_id": r.race_id,
                "checkin_at": r.checkin_at.isoformat() if r.checkin_at else None,
                "checkin_by": r.checkin_by,
                "checkout_at": r.checkout_at.isoformat() if r.checkout_at else None,
                "checkout_by": r.checkout_by,
                "sample_id": r.sample_id,
                "result": r.result,
                "notes": r.notes,
            }
            for r in records
        ],
    }