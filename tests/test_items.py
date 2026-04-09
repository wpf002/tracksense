"""
tests/test_items.py

Tests for Items 1–3:
  - Item 1: TrackPathPoint model + track-path endpoints
  - Item 2: BiosensorReading model + biosensor endpoints
  - Item 3: temperature_c on CheckInRecord + temperature endpoints
"""

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
from app.models import User, VenueRecord, GateRecord, Horse
from app.api_keys_router import require_jwt_or_api_key
from app import crud


# ─── Fixtures ────────────────────────────────────────────────────────────────

_mock_admin = User()
_mock_admin.id = 1
_mock_admin.username = "items_admin"
_mock_admin.hashed_password = "x"
_mock_admin.role = "admin"
_mock_admin.full_name = "Items Admin"
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
def test_client(db_session):
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


def _create_venue(c, venue_id="TESTOVAL"):
    c.post("/venues", json={
        "venue_id": venue_id,
        "name": "Test Oval",
        "total_distance_m": 1600.0,
    })
    c.post(f"/venues/{venue_id}/gates", json={
        "reader_id": "GATE-START", "name": "Start", "distance_m": 0.0, "is_finish": False,
    })
    c.post(f"/venues/{venue_id}/gates", json={
        "reader_id": "GATE-FINISH", "name": "Finish", "distance_m": 1600.0, "is_finish": True,
    })
    return venue_id


def _create_horse(db, epc="EPC-TEST-001", name="Test Horse"):
    db.merge(Horse(epc=epc, name=name))
    db.commit()
    return epc


# ─── Item 1: Track path ───────────────────────────────────────────────────────

class TestTrackPath:
    def test_set_and_get_track_path(self, test_client):
        c, db = test_client
        venue_id = _create_venue(c)

        points = [{"x": round(0.5 + 0.35 * (i * 0.1), 3), "y": 0.5} for i in range(5)]
        # Provide at least 3 valid points
        pts = [{"x": 0.1, "y": 0.5}, {"x": 0.5, "y": 0.1}, {"x": 0.9, "y": 0.5},
               {"x": 0.5, "y": 0.9}]

        r = c.post(f"/venues/{venue_id}/track-path", json={"points": pts})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["count"] == len(pts)

    def test_get_track_path(self, test_client):
        c, db = test_client
        venue_id = _create_venue(c)
        pts = [{"x": 0.1, "y": 0.5}, {"x": 0.5, "y": 0.1}, {"x": 0.9, "y": 0.5}]
        c.post(f"/venues/{venue_id}/track-path", json={"points": pts})

        r = c.get(f"/venues/{venue_id}/track-path")
        assert r.status_code == 200
        data = r.json()
        assert data["venue_id"] == venue_id
        assert data["count"] == len(pts)
        assert len(data["points"]) == len(pts)
        assert data["points"][0]["sequence"] == 0

    def test_track_path_404_for_unknown_venue(self, test_client):
        c, _ = test_client
        r = c.get("/venues/DOESNOTEXIST/track-path")
        assert r.status_code == 404

    def test_track_path_requires_min_3_points(self, test_client):
        c, db = test_client
        venue_id = _create_venue(c)
        r = c.post(f"/venues/{venue_id}/track-path", json={"points": [{"x": 0.1, "y": 0.5}]})
        assert r.status_code == 422

    def test_track_path_upsert_replaces_old(self, test_client):
        c, db = test_client
        venue_id = _create_venue(c)
        pts_a = [{"x": 0.1, "y": 0.5}, {"x": 0.5, "y": 0.1}, {"x": 0.9, "y": 0.5}]
        pts_b = [{"x": 0.2, "y": 0.5}, {"x": 0.5, "y": 0.2}, {"x": 0.8, "y": 0.5},
                 {"x": 0.5, "y": 0.8}]
        c.post(f"/venues/{venue_id}/track-path", json={"points": pts_a})
        c.post(f"/venues/{venue_id}/track-path", json={"points": pts_b})
        r = c.get(f"/venues/{venue_id}/track-path")
        assert r.json()["count"] == len(pts_b)


# ─── Item 2: Biosensor ────────────────────────────────────────────────────────

class TestBiosensor:
    def test_add_biosensor_reading(self, test_client):
        c, db = test_client
        epc = _create_horse(db)

        r = c.post(f"/horses/{epc}/biosensor", json={
            "heart_rate_bpm": 140,
            "temperature_c": 38.1,
            "stride_hz": 2.4,
            "source": "wearable",
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_get_biosensor_readings(self, test_client):
        c, db = test_client
        epc = _create_horse(db)
        c.post(f"/horses/{epc}/biosensor", json={"heart_rate_bpm": 145})
        c.post(f"/horses/{epc}/biosensor", json={"heart_rate_bpm": 148})

        r = c.get(f"/horses/{epc}/biosensor")
        assert r.status_code == 200
        assert len(r.json()["readings"]) == 2

    def test_biosensor_404_for_unknown_horse(self, test_client):
        c, _ = test_client
        r = c.post("/horses/EPC-FAKE-999/biosensor", json={"heart_rate_bpm": 140})
        assert r.status_code == 404

    def test_biosensor_validates_hr_range(self, test_client):
        c, db = test_client
        epc = _create_horse(db)
        r = c.post(f"/horses/{epc}/biosensor", json={"heart_rate_bpm": 500})
        assert r.status_code == 422

    def test_bulk_biosensor(self, test_client):
        c, db = test_client
        epc = _create_horse(db)
        # Create a race
        _create_venue(c)
        c.post("/races", json={
            "venue_id": "TESTOVAL",
            "race_date": "2026-04-09T15:00:00",
            "distance_m": 1600.0,
            "surface": "turf",
        })
        r = c.get("/races")
        race_id = r.json()["races"][0]["race_id"]

        bulk = {
            "readings": [
                {"horse_epc": epc, "heart_rate_bpm": 142, "temperature_c": 38.2},
                {"horse_epc": epc, "heart_rate_bpm": 147, "stride_hz": 2.3},
            ]
        }
        r = c.post(f"/races/{race_id}/biosensor/bulk", json=bulk)
        assert r.status_code == 200
        assert r.json()["created"] == 2


# ─── Item 3: Temperature ─────────────────────────────────────────────────────

class TestTemperature:
    def test_checkin_with_temperature(self, test_client):
        c, db = test_client
        epc = _create_horse(db)

        r = c.post(f"/horses/{epc}/checkins", json={
            "scanned_by": "Test Official",
            "location": "Paddock",
            "temperature_c": 38.3,
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_checkin_temperature_returned_in_list(self, test_client):
        c, db = test_client
        epc = _create_horse(db)
        c.post(f"/horses/{epc}/checkins", json={"temperature_c": 37.8})

        r = c.get(f"/horses/{epc}/checkins")
        assert r.status_code == 200
        checkins = r.json()["checkins"]
        assert len(checkins) == 1
        assert checkins[0]["temperature_c"] == pytest.approx(37.8, abs=0.01)

    def test_temperature_history_endpoint(self, test_client):
        c, db = test_client
        epc = _create_horse(db)
        c.post(f"/horses/{epc}/checkins", json={"temperature_c": 38.1})
        c.post(f"/horses/{epc}/checkins", json={})  # no temp — should not appear

        r = c.get(f"/horses/{epc}/temperature-history")
        assert r.status_code == 200
        readings = r.json()["readings"]
        assert len(readings) == 1
        assert readings[0]["temperature_c"] == pytest.approx(38.1, abs=0.01)

    def test_temperature_alerts_endpoint(self, test_client):
        c, db = test_client
        epc = _create_horse(db)
        c.post(f"/horses/{epc}/checkins", json={"temperature_c": 37.8})  # normal
        c.post(f"/horses/{epc}/checkins", json={"temperature_c": 39.2})  # red alert
        c.post(f"/horses/{epc}/checkins", json={"temperature_c": 38.6})  # amber

        r = c.get(f"/horses/{epc}/temperature-alerts")
        assert r.status_code == 200
        body = r.json()
        # Alerts at >= 39.0 or <= 37.0. 37.8 normal, 39.2 alert, 38.6 amber (not alert).
        assert body["alert_count"] == 1

    def test_temperature_alerts_severity(self, test_client):
        c, db = test_client
        epc = _create_horse(db)
        c.post(f"/horses/{epc}/checkins", json={"temperature_c": 39.5})  # red
        c.post(f"/horses/{epc}/checkins", json={"temperature_c": 36.5})  # red (low)

        r = c.get(f"/horses/{epc}/temperature-alerts")
        body = r.json()
        assert body["alert_count"] == 2
        severities = {a["severity"] for a in body["alerts"]}
        assert severities == {"red"}

    def test_temperature_history_404_unknown_horse(self, test_client):
        c, _ = test_client
        r = c.get("/horses/EPC-FAKE-9999/temperature-history")
        assert r.status_code == 404

    def test_checkin_without_temperature_is_null(self, test_client):
        c, db = test_client
        epc = _create_horse(db)
        c.post(f"/horses/{epc}/checkins", json={"scanned_by": "Official"})

        r = c.get(f"/horses/{epc}/checkins")
        assert r.json()["checkins"][0]["temperature_c"] is None
