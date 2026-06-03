"""
test_phase4.py

Phase 4 — Training Center Module tests.
Covers: VetCheckRecord CRUD, training roster, owner report, vet-check + owner-report
API endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.server import app
from app.routes import get_current_user
from app.database import get_db, Base
from app.models import User, VenueRecord, Horse
from app.api_keys_router import require_jwt_or_api_key
from app import crud

# ------------------------------------------------------------------ #
# Auth
# ------------------------------------------------------------------ #

_mock_admin = User()
_mock_admin.id = "00000000-0000-0000-0000-000000000002"
_mock_admin.username = "phase4_admin"
_mock_admin.hashed_password = "x"
_mock_admin.role = "admin"
_mock_admin.full_name = "Phase4 Admin"
_mock_admin.active = True
_mock_admin.tenant_id = None


@pytest.fixture(autouse=True)
def _override_auth():
    app.dependency_overrides[get_current_user] = lambda: _mock_admin
    app.dependency_overrides[require_jwt_or_api_key] = lambda: _mock_admin
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_jwt_or_api_key, None)


client = TestClient(app, raise_server_exceptions=True)


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
def db_with_horse(db_session):
    db_session.add(Horse(chip_id="985112000950001", name="Training Test Horse",
                         breed="Thoroughbred"))
    db_session.commit()
    return db_session


# ------------------------------------------------------------------ #
# VetCheckRecord CRUD
# ------------------------------------------------------------------ #

def test_add_vet_check(db_with_horse):
    result = crud.add_vet_check(
        db_with_horse,
        horse_chip_id="985112000950001",
        check_date="2026-06-01",
        check_type="routine",
        outcome="cleared",
        vet_name="Dr. Patel",
        notes="All clear.",
    )
    assert result["ok"] is True
    assert "id" in result


def test_add_vet_check_unknown_horse(db_session):
    result = crud.add_vet_check(
        db_session, horse_chip_id="985112000000000",
        check_date="2026-06-01", check_type="routine", outcome="cleared",
    )
    assert result["ok"] is False


def test_get_vet_checks_sorted(db_with_horse):
    crud.add_vet_check(db_with_horse, horse_chip_id="985112000950001",
                       check_date="2026-05-25", check_type="lameness", outcome="restricted")
    crud.add_vet_check(db_with_horse, horse_chip_id="985112000950001",
                       check_date="2026-06-01", check_type="routine", outcome="cleared")
    checks = crud.get_vet_checks(db_with_horse, "985112000950001")
    assert len(checks) == 2
    assert checks[0].check_date >= checks[1].check_date  # newest first


# ------------------------------------------------------------------ #
# Training roster
# ------------------------------------------------------------------ #

def test_training_roster_returns_horses(db_with_horse):
    roster = crud.get_training_roster(db_with_horse)
    assert len(roster) == 1
    h = roster[0]
    assert h["chip_id"] == "985112000950001"
    assert h["name"] == "Training Test Horse"
    assert "last_workout_date" in h
    assert "pending_hisa_count" in h
    assert "open_treatment_count" in h


def test_training_roster_snapshot_fields(db_with_horse):
    crud.add_vet_check(db_with_horse, horse_chip_id="985112000950001",
                       check_date="2026-06-01", check_type="routine", outcome="restricted")
    roster = crud.get_training_roster(db_with_horse)
    h = roster[0]
    assert h["latest_vet_check_outcome"] == "restricted"
    assert h["latest_vet_check_date"] == "2026-06-01"


# ------------------------------------------------------------------ #
# Owner report
# ------------------------------------------------------------------ #

def test_owner_report_returns_structure(db_with_horse):
    report = crud.get_owner_report(db_with_horse, "985112000950001", period="week")
    assert report is not None
    assert report["horse"]["chip_id"] == "985112000950001"
    assert "workouts" in report
    assert "vet_checks" in report
    assert "treatments" in report
    assert "race_results" in report
    assert report["period"] == "week"
    assert report["period_days"] == 7


def test_owner_report_month_period(db_with_horse):
    report = crud.get_owner_report(db_with_horse, "985112000950001", period="month")
    assert report["period_days"] == 30


def test_owner_report_unknown_horse(db_session):
    report = crud.get_owner_report(db_session, "985112000000000", period="week")
    assert report is None


# ------------------------------------------------------------------ #
# API endpoints
# ------------------------------------------------------------------ #

def test_add_vet_check_via_api():
    chip = "985112000951001"
    client.post("/horses", json={"chip_id": chip, "name": "API Vet Check Horse"})
    r = client.post(f"/horses/{chip}/vet-checks", json={
        "check_date": "2026-06-01",
        "check_type": "lameness",
        "outcome": "restricted",
        "vet_name": "Dr. Chen",
        "notes": "Mild left fore lameness.",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_get_vet_checks_via_api():
    chip = "985112000951002"
    client.post("/horses", json={"chip_id": chip, "name": "API Get Vet Check Horse"})
    client.post(f"/horses/{chip}/vet-checks", json={
        "check_date": "2026-06-01", "check_type": "routine", "outcome": "cleared",
    })
    r = client.get(f"/horses/{chip}/vet-checks")
    assert r.status_code == 200
    checks = r.json()["vet_checks"]
    assert len(checks) == 1
    assert checks[0]["outcome"] == "cleared"


def test_training_roster_via_api():
    r = client.get("/training/roster")
    assert r.status_code == 200
    body = r.json()
    assert "roster" in body
    assert "count" in body
    assert isinstance(body["roster"], list)


def test_owner_report_via_api():
    chip = "985112000951003"
    client.post("/horses", json={"chip_id": chip, "name": "Owner Report Horse"})
    r = client.get(f"/horses/{chip}/owner-report?period=week")
    assert r.status_code == 200
    body = r.json()
    assert body["horse"]["chip_id"] == chip
    assert body["period"] == "week"


def test_owner_report_invalid_period():
    chip = "985112000951004"
    client.post("/horses", json={"chip_id": chip, "name": "Bad Period Horse"})
    r = client.get(f"/horses/{chip}/owner-report?period=year")
    assert r.status_code == 400


def test_vet_check_unknown_horse_returns_404():
    r = client.post("/horses/985112000000000/vet-checks", json={
        "check_date": "2026-06-01", "check_type": "routine", "outcome": "cleared",
    })
    assert r.status_code == 404
