"""
tests/test_race_state.py

Unit tests for the race engine core.
No HTTP required — tests race_state directly.

Run: pytest tests/
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import time
import threading
from app.race_state import RaceState, RaceStatus, HorseEntry


def make_horses(n: int = 5) -> list[HorseEntry]:
    # Use realistic EPC format matching the UHF lip implant chips
    return [
        HorseEntry(
            horse_id=f"E200681100000001AABB{i:04X}",
            display_name=f"Horse {i}",
            saddle_cloth=str(i),
        )
        for i in range(1, n + 1)
    ]


# ------------------------------------------------------------------ #
# Setup
# ------------------------------------------------------------------ #

def test_initial_state():
    r = RaceState()
    assert r.status == RaceStatus.IDLE
    assert r.total_expected == 0


def test_register_horses():
    r = RaceState()
    result = r.register_horses(make_horses(5))
    assert result["ok"]
    assert result["registered"] == 5
    assert r.status == RaceStatus.ARMED


def test_register_wipes_previous_results():
    r = RaceState()
    r.register_horses(make_horses(3))
    r.submit_tag("E200681100000001AABB0001")
    r.register_horses(make_horses(3))
    assert len(r.finish_order) == 0
    assert r.status == RaceStatus.ARMED


def test_arm_without_registration_fails():
    r = RaceState()
    result = r.arm()
    assert not result["ok"]


def test_arm_clears_results_keeps_horses():
    r = RaceState()
    r.register_horses(make_horses(3))
    r.submit_tag("E200681100000001AABB0001")
    r.arm()
    assert len(r.finish_order) == 0
    assert len(r.registered_horses) == 3
    assert r.status == RaceStatus.ARMED


# ------------------------------------------------------------------ #
# Tag submission
# ------------------------------------------------------------------ #

def test_first_tag_starts_race():
    r = RaceState()
    r.register_horses(make_horses(5))
    result = r.submit_tag("E200681100000001AABB0001")
    assert result["ok"]
    assert result["position"] == 1
    assert r.status == RaceStatus.RUNNING


def test_finish_order_is_correct():
    r = RaceState()
    r.register_horses(make_horses(5))
    for i in range(1, 6):
        r.submit_tag(f"E200681100000001AABB{i:04X}")
    order = r.get_finish_order()
    assert [e["horse_id"] for e in order["results"]] == [
        f"E200681100000001AABB{i:04X}" for i in range(1, 6)
    ]


def test_duplicate_tag_not_re_recorded():
    r = RaceState()
    r.register_horses(make_horses(3))
    r.submit_tag("E200681100000001AABB0001")
    r.submit_tag("E200681100000001AABB0001")  # Duplicate
    r.submit_tag("E200681100000001AABB0001")  # Duplicate
    assert len(r.finish_order) == 1


def test_duplicate_returns_correct_position():
    r = RaceState()
    r.register_horses(make_horses(3))
    r.submit_tag("E200681100000001AABB0001")
    result = r.submit_tag("E200681100000001AABB0001")
    assert result["duplicate"]
    assert result["position"] == 1


def test_unknown_tag_rejected():
    r = RaceState()
    r.register_horses(make_horses(3))
    result = r.submit_tag("FFFFFFFFFFFFFFFFFFFFFFFF")
    assert not result["ok"]
    assert result["reason"] == "unknown_tag"


def test_race_finishes_when_all_horses_cross():
    r = RaceState()
    horses = make_horses(5)
    r.register_horses(horses)
    for i in range(1, 5):
        r.submit_tag(f"E200681100000001AABB{i:04X}")
    assert r.status == RaceStatus.RUNNING
    r.submit_tag("E200681100000001AABB0005")
    assert r.status == RaceStatus.FINISHED
    assert r.is_finished()


def test_tag_submission_while_idle_rejected():
    r = RaceState()
    result = r.submit_tag("E200681100000001AABB0001")
    assert not result["ok"]
    assert result["reason"] == "unknown_tag"


# ------------------------------------------------------------------ #
# Results
# ------------------------------------------------------------------ #

def test_finish_order_includes_splits():
    r = RaceState()
    r.register_horses(make_horses(3))
    r.submit_tag("E200681100000001AABB0001")
    time.sleep(0.05)
    r.submit_tag("E200681100000001AABB0002")
    time.sleep(0.05)
    r.submit_tag("E200681100000001AABB0003")
    order = r.get_finish_order()
    results = order["results"]
    # First place has no split (they ARE the reference)
    assert results[0]["split_ms"] is None
    # Second and third have splits
    assert results[1]["split_ms"] is not None
    assert results[2]["split_ms"] is not None


def test_reset_wipes_everything():
    r = RaceState()
    r.register_horses(make_horses(5))
    r.submit_tag("E200681100000001AABB0001")
    r.reset()
    assert r.status == RaceStatus.IDLE
    assert len(r.registered_horses) == 0
    assert len(r.finish_order) == 0


def test_duplicate_count_in_results():
    r = RaceState()
    r.register_horses(make_horses(3))
    r.submit_tag("E200681100000001AABB0001")
    r.submit_tag("E200681100000001AABB0001")  # dup
    r.submit_tag("E200681100000001AABB0001")  # dup
    order = r.get_finish_order()
    assert order["results"][0]["raw_reads"] == 3


# ------------------------------------------------------------------ #
# Thread safety
# ------------------------------------------------------------------ #

def test_concurrent_submissions():
    """Fire all tags simultaneously from threads — no crashes, correct count."""
    r = RaceState()
    n = 20
    r.register_horses(make_horses(n))

    threads = [
        threading.Thread(target=r.submit_tag, args=(f"E200681100000001AABB{i:04X}",))
        for i in range(1, n + 1)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    order = r.get_finish_order()
    assert len(order["results"]) == n
    assert r.is_finished()
