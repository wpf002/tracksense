
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from app import gatesmart
from app.database import get_db
from app import crud
from app.identity import normalize_chip_id, is_valid_chip_id
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


# ------------------------------------------------------------------ #
# Health
# ------------------------------------------------------------------ #

@router.get("/health")
def health():
    return {
        "ok": True,
        "service": "tracksense",
        "version": "3.0.0",
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


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Super-admin: role=admin AND no tenant_id (platform-level user)."""
    if current_user.role != "admin" or current_user.tenant_id is not None:
        raise HTTPException(status_code=403, detail="Super-admin role required")
    return current_user


# ------------------------------------------------------------------ #
# Auth endpoints
# ------------------------------------------------------------------ #

@router.post("/auth/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = crud.authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({
        "sub": user.username,
        "role": user.role,
        "tenant_id": user.tenant_id,
    })
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username,
        "tenant_id": user.tenant_id,
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
    new_token = create_access_token({
        "sub": username,
        "role": payload.get("role"),
        "tenant_id": payload.get("tenant_id"),
    })
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
    users = crud.list_users(db, tenant_id=current_user.tenant_id)
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


@router.post("/admin/horses/{chip_id}/map-to-gatesmart")
async def map_horse_to_gatesmart(
    chip_id: str,
    req: MapToGatesmartRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    chip_id = chip_id.strip().upper()
    horse = crud.get_horse(db, chip_id)
    if not horse:
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    ok = await gatesmart.post_horse_mapping(chip_id, horse.name, req.racing_api_horse_id)
    if ok:
        return {"mapped": True, "chip_id": chip_id, "racing_api_horse_id": req.racing_api_horse_id}
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
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    subs = crud.list_webhooks(db, tenant_id=current_user.tenant_id)
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
def create_venue(
    req: CreateVenueRequest,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models import VenueRecord
    venue_id = req.venue_id.strip().upper()
    if db.get(VenueRecord, venue_id):
        raise HTTPException(409, f"Venue '{venue_id}' already exists")
    crud.upsert_venue(db, venue_id=venue_id, name=req.name, total_distance_m=req.total_distance_m)
    return {"ok": True, "venue_id": venue_id, "name": req.name, "total_distance_m": req.total_distance_m}


@router.get("/venues")
def list_venues(db: Session = Depends(get_db)):
    from app.models import VenueRecord
    venues = db.query(VenueRecord).order_by(VenueRecord.name).all()
    return {
        "venues": [
            {"venue_id": v.venue_id, "name": v.name, "total_distance_m": v.total_distance_m}
            for v in venues
        ]
    }


@router.get("/venues/{venue_id}")
def get_venue(venue_id: str, db: Session = Depends(get_db)):
    from app.models import VenueRecord
    venue_id = venue_id.upper()
    v = db.get(VenueRecord, venue_id)
    if not v:
        raise HTTPException(404, f"Venue '{venue_id}' not found")
    return {
        "venue_id": v.venue_id,
        "name": v.name,
        "total_distance_m": v.total_distance_m,
    }


@router.delete("/venues/{venue_id}")
def delete_venue(
    venue_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    venue_id = venue_id.upper()
    if not crud.delete_venue(db, venue_id):
        raise HTTPException(404, f"Venue '{venue_id}' not found")
    return {"ok": True, "deleted": venue_id}


# ------------------------------------------------------------------ #
# Phase 3 request models
# ------------------------------------------------------------------ #

class CreateHorseRequest(BaseModel):
    chip_id: str = Field(..., description="Jockey Club LF microchip ID — 15-digit ISO 11784/11785 FDX-B")
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
    rider_name: Optional[str] = None
    clocker_name: Optional[str] = None
    timekeeper_name: Optional[str] = None
    notes: Optional[str] = None


class CheckInRequest(BaseModel):
    scanned_by: Optional[str] = None
    location: Optional[str] = None
    race_id: Optional[int] = None
    notes: Optional[str] = None
    temperature_c: Optional[float] = Field(None, description="Thermal chip temperature reading in °C")


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
    chip_id = normalize_chip_id(req.chip_id)
    if not is_valid_chip_id(chip_id):
        raise HTTPException(400, "chip_id must be a 15-digit Jockey Club LF microchip ID (ISO 11784/11785)")
    result = crud.create_horse(
        db,
        chip_id=chip_id,
        name=req.name,
        breed=req.breed,
        date_of_birth=req.date_of_birth,
        implant_date=req.implant_date,
        implant_vet=req.implant_vet,
        racing_api_horse_id=req.racing_api_horse_id,
    )
    if not result["ok"]:
        raise HTTPException(409, result["error"])
    crud.write_audit_log(db, current_user, "create", "horse", chip_id, {"name": req.name})
    return result


@router.get("/horses")
def list_horses(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    horses = crud.list_horses(db, skip=skip, limit=limit, tenant_id=current_user.tenant_id)
    return {
        "horses": [
            {
                "chip_id": h.chip_id,
                "name": h.name,
                "breed": h.breed,
                "date_of_birth": h.date_of_birth,
                "current_trainer": next((t.trainer_name for t in h.trainers if not t.to_date), None),
                "current_owner": next((o.owner_name for o in h.owners if not o.to_date), None),
            }
            for h in horses
        ]
    }


# Note: /horses/compare/{chip_id1}/vs/{chip_id2} is defined before /horses/{chip_id}
# to prevent FastAPI from matching "compare" as a chip_id value.
@router.get("/horses/compare/{chip_id1}/vs/{chip_id2}")
def compare_horses(chip_id1: str, chip_id2: str, db: Session = Depends(get_db)):
    chip_id1 = chip_id1.strip().upper()
    chip_id2 = chip_id2.strip().upper()
    if not crud.get_horse(db, chip_id1):
        raise HTTPException(404, f"Horse '{chip_id1}' not found")
    if not crud.get_horse(db, chip_id2):
        raise HTTPException(404, f"Horse '{chip_id2}' not found")
    return crud.get_head_to_head(db, chip_id1, chip_id2)


@router.get("/horses/{chip_id}")
def get_horse(chip_id: str, db: Session = Depends(get_db), _auth=Depends(require_jwt_or_api_key)):
    horse = crud.get_horse(db, chip_id.strip().upper())
    if not horse:
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    return {
        "chip_id": horse.chip_id,
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


@router.get("/horses/{chip_id}/summary")
def horse_summary(chip_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """
    One-call scan lookup for the check-in screen: identity plus welfare/compliance
    flags, so an official scanning a chip sees who the horse is and anything that
    needs attention before recording the visit.
    """
    chip_id = chip_id.strip().upper()
    horse = crud.get_horse(db, chip_id)
    if not horse:
        raise HTTPException(404, f"Horse '{chip_id}' not found")

    current_owner = next((o.owner_name for o in horse.owners if not o.to_date), None)
    current_trainer = next((t.trainer_name for t in horse.trainers if not t.to_date), None)

    temps = crud.get_temperature_history(db, chip_id, limit=1)
    latest_temp = temps[0].temperature_c if temps else None
    temp_alert = None
    if latest_temp is not None:
        if latest_temp >= 39.0 or latest_temp <= 37.0:
            temp_alert = "red"
        elif latest_temp >= 38.5:
            temp_alert = "amber"
        else:
            temp_alert = "normal"

    workouts = crud.get_workouts(db, chip_id)
    test_barn = crud.get_test_barn_records(db, chip_id)
    vet_records = crud.get_vet_records(db, chip_id)

    return {
        "chip_id": horse.chip_id,
        "name": horse.name,
        "breed": horse.breed,
        "current_owner": current_owner,
        "current_trainer": current_trainer,
        "latest_temperature_c": latest_temp,
        "temperature_alert": temp_alert,
        "workout_count": len(workouts),
        "last_workout_date": workouts[0].workout_date if workouts else None,
        "open_test_barn": any(r.checkout_at is None for r in test_barn),
        "vet_record_count": len(vet_records),
    }


@router.get("/horses/{chip_id}/career")
def horse_career(chip_id: str, db: Session = Depends(get_db), _auth=Depends(require_jwt_or_api_key)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    return {"chip_id": chip_id, "career": crud.get_career_history(db, chip_id)}


@router.get("/horses/{chip_id}/form")
def horse_form(chip_id: str, n: int = 5, db: Session = Depends(get_db)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    return {"chip_id": chip_id, "form": crud.get_form_guide(db, chip_id, n=n)}


@router.get("/horses/{chip_id}/vet")
def get_vet_records(chip_id: str, db: Session = Depends(get_db)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    records = crud.get_vet_records(db, chip_id)
    return {
        "chip_id": chip_id,
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


@router.post("/horses/{chip_id}/vet")
def add_vet_record(chip_id: str, req: AddVetRecordRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = crud.add_vet_record(
        db,
        chip_id=chip_id.strip().upper(),
        event_date=req.event_date,
        event_type=req.event_type,
        notes=req.notes,
        vet_name=req.vet_name,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    crud.write_audit_log(db, current_user, "vet_record", "horse", chip_id.strip().upper(),
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
            {"horse_chip_id": e.horse_chip_id, "saddle_cloth": e.saddle_cloth}
            for e in race.entries
        ],
        "results": [
            {
                "horse_chip_id": r.horse_chip_id,
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
    # Join horse names and saddle cloths for readable results
    entries_by_chip = {e.horse_chip_id: e for e in race.entries}
    results_out = []
    for r in sorted(race.results, key=lambda r: r.finish_position):
        horse = crud.get_horse(db, r.horse_chip_id)
        entry = entries_by_chip.get(r.horse_chip_id)
        results_out.append({
            "horse_chip_id": r.horse_chip_id,
            "horse_name": horse.name if horse else None,
            "saddle_cloth": entry.saddle_cloth if entry else None,
            "jockey": entry.jockey if entry else None,
            "finish_position": r.finish_position,
            "elapsed_ms": r.elapsed_ms,
        })
    return {
        "race_id": race.id,
        "name": race.name,
        "venue_id": race.venue_id,
        "race_date": race.race_date.isoformat() if race.race_date else None,
        "distance_m": race.distance_m,
        "surface": race.surface,
        "status": race.status,
        "results": results_out,
    }


# ------------------------------------------------------------------ #
# Phase 5A — Welfare & operational workflows
# ------------------------------------------------------------------ #

@router.post("/horses/{chip_id}/workouts")
def add_workout(chip_id: str, req: AddWorkoutRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    result = crud.add_workout(
        db,
        chip_id=chip_id.strip().upper(),
        workout_date=req.workout_date,
        distance_m=req.distance_m,
        surface=req.surface,
        duration_ms=req.duration_ms,
        track_condition=req.track_condition,
        trainer_name=req.trainer_name,
        rider_name=req.rider_name,
        clocker_name=req.clocker_name,
        timekeeper_name=req.timekeeper_name,
        source="manual",
        notes=req.notes,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.get("/horses/{chip_id}/workouts")
def get_workouts(chip_id: str, db: Session = Depends(get_db)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    records = crud.get_workouts(db, chip_id)
    return {
        "chip_id": chip_id,
        "workouts": [
            {
                "id": r.id,
                "workout_date": r.workout_date,
                "distance_m": r.distance_m,
                "surface": r.surface,
                "duration_ms": r.duration_ms,
                "track_condition": r.track_condition,
                "trainer_name": r.trainer_name,
                "rider_name": r.rider_name,
                "clocker_name": r.clocker_name,
                "timekeeper_name": r.timekeeper_name,
                "splits_json": r.splits_json,
                "source": r.source,
                "notes": r.notes,
            }
            for r in records
        ],
    }


@router.post("/horses/{chip_id}/checkins")
def add_checkin(chip_id: str, req: CheckInRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    result = crud.add_checkin(
        db,
        chip_id=chip_id.strip().upper(),
        scanned_by=req.scanned_by,
        location=req.location,
        race_id=req.race_id,
        notes=req.notes,
        temperature_c=req.temperature_c,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.get("/horses/{chip_id}/checkins")
def get_checkins(chip_id: str, race_id: Optional[int] = None, db: Session = Depends(get_db)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    records = crud.get_checkins(db, chip_id, race_id=race_id)
    return {
        "chip_id": chip_id,
        "checkins": [
            {
                "id": r.id,
                "race_id": r.race_id,
                "scanned_at": r.scanned_at.isoformat() if r.scanned_at else None,
                "scanned_by": r.scanned_by,
                "location": r.location,
                "verified": r.verified,
                "notes": r.notes,
                "temperature_c": r.temperature_c,
            }
            for r in records
        ],
    }


@router.get("/checkins/today-summary")
def checkins_today_summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Count of check-ins today plus the last 10 for the check-in landing screen."""
    from datetime import date
    from app.models import CheckInRecord
    today_str = date.today().isoformat()
    today_checkins = (
        db.query(CheckInRecord)
        .filter(CheckInRecord.scanned_at >= today_str)
        .order_by(CheckInRecord.scanned_at.desc())
        .all()
    )
    recent = today_checkins[:8]
    return {
        "today_count": len(today_checkins),
        "recent": [
            {
                "horse_chip_id": c.horse_chip_id,
                "horse_name": crud.get_horse(db, c.horse_chip_id).name if crud.get_horse(db, c.horse_chip_id) else None,
                "scanned_at": c.scanned_at.isoformat() if c.scanned_at else None,
                "location": c.location,
                "temperature_c": c.temperature_c,
                "verified": c.verified,
            }
            for c in recent
        ],
    }


@router.post("/horses/{chip_id}/testbarn/checkin")
def test_barn_checkin(chip_id: str, req: TestBarnCheckInRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    result = crud.test_barn_checkin(
        db,
        chip_id=chip_id.strip().upper(),
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


@router.get("/horses/{chip_id}/testbarn")
def get_test_barn_records(chip_id: str, db: Session = Depends(get_db)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    records = crud.get_test_barn_records(db, chip_id)
    return {
        "chip_id": chip_id,
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


# ------------------------------------------------------------------ #
# Biosensor (Item 2)
# ------------------------------------------------------------------ #

class BiosensorReadingRequest(BaseModel):
    recorded_at: Optional[str] = Field(None, description="ISO datetime; defaults to now")
    race_id: Optional[int] = None
    heart_rate_bpm: Optional[int] = Field(None, ge=20, le=300)
    temperature_c: Optional[float] = Field(None, ge=30.0, le=45.0)
    stride_hz: Optional[float] = Field(None, ge=0.5, le=5.0)
    source: str = "wearable"


class BiosensorBulkItem(BaseModel):
    horse_chip_id: str
    recorded_at: Optional[str] = None
    heart_rate_bpm: Optional[int] = Field(None, ge=20, le=300)
    temperature_c: Optional[float] = Field(None, ge=30.0, le=45.0)
    stride_hz: Optional[float] = Field(None, ge=0.5, le=5.0)
    source: str = "wearable"


class BiosensorBulkRequest(BaseModel):
    readings: list[BiosensorBulkItem]


@router.post("/horses/{chip_id}/biosensor")
def add_biosensor(
    chip_id: str,
    req: BiosensorReadingRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    chip_id = chip_id.strip().upper()
    recorded_at = None
    if req.recorded_at:
        try:
            recorded_at = datetime.fromisoformat(req.recorded_at)
        except ValueError:
            raise HTTPException(400, f"Invalid recorded_at format: '{req.recorded_at}'")
    result = crud.add_biosensor_reading(
        db, horse_chip_id=chip_id, recorded_at=recorded_at, race_id=req.race_id,
        heart_rate_bpm=req.heart_rate_bpm, temperature_c=req.temperature_c,
        stride_hz=req.stride_hz, source=req.source,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


def _biosensor_dict(r):
    return {
        "id": r.id,
        "horse_chip_id": r.horse_chip_id,
        "race_id": r.race_id,
        "recorded_at": r.recorded_at.isoformat() if r.recorded_at else None,
        "heart_rate_bpm": r.heart_rate_bpm,
        "temperature_c": r.temperature_c,
        "stride_hz": r.stride_hz,
        "source": r.source,
    }


@router.get("/horses/{chip_id}/biosensor")
def get_biosensor(chip_id: str, limit: int = 200, db: Session = Depends(get_db)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    readings = crud.get_biosensor_readings(db, chip_id, limit=min(limit, 500))
    return {"chip_id": chip_id, "readings": [_biosensor_dict(r) for r in readings]}


@router.get("/races/{race_id}/biosensor")
def get_race_biosensor(race_id: int, db: Session = Depends(get_db)):
    race = crud.get_race(db, race_id)
    if not race:
        raise HTTPException(404, f"Race {race_id} not found")
    readings = crud.get_race_biosensor_readings(db, race_id)
    return {"race_id": race_id, "readings": [_biosensor_dict(r) for r in readings]}


@router.post("/races/{race_id}/biosensor/bulk")
def bulk_biosensor(
    race_id: int,
    req: BiosensorBulkRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    race = crud.get_race(db, race_id)
    if not race:
        raise HTTPException(404, f"Race {race_id} not found")
    if not req.readings:
        raise HTTPException(400, "No readings provided")
    created = 0
    errors = []
    for item in req.readings:
        recorded_at = None
        if item.recorded_at:
            try:
                recorded_at = datetime.fromisoformat(item.recorded_at)
            except ValueError:
                errors.append(f"Invalid recorded_at: '{item.recorded_at}'")
                continue
        result = crud.add_biosensor_reading(
            db, horse_chip_id=item.horse_chip_id.strip().upper(),
            recorded_at=recorded_at, race_id=race_id,
            heart_rate_bpm=item.heart_rate_bpm, temperature_c=item.temperature_c,
            stride_hz=item.stride_hz, source=item.source,
        )
        if result["ok"]:
            created += 1
        else:
            errors.append(result["error"])
    return {"ok": True, "created": created, "errors": errors}


# ------------------------------------------------------------------ #
# Temperature history & alerts (Item 3)
# ------------------------------------------------------------------ #

@router.get("/horses/{chip_id}/temperature-history")
def temperature_history(chip_id: str, limit: int = 50, db: Session = Depends(get_db)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    records = crud.get_temperature_history(db, chip_id, limit=min(limit, 200))
    return {
        "chip_id": chip_id,
        "readings": [
            {
                "id": r.id,
                "scanned_at": r.scanned_at.isoformat() if r.scanned_at else None,
                "temperature_c": r.temperature_c,
                "location": r.location,
                "scanned_by": r.scanned_by,
                "race_id": r.race_id,
            }
            for r in records
        ],
    }


@router.get("/horses/{chip_id}/temperature-alerts")
def temperature_alerts(chip_id: str, db: Session = Depends(get_db)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    records = crud.get_temperature_alerts(db, chip_id)
    return {
        "chip_id": chip_id,
        "alert_count": len(records),
        "alerts": [
            {
                "id": r.id,
                "scanned_at": r.scanned_at.isoformat() if r.scanned_at else None,
                "temperature_c": r.temperature_c,
                "severity": "red" if r.temperature_c >= 39.0 or r.temperature_c <= 37.0 else "amber",
                "location": r.location,
                "race_id": r.race_id,
            }
            for r in records
        ],
    }


# ------------------------------------------------------------------ #
# Phase 3 — HISA Reporting Module
# ------------------------------------------------------------------ #

def require_compliance_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ("admin", "compliance"):
        raise HTTPException(status_code=403, detail="Compliance officer or admin role required")
    return current_user


# Treatment records

class AddTreatmentRequest(BaseModel):
    treatment_date: str = Field(..., description="ISO date e.g. '2026-06-01'")
    substance: str
    dose: Optional[str] = None
    route: Optional[str] = None
    withdrawal_time_hours: Optional[int] = None
    prescribed_by: Optional[str] = None
    administered_by: Optional[str] = None
    race_id: Optional[int] = None
    notes: Optional[str] = None
    is_prohibited: bool = False


@router.post("/horses/{chip_id}/treatments")
def add_treatment(chip_id: str, req: AddTreatmentRequest,
                  db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    result = crud.add_treatment(db, horse_chip_id=chip_id.strip().upper(),
                                treatment_date=req.treatment_date,
                                substance=req.substance,
                                dose=req.dose, route=req.route,
                                withdrawal_time_hours=req.withdrawal_time_hours,
                                prescribed_by=req.prescribed_by,
                                administered_by=req.administered_by,
                                race_id=req.race_id, notes=req.notes,
                                is_prohibited=req.is_prohibited)
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.get("/horses/{chip_id}/treatments")
def get_treatments(chip_id: str, db: Session = Depends(get_db)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    records = crud.get_treatments(db, chip_id)
    return {
        "chip_id": chip_id,
        "treatments": [
            {
                "id": r.id,
                "treatment_date": r.treatment_date,
                "substance": r.substance,
                "dose": r.dose,
                "route": r.route,
                "withdrawal_time_hours": r.withdrawal_time_hours,
                "prescribed_by": r.prescribed_by,
                "administered_by": r.administered_by,
                "race_id": r.race_id,
                "is_prohibited": r.is_prohibited,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }


# Stewards' rulings

class CreateStewardsRulingRequest(BaseModel):
    ruling_date: str = Field(..., description="ISO datetime e.g. '2026-06-01T15:00:00'")
    rule_violated: str
    description: str
    race_id: Optional[int] = None
    horse_chip_id: Optional[str] = None
    jockey_name: Optional[str] = None
    penalty: Optional[str] = None


@router.post("/stewards/rulings")
def create_stewards_ruling(req: CreateStewardsRulingRequest,
                            db: Session = Depends(get_db),
                            current_user: User = Depends(require_compliance_or_admin)):
    try:
        ruling_date = datetime.fromisoformat(req.ruling_date)
    except ValueError:
        raise HTTPException(400, f"Invalid ruling_date: '{req.ruling_date}'")
    result = crud.create_stewards_ruling(
        db,
        ruling_date=ruling_date,
        rule_violated=req.rule_violated,
        description=req.description,
        race_id=req.race_id,
        horse_chip_id=req.horse_chip_id.strip().upper() if req.horse_chip_id else None,
        jockey_name=req.jockey_name,
        penalty=req.penalty,
        created_by=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    # Auto-create pending HISA submission for this ruling
    from app import hisa_builder
    import json
    from app.models import StewardsRuling as StewardsRulingModel
    ruling_obj = db.get(StewardsRulingModel, result["id"])
    horse = crud.get_horse(db, ruling_obj.horse_chip_id) if ruling_obj.horse_chip_id else None
    payload = hisa_builder.build_stewards_submission(ruling_obj, horse=horse)
    crud.create_hisa_submission(
        db, rule_category="STEWARDS_RULING",
        source_record_type="StewardsRuling", source_record_id=result["id"],
        payload_json=json.dumps(payload),
        horse_chip_id=ruling_obj.horse_chip_id,
        deadline_at=ruling_obj.deadline_at,
        tenant_id=current_user.tenant_id,
    )
    crud.write_audit_log(db, current_user, "create", "stewards_ruling", str(result["id"]),
                         {"rule": req.rule_violated})
    return result


@router.get("/stewards/rulings")
def list_stewards_rulings(horse_chip_id: Optional[str] = None, race_id: Optional[int] = None,
                           db: Session = Depends(get_db),
                           _: User = Depends(require_compliance_or_admin)):
    rulings = crud.get_stewards_rulings(db, horse_chip_id=horse_chip_id, race_id=race_id)
    return {
        "rulings": [
            {
                "id": r.id,
                "ruling_date": r.ruling_date.isoformat() if r.ruling_date else None,
                "deadline_at": r.deadline_at.isoformat() if r.deadline_at else None,
                "race_id": r.race_id,
                "horse_chip_id": r.horse_chip_id,
                "jockey_name": r.jockey_name,
                "rule_violated": r.rule_violated,
                "description": r.description,
                "penalty": r.penalty,
                "status": r.status,
            }
            for r in rulings
        ]
    }


# Surface condition logs

class SurfaceConditionRequest(BaseModel):
    logged_date: str = Field(..., description="YYYY-MM-DD")
    surface_type: str = Field(..., description="Dirt|Turf|Synthetic")
    going_description: str = Field(..., description="Fast|Good|Soft|Heavy|Firm")
    moisture_pct: Optional[float] = None
    temperature_c: Optional[float] = None
    maintenance_notes: Optional[str] = None
    logged_by: Optional[str] = None


@router.post("/venues/{venue_id}/surface-conditions")
def add_surface_condition(venue_id: str, req: SurfaceConditionRequest,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(require_compliance_or_admin)):
    result = crud.upsert_surface_condition(
        db, venue_id=venue_id.upper(), logged_date=req.logged_date,
        surface_type=req.surface_type, going_description=req.going_description,
        moisture_pct=req.moisture_pct, temperature_c=req.temperature_c,
        maintenance_notes=req.maintenance_notes, logged_by=req.logged_by,
        tenant_id=current_user.tenant_id,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.get("/venues/{venue_id}/surface-conditions")
def get_surface_conditions(venue_id: str, db: Session = Depends(get_db)):
    logs = crud.get_surface_conditions(db, venue_id=venue_id.upper())
    return {
        "venue_id": venue_id.upper(),
        "logs": [
            {
                "id": l.id, "logged_date": l.logged_date,
                "surface_type": l.surface_type, "going_description": l.going_description,
                "moisture_pct": l.moisture_pct, "temperature_c": l.temperature_c,
                "maintenance_notes": l.maintenance_notes, "logged_by": l.logged_by,
            }
            for l in logs
        ],
    }


# HISA Submissions

@router.get("/hisa/submissions")
def list_hisa_submissions(
    status: Optional[str] = None,
    rule_category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_compliance_or_admin),
):
    subs = crud.get_hisa_submissions(db, status=status, rule_category=rule_category,
                                      tenant_id=current_user.tenant_id)
    return {
        "submissions": [
            {
                "id": s.id,
                "rule_category": s.rule_category,
                "status": s.status,
                "source_record_type": s.source_record_type,
                "source_record_id": s.source_record_id,
                "horse_chip_id": s.horse_chip_id,
                "deadline_at": s.deadline_at.isoformat() if s.deadline_at else None,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in subs
        ]
    }


@router.get("/hisa/submissions/{submission_id}")
def get_hisa_submission(submission_id: int, db: Session = Depends(get_db),
                         _: User = Depends(require_compliance_or_admin)):
    from app.models import HISASubmission as HISASubmissionModel
    sub = db.get(HISASubmissionModel, submission_id)
    if not sub:
        raise HTTPException(404, f"Submission {submission_id} not found")
    return {
        "id": sub.id,
        "rule_category": sub.rule_category,
        "status": sub.status,
        "source_record_type": sub.source_record_type,
        "source_record_id": sub.source_record_id,
        "horse_chip_id": sub.horse_chip_id,
        "deadline_at": sub.deadline_at.isoformat() if sub.deadline_at else None,
        "submitted_at": sub.submitted_at.isoformat() if sub.submitted_at else None,
        "payload_json": sub.payload_json,
        "response_json": sub.response_json,
        "created_at": sub.created_at.isoformat() if sub.created_at else None,
    }


@router.post("/hisa/submit/{submission_id}")
def submit_hisa(submission_id: int, db: Session = Depends(get_db),
                current_user: User = Depends(require_compliance_or_admin)):
    """Mark a submission as submitted. Returns the payload for manual portal upload."""
    sub = crud.mark_submission_submitted(db, submission_id, user_id=current_user.id)
    if not sub:
        raise HTTPException(404, f"Submission {submission_id} not found")
    import json
    return {
        "ok": True,
        "id": sub.id,
        "status": sub.status,
        "submitted_at": sub.submitted_at.isoformat(),
        "payload": json.loads(sub.payload_json) if sub.payload_json else None,
    }


@router.post("/hisa/build-all")
def build_all_hisa_submissions(db: Session = Depends(get_db),
                                current_user: User = Depends(require_compliance_or_admin)):
    """
    Scan all source records with no HISASubmission yet and create pending submissions.
    Idempotent — safe to call repeatedly.
    """
    from app import hisa_builder
    import json
    created = 0
    tenant_id = current_user.tenant_id

    # Workouts
    from app.models import WorkoutRecord
    for w in db.query(WorkoutRecord).all():
        if not crud.submission_exists(db, "WorkoutRecord", w.id):
            horse = crud.get_horse(db, w.horse_chip_id)
            payload = hisa_builder.build_workout_submission(w, horse=horse)
            crud.create_hisa_submission(db, rule_category="WORKOUTS",
                source_record_type="WorkoutRecord", source_record_id=w.id,
                horse_chip_id=w.horse_chip_id,
                payload_json=json.dumps(payload), tenant_id=tenant_id)
            created += 1

    # Test barn (ADMC sample chain)
    from app.models import TestBarnRecord
    for t in db.query(TestBarnRecord).all():
        if not crud.submission_exists(db, "TestBarnRecord", t.id):
            horse = crud.get_horse(db, t.horse_chip_id)
            payload = hisa_builder.build_sample_submission(t, horse=horse)
            crud.create_hisa_submission(db, rule_category="ADMC_SAMPLE",
                source_record_type="TestBarnRecord", source_record_id=t.id,
                horse_chip_id=t.horse_chip_id,
                payload_json=json.dumps(payload), tenant_id=tenant_id)
            created += 1

    # Treatment records (ADMC)
    from app.models import TreatmentRecord
    for tr in db.query(TreatmentRecord).all():
        if not crud.submission_exists(db, "TreatmentRecord", tr.id):
            horse = crud.get_horse(db, tr.horse_chip_id)
            payload = hisa_builder.build_treatment_submission(tr, horse=horse)
            crud.create_hisa_submission(db, rule_category="ADMC_TREATMENT",
                source_record_type="TreatmentRecord", source_record_id=tr.id,
                horse_chip_id=tr.horse_chip_id,
                payload_json=json.dumps(payload), tenant_id=tenant_id)
            created += 1

    # Check-ins
    from app.models import CheckInRecord
    for c in db.query(CheckInRecord).filter(CheckInRecord.race_id.isnot(None)).all():
        if not crud.submission_exists(db, "CheckInRecord", c.id):
            horse = crud.get_horse(db, c.horse_chip_id)
            payload = hisa_builder.build_checkin_submission(c, horse=horse)
            crud.create_hisa_submission(db, rule_category="CHECKIN",
                source_record_type="CheckInRecord", source_record_id=c.id,
                horse_chip_id=c.horse_chip_id,
                payload_json=json.dumps(payload), tenant_id=tenant_id)
            created += 1

    # Surface condition logs
    from app.models import SurfaceConditionLog
    for sl in db.query(SurfaceConditionLog).all():
        if not crud.submission_exists(db, "SurfaceConditionLog", sl.id):
            payload = hisa_builder.build_surface_submission(sl)
            crud.create_hisa_submission(db, rule_category="SURFACE",
                source_record_type="SurfaceConditionLog", source_record_id=sl.id,
                payload_json=json.dumps(payload), tenant_id=tenant_id)
            created += 1

    return {"ok": True, "created": created}


# ------------------------------------------------------------------ #
# Phase 4 — Training Center Module
# ------------------------------------------------------------------ #

class AddVetCheckRequest(BaseModel):
    check_date: str = Field(..., description="ISO date e.g. '2026-06-01'")
    check_type: str = Field(..., description="routine|lameness|pre_shipment|post_race|other")
    outcome: str = Field(..., description="cleared|restricted|scratched|referred")
    vet_name: Optional[str] = None
    race_id: Optional[int] = None
    notes: Optional[str] = None


@router.post("/horses/{chip_id}/vet-checks")
def add_vet_check(chip_id: str, req: AddVetCheckRequest,
                  db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    result = crud.add_vet_check(
        db, horse_chip_id=chip_id.strip().upper(),
        check_date=req.check_date, check_type=req.check_type,
        outcome=req.outcome, vet_name=req.vet_name,
        race_id=req.race_id, notes=req.notes,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.get("/horses/{chip_id}/vet-checks")
def get_vet_checks(chip_id: str, db: Session = Depends(get_db)):
    chip_id = chip_id.strip().upper()
    if not crud.get_horse(db, chip_id):
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    records = crud.get_vet_checks(db, chip_id)
    return {
        "chip_id": chip_id,
        "vet_checks": [
            {
                "id": r.id,
                "check_date": r.check_date,
                "check_type": r.check_type,
                "outcome": r.outcome,
                "vet_name": r.vet_name,
                "race_id": r.race_id,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ],
    }


@router.get("/training/roster")
def training_roster(db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    """
    Daily training center roster for the current tenant.
    Each horse has a status snapshot: last workout, latest vet check, open
    treatments, and pending HISA submissions.
    Trainers see all horses in their tenant; admins see all.
    """
    trainer_name = None
    if current_user.role == "trainer":
        trainer_name = current_user.full_name  # match against horse.trainers
    roster = crud.get_training_roster(
        db,
        tenant_id=current_user.tenant_id,
        trainer_name=trainer_name,
    )
    return {"roster": roster, "count": len(roster)}


@router.get("/horses/{chip_id}/owner-report")
def owner_report(chip_id: str, period: str = "week",
                 db: Session = Depends(get_db),
                 _: User = Depends(get_current_user)):
    """
    Aggregated owner report for a horse.
    period: 'week' (7 days) or 'month' (30 days).
    """
    chip_id = chip_id.strip().upper()
    if period not in ("week", "month"):
        raise HTTPException(400, "period must be 'week' or 'month'")
    report = crud.get_owner_report(db, horse_chip_id=chip_id, period=period)
    if report is None:
        raise HTTPException(404, f"Horse '{chip_id}' not found")
    return report


# ------------------------------------------------------------------ #
# Phase 5 — Race Day Operations Module
# ------------------------------------------------------------------ #

class AddEntryRequest(BaseModel):
    horse_chip_id: str
    saddle_cloth: str
    jockey: Optional[str] = None


class UpdateEntryRequest(BaseModel):
    saddle_cloth: Optional[str] = None
    jockey: Optional[str] = None


class ScratchRequest(BaseModel):
    scratch_type: str = Field(..., description="veterinary|trainer|steward|official")
    declared_by: Optional[str] = None
    reason: Optional[str] = None


class IngestResultsRequest(BaseModel):
    results: list[dict] = Field(..., description="[{horse_chip_id, finish_position, elapsed_ms?}]")


class UpdateRaceStatusRequest(BaseModel):
    status: str = Field(..., description="active|finished|pending")


class AddCropViolationRequest(BaseModel):
    jockey_name: str
    crop_count: int
    horse_chip_id: Optional[str] = None
    violation_determined: bool = False
    penalty: Optional[str] = None
    official_name: Optional[str] = None
    race_date: Optional[str] = None
    notes: Optional[str] = None


@router.post("/races/{race_id}/entries")
def add_race_entry(race_id: int, req: AddEntryRequest,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    result = crud.add_race_entry(
        db, race_id=race_id,
        horse_chip_id=req.horse_chip_id.strip().upper(),
        saddle_cloth=req.saddle_cloth,
        jockey=req.jockey,
    )
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    crud.write_audit_log(db, current_user, "add_entry", "race", str(race_id),
                         {"horse": req.horse_chip_id, "cloth": req.saddle_cloth})
    return result


@router.patch("/races/{race_id}/entries/{chip_id}")
def update_race_entry(race_id: int, chip_id: str, req: UpdateEntryRequest,
                      db: Session = Depends(get_db),
                      _: User = Depends(get_current_user)):
    result = crud.update_race_entry(
        db, race_id=race_id, horse_chip_id=chip_id.strip().upper(),
        saddle_cloth=req.saddle_cloth, jockey=req.jockey,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    return result


@router.post("/races/{race_id}/scratch/{chip_id}")
def scratch_horse(race_id: int, chip_id: str, req: ScratchRequest,
                  db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    """Scratch a horse from a race and auto-generate a HISA scratch submission."""
    chip_id = chip_id.strip().upper()
    result = crud.scratch_horse(
        db, race_id=race_id, horse_chip_id=chip_id,
        scratch_type=req.scratch_type, declared_by=req.declared_by,
        reason=req.reason, tenant_id=current_user.tenant_id,
    )
    if not result["ok"]:
        raise HTTPException(400, result["error"])

    # Auto-create HISA scratch submission
    from app import hisa_builder
    import json
    from app.models import ScratchRecord as ScratchModel
    scratch_obj = db.query(ScratchModel).filter_by(
        race_id=race_id, horse_chip_id=chip_id).first()
    if scratch_obj:
        horse = crud.get_horse(db, chip_id)
        race = crud.get_race(db, race_id)
        payload = hisa_builder.build_scratch_submission(scratch_obj, horse=horse, race=race)
        crud.create_hisa_submission(
            db, rule_category="SCRATCH",
            source_record_type="ScratchRecord", source_record_id=scratch_obj.id,
            horse_chip_id=chip_id, payload_json=json.dumps(payload),
            tenant_id=current_user.tenant_id,
        )

    crud.write_audit_log(db, current_user, "scratch", "race", str(race_id),
                         {"horse": chip_id, "type": req.scratch_type})
    return result


@router.get("/races/{race_id}/entries")
def list_race_entries(race_id: int, db: Session = Depends(get_db)):
    race = crud.get_race(db, race_id)
    if not race:
        raise HTTPException(404, f"Race {race_id} not found")
    entries = crud.get_race_entries(db, race_id)
    scratches = crud.get_scratches(db, race_id)
    return {
        "race_id": race_id,
        "entries": [
            {"id": e.id, "horse_chip_id": e.horse_chip_id,
             "saddle_cloth": e.saddle_cloth, "jockey": e.jockey}
            for e in entries
        ],
        "scratches": [
            {"horse_chip_id": s.horse_chip_id, "scratch_type": s.scratch_type,
             "declared_by": s.declared_by, "reason": s.reason,
             "declared_at": s.declared_at.isoformat() if s.declared_at else None}
            for s in scratches
        ],
    }


@router.post("/races/{race_id}/results/ingest")
def ingest_results(race_id: int, req: IngestResultsRequest,
                   db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    """
    Ingest official finish order from FinishLynx / MYLAPS / manual entry.
    TrackSense receives results — it does not produce them.
    """
    if not req.results:
        raise HTTPException(400, "results list is empty")
    result = crud.ingest_race_results(db, race_id=race_id, results=req.results)
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    crud.write_audit_log(db, current_user, "ingest_results", "race", str(race_id),
                         {"count": len(req.results)})
    return result


@router.patch("/races/{race_id}/status")
def update_race_status(race_id: int, req: UpdateRaceStatusRequest,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    if req.status not in ("pending", "active", "finished"):
        raise HTTPException(400, "status must be pending|active|finished")
    result = crud.update_race_status(db, race_id=race_id, status=req.status)
    if not result["ok"]:
        raise HTTPException(404, result["error"])
    crud.write_audit_log(db, current_user, "status_change", "race", str(race_id),
                         {"status": req.status})
    return result


@router.post("/races/{race_id}/crop-violations")
def add_crop_violation(race_id: int, req: AddCropViolationRequest,
                       db: Session = Depends(get_db),
                       current_user: User = Depends(require_compliance_or_admin)):
    """Record a Rule 2280/2281 riding crop violation and auto-create HISA submission."""
    result = crud.add_crop_violation(
        db, race_id=race_id, jockey_name=req.jockey_name,
        crop_count=req.crop_count,
        horse_chip_id=req.horse_chip_id.strip().upper() if req.horse_chip_id else None,
        violation_determined=req.violation_determined,
        penalty=req.penalty, official_name=req.official_name,
        race_date=req.race_date, notes=req.notes,
        tenant_id=current_user.tenant_id,
    )
    if not result["ok"]:
        raise HTTPException(404, result["error"])

    from app import hisa_builder
    import json
    from app.models import RidingCropViolation as CropModel
    v = db.get(CropModel, result["id"])
    horse = crud.get_horse(db, v.horse_chip_id) if v.horse_chip_id else None
    race = crud.get_race(db, race_id)
    payload = hisa_builder.build_crop_violation_submission(v, horse=horse, race=race)
    crud.create_hisa_submission(
        db, rule_category="CROP_VIOLATION",
        source_record_type="RidingCropViolation", source_record_id=v.id,
        horse_chip_id=v.horse_chip_id, payload_json=json.dumps(payload),
        tenant_id=current_user.tenant_id,
    )
    return result


@router.get("/races/{race_id}/crop-violations")
def list_crop_violations(race_id: int, db: Session = Depends(get_db),
                          _: User = Depends(require_compliance_or_admin)):
    race = crud.get_race(db, race_id)
    if not race:
        raise HTTPException(404, f"Race {race_id} not found")
    violations = crud.get_crop_violations(db, race_id)
    return {
        "race_id": race_id,
        "violations": [
            {"id": v.id, "jockey_name": v.jockey_name, "horse_chip_id": v.horse_chip_id,
             "crop_count": v.crop_count, "violation_determined": v.violation_determined,
             "penalty": v.penalty, "official_name": v.official_name}
            for v in violations
        ],
    }


# ------------------------------------------------------------------ #
# Tenants (super-admin only)
# ------------------------------------------------------------------ #

class CreateTenantRequest(BaseModel):
    name: str = Field(..., description="Human-readable tenant name e.g. 'Racing Victoria'")
    slug: str = Field(..., description="URL-safe unique slug e.g. 'racing-victoria'")


def _tenant_dict(t):
    return {
        "id": t.id,
        "name": t.name,
        "slug": t.slug,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("/tenants")
def list_tenants(
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return [_tenant_dict(t) for t in crud.list_tenants(db)]


@router.post("/tenants", status_code=201)
def create_tenant(
    req: CreateTenantRequest,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    if crud.get_tenant_by_slug(db, req.slug):
        raise HTTPException(status_code=409, detail=f"Slug '{req.slug}' already exists")
    tenant = crud.create_tenant(db, req.name, req.slug)
    return _tenant_dict(tenant)


@router.get("/tenants/{tenant_id}")
def get_tenant(
    tenant_id: str,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    tenant = crud.get_tenant(db, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _tenant_dict(tenant)


@router.delete("/tenants/{tenant_id}", status_code=204)
def delete_tenant(
    tenant_id: str,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    if not crud.delete_tenant(db, tenant_id):
        raise HTTPException(status_code=404, detail="Tenant not found")
    return None