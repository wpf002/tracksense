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
    Horse, Owner, Trainer, VenueRecord,
    Race, RaceEntry, RaceResult, VetRecord,
    WorkoutRecord, CheckInRecord, TestBarnRecord, User,
    AuditLog, WebhookDelivery, Tenant,
)
from app.auth import hash_password, verify_password


# ------------------------------------------------------------------ #
# Horse
# ------------------------------------------------------------------ #

def create_horse(
    db: Session,
    chip_id: str,
    name: str,
    breed: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    implant_date: Optional[str] = None,
    implant_vet: Optional[str] = None,
    racing_api_horse_id: Optional[str] = None,
) -> dict:
    if db.get(Horse, chip_id):
        return {"ok": False, "error": f"Horse with chip ID '{chip_id}' already exists"}
    horse = Horse(
        chip_id=chip_id,
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
    return {"ok": True, "chip_id": horse.chip_id}


def get_horse(db: Session, chip_id: str) -> Optional[Horse]:
    return db.get(Horse, chip_id)


def list_horses(db: Session, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None) -> list[Horse]:
    q = db.query(Horse)
    if tenant_id is not None:
        q = q.filter(Horse.tenant_id == tenant_id)
    return q.offset(skip).limit(limit).all()


def add_owner(
    db: Session,
    chip_id: str,
    owner_name: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    if not db.get(Horse, chip_id):
        return {"ok": False, "error": f"Horse '{chip_id}' not found"}
    db.add(Owner(horse_chip_id=chip_id, owner_name=owner_name, from_date=from_date, to_date=to_date))
    db.commit()
    return {"ok": True}


def add_trainer(
    db: Session,
    chip_id: str,
    trainer_name: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    if not db.get(Horse, chip_id):
        return {"ok": False, "error": f"Horse '{chip_id}' not found"}
    db.add(Trainer(horse_chip_id=chip_id, trainer_name=trainer_name, from_date=from_date, to_date=to_date))
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
# Career & analytics
# ------------------------------------------------------------------ #

def get_career_history(db: Session, chip_id: str) -> list[dict]:
    """All races this horse entered, with result if available, newest first."""
    entries = (
        db.query(RaceEntry)
        .filter_by(horse_chip_id=chip_id)
        .join(Race)
        .order_by(Race.race_date.desc())
        .all()
    )
    out = []
    for entry in entries:
        race = entry.race
        result = (
            db.query(RaceResult)
            .filter_by(race_id=race.id, horse_chip_id=chip_id)
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


def get_form_guide(db: Session, chip_id: str, n: int = 5) -> list[dict]:
    """Last n starts with results."""
    return get_career_history(db, chip_id)[:n]


def get_head_to_head(db: Session, chip_id1: str, chip_id2: str) -> dict:
    """
    Head-to-head comparison: races where both horses competed.
    Returns win counts and average finish positions for shared races.
    """
    races1 = {e.race_id for e in db.query(RaceEntry).filter_by(horse_chip_id=chip_id1).all()}
    races2 = {e.race_id for e in db.query(RaceEntry).filter_by(horse_chip_id=chip_id2).all()}
    shared_race_ids = races1 & races2

    h1_wins = 0
    h2_wins = 0
    h1_positions = []
    h2_positions = []
    shared_races = []

    for race_id in sorted(shared_race_ids):
        r1 = db.query(RaceResult).filter_by(race_id=race_id, horse_chip_id=chip_id1).first()
        r2 = db.query(RaceResult).filter_by(race_id=race_id, horse_chip_id=chip_id2).first()
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
        "chip_id1": chip_id1,
        "chip_id2": chip_id2,
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
    chip_id: str,
    event_date: str,
    event_type: str,
    notes: Optional[str] = None,
    vet_name: Optional[str] = None,
) -> dict:
    if not db.get(Horse, chip_id):
        return {"ok": False, "error": f"Horse '{chip_id}' not found"}
    record = VetRecord(
        horse_chip_id=chip_id,
        event_date=event_date,
        event_type=event_type,
        notes=notes,
        vet_name=vet_name,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "id": record.id}


def get_vet_records(db: Session, chip_id: str) -> list[VetRecord]:
    return (
        db.query(VetRecord)
        .filter_by(horse_chip_id=chip_id)
        .order_by(VetRecord.event_date.desc())
        .all()
    )


# ------------------------------------------------------------------ #
# Workout records
# ------------------------------------------------------------------ #

def add_workout(
    db: Session,
    chip_id: str,
    workout_date: str,
    distance_m: float,
    **kwargs,
) -> dict:
    if not db.get(Horse, chip_id):
        return {"ok": False, "error": f"Horse '{chip_id}' not found"}
    record = WorkoutRecord(
        horse_chip_id=chip_id,
        workout_date=workout_date,
        distance_m=distance_m,
        **kwargs,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "id": record.id}


def get_workouts(db: Session, chip_id: str) -> list[WorkoutRecord]:
    return (
        db.query(WorkoutRecord)
        .filter_by(horse_chip_id=chip_id)
        .order_by(WorkoutRecord.workout_date.desc())
        .all()
    )


# ------------------------------------------------------------------ #
# Check-in records
# ------------------------------------------------------------------ #

def add_checkin(
    db: Session,
    chip_id: str,
    scanned_by: Optional[str] = None,
    location: Optional[str] = None,
    race_id: Optional[int] = None,
    **kwargs,
) -> dict:
    if not db.get(Horse, chip_id):
        return {"ok": False, "error": f"Horse '{chip_id}' not found"}
    record = CheckInRecord(
        horse_chip_id=chip_id,
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
    chip_id: str,
    race_id: Optional[int] = None,
) -> list[CheckInRecord]:
    q = db.query(CheckInRecord).filter_by(horse_chip_id=chip_id)
    if race_id is not None:
        q = q.filter_by(race_id=race_id)
    return q.order_by(CheckInRecord.scanned_at.desc()).all()


# ------------------------------------------------------------------ #
# Test barn records
# ------------------------------------------------------------------ #

def test_barn_checkin(
    db: Session,
    chip_id: str,
    checkin_by: Optional[str] = None,
    race_id: Optional[int] = None,
    **kwargs,
) -> dict:
    if not db.get(Horse, chip_id):
        return {"ok": False, "error": f"Horse '{chip_id}' not found"}
    record = TestBarnRecord(
        horse_chip_id=chip_id,
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


def get_test_barn_records(db: Session, chip_id: str) -> list[TestBarnRecord]:
    return (
        db.query(TestBarnRecord)
        .filter_by(horse_chip_id=chip_id)
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
# Biosensor (Item 2)
# ------------------------------------------------------------------ #

from app.models import BiosensorReading
from datetime import datetime as _dt


def add_biosensor_reading(
    db: Session,
    horse_chip_id: str,
    recorded_at: Optional[_dt] = None,
    race_id: Optional[int] = None,
    heart_rate_bpm: Optional[int] = None,
    temperature_c: Optional[float] = None,
    stride_hz: Optional[float] = None,
    source: str = "wearable",
) -> dict:
    if not db.get(Horse, horse_chip_id):
        return {"ok": False, "error": f"Horse '{horse_chip_id}' not found"}
    reading = BiosensorReading(
        horse_chip_id=horse_chip_id,
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
    db: Session, horse_chip_id: str, limit: int = 200
) -> list[BiosensorReading]:
    return (
        db.query(BiosensorReading)
        .filter_by(horse_chip_id=horse_chip_id)
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
        .order_by(BiosensorReading.horse_chip_id, BiosensorReading.recorded_at)
        .all()
    )


# ------------------------------------------------------------------ #
# Thermal temperature history (Item 3)
# ------------------------------------------------------------------ #

TEMP_WARN_HIGH = 38.5    # amber
TEMP_ALERT_HIGH = 39.0   # red
TEMP_ALERT_LOW = 37.0    # red


def get_temperature_history(db: Session, horse_chip_id: str, limit: int = 50) -> list[CheckInRecord]:
    return (
        db.query(CheckInRecord)
        .filter(CheckInRecord.horse_chip_id == horse_chip_id, CheckInRecord.temperature_c.isnot(None))
        .order_by(CheckInRecord.scanned_at.desc())
        .limit(limit)
        .all()
    )


def get_temperature_alerts(db: Session, horse_chip_id: str) -> list[CheckInRecord]:
    from sqlalchemy import or_
    return (
        db.query(CheckInRecord)
        .filter(
            CheckInRecord.horse_chip_id == horse_chip_id,
            CheckInRecord.temperature_c.isnot(None),
            or_(
                CheckInRecord.temperature_c >= TEMP_ALERT_HIGH,
                CheckInRecord.temperature_c <= TEMP_ALERT_LOW,
            ),
        )
        .order_by(CheckInRecord.scanned_at.desc())
        .all()
    )


# ------------------------------------------------------------------ #
# Phase 3 — HISA Reporting
# ------------------------------------------------------------------ #

from app.models import TreatmentRecord, StewardsRuling, SurfaceConditionLog, HISASubmission


def add_treatment(db: Session, horse_chip_id: str, treatment_date: str, substance: str, **kwargs) -> dict:
    if not db.get(Horse, horse_chip_id):
        return {"ok": False, "error": f"Horse '{horse_chip_id}' not found"}
    record = TreatmentRecord(horse_chip_id=horse_chip_id, treatment_date=treatment_date,
                             substance=substance, **kwargs)
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "id": record.id}


def get_treatments(db: Session, horse_chip_id: str) -> list[TreatmentRecord]:
    return (db.query(TreatmentRecord).filter_by(horse_chip_id=horse_chip_id)
            .order_by(TreatmentRecord.treatment_date.desc()).all())


def create_stewards_ruling(db: Session, **kwargs) -> dict:
    from datetime import timedelta
    ruling_date = kwargs.get("ruling_date")
    if ruling_date and "deadline_at" not in kwargs:
        kwargs["deadline_at"] = ruling_date + timedelta(hours=48)
    ruling = StewardsRuling(**kwargs)
    db.add(ruling)
    db.commit()
    db.refresh(ruling)
    return {"ok": True, "id": ruling.id, "deadline_at": ruling.deadline_at.isoformat()}


def get_stewards_rulings(db: Session, horse_chip_id: Optional[str] = None,
                         race_id: Optional[int] = None) -> list[StewardsRuling]:
    q = db.query(StewardsRuling).order_by(StewardsRuling.ruling_date.desc())
    if horse_chip_id:
        q = q.filter_by(horse_chip_id=horse_chip_id)
    if race_id:
        q = q.filter_by(race_id=race_id)
    return q.all()


def upsert_surface_condition(db: Session, venue_id: str, logged_date: str, **kwargs) -> dict:
    from app.models import VenueRecord
    if not db.get(VenueRecord, venue_id):
        return {"ok": False, "error": f"Venue '{venue_id}' not found"}
    existing = (db.query(SurfaceConditionLog)
                .filter_by(venue_id=venue_id, logged_date=logged_date).first())
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return {"ok": True, "id": existing.id, "updated": True}
    log = SurfaceConditionLog(venue_id=venue_id, logged_date=logged_date, **kwargs)
    db.add(log)
    db.commit()
    db.refresh(log)
    return {"ok": True, "id": log.id, "updated": False}


def get_surface_conditions(db: Session, venue_id: str, limit: int = 30) -> list[SurfaceConditionLog]:
    return (db.query(SurfaceConditionLog).filter_by(venue_id=venue_id)
            .order_by(SurfaceConditionLog.logged_date.desc()).limit(limit).all())


def create_hisa_submission(db: Session, rule_category: str, source_record_type: str,
                           source_record_id: int, payload_json: str,
                           horse_chip_id: Optional[str] = None,
                           deadline_at=None,
                           tenant_id: Optional[str] = None) -> HISASubmission:
    sub = HISASubmission(
        rule_category=rule_category, status="pending",
        source_record_type=source_record_type, source_record_id=source_record_id,
        horse_chip_id=horse_chip_id, deadline_at=deadline_at,
        payload_json=payload_json, tenant_id=tenant_id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def get_hisa_submissions(db: Session, status: Optional[str] = None,
                         rule_category: Optional[str] = None,
                         tenant_id: Optional[str] = None,
                         limit: int = 100) -> list[HISASubmission]:
    q = db.query(HISASubmission).order_by(HISASubmission.created_at.desc())
    if status:
        q = q.filter(HISASubmission.status == status)
    if rule_category:
        q = q.filter(HISASubmission.rule_category == rule_category)
    if tenant_id:
        q = q.filter(HISASubmission.tenant_id == tenant_id)
    return q.limit(limit).all()


def mark_submission_submitted(db: Session, submission_id: int,
                               user_id: Optional[str] = None) -> Optional[HISASubmission]:
    sub = db.get(HISASubmission, submission_id)
    if not sub:
        return None
    sub.status = "submitted"
    sub.submitted_at = datetime.now(timezone.utc)
    sub.submitted_by = user_id
    db.commit()
    db.refresh(sub)
    return sub


def submission_exists(db: Session, source_record_type: str, source_record_id: int) -> bool:
    return db.query(HISASubmission).filter_by(
        source_record_type=source_record_type,
        source_record_id=source_record_id,
    ).first() is not None



# ------------------------------------------------------------------ #
# Phase 4 — Training Center Module
# ------------------------------------------------------------------ #

from app.models import VetCheckRecord


def add_vet_check(db: Session, horse_chip_id: str, check_date: str,
                  check_type: str, outcome: str, **kwargs) -> dict:
    if not db.get(Horse, horse_chip_id):
        return {"ok": False, "error": f"Horse '{horse_chip_id}' not found"}
    record = VetCheckRecord(horse_chip_id=horse_chip_id, check_date=check_date,
                            check_type=check_type, outcome=outcome, **kwargs)
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"ok": True, "id": record.id}


def get_vet_checks(db: Session, horse_chip_id: str) -> list[VetCheckRecord]:
    return (db.query(VetCheckRecord).filter_by(horse_chip_id=horse_chip_id)
            .order_by(VetCheckRecord.check_date.desc()).all())


def get_training_roster(db: Session, tenant_id: Optional[str] = None,
                        trainer_name: Optional[str] = None) -> list[dict]:
    """
    Daily training center roster: all horses for the tenant/trainer with a
    status snapshot — last workout, latest vet check outcome, open treatment
    count, and pending HISA submissions.
    """
    from app.models import WorkoutRecord, TreatmentRecord
    from sqlalchemy import func as sqlfunc

    q = db.query(Horse)
    if tenant_id:
        q = q.filter(Horse.tenant_id == tenant_id)

    horses = q.order_by(Horse.name).all()
    roster = []

    for horse in horses:
        # Filter by trainer if specified
        if trainer_name:
            current_trainer = next((t.trainer_name for t in horse.trainers if not t.to_date), None)
            if current_trainer != trainer_name:
                continue

        # Last workout
        last_workout = (db.query(WorkoutRecord).filter_by(horse_chip_id=horse.chip_id)
                        .order_by(WorkoutRecord.workout_date.desc()).first())

        # Latest vet check
        latest_check = (db.query(VetCheckRecord).filter_by(horse_chip_id=horse.chip_id)
                        .order_by(VetCheckRecord.check_date.desc()).first())

        # Open (non-cleared) treatment count
        open_treatments = (db.query(TreatmentRecord)
                           .filter(TreatmentRecord.horse_chip_id == horse.chip_id)
                           .count())

        # Pending HISA submissions for this horse
        pending_hisa = (db.query(HISASubmission)
                        .filter(HISASubmission.horse_chip_id == horse.chip_id,
                                HISASubmission.status == "pending")
                        .count())

        current_trainer_name = next((t.trainer_name for t in horse.trainers if not t.to_date), None)
        current_owner_name = next((o.owner_name for o in horse.owners if not o.to_date), None)

        roster.append({
            "chip_id": horse.chip_id,
            "name": horse.name,
            "breed": horse.breed,
            "current_trainer": current_trainer_name,
            "current_owner": current_owner_name,
            "last_workout_date": last_workout.workout_date if last_workout else None,
            "last_workout_distance_m": last_workout.distance_m if last_workout else None,
            "latest_vet_check_date": latest_check.check_date if latest_check else None,
            "latest_vet_check_outcome": latest_check.outcome if latest_check else None,
            "open_treatment_count": open_treatments,
            "pending_hisa_count": pending_hisa,
        })

    return roster


def get_owner_report(db: Session, horse_chip_id: str, period: str = "week") -> dict:
    """
    Aggregated performance summary for owner reporting.
    period: 'week' (7 days) or 'month' (30 days).
    """
    from datetime import date, timedelta
    from app.models import WorkoutRecord, TreatmentRecord, RaceResult, RaceEntry

    today = date.today()
    days = 7 if period == "week" else 30
    since = (today - timedelta(days=days)).isoformat()

    horse = db.get(Horse, horse_chip_id)
    if not horse:
        return None

    workouts = (db.query(WorkoutRecord)
                .filter(WorkoutRecord.horse_chip_id == horse_chip_id,
                        WorkoutRecord.workout_date >= since)
                .order_by(WorkoutRecord.workout_date.desc()).all())

    vet_checks = (db.query(VetCheckRecord)
                  .filter(VetCheckRecord.horse_chip_id == horse_chip_id,
                          VetCheckRecord.check_date >= since)
                  .order_by(VetCheckRecord.check_date.desc()).all())

    treatments = (db.query(TreatmentRecord)
                  .filter(TreatmentRecord.horse_chip_id == horse_chip_id,
                          TreatmentRecord.treatment_date >= since)
                  .all())

    # Recent race results
    recent_entries = (db.query(RaceEntry).filter_by(horse_chip_id=horse_chip_id)
                      .join(RaceEntry.race)
                      .order_by(db.query(RaceEntry).join(RaceEntry.race)
                                .filter_by(horse_chip_id=horse_chip_id)
                                .first().__class__.race_id.desc()
                                if False else RaceEntry.race_id.desc())
                      .limit(5).all()) if False else []

    # Simplified race lookup
    from app.models import Race
    race_results = (
        db.query(RaceResult, Race)
        .join(Race, RaceResult.race_id == Race.id)
        .filter(RaceResult.horse_chip_id == horse_chip_id,
                Race.race_date >= since)
        .order_by(Race.race_date.desc())
        .limit(5)
        .all()
    )

    current_trainer = next((t.trainer_name for t in horse.trainers if not t.to_date), None)
    current_owner = next((o.owner_name for o in horse.owners if not o.to_date), None)

    total_distance = sum(w.distance_m for w in workouts if w.distance_m)

    return {
        "horse": {"chip_id": horse.chip_id, "name": horse.name,
                  "breed": horse.breed, "current_trainer": current_trainer,
                  "current_owner": current_owner},
        "period": period,
        "period_days": days,
        "since": since,
        "workouts": {
            "count": len(workouts),
            "total_distance_m": total_distance,
            "records": [
                {"date": w.workout_date, "distance_m": w.distance_m,
                 "surface": w.surface, "duration_ms": w.duration_ms,
                 "trainer": w.trainer_name, "rider": w.rider_name}
                for w in workouts
            ],
        },
        "vet_checks": {
            "count": len(vet_checks),
            "last_outcome": vet_checks[0].outcome if vet_checks else None,
            "records": [
                {"date": v.check_date, "type": v.check_type,
                 "outcome": v.outcome, "vet": v.vet_name}
                for v in vet_checks
            ],
        },
        "treatments": {
            "count": len(treatments),
            "records": [
                {"date": t.treatment_date, "substance": t.substance,
                 "is_prohibited": t.is_prohibited}
                for t in treatments
            ],
        },
        "race_results": [
            {"race_id": rr.race_id, "finish_position": rr.finish_position,
             "elapsed_ms": rr.elapsed_ms, "venue_id": race.venue_id,
             "race_date": race.race_date.isoformat() if race.race_date else None}
            for rr, race in race_results
        ],
    }
