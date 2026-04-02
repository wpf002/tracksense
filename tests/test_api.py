"""
test_api.py

HTTP API tests for TrackSense — covers every route in routes.py via
FastAPI's TestClient (real ASGI transport, no actual server started).

Test isolation: both singletons (registry, tracker) are cleared before
and after every test by the clean_state fixture.
"""

import pytest
from fastapi.testclient import TestClient

from app.server import app
from app.gate_registry import registry
from app.race_tracker import set_tracker

client = TestClient(app, raise_server_exceptions=True)


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

@pytest.fixture(autouse=True)
def clean_state():
    """Reset both module-level singletons around every test."""
    registry._venues.clear()
    set_tracker(None)
    yield
    registry._venues.clear()
    set_tracker(None)


def _setup_venue(venue_id="TESTTRACK") -> str:
    """Create a venue with start, mid, and finish gates. Returns venue_id."""
    client.post("/venues", json={
        "venue_id": venue_id,
        "name": "Test Track",
        "total_distance_m": 804.0,
    })
    client.post(f"/venues/{venue_id}/gates", json={
        "reader_id": "GATE-START", "name": "Start", "distance_m": 0.0, "is_finish": False,
    })
    client.post(f"/venues/{venue_id}/gates", json={
        "reader_id": "GATE-MID", "name": "Furlong 2", "distance_m": 402.0, "is_finish": False,
    })
    client.post(f"/venues/{venue_id}/gates", json={
        "reader_id": "GATE-FINISH", "name": "Finish", "distance_m": 804.0, "is_finish": True,
    })
    return venue_id


def _make_horses(n=3) -> list[dict]:
    return [
        {
            "horse_id": f"E200681100000001AABB{i:04X}",
            "display_name": f"Horse {i}",
            "saddle_cloth": str(i),
        }
        for i in range(1, n + 1)
    ]


def _setup_race(n=3, venue_id="TESTTRACK") -> str:
    """Create venue, register n horses, return venue_id."""
    _setup_venue(venue_id)
    client.post("/race/register", json={
        "venue_id": venue_id,
        "horses": _make_horses(n),
    })
    return venue_id


# ------------------------------------------------------------------ #
# Health
# ------------------------------------------------------------------ #

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["service"] == "tracksense"
    assert "version" in body
    assert "ws_connections" in body


# ------------------------------------------------------------------ #
# Venue management
# ------------------------------------------------------------------ #

def test_create_venue():
    r = client.post("/venues", json={
        "venue_id": "FLEMINGTON",
        "name": "Flemington Racecourse",
        "total_distance_m": 1609.0,
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["venue_id"] == "FLEMINGTON"


def test_create_venue_uppercases_id():
    r = client.post("/venues", json={
        "venue_id": "flemington",
        "name": "Flemington",
        "total_distance_m": 1609.0,
    })
    assert r.status_code == 200
    assert r.json()["venue_id"] == "FLEMINGTON"


def test_create_duplicate_venue_returns_409():
    client.post("/venues", json={"venue_id": "V1", "name": "V1", "total_distance_m": 800.0})
    r = client.post("/venues", json={"venue_id": "V1", "name": "V1 again", "total_distance_m": 800.0})
    assert r.status_code == 409


def test_list_venues_empty():
    r = client.get("/venues")
    assert r.status_code == 200
    assert r.json()["venues"] == []


def test_list_venues_after_create():
    client.post("/venues", json={"venue_id": "V1", "name": "V1", "total_distance_m": 800.0})
    client.post("/venues", json={"venue_id": "V2", "name": "V2", "total_distance_m": 1600.0})
    r = client.get("/venues")
    assert r.status_code == 200
    ids = [v["venue_id"] for v in r.json()["venues"]]
    assert "V1" in ids and "V2" in ids


def test_get_venue():
    _setup_venue("RANDWICK")
    r = client.get("/venues/RANDWICK")
    assert r.status_code == 200
    body = r.json()
    assert body["venue_id"] == "RANDWICK"
    assert body["total_distance_m"] == 804.0
    assert len(body["gates"]) == 3


def test_get_venue_not_found():
    r = client.get("/venues/NOWHERE")
    assert r.status_code == 404


def test_get_venue_gates_ordered_by_distance():
    _setup_venue("CAULFIELD")
    r = client.get("/venues/CAULFIELD")
    distances = [g["distance_m"] for g in r.json()["gates"]]
    assert distances == sorted(distances)


def test_delete_venue():
    client.post("/venues", json={"venue_id": "TEMP", "name": "Temp", "total_distance_m": 800.0})
    r = client.delete("/venues/TEMP")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert client.get("/venues/TEMP").status_code == 404


def test_delete_venue_not_found():
    r = client.delete("/venues/GHOST")
    assert r.status_code == 404


# ------------------------------------------------------------------ #
# Gate management
# ------------------------------------------------------------------ #

def test_add_gate():
    client.post("/venues", json={"venue_id": "V1", "name": "V1", "total_distance_m": 804.0})
    r = client.post("/venues/V1/gates", json={
        "reader_id": "GATE-FINISH", "name": "Finish", "distance_m": 804.0, "is_finish": True,
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_add_gate_uppercases_reader_id():
    client.post("/venues", json={"venue_id": "V1", "name": "V1", "total_distance_m": 804.0})
    r = client.post("/venues/V1/gates", json={
        "reader_id": "gate-finish", "name": "Finish", "distance_m": 804.0, "is_finish": True,
    })
    assert r.status_code == 200
    gates = client.get("/venues/V1").json()["gates"]
    assert any(g["reader_id"] == "GATE-FINISH" for g in gates)


def test_add_gate_to_missing_venue():
    r = client.post("/venues/GHOST/gates", json={
        "reader_id": "G1", "name": "G1", "distance_m": 0.0, "is_finish": False,
    })
    assert r.status_code == 400


def test_duplicate_reader_id_rejected():
    client.post("/venues", json={"venue_id": "V1", "name": "V1", "total_distance_m": 804.0})
    client.post("/venues/V1/gates", json={
        "reader_id": "GATE-FINISH", "name": "Finish", "distance_m": 804.0, "is_finish": True,
    })
    r = client.post("/venues/V1/gates", json={
        "reader_id": "GATE-FINISH", "name": "Finish Again", "distance_m": 804.0, "is_finish": False,
    })
    assert r.status_code == 400


def test_second_finish_gate_rejected():
    client.post("/venues", json={"venue_id": "V1", "name": "V1", "total_distance_m": 804.0})
    client.post("/venues/V1/gates", json={
        "reader_id": "G-FINISH", "name": "Finish", "distance_m": 804.0, "is_finish": True,
    })
    r = client.post("/venues/V1/gates", json={
        "reader_id": "G-FINISH2", "name": "Finish 2", "distance_m": 900.0, "is_finish": True,
    })
    assert r.status_code == 400


def test_remove_gate():
    client.post("/venues", json={"venue_id": "V1", "name": "V1", "total_distance_m": 804.0})
    client.post("/venues/V1/gates", json={
        "reader_id": "GATE-START", "name": "Start", "distance_m": 0.0, "is_finish": False,
    })
    r = client.delete("/venues/V1/gates/GATE-START")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    gates = client.get("/venues/V1").json()["gates"]
    assert not any(g["reader_id"] == "GATE-START" for g in gates)


def test_remove_gate_not_found():
    client.post("/venues", json={"venue_id": "V1", "name": "V1", "total_distance_m": 804.0})
    r = client.delete("/venues/V1/gates/GHOST-GATE")
    assert r.status_code == 404


# ------------------------------------------------------------------ #
# Race registration
# ------------------------------------------------------------------ #

def test_register_horses():
    _setup_venue()
    r = client.post("/race/register", json={
        "venue_id": "TESTTRACK",
        "horses": _make_horses(5),
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["registered"] == 5


def test_register_empty_horses_rejected():
    _setup_venue()
    r = client.post("/race/register", json={"venue_id": "TESTTRACK", "horses": []})
    assert r.status_code == 400


def test_register_duplicate_horse_ids_rejected():
    _setup_venue()
    horse = {"horse_id": "AABBCCDD", "display_name": "Twice", "saddle_cloth": "1"}
    r = client.post("/race/register", json={"venue_id": "TESTTRACK", "horses": [horse, horse]})
    assert r.status_code == 400


def test_register_unknown_venue_rejected():
    r = client.post("/race/register", json={
        "venue_id": "NOWHERE",
        "horses": _make_horses(3),
    })
    assert r.status_code == 404


def test_register_venue_without_finish_gate_rejected():
    client.post("/venues", json={"venue_id": "NOFINISH", "name": "No Finish", "total_distance_m": 804.0})
    client.post("/venues/NOFINISH/gates", json={
        "reader_id": "GATE-START", "name": "Start", "distance_m": 0.0, "is_finish": False,
    })
    r = client.post("/race/register", json={"venue_id": "NOFINISH", "horses": _make_horses(3)})
    assert r.status_code == 400


# ------------------------------------------------------------------ #
# Race lifecycle (arm / reset)
# ------------------------------------------------------------------ #

def test_arm_race():
    _setup_race()
    r = client.post("/race/arm")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["armed"] is True


def test_arm_without_registration_fails():
    r = client.post("/race/arm")
    assert r.status_code == 400


def test_reset_race():
    _setup_race()
    r = client.post("/race/reset")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # After reset, status should be idle
    status = client.get("/race/status").json()
    assert status["status"] == "idle"


# ------------------------------------------------------------------ #
# Tag submission
# ------------------------------------------------------------------ #

def test_submit_tag_no_active_race():
    r = client.post("/tags/submit", json={"tag_id": "AABBCCDD", "reader_id": "GATE-START"})
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["reason"] == "no_active_race"


def test_submit_tag_starts_race():
    _setup_race()
    r = client.post("/tags/submit", json={
        "tag_id": "E200681100000001AABB0001",
        "reader_id": "GATE-START",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["duplicate"] is False
    assert body["gate_name"] == "Start"
    assert body["elapsed_ms"] >= 0


def test_submit_tag_uppercases_inputs():
    _setup_race()
    r = client.post("/tags/submit", json={
        "tag_id": "e200681100000001aabb0001",
        "reader_id": "gate-start",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_submit_unknown_tag_rejected():
    _setup_race()
    r = client.post("/tags/submit", json={
        "tag_id": "FFFFFFFFFFFFFFFFFFFFFFFF",
        "reader_id": "GATE-START",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["reason"] == "unknown_tag"


def test_submit_unknown_gate_rejected():
    _setup_race()
    r = client.post("/tags/submit", json={
        "tag_id": "E200681100000001AABB0001",
        "reader_id": "GATE-NONEXISTENT",
    })
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert r.json()["reason"] == "unknown_gate"


def test_submit_duplicate_folded():
    _setup_race()
    client.post("/tags/submit", json={"tag_id": "E200681100000001AABB0001", "reader_id": "GATE-START"})
    r = client.post("/tags/submit", json={"tag_id": "E200681100000001AABB0001", "reader_id": "GATE-START"})
    assert r.status_code == 200
    assert r.json()["duplicate"] is True


def test_submit_finish_records_position():
    _setup_race()
    r = client.post("/tags/submit", json={
        "tag_id": "E200681100000001AABB0001",
        "reader_id": "GATE-FINISH",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["is_finish"] is True
    assert body["finish_position"] == 1


def test_full_race_completes():
    _setup_race(n=3)
    for i in range(1, 4):
        client.post("/tags/submit", json={
            "tag_id": f"E200681100000001AABB{i:04X}",
            "reader_id": "GATE-FINISH",
        })
    status = client.get("/race/status").json()
    assert status["status"] == "finished"


# ------------------------------------------------------------------ #
# Race state reads
# ------------------------------------------------------------------ #

def test_race_status_no_tracker():
    r = client.get("/race/status")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"


def test_race_status_after_register():
    _setup_race()
    r = client.get("/race/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "armed"
    assert body["registered"] == 3


def test_race_status_running():
    _setup_race()
    client.post("/tags/submit", json={"tag_id": "E200681100000001AABB0001", "reader_id": "GATE-START"})
    r = client.get("/race/status")
    assert r.json()["status"] == "running"
    assert r.json()["elapsed_ms"] is not None


def test_finish_order_no_tracker():
    r = client.get("/race/finish-order")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"
    assert r.json()["results"] == []


def test_finish_order_after_race():
    _setup_race(n=3)
    for i in range(1, 4):
        client.post("/tags/submit", json={
            "tag_id": f"E200681100000001AABB{i:04X}",
            "reader_id": "GATE-FINISH",
        })
    r = client.get("/race/finish-order")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 3
    assert results[0]["position"] == 1
    assert results[1]["position"] == 2
    assert results[2]["position"] == 3
    assert all("elapsed_str" in res for res in results)
    # splits: first finisher has no split, rest do
    assert results[0]["split_ms"] is None
    assert results[1]["split_ms"] is not None


def test_race_state_no_tracker():
    r = client.get("/race/state")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"


def test_race_state_shape():
    import time
    _setup_race(n=3)
    client.post("/tags/submit", json={"tag_id": "E200681100000001AABB0001", "reader_id": "GATE-START"})
    time.sleep(0.05)
    client.post("/tags/submit", json={"tag_id": "E200681100000001AABB0001", "reader_id": "GATE-FINISH"})

    r = client.get("/race/state")
    assert r.status_code == 200
    body = r.json()
    assert "horses" in body
    assert "status" in body
    assert "total_expected" in body
    assert len(body["horses"]) == 3

    horse1 = next(h for h in body["horses"] if h["horse_id"] == "E200681100000001AABB0001")
    assert horse1["finish_position"] == 1
    assert len(horse1["events"]) == 2
    assert len(horse1["sectionals"]) == 1
    assert horse1["sectionals"][0]["distance_m"] == 804.0
    assert horse1["sectionals"][0]["speed_kmh"] > 0


def test_race_state_horses_sorted_by_finish_position():
    _setup_race(n=3)
    for i in range(1, 4):
        client.post("/tags/submit", json={
            "tag_id": f"E200681100000001AABB{i:04X}",
            "reader_id": "GATE-FINISH",
        })
    horses = client.get("/race/state").json()["horses"]
    positions = [h["finish_position"] for h in horses]
    assert positions == [1, 2, 3]


# ------------------------------------------------------------------ #
# WebSocket
# ------------------------------------------------------------------ #

def test_websocket_connects():
    with client.websocket_connect("/ws/race") as ws:
        assert ws is not None


def test_websocket_connection_count():
    assert client.get("/health").json()["ws_connections"] == 0
    with client.websocket_connect("/ws/race"):
        assert client.get("/health").json()["ws_connections"] == 1
    assert client.get("/health").json()["ws_connections"] == 0