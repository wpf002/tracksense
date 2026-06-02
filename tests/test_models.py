"""
tests/test_models.py

Database layer tests using SQLite in-memory.
No PostgreSQL connection required.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401 — registers all ORM classes
from app import crud


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


# ------------------------------------------------------------------ #
# Horse CRUD
# ------------------------------------------------------------------ #

def test_create_horse(db):
    result = crud.create_horse(db, chip_id="985112000100001", name="Thunderstrike")
    assert result["ok"] is True
    assert result["chip_id"] == "985112000100001"


def test_create_horse_duplicate(db):
    crud.create_horse(db, chip_id="985112000100001", name="Thunderstrike")
    result = crud.create_horse(db, chip_id="985112000100001", name="Other")
    assert result["ok"] is False
    assert "already exists" in result["error"]


def test_get_horse(db):
    crud.create_horse(db, chip_id="985112000100002", name="Bolt", breed="Thoroughbred")
    horse = crud.get_horse(db, "985112000100002")
    assert horse is not None
    assert horse.name == "Bolt"
    assert horse.breed == "Thoroughbred"


def test_get_horse_missing(db):
    assert crud.get_horse(db, "MISSING") is None


def test_list_horses(db):
    crud.create_horse(db, chip_id="985112000100001", name="A")
    crud.create_horse(db, chip_id="985112000100002", name="B")
    horses = crud.list_horses(db)
    assert len(horses) == 2


def test_list_horses_pagination(db):
    for i in range(5):
        crud.create_horse(db, chip_id=f"EPC{i:03d}", name=f"Horse{i}")
    page = crud.list_horses(db, skip=2, limit=2)
    assert len(page) == 2


def test_add_owner(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    result = crud.add_owner(db, "985112000100001", "Alice", from_date="2024-01-01")
    assert result["ok"] is True

    horse = crud.get_horse(db, "985112000100001")
    assert horse is not None
    assert len(horse.owners) == 1
    assert horse.owners[0].owner_name == "Alice"


def test_add_owner_missing_horse(db):
    result = crud.add_owner(db, "MISSING", "Alice")
    assert result["ok"] is False


def test_add_trainer(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    result = crud.add_trainer(db, "985112000100001", "Bob")
    assert result["ok"] is True

    horse = crud.get_horse(db, "985112000100001")
    assert horse is not None
    assert horse.trainers[0].trainer_name == "Bob"


# ------------------------------------------------------------------ #
# Venue (DB mirror)
# ------------------------------------------------------------------ #

def test_upsert_venue_create(db):
    venue = crud.upsert_venue(db, "FLEMINGTON", "Flemington Racecourse", 1609.0)
    assert venue.venue_id == "FLEMINGTON"
    assert venue.name == "Flemington Racecourse"


def test_upsert_venue_update(db):
    crud.upsert_venue(db, "FLEMINGTON", "Old Name", 1609.0)
    venue = crud.upsert_venue(db, "FLEMINGTON", "New Name", 2000.0)
    assert venue.name == "New Name"
    assert venue.total_distance_m == 2000.0


# ------------------------------------------------------------------ #
# Race CRUD
# ------------------------------------------------------------------ #

@pytest.fixture
def db_with_venue(db):
    crud.upsert_venue(db, "FLEMINGTON", "Flemington", 1609.0)
    return db


def test_create_race(db_with_venue):
    db = db_with_venue
    result = crud.create_race(db, "FLEMINGTON", datetime(2026, 4, 2, 14, 30), 1609.0)
    assert result["ok"] is True
    assert "race_id" in result


def test_create_race_missing_venue(db):
    result = crud.create_race(db, "NOWHERE", datetime(2026, 4, 2), 1609.0)
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_get_race(db_with_venue):
    db = db_with_venue
    r = crud.create_race(db, "FLEMINGTON", datetime(2026, 4, 2), 1609.0)
    race = crud.get_race(db, r["race_id"])
    assert race is not None
    assert race.venue_id == "FLEMINGTON"
    assert race.status == "pending"


def test_list_races(db_with_venue):
    db = db_with_venue
    crud.create_race(db, "FLEMINGTON", datetime(2026, 4, 1), 1609.0)
    crud.create_race(db, "FLEMINGTON", datetime(2026, 4, 2), 1609.0)
    races = crud.list_races(db)
    assert len(races) == 2
    # Should be newest first
    assert races[0].race_date > races[1].race_date


# ------------------------------------------------------------------ #
# Vet records
# ------------------------------------------------------------------ #

def test_add_vet_record(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    result = crud.add_vet_record(db, "985112000100001", "2026-04-01", "implant", vet_name="Dr. Smith")
    assert result["ok"] is True
    assert "id" in result


def test_add_vet_record_missing_horse(db):
    result = crud.add_vet_record(db, "MISSING", "2026-04-01", "implant")
    assert result["ok"] is False


def test_get_vet_records(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    crud.add_vet_record(db, "985112000100001", "2026-03-01", "clearance")
    crud.add_vet_record(db, "985112000100001", "2026-04-01", "implant")
    records = crud.get_vet_records(db, "985112000100001")
    assert len(records) == 2
    # Newest first
    assert records[0].event_date == "2026-04-01"


# ------------------------------------------------------------------ #
# Workout records
# ------------------------------------------------------------------ #

def test_add_workout(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    result = crud.add_workout(db, "985112000100001", "2026-03-15", 800.0,
                              surface="Turf", duration_ms=52000,
                              track_condition="Fast", trainer_name="J. Cummings",
                              notes="Strong gallop")
    assert result["ok"] is True
    assert "id" in result


def test_add_workout_missing_horse(db):
    result = crud.add_workout(db, "MISSING", "2026-03-15", 800.0)
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_get_workouts(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    crud.add_workout(db, "985112000100001", "2026-03-01", 600.0)
    crud.add_workout(db, "985112000100001", "2026-03-10", 800.0)
    crud.add_workout(db, "985112000100001", "2026-03-20", 1000.0)
    records = crud.get_workouts(db, "985112000100001")
    assert len(records) == 3
    # Newest first
    assert records[0].workout_date == "2026-03-20"


def test_get_workouts_empty(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    assert crud.get_workouts(db, "985112000100001") == []


# ------------------------------------------------------------------ #
# Check-in records
# ------------------------------------------------------------------ #

def test_add_checkin(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    result = crud.add_checkin(db, "985112000100001", scanned_by="Head Steward",
                              location="Paddock Check-In", verified=True)
    assert result["ok"] is True
    assert "id" in result


def test_add_checkin_missing_horse(db):
    result = crud.add_checkin(db, "MISSING", scanned_by="Head Steward")
    assert result["ok"] is False


def test_get_checkins(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    crud.add_checkin(db, "985112000100001", scanned_by="Steward A")
    crud.add_checkin(db, "985112000100001", scanned_by="Steward B")
    records = crud.get_checkins(db, "985112000100001")
    assert len(records) == 2


def test_get_checkins_filter_by_race(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    crud.add_checkin(db, "985112000100001", race_id=1)
    crud.add_checkin(db, "985112000100001", race_id=2)
    crud.add_checkin(db, "985112000100001", race_id=1)
    records = crud.get_checkins(db, "985112000100001", race_id=1)
    assert len(records) == 2


# ------------------------------------------------------------------ #
# Test barn records
# ------------------------------------------------------------------ #

def test_test_barn_checkin(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    result = crud.test_barn_checkin(db, "985112000100001", checkin_by="TB Official",
                                    sample_id="TB-0001-01-1234")
    assert result["ok"] is True
    assert "id" in result


def test_test_barn_checkin_missing_horse(db):
    result = crud.test_barn_checkin(db, "MISSING", checkin_by="TB Official")
    assert result["ok"] is False


def test_test_barn_checkout(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    checkin = crud.test_barn_checkin(db, "985112000100001", checkin_by="TB Official")
    record_id = checkin["id"]

    result = crud.test_barn_checkout(db, record_id, checkout_by="TB Official", result="Clear")
    assert result["ok"] is True

    from app.models import TestBarnRecord
    record = db.get(TestBarnRecord, record_id)
    assert record is not None
    assert record.checkout_by == "TB Official"
    assert record.result == "Clear"


def test_test_barn_checkout_missing_record(db):
    result = crud.test_barn_checkout(db, 9999, checkout_by="TB Official")
    assert result["ok"] is False
    assert "not found" in result["error"]


def test_get_test_barn_records(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    crud.test_barn_checkin(db, "985112000100001", sample_id="TB-0001-01-1111")
    crud.test_barn_checkin(db, "985112000100001", sample_id="TB-0002-01-2222")
    records = crud.get_test_barn_records(db, "985112000100001")
    assert len(records) == 2


def test_get_test_barn_records_empty(db):
    crud.create_horse(db, chip_id="985112000100001", name="Bolt")
    assert crud.get_test_barn_records(db, "985112000100001") == []


# ------------------------------------------------------------------ #
# Race name field (Item 4)
# ------------------------------------------------------------------ #

def test_create_race_with_name(db_with_venue):
    db = db_with_venue
    result = crud.create_race(db, "FLEMINGTON", datetime(2026, 5, 1, 14, 0), 1609.0, name="The Flemington Cup")
    assert result["ok"] is True
    race = crud.get_race(db, result["race_id"])
    assert race.name == "The Flemington Cup"


def test_create_race_without_name_is_null(db_with_venue):
    db = db_with_venue
    result = crud.create_race(db, "FLEMINGTON", datetime(2026, 5, 1, 14, 0), 1609.0)
    assert result["ok"] is True
    race = crud.get_race(db, result["race_id"])
    assert race.name is None