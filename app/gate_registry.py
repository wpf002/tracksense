
import threading
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Gate:
    reader_id: str          # Must match reader_id sent in tag submissions
    name: str               # Human-readable e.g. "Start", "Furlong 1", "Finish"
    distance_m: float       # Distance from start in metres
    is_finish: bool = False # True for the finish line gate


@dataclass
class Venue:
    venue_id: str
    name: str
    total_distance_m: float
    gates: list[Gate] = field(default_factory=list)

    def gates_ordered(self) -> list[Gate]:
        """Gates sorted by distance from start."""
        return sorted(self.gates, key=lambda g: g.distance_m)

    def get_gate(self, reader_id: str) -> Optional[Gate]:
        for g in self.gates:
            if g.reader_id == reader_id:
                return g
        return None

    def finish_gate(self) -> Optional[Gate]:
        for g in self.gates:
            if g.is_finish:
                return g
        return None

    def next_gate(self, reader_id: str) -> Optional[Gate]:
        """Return the gate after the given one, by distance."""
        ordered = self.gates_ordered()
        for i, g in enumerate(ordered):
            if g.reader_id == reader_id and i + 1 < len(ordered):
                return ordered[i + 1]
        return None

    def segment_distance(self, from_reader_id: str, to_reader_id: str) -> Optional[float]:
        """Distance in metres between two gates."""
        g1 = self.get_gate(from_reader_id)
        g2 = self.get_gate(to_reader_id)
        if g1 and g2:
            return abs(g2.distance_m - g1.distance_m)
        return None


class GateRegistry:
    """
    In-memory registry of all venues and their gate configurations.
    Thread-safe. One singleton shared across the app.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._venues: dict[str, Venue] = {}

    # ------------------------------------------------------------------ #
    # Venue management
    # ------------------------------------------------------------------ #

    def create_venue(
        self,
        venue_id: str,
        name: str,
        total_distance_m: float,
    ) -> dict:
        with self._lock:
            if venue_id in self._venues:
                return {"ok": False, "error": f"Venue '{venue_id}' already exists"}
            self._venues[venue_id] = Venue(
                venue_id=venue_id,
                name=name,
                total_distance_m=total_distance_m,
            )
            return {"ok": True, "venue_id": venue_id}

    def delete_venue(self, venue_id: str) -> dict:
        with self._lock:
            if venue_id not in self._venues:
                return {"ok": False, "error": f"Venue '{venue_id}' not found"}
            del self._venues[venue_id]
            return {"ok": True, "deleted": venue_id}

    def get_venue(self, venue_id: str) -> Optional[Venue]:
        with self._lock:
            return self._venues.get(venue_id)

    def list_venues(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "venue_id": v.venue_id,
                    "name": v.name,
                    "total_distance_m": v.total_distance_m,
                    "gate_count": len(v.gates),
                    "has_finish_gate": v.finish_gate() is not None,
                }
                for v in self._venues.values()
            ]

    # ------------------------------------------------------------------ #
    # Gate management
    # ------------------------------------------------------------------ #

    def add_gate(
        self,
        venue_id: str,
        reader_id: str,
        name: str,
        distance_m: float,
        is_finish: bool = False,
    ) -> dict:
        with self._lock:
            venue = self._venues.get(venue_id)
            if not venue:
                return {"ok": False, "error": f"Venue '{venue_id}' not found"}

            # reader_id must be unique within venue
            if any(g.reader_id == reader_id for g in venue.gates):
                return {"ok": False, "error": f"reader_id '{reader_id}' already exists in this venue"}

            # Only one finish gate per venue
            if is_finish and venue.finish_gate():
                return {"ok": False, "error": "Venue already has a finish gate"}

            venue.gates.append(Gate(
                reader_id=reader_id,
                name=name,
                distance_m=distance_m,
                is_finish=is_finish,
            ))
            return {"ok": True, "venue_id": venue_id, "reader_id": reader_id}

    def remove_gate(self, venue_id: str, reader_id: str) -> dict:
        with self._lock:
            venue = self._venues.get(venue_id)
            if not venue:
                return {"ok": False, "error": f"Venue '{venue_id}' not found"}
            before = len(venue.gates)
            venue.gates = [g for g in venue.gates if g.reader_id != reader_id]
            if len(venue.gates) == before:
                return {"ok": False, "error": f"Gate '{reader_id}' not found"}
            return {"ok": True, "removed": reader_id}

    def get_venue_for_reader(self, reader_id: str) -> Optional[tuple[Venue, Gate]]:
        """
        Given a reader_id, find which venue and gate it belongs to.
        Used during tag submission to route reads to the correct venue.
        """
        with self._lock:
            for venue in self._venues.values():
                gate = venue.get_gate(reader_id)
                if gate:
                    return (venue, gate)
        return None

    def list_gates(self, venue_id: str) -> dict:
        with self._lock:
            venue = self._venues.get(venue_id)
            if not venue:
                return {"ok": False, "error": f"Venue '{venue_id}' not found"}
            return {
                "ok": True,
                "venue_id": venue_id,
                "gates": [
                    {
                        "reader_id": g.reader_id,
                        "name": g.name,
                        "distance_m": g.distance_m,
                        "is_finish": g.is_finish,
                    }
                    for g in venue.gates_ordered()
                ],
            }


# Singleton
registry = GateRegistry()
