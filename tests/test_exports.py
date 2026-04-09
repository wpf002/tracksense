"""
tests/test_exports.py

Tests for ITEM 7: Industry-format export endpoints.
Covers Racing Australia XML, BHA JSON, Jockey Club XML.
"""

import xml.etree.ElementTree as ET
import json
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.server import app
from app.gate_registry import registry
from app.race_tracker import set_tracker
from app.routes import get_current_user
from app.database import get_db, Base
from app.models import User, VenueRecord, Race, Horse, RaceEntry, RaceResult
from app.api_keys_router import require_jwt_or_api_key


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

_mock_admin = User()
_mock_admin.id = 1
_mock_admin.username = "export_admin"
_mock_admin.hashed_password = "x"
_mock_admin.role = "admin"
_mock_admin.full_name = "Export Admin"
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
def export_client(db_session):
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


def _seed_finished_race(db):
    """Seed a venue, horse, race, and results into the test DB."""
    venue = VenueRecord(venue_id="EXPORT-V", name="Export Venue", total_distance_m=1200.0)
    db.add(venue)

    horse = Horse(epc="EPC-EXPORT-1", name="Thunder Road")
    db.add(horse)
    horse2 = Horse(epc="EPC-EXPORT-2", name="Silver Bullet")
    db.add(horse2)
    db.flush()

    race = Race(
        venue_id="EXPORT-V",
        name="The Big Cup",
        race_date=datetime(2026, 4, 8, 14, 30, tzinfo=timezone.utc),
        distance_m=1200.0,
        surface="turf",
        conditions="Good",
        status="finished",
    )
    db.add(race)
    db.flush()

    entry1 = RaceEntry(race_id=race.id, horse_epc="EPC-EXPORT-1", saddle_cloth="1")
    entry2 = RaceEntry(race_id=race.id, horse_epc="EPC-EXPORT-2", saddle_cloth="2")
    db.add_all([entry1, entry2])

    result1 = RaceResult(race_id=race.id, horse_epc="EPC-EXPORT-1", finish_position=1, elapsed_ms=75000)
    result2 = RaceResult(race_id=race.id, horse_epc="EPC-EXPORT-2", finish_position=2, elapsed_ms=76200)
    db.add_all([result1, result2])

    db.commit()
    return race


def _seed_unfinished_race(db):
    venue = VenueRecord(venue_id="PEND-V", name="Pending Venue", total_distance_m=1000.0)
    db.add(venue)
    db.flush()
    race = Race(
        venue_id="PEND-V",
        name="Pending Race",
        race_date=datetime(2026, 4, 8, tzinfo=timezone.utc),
        distance_m=1000.0,
        surface="turf",
        status="pending",
    )
    db.add(race)
    db.commit()
    return race


# ------------------------------------------------------------------ #
# Racing Australia XML
# ------------------------------------------------------------------ #

def test_racing_australia_export_shape(export_client):
    c, db = export_client
    race = _seed_finished_race(db)
    r = c.get(f"/races/{race.id}/export/racing-australia")
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]

    root = ET.fromstring(r.content)
    assert root.tag == "RaceResults"
    race_el = root.find("Race")
    assert race_el is not None
    assert race_el.get("name") == "The Big Cup"
    results = race_el.findall("Result")
    assert len(results) == 2


def test_racing_australia_result_positions(export_client):
    c, db = export_client
    race = _seed_finished_race(db)
    r = c.get(f"/races/{race.id}/export/racing-australia")
    root = ET.fromstring(r.content)
    race_el = root.find("Race")
    results = sorted(race_el.findall("Result"), key=lambda el: int(el.get("finishPosition")))
    assert results[0].get("finishPosition") == "1"
    assert results[0].get("horseName") == "Thunder Road"
    assert results[1].get("finishPosition") == "2"
    assert results[1].get("horseName") == "Silver Bullet"


def test_racing_australia_404_unknown_race(export_client):
    c, _ = export_client
    r = c.get("/races/99999/export/racing-australia")
    assert r.status_code == 404


def test_racing_australia_409_unfinished_race(export_client):
    c, db = export_client
    race = _seed_unfinished_race(db)
    r = c.get(f"/races/{race.id}/export/racing-australia")
    assert r.status_code == 409


# ------------------------------------------------------------------ #
# BHA JSON
# ------------------------------------------------------------------ #

def test_bha_export_shape(export_client):
    c, db = export_client
    race = _seed_finished_race(db)
    r = c.get(f"/races/{race.id}/export/bha")
    assert r.status_code == 200
    assert "application/json" in r.headers["content-type"]
    body = r.json()
    assert body["schema"] == "BHA-Results-v1"
    assert body["race"]["name"] == "The Big Cup"
    assert len(body["finishers"]) == 2


def test_bha_export_finisher_order(export_client):
    c, db = export_client
    race = _seed_finished_race(db)
    r = c.get(f"/races/{race.id}/export/bha")
    finishers = r.json()["finishers"]
    positions = [f["position"] for f in finishers]
    assert positions == sorted(positions)
    assert finishers[0]["horseName"] == "Thunder Road"


def test_bha_export_elapsed_and_time(export_client):
    c, db = export_client
    race = _seed_finished_race(db)
    r = c.get(f"/races/{race.id}/export/bha")
    first = r.json()["finishers"][0]
    assert first["elapsedMs"] == 75000
    assert ":" in first["finishTime"]  # e.g. "1:15.000"


def test_bha_404_unknown_race(export_client):
    c, _ = export_client
    r = c.get("/races/99999/export/bha")
    assert r.status_code == 404


def test_bha_409_unfinished_race(export_client):
    c, db = export_client
    race = _seed_unfinished_race(db)
    r = c.get(f"/races/{race.id}/export/bha")
    assert r.status_code == 409


# ------------------------------------------------------------------ #
# Jockey Club XML
# ------------------------------------------------------------------ #

def test_jockey_club_export_shape(export_client):
    c, db = export_client
    race = _seed_finished_race(db)
    r = c.get(f"/races/{race.id}/export/jockey-club")
    assert r.status_code == 200
    assert "application/xml" in r.headers["content-type"]

    root = ET.fromstring(r.content)
    assert "JockeyClubResults" in root.tag
    race_card = root.find("RaceCard")
    assert race_card is not None
    horse_results = race_card.findall("HorseResult")
    assert len(horse_results) == 2


def test_jockey_club_result_order(export_client):
    c, db = export_client
    race = _seed_finished_race(db)
    r = c.get(f"/races/{race.id}/export/jockey-club")
    root = ET.fromstring(r.content)
    race_card = root.find("RaceCard")
    hrs = race_card.findall("HorseResult")
    positions = [int(hr.find("FinishPosition").text) for hr in hrs]
    assert positions == sorted(positions)
    assert hrs[0].find("HorseName").text == "Thunder Road"


def test_jockey_club_404_unknown_race(export_client):
    c, _ = export_client
    r = c.get("/races/99999/export/jockey-club")
    assert r.status_code == 404


def test_jockey_club_409_unfinished_race(export_client):
    c, db = export_client
    race = _seed_unfinished_race(db)
    r = c.get(f"/races/{race.id}/export/jockey-club")
    assert r.status_code == 409
