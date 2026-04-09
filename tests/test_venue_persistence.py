"""
tests/test_venue_persistence.py

Tests for ITEM 2: Venue and gate persistence to the database.
Uses the shared test client (like test_api.py) so requests go through
the real FastAPI routing and hit a real SQLite DB.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.server import app
from app.gate_registry import registry
from app.race_tracker import set_tracker
from app.routes import get_current_user
from app.database import get_db, Base
from app.models import User, VenueRecord, GateRecord


# ------------------------------------------------------------------ #
# Auth bypass
# ------------------------------------------------------------------ #

_mock_admin = User()
_mock_admin.id = 999
_mock_admin.username = "persist_test_admin"
_mock_admin.hashed_password = "x"
_mock_admin.role = "admin"
_mock_admin.full_name = "Persist Test Admin"
_mock_admin.active = True
_mock_admin.tenant_id = None


# ------------------------------------------------------------------ #
# Per-test in-memory DB + client
# ------------------------------------------------------------------ #

@pytest.fixture
def test_db():
    """Fresh in-memory SQLite DB for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    yield TestingSession, engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def client(test_db):
    """TestClient with auth override and in-memory DB."""
    TestingSession, engine = test_db
    session = TestingSession()

    def override_db():
        try:
            yield session
        finally:
            pass  # don't close — we reuse this session for assertions

    app.dependency_overrides[get_current_user] = lambda: _mock_admin
    app.dependency_overrides[get_db] = override_db
    registry._venues.clear()
    set_tracker(None)

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, session

    registry._venues.clear()
    set_tracker(None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)
    session.close()


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #

def test_post_venues_creates_db_record(client):
    c, db = client
    r = c.post("/venues", json={
        "venue_id": "PERSIST_TEST",
        "name": "Persistence Test Track",
        "total_distance_m": 1000.0,
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True

    db.expire_all()
    venue = db.get(VenueRecord, "PERSIST_TEST")
    assert venue is not None
    assert venue.name == "Persistence Test Track"
    assert venue.total_distance_m == 1000.0


def test_post_venue_gates_persists_to_db(client):
    c, db = client
    c.post("/venues", json={
        "venue_id": "GV1",
        "name": "Gate Venue 1",
        "total_distance_m": 804.0,
    })
    r = c.post("/venues/GV1/gates", json={
        "reader_id": "GATE-FINISH",
        "name": "Finish",
        "distance_m": 804.0,
        "is_finish": True,
    })
    assert r.status_code == 200

    db.expire_all()
    gate = db.query(GateRecord).filter_by(venue_id="GV1", reader_id="GATE-FINISH").first()
    assert gate is not None
    assert gate.name == "Finish"
    assert gate.distance_m == 804.0
    assert gate.is_finish is True


def test_delete_venue_removes_from_db(client):
    c, db = client
    c.post("/venues", json={
        "venue_id": "DEL_V",
        "name": "Delete Me",
        "total_distance_m": 500.0,
    })
    r = c.delete("/venues/DEL_V")
    assert r.status_code == 200

    db.expire_all()
    assert db.get(VenueRecord, "DEL_V") is None


def test_delete_gate_removes_from_db(client):
    c, db = client
    c.post("/venues", json={
        "venue_id": "DGTEST",
        "name": "Delete Gate Test",
        "total_distance_m": 800.0,
    })
    c.post("/venues/DGTEST/gates", json={
        "reader_id": "G-START",
        "name": "Start",
        "distance_m": 0.0,
        "is_finish": False,
    })
    r = c.delete("/venues/DGTEST/gates/G-START")
    assert r.status_code == 200

    db.expire_all()
    gate = db.query(GateRecord).filter_by(venue_id="DGTEST", reader_id="G-START").first()
    assert gate is None


def test_restart_hydrates_venue_from_db(test_db):
    """
    Simulate a restart: create a venue+gates in DB directly, then
    verify registry.create_venue + registry.add_gate can load them
    (matching the lifespan hydration logic in server.py).
    """
    TestingSession, engine = test_db
    db = TestingSession()

    # Write venue + gates directly to DB (as if persisted by prior run)
    from app import crud
    crud.upsert_venue(db, "HYDRATE_V", "Hydrate Venue", 804.0)
    crud.upsert_gate(db, "HYDRATE_V", "GH-START", "Start", 0.0, False)
    crud.upsert_gate(db, "HYDRATE_V", "GH-FINISH", "Finish", 804.0, True)

    # Clear registry (simulate fresh process)
    registry._venues.clear()
    assert registry.get_venue("HYDRATE_V") is None

    # Re-run the lifespan hydration logic
    from app.models import VenueRecord, GateRecord
    venues = db.query(VenueRecord).all()
    for venue in venues:
        registry.create_venue(venue.venue_id, venue.name, venue.total_distance_m)
        gates = db.query(GateRecord).filter_by(venue_id=venue.venue_id).all()
        for gate in gates:
            registry.add_gate(venue.venue_id, gate.reader_id, gate.name,
                              gate.distance_m, gate.is_finish)

    # Verify venue is now in memory
    v = registry.get_venue("HYDRATE_V")
    assert v is not None
    assert v.name == "Hydrate Venue"
    assert len(v.gates) == 2

    finish = v.finish_gate()
    assert finish is not None
    assert finish.reader_id == "GH-FINISH"

    registry._venues.clear()
    db.close()
