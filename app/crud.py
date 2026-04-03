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

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.models import (
    Horse, Owner, Trainer, VenueRecord, GateRecord,
    Race, RaceEntry, GateRead, RaceResult, VetRecord,
    WorkoutRecord, CheckInRecord, TestBarnRecord,
)


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
    )
    db.add(horse)
    db.commit()
    db.refresh(horse)
    return {"ok": True, "epc": horse.epc}


def get_horse(db: Session, epc: str) -> Optional[Horse]:
    return db.get(Horse, epc)


def list_horses(db: Session, skip: int = 0, limit: int = 100) -> list[Horse]:
    return db.query(Horse).offset(skip).limit(limit).all()


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
) -> dict:
    if not db.get(VenueRecord, venue_id):
        return {"ok": False, "error": f"Venue '{venue_id}' not found in database"}
    race = Race(
        venue_id=venue_id,
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


def list_races(db: Session, skip: int = 0, limit: int = 50) -> list[Race]:
    return (
        db.query(Race)
        .order_by(Race.race_date.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


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