
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import time
import threading
from app.gate_registry import GateRegistry
from app.race_tracker import RaceTracker, HorseEntry, RaceStatus


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #

def make_registry_with_venue(venue_id="TEST-TRACK") -> GateRegistry:
    """Registry with a standard 4-gate test venue."""
    reg = GateRegistry()
    reg.create_venue(venue_id, "Test Track", 804.0)
    reg.add_gate(venue_id, "GATE-START",  "Start",    0.0,   False)
    reg.add_gate(venue_id, "GATE-F2",     "Furlong 2", 402.0, False)
    reg.add_gate(venue_id, "GATE-FINISH", "Finish",   804.0, True)
    return reg


def make_horses(n=5) -> list[HorseEntry]:
    return [
        HorseEntry(
            horse_id=f"E200681100000001AABB{i:04X}",
            display_name=f"Horse {i}",
            saddle_cloth=str(i),
        )
        for i in range(1, n + 1)
    ]


def make_tracker(venue_id="TEST-TRACK") -> tuple[RaceTracker, GateRegistry]:
    reg = make_registry_with_venue(venue_id)
    t = RaceTracker(venue_id=venue_id, registry=reg)
    return t, reg


# ------------------------------------------------------------------ #
# GateRegistry tests
# ------------------------------------------------------------------ #

def test_create_venue():
    reg = GateRegistry()
    result = reg.create_venue("V1", "Venue One", 1609.0)
    assert result["ok"]
    assert reg.get_venue("V1") is not None


def test_duplicate_venue_rejected():
    reg = GateRegistry()
    reg.create_venue("V1", "Venue One", 1609.0)
    result = reg.create_venue("V1", "Venue One Again", 1609.0)
    assert not result["ok"]


def test_add_gate():
    reg = GateRegistry()
    reg.create_venue("V1", "Venue One", 804.0)
    result = reg.add_gate("V1", "GATE-FINISH", "Finish", 804.0, True)
    assert result["ok"]
    venue = reg.get_venue("V1")
    assert venue is not None
    assert venue.get_gate("GATE-FINISH") is not None


def test_duplicate_reader_id_rejected():
    reg = GateRegistry()
    reg.create_venue("V1", "Venue One", 804.0)
    reg.add_gate("V1", "GATE-FINISH", "Finish", 804.0, True)
    result = reg.add_gate("V1", "GATE-FINISH", "Finish Again", 804.0, False)
    assert not result["ok"]


def test_only_one_finish_gate():
    reg = GateRegistry()
    reg.create_venue("V1", "Venue One", 804.0)
    reg.add_gate("V1", "GATE-FINISH", "Finish", 804.0, True)
    result = reg.add_gate("V1", "GATE-FINISH2", "Finish 2", 900.0, True)
    assert not result["ok"]


def test_gates_ordered_by_distance():
    reg = make_registry_with_venue()
    venue = reg.get_venue("TEST-TRACK")
    assert venue is not None
    ordered = venue.gates_ordered()
    distances = [g.distance_m for g in ordered]
    assert distances == sorted(distances)


def test_get_venue_for_reader():
    reg = make_registry_with_venue()
    result = reg.get_venue_for_reader("GATE-FINISH")
    assert result is not None
    venue, gate = result
    assert gate.is_finish


def test_segment_distance():
    reg = make_registry_with_venue()
    venue = reg.get_venue("TEST-TRACK")
    assert venue is not None
    dist = venue.segment_distance("GATE-START", "GATE-F2")
    assert dist == 402.0


# ------------------------------------------------------------------ #
# RaceTracker tests
# ------------------------------------------------------------------ #

def test_register_requires_venue():
    reg = GateRegistry()  # No venues
    t = RaceTracker(venue_id="NOWHERE", registry=reg)
    result = t.register_horses(make_horses(3))
    assert not result["ok"]


def test_register_requires_finish_gate():
    reg = GateRegistry()
    reg.create_venue("V1", "Venue", 804.0)
    reg.add_gate("V1", "GATE-START", "Start", 0.0, False)  # No finish gate
    t = RaceTracker(venue_id="V1", registry=reg)
    result = t.register_horses(make_horses(3))
    assert not result["ok"]


def test_register_success():
    t, _ = make_tracker()
    result = t.register_horses(make_horses(5))
    assert result["ok"] and result["registered"] == 5
    assert t.status == RaceStatus.ARMED


def test_unknown_tag_rejected():
    t, _ = make_tracker()
    t.register_horses(make_horses(3))
    result = t.submit_tag("FFFFFFFFFFFFFFFFFFFFFFFF", "GATE-START")
    assert not result["ok"] and result["reason"] == "unknown_tag"


def test_unknown_gate_rejected():
    t, _ = make_tracker()
    t.register_horses(make_horses(3))
    result = t.submit_tag("E200681100000001AABB0001", "GATE-NONEXISTENT")
    assert not result["ok"] and result["reason"] == "unknown_gate"


def test_first_tag_starts_race():
    t, _ = make_tracker()
    t.register_horses(make_horses(5))
    result = t.submit_tag("E200681100000001AABB0001", "GATE-START")
    assert result["ok"] and not result["duplicate"]
    assert t.status == RaceStatus.RUNNING


def test_gate_event_recorded():
    t, _ = make_tracker()
    t.register_horses(make_horses(3))
    t.submit_tag("E200681100000001AABB0001", "GATE-START")
    track = t.tracks["E200681100000001AABB0001"]
    assert len(track.events) == 1
    assert track.events[0].reader_id == "GATE-START"


def test_duplicate_gate_read_folded():
    t, _ = make_tracker()
    t.register_horses(make_horses(3))
    t.submit_tag("E200681100000001AABB0001", "GATE-START")
    t.submit_tag("E200681100000001AABB0001", "GATE-START")  # duplicate
    t.submit_tag("E200681100000001AABB0001", "GATE-START")  # duplicate
    track = t.tracks["E200681100000001AABB0001"]
    assert len(track.events) == 1  # Still just one event
    assert t.duplicate_counts["E200681100000001AABB0001"]["GATE-START"] == 2


def test_horse_passes_multiple_gates():
    t, _ = make_tracker()
    t.register_horses(make_horses(3))
    t.submit_tag("E200681100000001AABB0001", "GATE-START")
    t.submit_tag("E200681100000001AABB0001", "GATE-F2")
    t.submit_tag("E200681100000001AABB0001", "GATE-FINISH")
    track = t.tracks["E200681100000001AABB0001"]
    assert len(track.events) == 3
    assert track.finish_position == 1


def test_finish_order_is_correct():
    t, _ = make_tracker()
    t.register_horses(make_horses(3))
    for i in range(1, 4):
        t.submit_tag(f"E200681100000001AABB{i:04X}", "GATE-FINISH")
    assert t.finish_order == [
        "E200681100000001AABB0001",
        "E200681100000001AABB0002",
        "E200681100000001AABB0003",
    ]


def test_race_finishes_when_all_cross_finish():
    t, _ = make_tracker()
    t.register_horses(make_horses(5))
    for i in range(1, 5):
        t.submit_tag(f"E200681100000001AABB{i:04X}", "GATE-FINISH")
    assert t.status == RaceStatus.RUNNING
    t.submit_tag("E200681100000001AABB0005", "GATE-FINISH")
    assert t.status == RaceStatus.FINISHED
    assert t.is_finished()


def test_sectionals_computed():
    t, reg = make_tracker()
    t.register_horses(make_horses(1))
    t.submit_tag("E200681100000001AABB0001", "GATE-START")
    time.sleep(0.05)
    t.submit_tag("E200681100000001AABB0001", "GATE-F2")
    time.sleep(0.05)
    t.submit_tag("E200681100000001AABB0001", "GATE-FINISH")

    venue = reg.get_venue("TEST-TRACK")
    assert venue is not None
    track = t.tracks["E200681100000001AABB0001"]
    sectionals = track.sectionals(venue)

    assert len(sectionals) == 2
    assert sectionals[0].distance_m == 402.0
    assert sectionals[0].speed_kmh > 0
    assert sectionals[1].distance_m == 402.0


def test_get_race_state_shape():
    t, _ = make_tracker()
    t.register_horses(make_horses(3))
    t.submit_tag("E200681100000001AABB0001", "GATE-START")
    t.submit_tag("E200681100000001AABB0001", "GATE-FINISH")

    state = t.get_race_state()
    assert "horses" in state
    assert "status" in state
    assert len(state["horses"]) == 3
    horse1 = next(h for h in state["horses"] if h["horse_id"] == "E200681100000001AABB0001")
    assert horse1["finish_position"] == 1
    assert len(horse1["events"]) == 2


def test_get_finish_order_compatible_shape():
    t, _ = make_tracker()
    t.register_horses(make_horses(3))
    for i in range(1, 4):
        t.submit_tag(f"E200681100000001AABB{i:04X}", "GATE-FINISH")

    result = t.get_finish_order()
    assert "results" in result
    assert len(result["results"]) == 3
    assert result["results"][0]["position"] == 1
    assert "elapsed_str" in result["results"][0]


def test_arm_clears_results_keeps_horses():
    t, _ = make_tracker()
    t.register_horses(make_horses(3))
    t.submit_tag("E200681100000001AABB0001", "GATE-FINISH")
    t.arm()
    assert len(t.finish_order) == 0
    assert len(t.registered_horses) == 3
    assert t.status == RaceStatus.ARMED


def test_reset_wipes_everything():
    t, _ = make_tracker()
    t.register_horses(make_horses(3))
    t.submit_tag("E200681100000001AABB0001", "GATE-FINISH")
    t.reset()
    assert t.status == RaceStatus.IDLE
    assert len(t.registered_horses) == 0
    assert len(t.finish_order) == 0


def test_gate_event_callback():
    """Verify on_gate_event callback fires for each new gate event."""
    events_received = []

    def capture(event):
        events_received.append(event)

    t, _ = make_tracker()
    t._on_gate_event = capture
    t.register_horses(make_horses(2))
    t.submit_tag("E200681100000001AABB0001", "GATE-START")
    t.submit_tag("E200681100000001AABB0001", "GATE-FINISH")
    time.sleep(0.05)  # Let callback threads complete
    assert len(events_received) == 2


def test_thread_safety():
    """20 horses simultaneously crossing the finish gate — correct count, no crashes."""
    t, _ = make_tracker()
    n = 20
    t.register_horses(make_horses(n))

    threads = [
        threading.Thread(
            target=t.submit_tag,
            args=(f"E200681100000001AABB{i:04X}", "GATE-FINISH"),
        )
        for i in range(1, n + 1)
    ]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    result = t.get_finish_order()
    assert len(result["results"]) == n
    assert t.is_finished()