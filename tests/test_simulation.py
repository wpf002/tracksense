"""
tests/test_simulation.py

ITEM 9: Full end-to-end simulation validation.

Exercises the complete race lifecycle using POST /race/simulate:
  1. Register venue + gates
  2. Register horses and start race
  3. Trigger simulation (runs in background threads)
  4. Wait for all horses to finish
  5. Assert finish order, gate reads, and race state are correct
  6. Persist results to DB and verify export endpoints

The simulation runs at real speed (scaled down by the test) using the
existing simulate endpoint and race tracker, giving true end-to-end coverage.
"""

import time
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.server import app
from app.gate_registry import registry
from app.race_tracker import set_tracker
from app.routes import get_current_user
from app.database import get_db, Base
from app.models import User, VenueRecord, GateRecord, Horse, Race
from app.api_keys_router import require_jwt_or_api_key
from app import crud


# ------------------------------------------------------------------ #
# Auth + DB fixtures
# ------------------------------------------------------------------ #

_mock_admin = User()
_mock_admin.id = 1
_mock_admin.username = "sim_admin"
_mock_admin.hashed_password = "x"
_mock_admin.role = "admin"
_mock_admin.full_name = "Sim Admin"
_mock_admin.active = True
_mock_admin.tenant_id = None


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sim_client(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_current_user] = lambda: _mock_admin
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_jwt_or_api_key] = lambda: _mock_admin
    registry._venues.clear()
    set_tracker(None)

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, db_session

    registry._venues.clear()
    set_tracker(None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_jwt_or_api_key, None)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

VENUE_ID = "SIM-TRACK"
# Short track: 200m total — at 25 m/s that's ~8s per race, well within timeout
DISTANCE_M = 200.0

GATES = [
    {"reader_id": "SIM-START",  "name": "Start",  "distance_m": 0.0,   "is_finish": False},
    {"reader_id": "SIM-HALF",   "name": "Mid",    "distance_m": 100.0, "is_finish": False},
    {"reader_id": "SIM-FINISH", "name": "Finish", "distance_m": 200.0, "is_finish": True},
]

HORSES = [
    {"horse_id": "EPC-SIM-001", "display_name": "Alpha", "saddle_cloth": "1"},
    {"horse_id": "EPC-SIM-002", "display_name": "Beta",  "saddle_cloth": "2"},
    {"horse_id": "EPC-SIM-003", "display_name": "Gamma", "saddle_cloth": "3"},
]


def _setup_venue(c):
    r = c.post("/venues", json={
        "venue_id": VENUE_ID,
        "name": "Simulation Track",
        "total_distance_m": DISTANCE_M,
    })
    assert r.status_code == 200, f"POST /venues failed: {r.text}"

    for gate in GATES:
        r = c.post(f"/venues/{VENUE_ID}/gates", json=gate)
        assert r.status_code == 200, f"POST /venues/gates failed: {r.text}"


def _register_race(c, db):
    """Register horses in DB + tracker, create Race record, start race."""
    for h in HORSES:
        db.merge(Horse(epc=h["horse_id"], name=h["display_name"]))
    db.commit()

    r = c.post("/race/register", json={
        "venue_id": VENUE_ID,
        "horses": HORSES,
    })
    assert r.status_code == 200, f"POST /race/register failed: {r.text}"

    # Create race record in DB
    r = c.post("/races", json={
        "venue_id": VENUE_ID,
        "name": "Simulation Cup",
        "race_date": "2026-04-08T15:00:00",
        "distance_m": DISTANCE_M,
        "surface": "turf",
    })
    assert r.status_code in (200, 201), f"POST /races failed: {r.text}"
    return r.json()["race_id"]


def _wait_for_finish(c, timeout=20.0, poll_interval=0.25):
    """Poll /race/status until status is 'finished' or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = c.get("/race/status")
        if r.status_code == 200:
            status = r.json().get("status")
            if status == "finished":
                return True
        time.sleep(poll_interval)
    return False


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #

def test_simulation_all_horses_finish(sim_client):
    """
    Full end-to-end: start simulation, wait for all horses to pass the
    finish gate, assert finish order is populated with all runners.
    """
    c, db = sim_client
    _setup_venue(c)
    _register_race(c, db)

    r = c.post("/race/simulate")
    assert r.status_code == 200, f"POST /race/simulate failed: {r.text}"
    body = r.json()
    assert body["ok"] is True
    assert body["runners"] == len(HORSES)
    assert body["gates"] == len(GATES)

    finished = _wait_for_finish(c)
    assert finished, "Race did not reach 'finished' state within 20 seconds"

    # Verify finish order
    r = c.get("/race/finish-order")
    assert r.status_code == 200
    order = r.json().get("results", [])
    assert len(order) == len(HORSES), f"Expected {len(HORSES)} finishers, got {len(order)}"


def test_simulation_finish_positions_are_unique(sim_client):
    """Each horse must occupy a unique finish position."""
    c, db = sim_client
    _setup_venue(c)
    _register_race(c, db)

    c.post("/race/simulate")
    _wait_for_finish(c)

    r = c.get("/race/finish-order")
    order = r.json().get("results", [])
    positions = [entry.get("position") for entry in order]
    assert len(positions) == len(set(positions)), "Duplicate finish positions found"


def test_simulation_race_state_has_gate_reads(sim_client):
    """After simulation, each horse should have gate read events."""
    c, db = sim_client
    _setup_venue(c)
    _register_race(c, db)

    c.post("/race/simulate")
    _wait_for_finish(c)

    r = c.get("/race/state")
    assert r.status_code == 200
    state = r.json()
    horses = state.get("horses", [])
    assert len(horses) == len(HORSES)

    for horse in horses:
        events = horse.get("events", [])
        assert len(events) >= 1, f"Horse {horse.get('horse_id')} has no gate read events"


def test_simulation_persist_and_export(sim_client):
    """After simulation finishes, persist results and verify export endpoints."""
    c, db = sim_client
    _setup_venue(c)
    race_id = _register_race(c, db)

    c.post("/race/simulate")
    finished = _wait_for_finish(c, timeout=30.0)
    assert finished, "Race did not finish within 20 seconds"

    # Persist results
    r = c.post(f"/races/{race_id}/persist")
    assert r.status_code == 200, f"POST /races/{race_id}/persist failed: {r.text}"
    persist_body = r.json()
    assert persist_body.get("ok") is True

    # Verify the race record is now 'finished' in DB
    db.expire_all()
    race = db.get(Race, race_id)
    assert race is not None
    assert race.status == "finished"
    assert len(race.results) == len(HORSES)

    # Export endpoints should return valid data
    r = c.get(f"/races/{race_id}/export/bha")
    assert r.status_code == 200
    bha = r.json()
    assert bha["schema"] == "BHA-Results-v1"
    assert len(bha["finishers"]) == len(HORSES)

    r = c.get(f"/races/{race_id}/export/racing-australia")
    assert r.status_code == 200
    assert b"<RaceResults" in r.content

    r = c.get(f"/races/{race_id}/export/jockey-club")
    assert r.status_code == 200
    assert b"<JockeyClubResults" in r.content


def test_simulation_elapsed_times_are_positive(sim_client):
    """All persisted finish times must be positive milliseconds."""
    c, db = sim_client
    _setup_venue(c)
    race_id = _register_race(c, db)

    c.post("/race/simulate")
    _wait_for_finish(c)
    c.post(f"/races/{race_id}/persist")

    db.expire_all()
    race = db.get(Race, race_id)
    for result in race.results:
        assert result.elapsed_ms > 0, f"Horse {result.horse_epc} has non-positive elapsed_ms"


def test_simulation_cannot_start_twice(sim_client):
    """Starting a second simulation while one is running returns 400."""
    c, db = sim_client
    _setup_venue(c)
    _register_race(c, db)

    r1 = c.post("/race/simulate")
    assert r1.status_code == 200

    # Wait for the tracker to transition to RUNNING (first tag submit happens after ~0.1s)
    deadline = time.time() + 2.0
    while time.time() < deadline:
        r = c.get("/race/status")
        if r.status_code == 200 and r.json().get("status") == "active":
            break
        time.sleep(0.05)

    # Now the race is active — a second simulate call should fail
    r2 = c.post("/race/simulate")
    assert r2.status_code == 400
