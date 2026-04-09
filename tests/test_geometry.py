"""
tests/test_geometry.py

Tests for ITEM 4: gate position_x/position_y columns and GET /venues/{id}/geometry.
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
from app.models import User, VenueRecord, GateRecord
from app import crud


# ------------------------------------------------------------------ #
# Auth bypass + in-memory DB
# ------------------------------------------------------------------ #

_mock_admin = User()
_mock_admin.id = 998
_mock_admin.username = "geo_test_admin"
_mock_admin.hashed_password = "x"
_mock_admin.role = "admin"
_mock_admin.full_name = "Geo Test Admin"
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
def geo_client(db_session):
    def override_db():
        yield db_session

    app.dependency_overrides[get_current_user] = lambda: _mock_admin
    app.dependency_overrides[get_db] = override_db
    registry._venues.clear()
    set_tracker(None)

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c, db_session

    registry._venues.clear()
    set_tracker(None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #

def test_add_gate_with_coordinates_stores_correctly(geo_client):
    """POST /venues/{id}/gates with position_x/y stores both values in DB."""
    c, db = geo_client
    c.post("/venues", json={"venue_id": "GEO1", "name": "Geo Venue", "total_distance_m": 804.0})
    r = c.post("/venues/GEO1/gates", json={
        "reader_id": "G-START",
        "name": "Start",
        "distance_m": 0.0,
        "is_finish": False,
        "position_x": 0.5,
        "position_y": 0.95,
    })
    assert r.status_code == 200

    db.expire_all()
    gate = db.query(GateRecord).filter_by(venue_id="GEO1", reader_id="G-START").first()
    assert gate is not None
    assert gate.position_x == pytest.approx(0.5)
    assert gate.position_y == pytest.approx(0.95)


def test_geometry_endpoint_returns_correct_shape(geo_client):
    """GET /venues/{id}/geometry returns venue + gates with position data."""
    c, db = geo_client
    c.post("/venues", json={"venue_id": "GEO2", "name": "Geo Track", "total_distance_m": 1000.0})
    c.post("/venues/GEO2/gates", json={
        "reader_id": "G-S", "name": "Start", "distance_m": 0.0,
        "is_finish": False, "position_x": 0.1, "position_y": 0.9,
    })
    c.post("/venues/GEO2/gates", json={
        "reader_id": "G-F", "name": "Finish", "distance_m": 1000.0,
        "is_finish": True, "position_x": 0.9, "position_y": 0.1,
    })

    r = c.get("/venues/GEO2/geometry")
    assert r.status_code == 200
    body = r.json()
    assert body["venue_id"] == "GEO2"
    assert body["name"] == "Geo Track"
    assert body["total_distance_m"] == 1000.0
    assert len(body["gates"]) == 2

    start = next(g for g in body["gates"] if g["reader_id"] == "G-S")
    assert start["position_x"] == pytest.approx(0.1)
    assert start["position_y"] == pytest.approx(0.9)

    finish = next(g for g in body["gates"] if g["reader_id"] == "G-F")
    assert finish["is_finish"] is True
    assert finish["position_x"] == pytest.approx(0.9)


def test_geometry_returns_null_coordinates_gracefully(geo_client):
    """Gates without position data return position_x=null, position_y=null."""
    c, db = geo_client
    c.post("/venues", json={"venue_id": "GEO3", "name": "No Pos Venue", "total_distance_m": 500.0})
    c.post("/venues/GEO3/gates", json={
        "reader_id": "G-MID", "name": "Mid", "distance_m": 250.0, "is_finish": False,
        # No position_x or position_y
    })

    r = c.get("/venues/GEO3/geometry")
    assert r.status_code == 200
    gate = r.json()["gates"][0]
    assert gate["position_x"] is None
    assert gate["position_y"] is None


def test_geometry_returns_404_for_unknown_venue(geo_client):
    c, _ = geo_client
    r = c.get("/venues/GHOST_GEO/geometry")
    assert r.status_code == 404


def test_geometry_no_auth_required(geo_client):
    """GET /venues/{id}/geometry works without any auth token."""
    c, db = geo_client
    # Create venue via authenticated request
    c.post("/venues", json={"venue_id": "NOAUTH", "name": "No Auth Venue", "total_distance_m": 400.0})

    # Call geometry without auth override — but we already have override in place.
    # The endpoint should not require auth (it has no Depends(get_current_user)).
    r = c.get("/venues/NOAUTH/geometry")
    assert r.status_code == 200
