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
    result = crud.create_horse(db, epc="EPC001", name="Thunderstrike")
    assert result["ok"] is True
    assert result["epc"] == "EPC001"


def test_create_horse_duplicate(db):
    crud.create_horse(db, epc="EPC001", name="Thunderstrike")
    result = crud.create_horse(db, epc="EPC001", name="Other")
    assert result["ok"] is False
    assert "already exists" in result["error"]


def test_get_horse(db):
    crud.create_horse(db, epc="EPC002", name="Bolt", breed="Thoroughbred")
    horse = crud.get_horse(db, "EPC002")
    assert horse is not None
    assert horse.name == "Bolt"
    assert horse.breed == "Thoroughbred"


def test_get_horse_missing(db):
    assert crud.get_horse(db, "MISSING") is None


def test_list_horses(db):
    crud.create_horse(db, epc="EPC001", name="A")
    crud.create_horse(db, epc="EPC002", name="B")
    horses = crud.list_horses(db)
    assert len(horses) == 2


def test_list_horses_pagination(db):
    for i in range(5):
        crud.create_horse(db, epc=f"EPC{i:03d}", name=f"Horse{i}")
    page = crud.list_horses(db, skip=2, limit=2)
    assert len(page) == 2


def test_add_owner(db):
    crud.create_horse(db, epc="EPC001", name="Bolt")
    result = crud.add_owner(db, "EPC001", "Alice", from_date="2024-01-01")
    assert result["ok"] is True

    horse = crud.get_horse(db, "EPC001")
    assert horse is not None
    assert len(horse.owners) == 1
    assert horse.owners[0].owner_name == "Alice"


def test_add_owner_missing_horse(db):
    result = crud.add_owner(db, "MISSING", "Alice")
    assert result["ok"] is False


def test_add_trainer(db):
    crud.create_horse(db, epc="EPC001", name="Bolt")
    result = crud.add_trainer(db, "EPC001", "Bob")
    assert result["ok"] is True

    horse = crud.get_horse(db, "EPC001")
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
# Persist race results
# ------------------------------------------------------------------ #

def _make_tracker_state(horses_data: list[dict], status: str = "finished") -> dict:
    return {"status": status, "horses": horses_data}


def _horse_data(horse_id: str, saddle_cloth: str, events: list[dict], finish_position=None) -> dict:
    return {
        "horse_id": horse_id,
        "saddle_cloth": saddle_cloth,
        "events": events,
        "finish_position": finish_position,
    }


def _event(reader_id: str, gate_name: str, distance_m: float, elapsed_ms: int, is_finish=False) -> dict:
    return {
        "reader_id": reader_id,
        "gate_name": gate_name,
        "distance_m": distance_m,
        "elapsed_ms": elapsed_ms,
        "is_finish": is_finish,
    }


@pytest.fixture
def db_ready(db):
    """DB with venue, two horses, and one race."""
    crud.upsert_venue(db, "FLEMINGTON", "Flemington", 1609.0)
    crud.create_horse(db, epc="EPC001", name="Thunderstrike")
    crud.create_horse(db, epc="EPC002", name="Bolt")
    r = crud.create_race(db, "FLEMINGTON", datetime(2026, 4, 2, 14, 30), 1609.0)
    db._test_race_id = r["race_id"]
    return db


def test_persist_race_results_basic(db_ready):
    db = db_ready
    race_id = db._test_race_id

    state = _make_tracker_state([
        _horse_data("EPC001", "1", [
            _event("GATE-START", "Start", 0, 0),
            _event("GATE-FINISH", "Finish", 1609, 92000, is_finish=True),
        ], finish_position=1),
        _horse_data("EPC002", "2", [
            _event("GATE-START", "Start", 0, 0),
            _event("GATE-FINISH", "Finish", 1609, 95000, is_finish=True),
        ], finish_position=2),
    ])

    result = crud.persist_race_results(db, race_id, state)
    assert result["ok"] is True
    assert result["persisted_entries"] == 2
    assert result["persisted_reads"] == 4
    assert result["persisted_results"] == 2
    assert result["skipped_horses"] == []

    race = crud.get_race(db, race_id)
    assert race is not None
    assert race.status == "finished"


def test_persist_race_results_idempotent(db_ready):
    db = db_ready
    race_id = db._test_race_id

    state = _make_tracker_state([
        _horse_data("EPC001", "1", [
            _event("GATE-FINISH", "Finish", 1609, 92000, is_finish=True),
        ], finish_position=1),
    ])

    r1 = crud.persist_race_results(db, race_id, state)
    r2 = crud.persist_race_results(db, race_id, state)

    assert r1["ok"] is True
    assert r2["ok"] is True
    # Second call should not insert new rows
    assert r2["persisted_entries"] == 0
    assert r2["persisted_reads"] == 0
    assert r2["persisted_results"] == 0


def test_persist_skips_unknown_horses(db_ready):
    db = db_ready
    race_id = db._test_race_id

    state = _make_tracker_state([
        _horse_data("EPC_UNKNOWN", "99", [
            _event("GATE-FINISH", "Finish", 1609, 90000, is_finish=True),
        ], finish_position=1),
    ])

    result = crud.persist_race_results(db, race_id, state)
    assert result["ok"] is True
    assert "EPC_UNKNOWN" in result["skipped_horses"]
    assert result["persisted_entries"] == 0


def test_persist_missing_race(db):
    state = _make_tracker_state([])
    result = crud.persist_race_results(db, 9999, state)
    assert result["ok"] is False
    assert "not found" in result["error"]


# ------------------------------------------------------------------ #
# Career & analytics
# ------------------------------------------------------------------ #

def test_get_career_history_empty(db_ready):
    db = db_ready
    history = crud.get_career_history(db, "EPC001")
    assert history == []


def test_get_career_history_after_persist(db_ready):
    db = db_ready
    race_id = db._test_race_id

    state = _make_tracker_state([
        _horse_data("EPC001", "1", [
            _event("GATE-FINISH", "Finish", 1609, 92000, is_finish=True),
        ], finish_position=1),
    ])
    crud.persist_race_results(db, race_id, state)

    history = crud.get_career_history(db, "EPC001")
    assert len(history) == 1
    assert history[0]["finish_position"] == 1
    assert history[0]["elapsed_ms"] == 92000


def test_get_form_guide(db_ready):
    db = db_ready
    crud.upsert_venue(db, "FLEMINGTON", "Flemington", 1609.0)

    # Create 3 races, persist EPC001 results in all
    for i in range(3):
        r = crud.create_race(db, "FLEMINGTON", datetime(2026, 4, i + 1, 14, 30), 1609.0)
        state = _make_tracker_state([
            _horse_data("EPC001", "1", [
                _event("GATE-FINISH", "Finish", 1609, 90000 + i * 1000, is_finish=True),
            ], finish_position=1),
        ])
        crud.persist_race_results(db, r["race_id"], state)

    form = crud.get_form_guide(db, "EPC001", n=2)
    assert len(form) == 2  # only last 2


def test_get_sectional_averages(db_ready):
    db = db_ready
    race_id = db._test_race_id

    state = _make_tracker_state([
        _horse_data("EPC001", "1", [
            _event("GATE-START", "Start", 0, 0),
            _event("GATE-MID", "Furlong 4", 800, 45000),
            _event("GATE-FINISH", "Finish", 1609, 92000, is_finish=True),
        ], finish_position=1),
    ])
    crud.persist_race_results(db, race_id, state)

    avgs = crud.get_sectional_averages(db, "EPC001")
    assert len(avgs) == 2  # Start→Mid and Mid→Finish
    segments = {a["segment"] for a in avgs}
    assert "Start → Furlong 4" in segments
    assert "Furlong 4 → Finish" in segments


def test_get_head_to_head(db_ready):
    db = db_ready
    race_id = db._test_race_id

    state = _make_tracker_state([
        _horse_data("EPC001", "1", [
            _event("GATE-FINISH", "Finish", 1609, 92000, is_finish=True),
        ], finish_position=1),
        _horse_data("EPC002", "2", [
            _event("GATE-FINISH", "Finish", 1609, 95000, is_finish=True),
        ], finish_position=2),
    ])
    crud.persist_race_results(db, race_id, state)

    h2h = crud.get_head_to_head(db, "EPC001", "EPC002")
    assert h2h["shared_races"] == 1
    assert h2h["epc1_wins"] == 1
    assert h2h["epc2_wins"] == 0
    assert h2h["epc1_avg_position"] == 1.0
    assert h2h["epc2_avg_position"] == 2.0


# ------------------------------------------------------------------ #
# Vet records
# ------------------------------------------------------------------ #

def test_add_vet_record(db):
    crud.create_horse(db, epc="EPC001", name="Bolt")
    result = crud.add_vet_record(db, "EPC001", "2026-04-01", "implant", vet_name="Dr. Smith")
    assert result["ok"] is True
    assert "id" in result


def test_add_vet_record_missing_horse(db):
    result = crud.add_vet_record(db, "MISSING", "2026-04-01", "implant")
    assert result["ok"] is False


def test_get_vet_records(db):
    crud.create_horse(db, epc="EPC001", name="Bolt")
    crud.add_vet_record(db, "EPC001", "2026-03-01", "clearance")
    crud.add_vet_record(db, "EPC001", "2026-04-01", "implant")
    records = crud.get_vet_records(db, "EPC001")
    assert len(records) == 2
    # Newest first
    assert records[0].event_date == "2026-04-01"