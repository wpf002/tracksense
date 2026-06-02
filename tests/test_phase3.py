"""
test_phase3.py

Phase 3 — HISA Reporting Module tests.
Covers: TreatmentRecord CRUD, StewardsRuling + auto-deadline, SurfaceConditionLog,
HISASubmission build/status, hisa_builder payload shapes, submission endpoints.
"""
import json
import pytest
from datetime import datetime, timezone
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
_mock_admin.id = "00000000-0000-0000-0000-000000000001"
_mock_admin.username = "phase3_admin"
_mock_admin.hashed_password = "x"
_mock_admin.role = "admin"
_mock_admin.full_name = "Phase3 Admin"
_mock_admin.active = True
_mock_admin.tenant_id = None


@pytest.fixture(autouse=True)
def _override_auth():
    """Set auth overrides for Phase 3 API tests; restore after each test."""
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
    db_session.add(Horse(chip_id="985112000900100", name="HISA Test Horse"))
    db_session.commit()
    return db_session


@pytest.fixture
def db_with_venue(db_session):
    db_session.add(VenueRecord(venue_id="HISA_TRACK", name="HISA Track", total_distance_m=1600.0))
    db_session.commit()
    return db_session


# ------------------------------------------------------------------ #
# TreatmentRecord CRUD
# ------------------------------------------------------------------ #

def test_add_treatment(db_with_horse):
    result = crud.add_treatment(
        db_with_horse,
        horse_chip_id="985112000900100",
        treatment_date="2026-06-01",
        substance="Phenylbutazone",
        dose="4.4 mg/kg",
        route="IV",
        withdrawal_time_hours=48,
        prescribed_by="Dr. Smith",
        administered_by="Dr. Smith",
        is_prohibited=False,
    )
    assert result["ok"] is True
    assert "id" in result


def test_add_treatment_unknown_horse(db_session):
    result = crud.add_treatment(
        db_session,
        horse_chip_id="985112000000000",
        treatment_date="2026-06-01",
        substance="Aspirin",
    )
    assert result["ok"] is False


def test_get_treatments(db_with_horse):
    crud.add_treatment(db_with_horse, horse_chip_id="985112000900100",
                       treatment_date="2026-06-01", substance="Lasix")
    crud.add_treatment(db_with_horse, horse_chip_id="985112000900100",
                       treatment_date="2026-05-28", substance="Bute")
    records = crud.get_treatments(db_with_horse, "985112000900100")
    assert len(records) == 2
    # Should be newest first
    assert records[0].treatment_date >= records[1].treatment_date


# ------------------------------------------------------------------ #
# StewardsRuling + auto-deadline
# ------------------------------------------------------------------ #

def test_create_stewards_ruling_auto_deadline(db_session):
    ruling_date = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
    result = crud.create_stewards_ruling(
        db_session,
        ruling_date=ruling_date,
        rule_violated="Rule 2230 — Unsatisfactory performance",
        description="Horse exhibited irregular gait post-race.",
    )
    assert result["ok"] is True
    # Deadline should be 48h after ruling_date (strip tz for comparison)
    deadline = datetime.fromisoformat(result["deadline_at"].replace("Z", "+00:00"))
    ruling_naive = ruling_date.replace(tzinfo=None)
    deadline_naive = deadline.replace(tzinfo=None)
    assert (deadline_naive - ruling_naive).total_seconds() == 48 * 3600


def test_create_stewards_ruling_explicit_deadline(db_session):
    from datetime import timedelta
    ruling_date = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
    explicit_deadline = ruling_date + timedelta(hours=24)
    result = crud.create_stewards_ruling(
        db_session,
        ruling_date=ruling_date,
        rule_violated="Rule 2281 — Crop",
        description="Excessive crop use.",
        deadline_at=explicit_deadline,
    )
    assert result["ok"] is True
    deadline = datetime.fromisoformat(result["deadline_at"].replace("Z", "+00:00"))
    ruling_naive = ruling_date.replace(tzinfo=None)
    deadline_naive = deadline.replace(tzinfo=None)
    assert (deadline_naive - ruling_naive).total_seconds() == 24 * 3600


# ------------------------------------------------------------------ #
# SurfaceConditionLog
# ------------------------------------------------------------------ #

def test_upsert_surface_condition_create(db_with_venue):
    result = crud.upsert_surface_condition(
        db_with_venue, venue_id="HISA_TRACK", logged_date="2026-06-01",
        surface_type="Dirt", going_description="Fast",
        moisture_pct=12.5, temperature_c=22.0, logged_by="Track Super",
    )
    assert result["ok"] is True
    assert result["updated"] is False


def test_upsert_surface_condition_update(db_with_venue):
    crud.upsert_surface_condition(
        db_with_venue, venue_id="HISA_TRACK", logged_date="2026-06-01",
        surface_type="Dirt", going_description="Fast",
    )
    result = crud.upsert_surface_condition(
        db_with_venue, venue_id="HISA_TRACK", logged_date="2026-06-01",
        surface_type="Dirt", going_description="Good",  # updated
    )
    assert result["ok"] is True
    assert result["updated"] is True


def test_upsert_surface_condition_unknown_venue(db_session):
    result = crud.upsert_surface_condition(
        db_session, venue_id="NOWHERE", logged_date="2026-06-01",
        surface_type="Dirt", going_description="Fast",
    )
    assert result["ok"] is False


# ------------------------------------------------------------------ #
# hisa_builder — payload shapes
# ------------------------------------------------------------------ #

def test_build_workout_submission_shape():
    from app.hisa_builder import build_workout_submission
    from unittest.mock import MagicMock

    workout = MagicMock()
    workout.horse_chip_id = "985112000900100"
    workout.workout_date = "2026-06-01"
    workout.distance_m = 800.0
    workout.surface = "Dirt"
    workout.track_condition = "Fast"
    workout.duration_ms = 50000
    workout.trainer_name = "Bob Baffert"
    workout.rider_name = "J. Smith"
    workout.clocker_name = "H. Goldberg"
    workout.timekeeper_name = None
    workout.source = "manual"
    workout.notes = None

    payload = build_workout_submission(workout)
    assert payload["hisa_report_type"] == "TIMED_REPORTED_WORKOUT"
    assert payload["horse"]["jockey_club_chip_id"] == "985112000900100"
    assert payload["workout"]["distance_m"] == 800.0
    assert payload["workout"]["trainer"] == "Bob Baffert"
    assert "generated_at" in payload


def test_build_treatment_submission_shape():
    from app.hisa_builder import build_treatment_submission
    from unittest.mock import MagicMock

    tr = MagicMock()
    tr.horse_chip_id = "985112000900100"
    tr.treatment_date = "2026-06-01"
    tr.substance = "Phenylbutazone"
    tr.dose = "4.4 mg/kg"
    tr.route = "IV"
    tr.withdrawal_time_hours = 48
    tr.prescribed_by = "Dr. Smith"
    tr.administered_by = "Dr. Smith"
    tr.race_id = None
    tr.is_prohibited = False
    tr.notes = None

    payload = build_treatment_submission(tr)
    assert payload["hisa_report_type"] == "ADMC_TREATMENT"
    assert payload["treatment"]["substance"] == "Phenylbutazone"
    assert payload["treatment"]["is_prohibited_substance"] is False


def test_build_stewards_submission_shape():
    from app.hisa_builder import build_stewards_submission
    from unittest.mock import MagicMock

    ruling = MagicMock()
    ruling.horse_chip_id = "985112000900100"
    ruling.ruling_date = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)
    ruling.deadline_at = datetime(2026, 6, 3, 15, 0, tzinfo=timezone.utc)
    ruling.race_id = None
    ruling.rule_violated = "Rule 2230"
    ruling.description = "Post-race irregularity"
    ruling.penalty = "Fine $500"
    ruling.jockey_name = "J. Castellano"

    payload = build_stewards_submission(ruling)
    assert payload["hisa_report_type"] == "STEWARDS_RULING"
    assert payload["ruling"]["rule_violated"] == "Rule 2230"
    assert payload["ruling"]["penalty"] == "Fine $500"


def test_build_surface_submission_shape():
    from app.hisa_builder import build_surface_submission
    from unittest.mock import MagicMock

    log = MagicMock()
    log.venue_id = "HISA_TRACK"
    log.logged_date = "2026-06-01"
    log.surface_type = "Dirt"
    log.going_description = "Fast"
    log.moisture_pct = 12.5
    log.temperature_c = 22.0
    log.maintenance_notes = None
    log.logged_by = "Track Superintendent"

    payload = build_surface_submission(log)
    assert payload["hisa_report_type"] == "SURFACE_CONDITION"
    assert payload["rule_reference"] == "2151/2154"
    assert payload["venue_id"] == "HISA_TRACK"
    assert payload["surface"]["going_description"] == "Fast"


# ------------------------------------------------------------------ #
# HISASubmission — API endpoints
# ------------------------------------------------------------------ #

def test_list_hisa_submissions_empty():
    r = client.get("/hisa/submissions")
    assert r.status_code == 200
    assert r.json()["submissions"] == []


def test_build_all_creates_submissions():
    """POST /hisa/build-all should return ok (0 created in empty test DB)."""
    r = client.post("/hisa/build-all")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert "created" in r.json()


def test_create_stewards_ruling_via_api():
    r = client.post("/stewards/rulings", json={
        "ruling_date": "2026-06-01T15:00:00",
        "rule_violated": "Rule 2230 — test",
        "description": "Test ruling description.",
        "penalty": "Caution",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True
    ruling_id = r.json()["id"]
    assert ruling_id > 0
    # Auto-creates a HISASubmission with deadline 48h later
    subs = client.get("/hisa/submissions").json()["submissions"]
    assert any(s["rule_category"] == "STEWARDS_RULING" and
               s["source_record_id"] == ruling_id for s in subs)


def test_submit_hisa_marks_submitted():
    # Create a ruling → auto-creates a pending submission
    r = client.post("/stewards/rulings", json={
        "ruling_date": "2026-06-01T12:00:00",
        "rule_violated": "Rule 2281 — submit test",
        "description": "Submit test.",
    })
    ruling_id = r.json()["id"]
    subs = client.get("/hisa/submissions").json()["submissions"]
    sub = next((s for s in subs if s["source_record_id"] == ruling_id), None)
    assert sub is not None

    # Submit it
    r2 = client.post(f"/hisa/submit/{sub['id']}")
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "submitted"
    assert body["payload"] is not None
    assert body["payload"]["hisa_report_type"] == "STEWARDS_RULING"


def test_add_treatment_via_api():
    chip = "985112000901001"
    client.post("/horses", json={"chip_id": chip, "name": "Treatment Test Horse"})
    r = client.post(f"/horses/{chip}/treatments", json={
        "treatment_date": "2026-06-01",
        "substance": "Lasix",
        "dose": "250 mg",
        "route": "IV",
        "withdrawal_time_hours": 24,
        "administered_by": "Dr. Chen",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_get_treatments_via_api():
    chip = "985112000901002"
    client.post("/horses", json={"chip_id": chip, "name": "Get Treatment Horse"})
    client.post(f"/horses/{chip}/treatments", json={
        "treatment_date": "2026-06-01", "substance": "Bute",
    })
    r = client.get(f"/horses/{chip}/treatments")
    assert r.status_code == 200
    assert len(r.json()["treatments"]) == 1
    assert r.json()["treatments"][0]["substance"] == "Bute"


def test_surface_condition_via_api():
    client.post("/venues", json={
        "venue_id": "SCL_TEST", "name": "SCL Test", "total_distance_m": 1600.0,
    })
    r = client.post("/venues/SCL_TEST/surface-conditions", json={
        "logged_date": "2026-06-01",
        "surface_type": "Turf",
        "going_description": "Good",
        "moisture_pct": 15.0,
        "logged_by": "Track Super",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r2 = client.get("/venues/SCL_TEST/surface-conditions")
    assert r2.status_code == 200
    logs = r2.json()["logs"]
    assert len(logs) == 1
    assert logs[0]["going_description"] == "Good"
