"""
test_phase5.py — Phase 5: Race Day Operations Module.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.server import app
from app.routes import get_current_user
from app.database import get_db, Base
from app.models import User, VenueRecord, Horse, Race
from app.api_keys_router import require_jwt_or_api_key
from app import crud

_mock = User()
_mock.id = "00000000-0000-0000-0000-000000000003"
_mock.username = "p5_admin"; _mock.hashed_password = "x"
_mock.role = "admin"; _mock.full_name = "P5 Admin"
_mock.active = True; _mock.tenant_id = None


@pytest.fixture(autouse=True)
def _auth():
    app.dependency_overrides[get_current_user] = lambda: _mock
    app.dependency_overrides[require_jwt_or_api_key] = lambda: _mock
    yield
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_jwt_or_api_key, None)


client = TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    S = sessionmaker(bind=engine)
    s = S()
    yield s
    s.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def race_db(db):
    db.add(VenueRecord(venue_id="TESTRD", name="Test RD", total_distance_m=1600.0))
    db.add(Horse(chip_id="985112000960001", name="Race Day Horse 1"))
    db.add(Horse(chip_id="985112000960002", name="Race Day Horse 2"))
    db.add(Horse(chip_id="985112000960003", name="Race Day Horse 3"))
    from datetime import datetime
    db.add(Race(venue_id="TESTRD", race_date=datetime(2026, 6, 5, 14, 0),
                distance_m=1600.0, surface="turf", status="pending", id=9001))
    db.commit()
    return db


# ── Entry management ──────────────────────────────────────────────────────────

def test_add_race_entry(race_db):
    r = crud.add_race_entry(race_db, race_id=9001,
                             horse_chip_id="985112000960001", saddle_cloth="1",
                             jockey="J. Castellano")
    assert r["ok"] is True


def test_add_race_entry_duplicate(race_db):
    crud.add_race_entry(race_db, 9001, "985112000960001", "1")
    r = crud.add_race_entry(race_db, 9001, "985112000960001", "2")
    assert r["ok"] is False


def test_add_race_entry_unknown_horse(race_db):
    r = crud.add_race_entry(race_db, 9001, "985112000000000", "1")
    assert r["ok"] is False


def test_update_race_entry(race_db):
    crud.add_race_entry(race_db, 9001, "985112000960001", "1", jockey="Old Jockey")
    r = crud.update_race_entry(race_db, 9001, "985112000960001", jockey="New Jockey")
    assert r["ok"] is True
    entries = crud.get_race_entries(race_db, 9001)
    assert entries[0].jockey == "New Jockey"


# ── Scratch ───────────────────────────────────────────────────────────────────

def test_scratch_horse(race_db):
    crud.add_race_entry(race_db, 9001, "985112000960001", "1")
    r = crud.scratch_horse(race_db, 9001, "985112000960001",
                            scratch_type="veterinary", declared_by="Dr. Patel",
                            reason="Lameness detected at morning inspection")
    assert r["ok"] is True
    assert "scratch_id" in r
    # Entry removed
    assert len(crud.get_race_entries(race_db, 9001)) == 0
    # Scratch record created
    scratches = crud.get_scratches(race_db, 9001)
    assert len(scratches) == 1
    assert scratches[0].scratch_type == "veterinary"


def test_scratch_nonexistent_entry(race_db):
    r = crud.scratch_horse(race_db, 9001, "985112000960001",
                            scratch_type="trainer")
    assert r["ok"] is False


# ── Results ingestion ─────────────────────────────────────────────────────────

def test_ingest_results(race_db):
    crud.add_race_entry(race_db, 9001, "985112000960001", "1")
    crud.add_race_entry(race_db, 9001, "985112000960002", "2")
    r = crud.ingest_race_results(race_db, 9001, [
        {"horse_chip_id": "985112000960001", "finish_position": 1, "elapsed_ms": 98000},
        {"horse_chip_id": "985112000960002", "finish_position": 2, "elapsed_ms": 99100},
    ])
    assert r["ok"] is True
    assert r["race_status"] == "finished"
    from app.models import RaceResult
    results = race_db.query(RaceResult).filter_by(race_id=9001).all()
    assert len(results) == 2


def test_ingest_results_idempotent(race_db):
    data = [{"horse_chip_id": "985112000960001", "finish_position": 1, "elapsed_ms": 98000}]
    crud.ingest_race_results(race_db, 9001, data)
    r2 = crud.ingest_race_results(race_db, 9001, data)
    assert r2["ok"] is True
    assert r2["created"] == 0  # already existed


# ── Race status ───────────────────────────────────────────────────────────────

def test_update_race_status(race_db):
    r = crud.update_race_status(race_db, 9001, "active")
    assert r["ok"] is True
    from app.models import Race as RaceModel
    race = race_db.get(RaceModel, 9001)
    assert race.status == "active"


# ── API endpoints ─────────────────────────────────────────────────────────────

def _setup_race():
    client.post("/venues", json={"venue_id": "RDTST", "name": "RD Test", "total_distance_m": 1600.0})
    r = client.post("/races", json={"venue_id": "RDTST",
                                    "race_date": "2026-06-05T14:00:00",
                                    "distance_m": 1600.0, "surface": "dirt"})
    return r.json()["race_id"]


def test_add_and_list_entries_via_api():
    raceId = _setup_race()
    chip = "985112000961001"
    client.post("/horses", json={"chip_id": chip, "name": "API Entry Horse"})
    r = client.post(f"/races/{raceId}/entries",
                    json={"horse_chip_id": chip, "saddle_cloth": "5", "jockey": "I. Ortiz"})
    assert r.status_code == 200

    r2 = client.get(f"/races/{raceId}/entries")
    assert r2.status_code == 200
    assert any(e["horse_chip_id"] == chip for e in r2.json()["entries"])


def test_scratch_via_api():
    raceId = _setup_race()
    chip = "985112000961002"
    client.post("/horses", json={"chip_id": chip, "name": "API Scratch Horse"})
    client.post(f"/races/{raceId}/entries",
                json={"horse_chip_id": chip, "saddle_cloth": "3"})
    r = client.post(f"/races/{raceId}/scratch/{chip}",
                    json={"scratch_type": "trainer", "declared_by": "Bob Baffert",
                          "reason": "Off feed this morning"})
    assert r.status_code == 200

    # Entry removed, scratch in list
    entries = client.get(f"/races/{raceId}/entries").json()
    assert not any(e["horse_chip_id"] == chip for e in entries["entries"])
    assert any(s["horse_chip_id"] == chip for s in entries["scratches"])


def test_ingest_results_via_api():
    raceId = _setup_race()
    chips = ["985112000961003", "985112000961004"]
    for i, c in enumerate(chips):
        client.post("/horses", json={"chip_id": c, "name": f"Ingest Horse {i}"})
        client.post(f"/races/{raceId}/entries",
                    json={"horse_chip_id": c, "saddle_cloth": str(i + 1)})
    r = client.post(f"/races/{raceId}/results/ingest", json={"results": [
        {"horse_chip_id": chips[0], "finish_position": 1, "elapsed_ms": 97500},
        {"horse_chip_id": chips[1], "finish_position": 2, "elapsed_ms": 98200},
    ]})
    assert r.status_code == 200
    assert r.json()["race_status"] == "finished"


def test_race_status_update_via_api():
    raceId = _setup_race()
    r = client.patch(f"/races/{raceId}/status", json={"status": "active"})
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_race_status_invalid():
    raceId = _setup_race()
    r = client.patch(f"/races/{raceId}/status", json={"status": "cancelled"})
    assert r.status_code == 400


def test_crop_violation_via_api():
    raceId = _setup_race()
    r = client.post(f"/races/{raceId}/crop-violations", json={
        "jockey_name": "I. Ortiz Jr.",
        "crop_count": 8,
        "violation_determined": True,
        "penalty": "Fine $500",
        "official_name": "Chief Steward Johnson",
    })
    assert r.status_code == 200
    r2 = client.get(f"/races/{raceId}/crop-violations")
    assert r2.status_code == 200
    assert r2.json()["violations"][0]["crop_count"] == 8
