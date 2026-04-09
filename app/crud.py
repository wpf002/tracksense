"""
crud.py

All database operations for TrackSense Phase 3.

Design decisions:
- Every function takes an explicit Session — no global state, fully testable.
- persist_race_results() is idempotent: safe to call multiple times for the
  same race_id. Uses check-before-insert so it works on SQLite and PostgreSQL.
- Analytics (sectional averages, head-to-head) run in Python over SQLAlchemy
  query results rather than raw SQL to stay portable across DB backends.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

import json
import uuid

from app.models import (
    Horse, Owner, Trainer, VenueRecord, GateRecord,
    Race, RaceEntry, GateRead, RaceResult, VetRecord,
    WorkoutRecord, CheckInRecord, TestBarnRecord, User,
    AuditLog, WebhookDelivery, Tenant,
)
from app.auth import hash_password, verify_password


# ------------------------------------------------------------------ #
# Horse
# ------------------------------------------------------------------ #

def create_horse(
    db: Session,
    epc: str,
    name: str,
    breed: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    implant_date: Optional[str] = None,
    implant_vet: Optional[str] = None,
    racing_api_horse_id: Optional[str] = None,
) -> dict:
    if db.get(Horse, epc):
        return {"ok": False, "error": f"Horse with EPC '{epc}' already exists"}
    horse = Horse(
        epc=epc,
        name=name,
        breed=breed,
        date_of_birth=date_of_birth,
        implant_date=implant_date,
        implant_vet=implant_vet,
        racing_api_horse_id=racing_api_horse_id,
    )
    db.add(horse)
    db.commit()
    db.refresh(horse)
    return {"ok": True, "epc": horse.epc}


def get_horse(db: Session, epc: str) -> Optional[Horse]:
    return db.get(Horse, epc)


def list_horses(db: Session, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None) -> list[Horse]:
    q = db.query(Horse)
    if tenant_id is not None:
        q = q.filter(Horse.tenant_id == tenant_id)
    return q.offset(skip).limit(limit).all()


def add_owner(
    db: Session,
    epc: str,
    owner_name: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    if not db.get(Horse, epc):
        return {"ok": False, "error": f"Horse '{epc}' not found"}
    db.add(Owner(horse_epc=epc, owner_name=owner_name, from_date=from_date, to_date=to_date))
    db.commit()
    return {"ok": True}


def add_trainer(
    db: Session,
    epc: str,
    trainer_name: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    if not db.get(Horse, epc):
        return {"ok": False, "error": f"Horse '{epc}' not found"}
    db.add(Trainer(horse_epc=epc, trainer_name=trainer_name, from_date=from_date, to_date=to_date))
    db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ #
# Venue (DB mirror of in-memory GateRegistry)
# ------------------------------------------------------------------ #

def upsert_venue(
    db: Session,
    venue_id: str,
    name: str,
    total_distance_m: float,
) -> VenueRecord:
    venue = db.get(VenueRecord, venue_id)
    if venue:
        venue.name = name
        venue.total_distance_m = total_distance_m
    else:
        venue = VenueRecord(venue_id=venue_id, name=name, total_distance_m=total_distance_m)
        db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


def delete_venue(db: Session, venue_id: str) -> bool:
    """Delete a venue and all its gates (cascade). Returns True if found and deleted."""
    venue = db.get(VenueRecord, venue_id)
    if not venue:
        return False
    db.delete(venue)
    db.commit()
    return True


def upsert_gate(
    db: Session,
    venue_id: str,
    reader_id: str,
    name: str,
    distance_m: float,
    is_finish: bool,
    position_x: Optional[float] = None,
    position_y: Optional[float] = None,
) -> GateRecord:
    """Insert or update a gate record for a venue."""
    existing = (
        db.query(GateRecord)
        .filter_by(venue_id=venue_id, reader_id=reader_id)
        .first()
    )
    if existing:
        existing.name = name
        existing.distance_m = distance_m
        existing.is_finish = is_finish
        existing.position_x = position_x
        existing.position_y = position_y
        db.commit()
        db.refresh(existing)
        return existing
    gate = GateRecord(
        venue_id=venue_id,
        reader_id=reader_id,
        name=name,
        distance_m=distance_m,
        is_finish=is_finish,
        position_x=position_x,
        position_y=position_y,
    )
    db.add(gate)
    db.commit()
    db.refresh(gate)
    return gate


def delete_gate(db: Session, venue_id: str, reader_id: str) -> bool:
    """Delete a single gate. Returns True if found and deleted."""
    gate = (
        db.query(GateRecord)
        .filter_by(venue_id=venue_id, reader_id=reader_id)
        .first()
    )
    if not gate:
        return False
    db.delete(gate)
    db.commit()
    return True


# ------------------------------------------------------------------ #
# Race
# ------------------------------------------------------------------ #

def create_race(
    db: Session,
    venue_id: str,
    race_date: datetime,
    distance_m: float,
    surface: str = "turf",
    conditions: Optional[str] = None,
    name: Optional[str] = None,
) -> dict:
    if not db.get(VenueRecord, venue_id):
        return {"ok": False, "error": f"Venue '{venue_id}' not found in database"}
    race = Race(
        venue_id=venue_id,
        name=name,
        race_date=race_date,
        distance_m=distance_m,
        surface=surface,
        conditions=conditions,
        status="pending",
    )
    db.add(race)
    db.commit()
    db.refresh(race)
    return {"ok": True, "race_id": race.id}


def get_race(db: Session, race_id: int) -> Optional[Race]:
    return db.get(Race, race_id)


def list_races(db: Session, skip: int = 0, limit: int = 50, tenant_id: Optional[str] = None) -> list[Race]:
    q = db.query(Race).order_by(Race.race_date.desc())
    if tenant_id is not None:
        q = q.filter(Race.tenant_id == tenant_id)
    return q.offset(skip).limit(limit).all()


# ------------------------------------------------------------------ #
# Persist race results — idempotent
# ------------------------------------------------------------------ #

def persist_race_results(db: Session, race_id: int, tracker_state: dict) -> dict:
    """
    Write the in-memory tracker state to the database.

    Idempotent: calling this twice for the same race produces the same result.
    Uses check-before-insert for all child records.

    tracker_state is the dict returned by RaceTracker.get_race_state().
    Horses must already exist in the horses table (created via POST /horses).
    Missing horses are skipped with a warning in the return value.
    """
    race = db.get(Race, race_id)
    if not race:
        return {"ok": False, "error": f"Race {race_id} not found"}

    skipped_horses = []
    persisted_entries = 0
    persisted_reads = 0
    persisted_results = 0

    for horse_data in tracker_state.get("horses", []):
        epc = horse_data["horse_id"]

        if not db.get(Horse, epc):
            skipped_horses.append(epc)
            continue

        # RaceEntry — idempotent
        entry = (
            db.query(RaceEntry)
            .filter_by(race_id=race_id, horse_epc=epc)
            .first()
        )
        if not entry:
            db.add(RaceEntry(
                race_id=race_id,
                horse_epc=epc,
                saddle_cloth=horse_data.get("saddle_cloth", "?"),
            ))
            persisted_entries += 1

        # GateReads — one per gate per horse per race, idempotent
        for event in horse_data.get("events", []):
            existing_read = (
                db.query(GateRead)
                .filter_by(race_id=race_id, horse_epc=epc, reader_id=event["reader_id"])
                .first()
            )
            if not existing_read:
                db.add(GateRead(
                    race_id=race_id,
                    horse_epc=epc,
                    reader_id=event["reader_id"],
                    gate_name=event["gate_name"],
                    distance_m=event["distance_m"],
                    race_elapsed_ms=event["elapsed_ms"],
                    wall_time=None,
                ))
                persisted_reads += 1

        # RaceResult — only if horse has a finish position, idempotent
        finish_position = horse_data.get("finish_position")
        if finish_position is not None:
            elapsed_ms = _finish_elapsed_ms(horse_data.get("events", []))
            existing_result = (
                db.query(RaceResult)
                .filter_by(race_id=race_id, horse_epc=epc)
                .first()
            )
            if not existing_result:
                if elapsed_ms is not None:
                    db.add(RaceResult(
                        race_id=race_id,
                        horse_epc=epc,
                        finish_position=finish_position,
                        elapsed_ms=elapsed_ms,
                    ))
                    persisted_results += 1
            else:
                existing_result.finish_position = finish_position
                if elapsed_ms is not None:
                    existing_result.elapsed_ms = elapsed_ms

    if tracker_state.get("status") == "finished":
        race.status = "finished"

    db.commit()
    return {
        "ok": True,
        "race_id": race_id,
        "persisted_entries": persisted_entries,
        "persisted_reads": persisted_reads,
        "persisted_results": persisted_results,
        "skipped_horses": skipped_horses,
    }


def _finish_elapsed_ms(events: list[dict]) -> Optional[int]:
    for event in events:
        if event.get("is_finish"):
            return event["elapsed_ms"]
    return None


# ------------------------------------------------------------------ #
# Career & analytics
# ------------------------------------------------------------------ #

def get_career_history(db: Session, epc: str) -> list[dict]:
    """All races this horse entered, with result if available, newest first."""
    entries = (
        db.query(RaceEntry)
        .filter_by(horse_epc=epc)
        .join(Race)
        .order_by(Race.race_date.desc())
        .all()
    )
    out = []
    for entry in entries:
        race = entry.race
        result = (
            db.query(RaceResult)
            .filter_by(race_id=race.id, horse_epc=epc)
            .first()
        )
        out.append({
            "race_id": race.id,
            "venue_id": race.venue_id,
            "race_date": race.race_date.isoformat() if race.race_date else None,
            "distance_m": race.distance_m,
            "surface": race.surface,
            "conditions": race.conditions,
            "saddle_cloth": entry.saddle_cloth,
            "finish_position": result.finish_position if result else None,
            "elapsed_ms": result.elapsed_ms if result else None,
        })
    return out


def get_form_guide(db: Session, epc: str, n: int = 5) -> list[dict]:
    """Last n starts with results."""
    return get_career_history(db, epc)[:n]


def get_sectional_averages(db: Session, epc: str) -> list[dict]:
    """
    Average elapsed time and speed for each gate segment across all races.

    Segments are identified by (from_reader_id, to_reader_id) pairs.
    Only consecutive gate pairs (by distance) within each race are counted.
    """
    reads = (
        db.query(GateRead)
        .filter_by(horse_epc=epc)
        .order_by(GateRead.race_id, GateRead.distance_m)
        .all()
    )

    # Group by race
    by_race: dict[int, list[GateRead]] = {}
    for r in reads:
        by_race.setdefault(r.race_id, []).append(r)

    # Accumulate segment times: key = (from_reader_id, to_reader_id)
    segments: dict[tuple, dict] = {}
    for race_reads in by_race.values():
        sorted_reads = sorted(race_reads, key=lambda r: r.distance_m)
        for i in range(len(sorted_reads) - 1):
            r1 = sorted_reads[i]
            r2 = sorted_reads[i + 1]
            elapsed = r2.race_elapsed_ms - r1.race_elapsed_ms
            distance = r2.distance_m - r1.distance_m
            if elapsed <= 0 or distance <= 0:
                continue
            key = (r1.reader_id, r2.reader_id)
            if key not in segments:
                segments[key] = {
                    "from_reader_id": r1.reader_id,
                    "from_gate_name": r1.gate_name,
                    "to_reader_id": r2.reader_id,
                    "to_gate_name": r2.gate_name,
                    "distance_m": distance,
                    "elapsed_ms_sum": 0,
                    "count": 0,
                }
            segments[key]["elapsed_ms_sum"] += elapsed
            segments[key]["count"] += 1

    out = []
    for seg in segments.values():
        avg_ms = seg["elapsed_ms_sum"] / seg["count"]
        distance = seg["distance_m"]
        speed_ms = distance / (avg_ms / 1000) if avg_ms > 0 else 0
        out.append({
            "segment": f"{seg['from_gate_name']} → {seg['to_gate_name']}",
            "from_reader_id": seg["from_reader_id"],
            "to_reader_id": seg["to_reader_id"],
            "distance_m": round(distance, 1),
            "avg_elapsed_ms": round(avg_ms),
            "avg_speed_ms": round(speed_ms, 2),
            "avg_speed_kmh": round(speed_ms * 3.6, 2),
            "sample_count": seg["count"],
        })
    return out


def get_head_to_head(db: Session, epc1: str, epc2: str) -> dict:
    """
    Head-to-head comparison: races where both horses competed.
    Returns win counts and average finish positions for shared races.
    """
    races1 = {e.race_id for e in db.query(RaceEntry).filter_by(horse_epc=epc1).all()}
    races2 = {e.race_id for e in db.query(RaceEntry).filter_by(horse_epc=epc2).all()}
    shared_race_ids = races1 & races2

    h1_wins = 0
    h2_wins = 0
    h1_positions = []
    h2_positions = []
    shared_races = []

    for race_id in sorted(shared_race_ids):
        r1 = db.query(RaceResult).filter_by(race_id=race_id, horse_epc=epc1).first()
        r2 = db.query(RaceResult).filter_by(race_id=race_id, horse_epc=epc2).first()
        if not r1 or not r2:
            continue
        if r1.finish_position < r2.finish_position:
            h1_wins += 1
        elif r2.finish_position < r1.finish_position:
            h2_wins += 1
        h1_positions.append(r1.finish_position)
        h2_positions.append(r2.finish_position)
        race = db.get(Race, race_id)
        shared_races.append({
            "race_id": race_id,
            "race_date": race.race_date.isoformat() if race else None,
            "epc1_position": r1.finish_position,
            "epc2_position": r2.finish_position,
            "epc1_elapsed_ms": r1.elapsed_ms,
            "epc2_elapsed_ms": r2.elapsed_ms,
        })

    return {
        "epc1": epc1,
        "epc2": epc2,
        "shared_races": len(shared_races),
        "epc1_wins": h1_wins,
        "epc2_wins": h2_wins,
        "draws": len(shared_races) - h1_wins - h2_wins,
        "epc1_avg_position": round(sum(h1_positions) / len(h1_positions), 2) if h1_positions else None,
        "epc2_avg_position": round(sum(h2_positions) / len(h2_positions), 2) if h2_positions else None,
        "races": shared_races,
    }


# ------------------------------------------------------------------ #
# Vet records
# ------------------------------------------------------------------ #

def add_vet_record(
    db: Session,
    epc: str,
    event_date: str,
    event_type: str,
    notes: Optional[str] = None,
    vet_name: Optional[str] = None,
) -> dict:
    if not db.get(Horse, epc):
        return {"ok": False, "error": f"Horse '{epc}' not found"}
    record = VetRecord(
        horse_epc=epc,
        event_date=event_date,
        event_type=event_type,
        notes=notes,
        vet_name=vet_name,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "id": record.id}


def get_vet_records(db: Session, epc: str) -> list[VetRecord]:
    return (
        db.query(VetRecord)
        .filter_by(horse_epc=epc)
        .order_by(VetRecord.event_date.desc())
        .all()
    )


# ------------------------------------------------------------------ #
# Workout records
# ------------------------------------------------------------------ #

def add_workout(
    db: Session,
    epc: str,
    workout_date: str,
    distance_m: float,
    **kwargs,
) -> dict:
    if not db.get(Horse, epc):
        return {"ok": False, "error": f"Horse '{epc}' not found"}
    record = WorkoutRecord(
        horse_epc=epc,
        workout_date=workout_date,
        distance_m=distance_m,
        **kwargs,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "id": record.id}


def get_workouts(db: Session, epc: str) -> list[WorkoutRecord]:
    return (
        db.query(WorkoutRecord)
        .filter_by(horse_epc=epc)
        .order_by(WorkoutRecord.workout_date.desc())
        .all()
    )


# ------------------------------------------------------------------ #
# Check-in records
# ------------------------------------------------------------------ #

def add_checkin(
    db: Session,
    epc: str,
    scanned_by: Optional[str] = None,
    location: Optional[str] = None,
    race_id: Optional[int] = None,
    **kwargs,
) -> dict:
    if not db.get(Horse, epc):
        return {"ok": False, "error": f"Horse '{epc}' not found"}
    record = CheckInRecord(
        horse_epc=epc,
        scanned_by=scanned_by,
        location=location,
        race_id=race_id,
        **kwargs,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "id": record.id}


def get_checkins(
    db: Session,
    epc: str,
    race_id: Optional[int] = None,
) -> list[CheckInRecord]:
    q = db.query(CheckInRecord).filter_by(horse_epc=epc)
    if race_id is not None:
        q = q.filter_by(race_id=race_id)
    return q.order_by(CheckInRecord.scanned_at.desc()).all()


# ------------------------------------------------------------------ #
# Test barn records
# ------------------------------------------------------------------ #

def test_barn_checkin(
    db: Session,
    epc: str,
    checkin_by: Optional[str] = None,
    race_id: Optional[int] = None,
    **kwargs,
) -> dict:
    if not db.get(Horse, epc):
        return {"ok": False, "error": f"Horse '{epc}' not found"}
    record = TestBarnRecord(
        horse_epc=epc,
        checkin_by=checkin_by,
        race_id=race_id,
        **kwargs,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "id": record.id}


def test_barn_checkout(
    db: Session,
    record_id: int,
    checkout_by: Optional[str] = None,
    result: str = "Clear",
    **kwargs,
) -> dict:
    record = db.get(TestBarnRecord, record_id)
    if not record:
        return {"ok": False, "error": f"Test barn record {record_id} not found"}
    record.checkout_by = checkout_by
    record.result = result
    for k, v in kwargs.items():
        setattr(record, k, v)
    db.commit()
    return {"ok": True, "id": record.id}


def get_test_barn_records(db: Session, epc: str) -> list[TestBarnRecord]:
    return (
        db.query(TestBarnRecord)
        .filter_by(horse_epc=epc)
        .order_by(TestBarnRecord.checkin_at.desc())
        .all()
    )


# ------------------------------------------------------------------ #
# User management
# ------------------------------------------------------------------ #

def get_user_by_username(db: Session, username: str) -> Optional[User]:
    return db.query(User).filter_by(username=username).first()


def create_user(
    db: Session,
    username: str,
    password: str,
    role: str,
    full_name: Optional[str] = None,
) -> User:
    user = User(
        username=username,
        hashed_password=hash_password(password),
        role=role,
        full_name=full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user or not user.active:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def list_users(db: Session, tenant_id: Optional[str] = None) -> list[User]:
    q = db.query(User).order_by(User.id)
    if tenant_id is not None:
        q = q.filter(User.tenant_id == tenant_id)
    return q.all()


def update_user(db: Session, user_id: int, **kwargs) -> Optional[User]:
    user = db.get(User, user_id)
    if not user:
        return None
    for k, v in kwargs.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> bool:
    user = db.get(User, user_id)
    if not user:
        return False
    db.delete(user)
    db.commit()
    return True


def reset_password(db: Session, user_id: int, new_password: str) -> bool:
    user = db.get(User, user_id)
    if not user:
        return False
    user.hashed_password = hash_password(new_password)
    db.commit()
    return True


# ------------------------------------------------------------------ #
# Webhook subscriptions
# ------------------------------------------------------------------ #

from app.models import WebhookSubscription


def list_webhooks(db: Session, tenant_id: Optional[str] = None) -> list[WebhookSubscription]:
    q = db.query(WebhookSubscription).order_by(WebhookSubscription.id)
    if tenant_id is not None:
        q = q.filter(WebhookSubscription.tenant_id == tenant_id)
    return q.all()


def get_webhook(db: Session, webhook_id: int) -> Optional[WebhookSubscription]:
    return db.get(WebhookSubscription, webhook_id)


def create_webhook(
    db: Session,
    name: str,
    url: str,
    secret: str,
    event_type: str = "race.finished",
    created_by: Optional[str] = None,
) -> WebhookSubscription:
    sub = WebhookSubscription(
        name=name,
        url=url,
        secret=secret,
        event_type=event_type,
        created_by=created_by,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def update_webhook(db: Session, webhook_id: int, **kwargs) -> Optional[WebhookSubscription]:
    sub = db.get(WebhookSubscription, webhook_id)
    if not sub:
        return None
    for k, v in kwargs.items():
        setattr(sub, k, v)
    db.commit()
    db.refresh(sub)
    return sub


def delete_webhook(db: Session, webhook_id: int) -> bool:
    sub = db.get(WebhookSubscription, webhook_id)
    if not sub:
        return False
    db.delete(sub)
    db.commit()
    return True


# ------------------------------------------------------------------ #
# Webhook delivery log
# ------------------------------------------------------------------ #

def get_webhook_deliveries(
    db: Session, webhook_id: int, limit: int = 50
) -> list[WebhookDelivery]:
    return (
        db.query(WebhookDelivery)
        .filter_by(subscription_id=webhook_id)
        .order_by(WebhookDelivery.attempted_at.desc())
        .limit(limit)
        .all()
    )


def get_failed_deliveries(db: Session, limit: int = 50) -> list[WebhookDelivery]:
    return (
        db.query(WebhookDelivery)
        .filter_by(success=False)
        .order_by(WebhookDelivery.attempted_at.desc())
        .limit(limit)
        .all()
    )


# ------------------------------------------------------------------ #
# Audit log
# ------------------------------------------------------------------ #

def write_audit_log(
    db: Session,
    user: Optional[User],
    action: str,
    target_type: str,
    target_id: str,
    detail: Optional[dict] = None,
) -> None:
    """Write an audit log entry. Best-effort: exceptions are swallowed so they never fail a request."""
    try:
        entry = AuditLog(
            id=str(uuid.uuid4()),
            user_id=user.id if user else None,
            username=user.username if user else "system",
            action=action,
            target_type=target_type,
            target_id=str(target_id),
            detail=json.dumps(detail) if detail else None,
            occurred_at=datetime.now(timezone.utc),
        )
        db.add(entry)
        db.commit()
    except Exception:
        db.rollback()


def list_audit_log(
    db: Session,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    limit: int = 100,
) -> list[AuditLog]:
    q = db.query(AuditLog)
    if target_type:
        q = q.filter(AuditLog.target_type == target_type)
    if target_id:
        q = q.filter(AuditLog.target_id == target_id)
    return q.order_by(AuditLog.occurred_at.desc()).limit(limit).all()


# ------------------------------------------------------------------ #
# Tenants
# ------------------------------------------------------------------ #

def create_tenant(db: Session, name: str, slug: str) -> Tenant:
    tenant = Tenant(
        id=str(uuid.uuid4()),
        name=name,
        slug=slug,
        created_at=datetime.now(timezone.utc),
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


def get_tenant(db: Session, tenant_id: str) -> Optional[Tenant]:
    return db.get(Tenant, tenant_id)


def get_tenant_by_slug(db: Session, slug: str) -> Optional[Tenant]:
    return db.query(Tenant).filter(Tenant.slug == slug).first()


def list_tenants(db: Session) -> list[Tenant]:
    return db.query(Tenant).order_by(Tenant.name).all()


def delete_tenant(db: Session, tenant_id: str) -> bool:
    tenant = db.get(Tenant, tenant_id)
    if not tenant:
        return False
    db.delete(tenant)
    db.commit()
    return True


# ------------------------------------------------------------------ #
# Track path (Item 1)
# ------------------------------------------------------------------ #

from app.models import TrackPathPoint


def upsert_track_path(db: Session, venue_id: str, points: list[dict]) -> dict:
    """Replace the entire track path for a venue. points = [{x, y}, ...]."""
    if not db.get(VenueRecord, venue_id):
        return {"ok": False, "error": f"Venue '{venue_id}' not found"}
    db.query(TrackPathPoint).filter_by(venue_id=venue_id).delete()
    for seq, pt in enumerate(points):
        db.add(TrackPathPoint(venue_id=venue_id, sequence=seq, x=pt["x"], y=pt["y"]))
    db.commit()
    return {"ok": True, "count": len(points)}


def get_track_path(db: Session, venue_id: str) -> list[TrackPathPoint]:
    return (
        db.query(TrackPathPoint)
        .filter_by(venue_id=venue_id)
        .order_by(TrackPathPoint.sequence)
        .all()
    )


# ------------------------------------------------------------------ #
# Biosensor (Item 2)
# ------------------------------------------------------------------ #

from app.models import BiosensorReading
from datetime import datetime as _dt


def add_biosensor_reading(
    db: Session,
    horse_epc: str,
    recorded_at: Optional[_dt] = None,
    race_id: Optional[int] = None,
    heart_rate_bpm: Optional[int] = None,
    temperature_c: Optional[float] = None,
    stride_hz: Optional[float] = None,
    source: str = "wearable",
) -> dict:
    if not db.get(Horse, horse_epc):
        return {"ok": False, "error": f"Horse '{horse_epc}' not found"}
    reading = BiosensorReading(
        horse_epc=horse_epc,
        race_id=race_id,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        heart_rate_bpm=heart_rate_bpm,
        temperature_c=temperature_c,
        stride_hz=stride_hz,
        source=source,
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return {"ok": True, "id": reading.id}


def get_biosensor_readings(
    db: Session, horse_epc: str, limit: int = 200
) -> list[BiosensorReading]:
    return (
        db.query(BiosensorReading)
        .filter_by(horse_epc=horse_epc)
        .order_by(BiosensorReading.recorded_at.desc())
        .limit(limit)
        .all()
    )


def get_race_biosensor_readings(
    db: Session, race_id: int
) -> list[BiosensorReading]:
    return (
        db.query(BiosensorReading)
        .filter_by(race_id=race_id)
        .order_by(BiosensorReading.horse_epc, BiosensorReading.recorded_at)
        .all()
    )


# ------------------------------------------------------------------ #
# Thermal temperature history (Item 3)
# ------------------------------------------------------------------ #

TEMP_WARN_HIGH = 38.5    # amber
TEMP_ALERT_HIGH = 39.0   # red
TEMP_ALERT_LOW = 37.0    # red


def get_temperature_history(db: Session, horse_epc: str, limit: int = 50) -> list[CheckInRecord]:
    return (
        db.query(CheckInRecord)
        .filter(CheckInRecord.horse_epc == horse_epc, CheckInRecord.temperature_c.isnot(None))
        .order_by(CheckInRecord.scanned_at.desc())
        .limit(limit)
        .all()
    )


def get_temperature_alerts(db: Session, horse_epc: str) -> list[CheckInRecord]:
    from sqlalchemy import or_
    return (
        db.query(CheckInRecord)
        .filter(
            CheckInRecord.horse_epc == horse_epc,
            CheckInRecord.temperature_c.isnot(None),
            or_(
                CheckInRecord.temperature_c >= TEMP_ALERT_HIGH,
                CheckInRecord.temperature_c <= TEMP_ALERT_LOW,
            ),
        )
        .order_by(CheckInRecord.scanned_at.desc())
        .all()
    )