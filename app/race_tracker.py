
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

from app.gate_registry import GateRegistry, Venue, Gate, registry as default_registry


class RaceStatus(str, Enum):
    IDLE = "idle"
    ARMED = "armed"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


@dataclass
class HorseEntry:
    horse_id: str       # UHF chip EPC
    display_name: str
    saddle_cloth: str


@dataclass
class GateEvent:
    horse_id: str
    reader_id: str
    gate_name: str
    distance_m: float
    wall_time: float        # Unix timestamp
    race_elapsed_ms: int    # Ms since race start
    raw_reads: int = 1      # Duplicate reads folded into this event
    is_finish: bool = False


@dataclass
class Sectional:
    from_gate: str          # reader_id
    to_gate: str            # reader_id
    from_gate_name: str
    to_gate_name: str
    distance_m: float
    elapsed_ms: int         # Time to cover this segment
    speed_ms: float         # Metres per second
    speed_kmh: float        # Km/h


@dataclass
class HorseTrack:
    horse_id: str
    display_name: str
    saddle_cloth: str
    events: list[GateEvent] = field(default_factory=list)
    finish_position: Optional[int] = None

    def last_event(self) -> Optional[GateEvent]:
        return self.events[-1] if self.events else None

    def has_passed_gate(self, reader_id: str) -> bool:
        return any(e.reader_id == reader_id for e in self.events)

    def get_event(self, reader_id: str) -> Optional[GateEvent]:
        for e in self.events:
            if e.reader_id == reader_id:
                return e
        return None

    def sectionals(self, venue: Venue) -> list[Sectional]:
        """
        Compute sectional times between consecutive gate events.
        Returns one Sectional per segment the horse has completed.
        """
        result = []
        ordered_events = sorted(self.events, key=lambda e: e.distance_m)

        for i in range(len(ordered_events) - 1):
            e1 = ordered_events[i]
            e2 = ordered_events[i + 1]
            elapsed_ms = e2.race_elapsed_ms - e1.race_elapsed_ms
            distance_m = e2.distance_m - e1.distance_m

            if elapsed_ms <= 0 or distance_m <= 0:
                continue

            speed_ms = distance_m / (elapsed_ms / 1000)
            result.append(Sectional(
                from_gate=e1.reader_id,
                to_gate=e2.reader_id,
                from_gate_name=e1.gate_name,
                to_gate_name=e2.gate_name,
                distance_m=distance_m,
                elapsed_ms=elapsed_ms,
                speed_ms=round(speed_ms, 2),
                speed_kmh=round(speed_ms * 3.6, 2),
            ))
        return result

    def current_position_name(self) -> str:
        last = self.last_event()
        return last.gate_name if last else "Not started"


class RaceTracker:
    """
    Thread-safe multi-gate race tracking engine.

    One RaceTracker per active race. Accepts tag reads from any gate,
    routes them correctly, and maintains the full picture of the race.

    on_gate_event: optional callback fired on every new confirmed gate
    event. Used by the WebSocket manager to push live updates.
    """

    def __init__(
        self,
        venue_id: str,
        registry: Optional[GateRegistry] = None,
        on_gate_event: Optional[Callable[[dict], None]] = None,
    ):
        self.venue_id = venue_id
        self._registry = registry or default_registry
        self._on_gate_event = on_gate_event
        self._lock = threading.Lock()
        self._reset()

    def _reset(self):
        self.status: RaceStatus = RaceStatus.IDLE
        self.registered_horses: dict[str, HorseEntry] = {}
        self.tracks: dict[str, HorseTrack] = {}          # horse_id → HorseTrack
        self.duplicate_counts: dict[str, dict[str, int]] = {}  # horse_id → {reader_id → count}
        self.finish_order: list[str] = []                 # horse_ids in finish order
        self.race_start_wall: Optional[float] = None
        self.race_start_mono: Optional[float] = None
        self.race_finish_elapsed_ms: Optional[int] = None
        self.total_expected: int = 0
        # Simulation pause/stop controls
        self._sim_pause = threading.Event()
        self._sim_pause.set()           # set = running, cleared = paused
        self._sim_stop = threading.Event()
        self._pause_start_mono: Optional[float] = None   # wall time when current pause began
        self._total_paused_s: float = 0.0                # accumulated paused seconds

    # ------------------------------------------------------------------ #
    # Setup
    # ------------------------------------------------------------------ #

    def register_horses(self, horses: list[HorseEntry]) -> dict:
        with self._lock:
            if self.status == RaceStatus.RUNNING:
                return {"ok": False, "error": "Cannot re-register mid-race"}

            venue = self._registry.get_venue(self.venue_id)
            if not venue:
                return {"ok": False, "error": f"Venue '{self.venue_id}' not found"}
            if not venue.finish_gate():
                return {"ok": False, "error": "Venue has no finish gate configured"}

            self._reset()
            for h in horses:
                self.registered_horses[h.horse_id] = h
                self.tracks[h.horse_id] = HorseTrack(
                    horse_id=h.horse_id,
                    display_name=h.display_name,
                    saddle_cloth=h.saddle_cloth,
                )
                self.duplicate_counts[h.horse_id] = {}

            self.total_expected = len(horses)
            self.status = RaceStatus.ARMED
            return {"ok": True, "registered": len(horses), "venue_id": self.venue_id}

    def pause(self) -> dict:
        with self._lock:
            if self.status != RaceStatus.RUNNING:
                return {"ok": False, "error": f"Cannot pause in '{self.status}' state"}
            self._sim_pause.clear()
            self._pause_start_mono = time.monotonic()
            self.status = RaceStatus.PAUSED
            return {"ok": True, "paused": True}

    def resume(self) -> dict:
        with self._lock:
            if self.status != RaceStatus.PAUSED:
                return {"ok": False, "error": f"Cannot resume in '{self.status}' state"}
            if self._pause_start_mono is not None:
                self._total_paused_s += time.monotonic() - self._pause_start_mono
                self._pause_start_mono = None
            self.status = RaceStatus.RUNNING
            self._sim_pause.set()    # unblock waiting threads
            return {"ok": True, "resumed": True}

    def arm(self) -> dict:
        with self._lock:
            if not self.registered_horses:
                return {"ok": False, "error": "No horses registered"}
            # Clear tracking data, keep horse registration
            for horse_id, horse in self.registered_horses.items():
                self.tracks[horse_id] = HorseTrack(
                    horse_id=horse_id,
                    display_name=horse.display_name,
                    saddle_cloth=horse.saddle_cloth,
                )
                self.duplicate_counts[horse_id] = {}
            self.finish_order.clear()
            self.race_start_wall = None
            self.race_start_mono = None
            self.race_finish_elapsed_ms = None
            self.status = RaceStatus.ARMED
            return {"ok": True, "armed": True, "horses": len(self.registered_horses)}

    # ------------------------------------------------------------------ #
    # Tag ingestion — hot path
    # ------------------------------------------------------------------ #

    def submit_tag(self, tag_id: str, reader_id: str) -> dict:
        """
        Process a tag read from a specific gate.

        reader_id identifies which physical gate fired.
        The gate must exist in the venue configuration.

        Duplicate handling: a horse can pass through the same gate multiple
        times in real reads (the reader fires 2-4 times per transit).
        Only the first read per gate per horse is recorded as a GateEvent.
        """
        tag_id = tag_id.strip().upper()
        reader_id = reader_id.strip().upper()

        with self._lock:
            # Unknown horse
            if tag_id not in self.registered_horses:
                return {"ok": False, "reason": "unknown_tag", "tag_id": tag_id}

            # Unknown gate — not in venue config
            venue = self._registry.get_venue(self.venue_id)
            if not venue:
                return {"ok": False, "reason": "venue_not_found"}

            gate = venue.get_gate(reader_id)
            if not gate:
                return {"ok": False, "reason": "unknown_gate", "reader_id": reader_id}

            track = self.tracks[tag_id]

            # Duplicate read at this gate — fold it
            if track.has_passed_gate(reader_id):
                self.duplicate_counts[tag_id][reader_id] = (
                    self.duplicate_counts[tag_id].get(reader_id, 0) + 1
                )
                return {
                    "ok": True,
                    "duplicate": True,
                    "tag_id": tag_id,
                    "reader_id": reader_id,
                    "gate_name": gate.name,
                }

            now_wall = time.time()
            now_mono = time.monotonic()

            # First tag anywhere on track starts the race clock
            if self.status == RaceStatus.ARMED:
                self.race_start_wall = now_wall
                self.race_start_mono = now_mono
                self.status = RaceStatus.RUNNING

            assert self.race_start_mono is not None
            elapsed_ms = int((now_mono - self.race_start_mono) * 1000)

            event = GateEvent(
                horse_id=tag_id,
                reader_id=reader_id,
                gate_name=gate.name,
                distance_m=gate.distance_m,
                wall_time=now_wall,
                race_elapsed_ms=elapsed_ms,
                is_finish=gate.is_finish,
            )

            track.events.append(event)

            # If this is the finish gate, record finish position
            if gate.is_finish:
                self.finish_order.append(tag_id)
                track.finish_position = len(self.finish_order)
                if len(self.finish_order) >= self.total_expected:
                    self.status = RaceStatus.FINISHED
                    self.race_finish_elapsed_ms = self._compute_elapsed_ms()
                    # Fire webhooks after lock is released. get_race_state()
                    # acquires self._lock itself, so it must not be called while
                    # we hold it. Thread.start() here schedules the thread; by
                    # the time it actually runs, submit_tag has returned and
                    # released the lock, so get_race_state() succeeds cleanly.
                    tracker_ref = self
                    def _fire():
                        from app.webhooks import fire_webhooks
                        fire_webhooks(tracker_ref.get_race_state())
                    threading.Thread(target=_fire, daemon=True).start()

            horse = self.registered_horses[tag_id]
            response = {
                "ok": True,
                "duplicate": False,
                "tag_id": tag_id,
                "display_name": horse.display_name,
                "saddle_cloth": horse.saddle_cloth,
                "reader_id": reader_id,
                "gate_name": gate.name,
                "distance_m": gate.distance_m,
                "elapsed_ms": elapsed_ms,
                "elapsed_str": _ms_to_str(elapsed_ms),
                "is_finish": gate.is_finish,
                "finish_position": track.finish_position,
                "race_finished": self.status == RaceStatus.FINISHED,
            }

            # Fire callback outside lock to avoid deadlock
            if self._on_gate_event:
                threading.Thread(
                    target=self._on_gate_event,
                    args=(response,),
                    daemon=True,
                ).start()

            return response

    # ------------------------------------------------------------------ #
    # Reads
    # ------------------------------------------------------------------ #

    def get_race_state(self) -> dict:
        """Full snapshot of the race — all horses, all gates, all sectionals."""
        with self._lock:
            venue = self._registry.get_venue(self.venue_id)
            horses_out = []

            for horse_id, track in self.tracks.items():
                sectionals = track.sectionals(venue) if venue else []
                horses_out.append({
                    "horse_id": horse_id,
                    "display_name": track.display_name,
                    "saddle_cloth": track.saddle_cloth,
                    "finish_position": track.finish_position,
                    "current_gate": track.current_position_name(),
                    "gates_passed": len(track.events),
                    "events": [
                        {
                            "gate_name": e.gate_name,
                            "reader_id": e.reader_id,
                            "distance_m": e.distance_m,
                            "elapsed_ms": e.race_elapsed_ms,
                            "elapsed_str": _ms_to_str(e.race_elapsed_ms),
                            "is_finish": e.is_finish,
                            "raw_reads": 1 + self.duplicate_counts.get(horse_id, {}).get(e.reader_id, 0),
                        }
                        for e in sorted(track.events, key=lambda e: e.distance_m)
                    ],
                    "sectionals": [
                        {
                            "segment": f"{s.from_gate_name} → {s.to_gate_name}",
                            "distance_m": s.distance_m,
                            "elapsed_ms": s.elapsed_ms,
                            "elapsed_str": _ms_to_str(s.elapsed_ms),
                            "speed_ms": s.speed_ms,
                            "speed_kmh": s.speed_kmh,
                        }
                        for s in sectionals
                    ],
                })

            # Sort: finished horses first by position, then unfinished by gates passed
            horses_out.sort(key=lambda h: (
                h["finish_position"] if h["finish_position"] else 999,
                -h["gates_passed"],
            ))

            elapsed = None
            if self.race_start_mono:
                elapsed = self._compute_elapsed_ms()

            return {
                "status": self.status,
                "venue_id": self.venue_id,
                "total_expected": self.total_expected,
                "total_finished": len(self.finish_order),
                "elapsed_ms": elapsed,
                "elapsed_str": _ms_to_str(elapsed),
                "horses": horses_out,
            }

    def get_finish_order(self) -> dict:
        """Finish-line results only — compatible with Phase 1 API shape."""
        with self._lock:
            results = []
            prev_ms = None

            for position, horse_id in enumerate(self.finish_order, 1):
                track = self.tracks.get(horse_id)
                if not track:
                    continue
                finish_event = next(
                    (e for e in track.events if e.is_finish), None
                )
                if not finish_event:
                    continue

                elapsed_ms = finish_event.race_elapsed_ms
                split_ms = (elapsed_ms - prev_ms) if prev_ms is not None else None
                prev_ms = elapsed_ms

                results.append({
                    "position": position,
                    "horse_id": horse_id,
                    "display_name": track.display_name,
                    "saddle_cloth": track.saddle_cloth,
                    "elapsed_ms": elapsed_ms,
                    "elapsed_str": _ms_to_str(elapsed_ms),
                    "split_ms": split_ms,
                    "split_str": _ms_to_str(split_ms) if split_ms is not None else None,
                })

            return {
                "status": self.status,
                "total_expected": self.total_expected,
                "total_finished": len(self.finish_order),
                "results": results,
            }

    def _compute_elapsed_ms(self) -> int:
        """Elapsed race time in ms, paused time subtracted. Call inside lock."""
        if self.race_finish_elapsed_ms is not None:
            return self.race_finish_elapsed_ms
        raw_s = time.monotonic() - self.race_start_mono
        paused_s = self._total_paused_s
        if self._pause_start_mono is not None:
            # Currently paused — freeze elapsed at the value it had when we paused
            paused_s += time.monotonic() - self._pause_start_mono
        return int((raw_s - paused_s) * 1000)

    def get_status(self) -> dict:
        with self._lock:
            elapsed = None
            if self.race_start_mono:
                elapsed = self._compute_elapsed_ms()
            return {
                "status": self.status,
                "venue_id": self.venue_id,
                "registered": len(self.registered_horses),
                "finished": len(self.finish_order),
                "remaining": self.total_expected - len(self.finish_order),
                "elapsed_ms": elapsed,
            }

    def reset(self) -> dict:
        with self._lock:
            self._sim_stop.set()     # signal threads to exit
            self._sim_pause.set()    # unblock any paused threads so they see the stop flag
            self._reset()            # replaces both events with fresh ones
            return {"ok": True, "reset": True}

    def is_finished(self) -> bool:
        with self._lock:
            return self.status == RaceStatus.FINISHED


def _ms_to_str(ms: Optional[int]) -> Optional[str]:
    if ms is None:
        return None
    minutes = ms // 60000
    seconds = (ms % 60000) / 1000
    return f"{minutes}:{seconds:06.3f}"


# Active tracker singleton — one race at a time for Phase 2
# Phase 3 will support concurrent races across multiple venues
tracker: Optional[RaceTracker] = None
tracker_lock = threading.Lock()


def get_tracker() -> Optional[RaceTracker]:
    return tracker


def set_tracker(t: Optional[RaceTracker]):
    global tracker
    tracker = t
