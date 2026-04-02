"""
race_state.py

Central in-memory race engine for TrackSense.

Design decisions:
- Thread-safe: mock reader and future hardware readers run in separate threads
- Timestamps every tag read with monotonic + wall clock
- Supports multiple race sessions without restart
- Validates tag IDs against registered horses (prevents garbage reads)
- Tracks duplicate reads (real RFID readers spam duplicates — we handle it)
- Exposes clean finish order with split times
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class RaceStatus(str, Enum):
    IDLE = "idle"           # No race loaded
    ARMED = "armed"         # Horses registered, waiting for first tag
    RUNNING = "running"     # First tag received, race in progress
    FINISHED = "finished"   # All horses have crossed


@dataclass
class TagRead:
    horse_id: str
    position: int               # Finish position (1-indexed)
    wall_time: float            # Unix timestamp
    race_elapsed_ms: int        # Milliseconds since first tag crossed
    raw_reads: int = 1          # How many times this tag was seen (duplicates folded)


@dataclass
class HorseEntry:
    horse_id: str               # Matches RFID tag ID
    display_name: str           # Human-readable name
    saddle_cloth: str           # Race number on cloth


class RaceState:
    def __init__(self):
        self._lock = threading.Lock()
        self._reset()

    def _reset(self):
        """Full state wipe. Call under lock or during init."""
        self.status: RaceStatus = RaceStatus.IDLE
        self.registered_horses: dict[str, HorseEntry] = {}
        self.finish_order: list[TagRead] = []
        self.seen_ids: set[str] = set()
        self.duplicate_counts: dict[str, int] = {}
        self.race_start_wall: Optional[float] = None
        self.race_start_mono: Optional[float] = None
        self.total_expected: int = 0

    # ------------------------------------------------------------------ #
    # Setup
    # ------------------------------------------------------------------ #

    def register_horses(self, horses: list[HorseEntry]) -> dict:
        """Register the field before arming. Replaces any existing registration."""
        with self._lock:
            if self.status == RaceStatus.RUNNING:
                return {"ok": False, "error": "Cannot re-register mid-race"}
            self._reset()
            for h in horses:
                self.registered_horses[h.horse_id] = h
            self.total_expected = len(horses)
            self.status = RaceStatus.ARMED
            return {"ok": True, "registered": len(horses)}

    def arm(self) -> dict:
        """Arm without re-registering (use existing horse list)."""
        with self._lock:
            if not self.registered_horses:
                return {"ok": False, "error": "No horses registered"}
            # Clear results only, keep horse registry
            self.finish_order.clear()
            self.seen_ids.clear()
            self.duplicate_counts.clear()
            self.race_start_wall = None
            self.race_start_mono = None
            self.status = RaceStatus.ARMED
            return {"ok": True, "armed": True, "horses": len(self.registered_horses)}

    # ------------------------------------------------------------------ #
    # Tag ingestion — the hot path
    # ------------------------------------------------------------------ #

    def submit_tag(self, tag_id: str) -> dict:
        """
        Process an incoming RFID tag read.

        Returns a response dict that hardware readers and the mock reader
        both consume to decide what to do next.

        Key behaviors:
        - Unknown tags are rejected (garbage reads from nearby tags)
        - Duplicate tags are counted but not re-recorded in finish order
        - First tag ever starts the race clock
        - When all horses finish, status flips to FINISHED
        """
        tag_id = tag_id.strip().upper()

        with self._lock:
            # Unknown tag — not in this race's field
            if tag_id not in self.registered_horses:
                return {
                    "ok": False,
                    "reason": "unknown_tag",
                    "tag_id": tag_id
                }

            # Duplicate read — tag already finished
            if tag_id in self.seen_ids:
                self.duplicate_counts[tag_id] = self.duplicate_counts.get(tag_id, 0) + 1
                return {
                    "ok": True,
                    "duplicate": True,
                    "tag_id": tag_id,
                    "position": next(
                        r.position for r in self.finish_order if r.horse_id == tag_id
                    )
                }

            now_wall = time.time()
            now_mono = time.monotonic()

            # First tag — start the race clock
            if self.status == RaceStatus.ARMED:
                self.race_start_wall = now_wall
                self.race_start_mono = now_mono
                self.status = RaceStatus.RUNNING

            assert self.race_start_mono is not None
            elapsed_ms = int((now_mono - self.race_start_mono) * 1000)
            position = len(self.finish_order) + 1

            read = TagRead(
                horse_id=tag_id,
                position=position,
                wall_time=now_wall,
                race_elapsed_ms=elapsed_ms,
                raw_reads=1,
            )

            self.finish_order.append(read)
            self.seen_ids.add(tag_id)

            # Check if race is done
            if len(self.finish_order) >= self.total_expected:
                self.status = RaceStatus.FINISHED

            horse = self.registered_horses[tag_id]
            return {
                "ok": True,
                "duplicate": False,
                "tag_id": tag_id,
                "display_name": horse.display_name,
                "saddle_cloth": horse.saddle_cloth,
                "position": position,
                "elapsed_ms": elapsed_ms,
                "race_finished": self.status == RaceStatus.FINISHED,
            }

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def get_finish_order(self) -> dict:
        with self._lock:
            horse_map = self.registered_horses
            results = []
            prev_ms = None

            for r in self.finish_order:
                horse = horse_map.get(r.horse_id)
                split_ms = (r.race_elapsed_ms - prev_ms) if prev_ms is not None else None
                prev_ms = r.race_elapsed_ms
                results.append({
                    "position": r.position,
                    "horse_id": r.horse_id,
                    "display_name": horse.display_name if horse else r.horse_id,
                    "saddle_cloth": horse.saddle_cloth if horse else "?",
                    "elapsed_ms": r.race_elapsed_ms,
                    "elapsed_str": _ms_to_str(r.race_elapsed_ms),
                    "split_ms": split_ms,
                    "split_str": _ms_to_str(split_ms) if split_ms is not None else None,
                    "raw_reads": r.raw_reads + self.duplicate_counts.get(r.horse_id, 0),
                })

            return {
                "status": self.status,
                "total_expected": self.total_expected,
                "total_finished": len(self.finish_order),
                "results": results,
            }

    def get_status(self) -> dict:
        with self._lock:
            elapsed = None
            if self.race_start_mono:
                elapsed = int((time.monotonic() - self.race_start_mono) * 1000)
            return {
                "status": self.status,
                "registered": len(self.registered_horses),
                "finished": len(self.finish_order),
                "remaining": self.total_expected - len(self.finish_order),
                "elapsed_ms": elapsed,
            }

    def reset(self) -> dict:
        with self._lock:
            self._reset()
            return {"ok": True, "reset": True}

    def is_finished(self) -> bool:
        with self._lock:
            return self.status == RaceStatus.FINISHED


def _ms_to_str(ms: Optional[int]) -> Optional[str]:
    """Convert milliseconds to m:ss.mmm string."""
    if ms is None:
        return None
    minutes = ms // 60000
    seconds = (ms % 60000) / 1000
    return f"{minutes}:{seconds:06.3f}"


# Singleton — imported everywhere
race = RaceState()
