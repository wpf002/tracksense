"""
scripts/seed.py

Seed the TrackSense database with rich, realistic demo data.

Defaults to SQLite (tracksense.db) when DATABASE_URL is not set.
Override: DATABASE_URL=postgresql://... python -m scripts.seed

Run from project root:
    python -m scripts.seed
    python -m scripts.seed --force    # wipe and re-seed
"""

import math
import os
import sys
import random
import argparse
from datetime import date, datetime, time, timedelta

# Must set before importing app modules so database.py picks it up
os.environ.setdefault("DATABASE_URL", "sqlite:///./tracksense.db")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401 — registers all ORM classes
from app.models import (
    Horse, Owner, Trainer, VetRecord,
    VenueRecord, GateRecord, TrackPathPoint,
    Race, RaceEntry, GateRead, RaceResult,
    WorkoutRecord, CheckInRecord, TestBarnRecord,
)

DATABASE_URL = os.environ["DATABASE_URL"]

# ------------------------------------------------------------------ #
# Static reference data
# ------------------------------------------------------------------ #

TRAINERS = [
    "Bob Baffert",       "Todd Pletcher",     "Steve Asmussen",    "Chad Brown",
    "Bill Mott",         "Mark Casse",        "Brad Cox",          "Doug O'Neill",
    "Chris Waller",      "Gai Waterhouse",    "Peter Moody",       "Aidan O'Brien",
    "John Gosden",       "Charlie Appleby",   "Dermot Weld",
    "Willie Mullins",    "Lindsay Park",      "Michael Stoute",
    "Saeed bin Suroor",  "James Cummings",
]

OWNERS = [
    "Godolphin",                   "Coolmore Stud",             "WinStar Farm",
    "Juddmonte Farms",             "Klaravich Stables",         "Eclipse Thoroughbred Partners",
    "Calumet Farm",                "Stonestreet Stables",       "Repole Stable",
    "SF Racing LLC",               "Sheikh Mohammed Al Maktoum","Khalid Abdullah",
    "Paul Reddam",                 "Mike Repole",               "Barry Irwin",
    "George Strawbridge Jr.",      "Kendall Hansen",            "Gary and Mary West",
    "Spendthrift Farm",            "Shortleaf Stable",
]

# Jockeys used only in workout notes (no jockey field on RaceEntry)
JOCKEYS = [
    "John Velazquez",    "Javier Castellano", "Irad Ortiz Jr.",    "Luis Saez",
    "Flavien Prat",      "Joel Rosario",      "Mike Smith",        "Victor Espinoza",
    "Gary Stevens",      "Pat Day",           "Frankie Dettori",   "Ryan Moore",
    "Christophe Soumillon", "James McDonald", "Oisin Murphy",
    "William Buick",     "Mickael Barzalona", "Rafael Bejarano",
    "Corey Nakatani",    "Tyler Gaffalione",
]

VET_NAMES = ["Dr. Sarah Chen", "Dr. Marcus Webb", "Dr. Priya Nair"]

CHECKIN_OFFICIALS = ["Head Steward", "Assistant Steward", "Gate Official"]
CHECKIN_LOCATIONS  = ["Paddock Check-In", "Mounting Yard", "Pre-Parade Ring"]

RACE_CONDITIONS = ["Fast", "Good", "Soft", "Heavy", "Firm"]

# 4 post times per race day
POST_TIMES = [time(12, 30), time(14, 0), time(15, 30), time(17, 0)]

WORKOUT_NOTES = [
    "Strong gallop, pulled up well",
    "Easy canter, feel good",
    "Barrier trial — jumped cleanly",
    "Quiet morning, just stretching the legs",
    "Worked with {horse} — held pace well",
    "Solid hit-out, trainer pleased",
    "Sweated up slightly, otherwise good",
    "Good tempo throughout",
    "Rider reports horse travelling well",
    "Light work ahead of race prep",
    "First workout back after rest",
    "Galloped under {jockey}, impressive feel",
    "Looked sharp through the turn",
    "Trainer flagged ground as key concern",
    "Excellent barrier manners on trial",
]

# ------------------------------------------------------------------ #
# Horses — 30 total
# ------------------------------------------------------------------ #

HORSES = [
    # EPCs unchanged — real-world champion racehorses
    {"epc": "E200681100000001AABB0001", "name": "Secretariat",       "breed": "Thoroughbred", "dob": "2020-03-30", "surface": "Dirt",      "speed": 0.88, "profile": "pacer"},
    {"epc": "E200681100000001AABB0002", "name": "Winx",              "breed": "Thoroughbred", "dob": "2011-09-14", "surface": "Turf",      "speed": 0.90, "profile": "closer"},
    {"epc": "E200681100000001AABB0003", "name": "Frankel",           "breed": "Thoroughbred", "dob": "2008-02-11", "surface": "Turf",      "speed": 0.91, "profile": "pacer"},
    {"epc": "E200681100000001AABB0004", "name": "Black Caviar",      "breed": "Thoroughbred", "dob": "2006-08-18", "surface": "Turf",      "speed": 0.92, "profile": "pacer"},
    {"epc": "E200681100000001AABB0005", "name": "American Pharoah",  "breed": "Thoroughbred", "dob": "2012-02-02", "surface": "Dirt",      "speed": 0.93, "profile": "midfield"},
    {"epc": "E200681100000001AABB0006", "name": "Justify",           "breed": "Thoroughbred", "dob": "2015-03-28", "surface": "Dirt",      "speed": 0.93, "profile": "midfield"},
    {"epc": "E200681100000001AABB0007", "name": "Zenyatta",          "breed": "Thoroughbred", "dob": "2004-04-01", "surface": "Dirt",      "speed": 0.93, "profile": "closer"},
    {"epc": "E200681100000001AABB0008", "name": "Enable",            "breed": "Thoroughbred", "dob": "2014-02-19", "surface": "Turf",      "speed": 0.94, "profile": "closer"},
    {"epc": "E200681100000001AABB0009", "name": "Sea The Stars",     "breed": "Thoroughbred", "dob": "2006-04-06", "surface": "Turf",      "speed": 0.94, "profile": "midfield"},
    {"epc": "E200681100000001AABB000A", "name": "Deep Impact",       "breed": "Thoroughbred", "dob": "2002-03-25", "surface": "Turf",      "speed": 0.94, "profile": "closer"},
    {"epc": "E200681100000001AABB000B", "name": "Arrogate",          "breed": "Thoroughbred", "dob": "2013-05-19", "surface": "Dirt",      "speed": 0.95, "profile": "closer"},
    {"epc": "E200681100000001AABB000C", "name": "Flightline",        "breed": "Thoroughbred", "dob": "2018-03-02", "surface": "Dirt",      "speed": 0.95, "profile": "pacer"},
    {"epc": "E200681100000001AABB000D", "name": "Curlin",            "breed": "Thoroughbred", "dob": "2004-03-30", "surface": "Dirt",      "speed": 0.96, "profile": "midfield"},
    {"epc": "E200681100000001AABB000E", "name": "Rachel Alexandra",  "breed": "Thoroughbred", "dob": "2006-02-26", "surface": "Dirt",      "speed": 0.96, "profile": "closer"},
    {"epc": "E200681100000001AABB000F", "name": "California Chrome", "breed": "Thoroughbred", "dob": "2011-02-18", "surface": "Dirt",      "speed": 0.96, "profile": "midfield"},
    {"epc": "E200681100000001AABB0010", "name": "Gun Runner",        "breed": "Thoroughbred", "dob": "2013-03-20", "surface": "Dirt",      "speed": 0.97, "profile": "pacer"},
    {"epc": "E200681100000001AABB0011", "name": "Beholder",          "breed": "Thoroughbred", "dob": "2010-01-21", "surface": "Dirt",      "speed": 0.97, "profile": "closer"},
    {"epc": "E200681100000001AABB0012", "name": "Songbird",          "breed": "Thoroughbred", "dob": "2013-02-07", "surface": "Dirt",      "speed": 0.97, "profile": "midfield"},
    {"epc": "E200681100000001AABB0013", "name": "Golden Sixty",      "breed": "Thoroughbred", "dob": "2017-01-24", "surface": "Turf",      "speed": 0.97, "profile": "closer"},
    {"epc": "E200681100000001AABB0014", "name": "Equinox",           "breed": "Thoroughbred", "dob": "2019-02-23", "surface": "Turf",      "speed": 0.98, "profile": "midfield"},
    {"epc": "E200681100000001AABB0015", "name": "Galileo",           "breed": "Thoroughbred", "dob": "1998-03-30", "surface": "Turf",      "speed": 0.98, "profile": "midfield"},
    {"epc": "E200681100000001AABB0016", "name": "Orb",               "breed": "Thoroughbred", "dob": "2010-02-28", "surface": "Dirt",      "speed": 0.98, "profile": "closer"},
    {"epc": "E200681100000001AABB0017", "name": "Havre de Grace",    "breed": "Thoroughbred", "dob": "2008-02-17", "surface": "Dirt",      "speed": 0.99, "profile": "pacer"},
    {"epc": "E200681100000001AABB0018", "name": "Accelerate",        "breed": "Thoroughbred", "dob": "2013-02-25", "surface": "Dirt",      "speed": 0.99, "profile": "closer"},
    {"epc": "E200681100000001AABB0019", "name": "McKinzie",          "breed": "Thoroughbred", "dob": "2015-03-08", "surface": "Dirt",      "speed": 0.99, "profile": "midfield"},
    {"epc": "E200681100000001AABB001A", "name": "Vino Rosso",        "breed": "Thoroughbred", "dob": "2015-05-01", "surface": "Dirt",      "speed": 1.00, "profile": "pacer"},
    {"epc": "E200681100000001AABB001B", "name": "Essential Quality", "breed": "Thoroughbred", "dob": "2018-01-20", "surface": "Dirt",      "speed": 1.00, "profile": "midfield"},
    {"epc": "E200681100000001AABB001C", "name": "Tapit Trice",       "breed": "Thoroughbred", "dob": "2020-04-14", "surface": "Dirt",      "speed": 1.00, "profile": "closer"},
    {"epc": "E200681100000001AABB001D", "name": "Code of Honor",     "breed": "Thoroughbred", "dob": "2016-03-12", "surface": "Dirt",      "speed": 1.01, "profile": "pacer"},
    {"epc": "E200681100000001AABB001E", "name": "Monomoy Girl",      "breed": "Thoroughbred", "dob": "2015-02-04", "surface": "Dirt",      "speed": 1.01, "profile": "closer"},
]

# ------------------------------------------------------------------ #
# Venues — 10 venues with programmatically generated gates
# ------------------------------------------------------------------ #

VENUES = [
    {"venue_id": "CHURCHILL",   "name": "Churchill Downs, Louisville KY",           "distance": 2012.0, "surface": "Dirt", "race_days": [4, 5]},  # Fri, Sat
    {"venue_id": "SARATOGA",    "name": "Saratoga Race Course, Saratoga Springs NY", "distance": 1809.0, "surface": "Dirt", "race_days": [2, 5]},  # Wed, Sat
    {"venue_id": "SANTA_ANITA", "name": "Santa Anita Park, Arcadia CA",              "distance": 1809.0, "surface": "Dirt", "race_days": [3, 5]},  # Thu, Sat
    {"venue_id": "BELMONT",     "name": "Belmont Park, Elmont NY",                  "distance": 2414.0, "surface": "Dirt", "race_days": [4, 5]},  # Fri, Sat
    {"venue_id": "KEENELAND",   "name": "Keeneland Race Course, Lexington KY",       "distance": 1809.0, "surface": "Dirt", "race_days": [3, 5]},  # Thu, Sat
    {"venue_id": "OAKLAWN",     "name": "Oaklawn Park, Hot Springs AR",              "distance": 1609.0, "surface": "Dirt", "race_days": [3, 5]},  # Thu, Sat
    {"venue_id": "DEL_MAR",     "name": "Del Mar Thoroughbred Club, Del Mar CA",     "distance": 1609.0, "surface": "Turf", "race_days": [4, 5]},  # Fri, Sat
    {"venue_id": "LA_DOWNS",    "name": "Louisiana Downs, Bossier City LA",          "distance": 1409.0, "surface": "Dirt", "race_days": [2, 5]},  # Wed, Sat
    {"venue_id": "FLEMINGTON",  "name": "Flemington Racecourse, Melbourne AU",       "distance": 2040.0, "surface": "Turf", "race_days": [4, 5]},  # Fri, Sat
    {"venue_id": "ASCOT",       "name": "Royal Ascot, Berkshire UK",                 "distance": 2012.0, "surface": "Turf", "race_days": [3, 5]},  # Thu, Sat
]

# Winner time lookup by total track distance (ms)
WINNER_TIMES_MS = {
    1409: 84_000,
    1609: 96_000,
    1809: 108_000,
    2012: 122_000,
    2040: 124_000,
    2414: 146_000,
}

# Furlong markers inserted when strictly less than total_distance_m
FURLONG_MARKERS = [
    ("GATE-F2", "Furlong 2",  402.0),
    ("GATE-F4", "Furlong 4",  804.0),
    ("GATE-F6", "Furlong 6", 1207.0),
    ("GATE-F8", "Furlong 8", 1609.0),
]

SPEED_PROFILES = {
    "pacer":    [0.92, 0.96, 1.02, 1.08, 1.12],
    "closer":   [1.10, 1.05, 1.00, 0.95, 0.88],
    "midfield": [1.00, 1.00, 1.00, 1.00, 1.00],
}

# ------------------------------------------------------------------ #
# Oval arc-length helpers (mirrors TrackMap.jsx oval parameterisation)
# ------------------------------------------------------------------ #

_OVAL_CX, _OVAL_CY = 0.5, 0.5
_OVAL_MID_RX = 287 / 800    # MID_RX / W_OVAL
_OVAL_MID_RY = 105 / 310    # MID_RY / H_OVAL
_ARC_STEPS = 720


def _build_arc_table():
    table = [(0.0, 0.0)]
    total = 0.0
    da = 2 * math.pi / _ARC_STEPS
    for i in range(1, _ARC_STEPS + 1):
        mid = (i - 0.5) * da
        ds = math.sqrt(
            (287 * math.cos(mid)) ** 2 + (105 * math.sin(mid)) ** 2
        ) * da
        total += ds
        table.append((i * da, total))
    return table, total


_ARC_TABLE, _ARC_TOTAL = _build_arc_table()


def _progress_to_angle(progress: float) -> float:
    target = (progress % 1.0) * _ARC_TOTAL
    lo, hi = 0, len(_ARC_TABLE) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if _ARC_TABLE[mid][1] <= target:
            lo = mid
        else:
            hi = mid
    a0, l0 = _ARC_TABLE[lo]
    a1, l1 = _ARC_TABLE[hi]
    f = 0 if l1 == l0 else (target - l0) / (l1 - l0)
    arc_angle = a0 + f * (a1 - a0)
    return math.pi / 2 - arc_angle


def gate_oval_position(distance_m: float, total_distance_m: float) -> tuple:
    """Return normalised (x, y) for a gate at distance_m on the oval."""
    progress = distance_m / total_distance_m if total_distance_m > 0 else 0
    angle = _progress_to_angle(progress)
    x = _OVAL_CX + _OVAL_MID_RX * math.cos(angle)
    y = _OVAL_CY + _OVAL_MID_RY * math.sin(angle)
    return round(x, 4), round(y, 4)


def oval_path_points(n: int = 48) -> list[dict]:
    """Generate n evenly-spaced points on the mid-track oval, starting at progress=0."""
    pts = []
    for i in range(n):
        angle = _progress_to_angle(i / n)
        pts.append({
            "x": round(_OVAL_CX + _OVAL_MID_RX * math.cos(angle), 4),
            "y": round(_OVAL_CY + _OVAL_MID_RY * math.sin(angle), 4),
        })
    return pts


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def build_venue_gates(total_distance_m: float) -> list:
    """Generate gate tuples for a venue from its total distance."""
    gates = [("GATE-START", "Start", 0.0, False)]
    for reader_id, name, dist in FURLONG_MARKERS:
        if dist < total_distance_m:
            gates.append((reader_id, name, dist, False))
    gates.append(("GATE-FINISH", "Finish", float(total_distance_m), True))
    return gates


def compute_segments_ms(gates: list, total_distance_m: float) -> list:
    """Base segment times in ms, proportional to winner time for this distance."""
    winner_ms = WINNER_TIMES_MS.get(round(total_distance_m), 96_000)
    return [
        int(((gates[i + 1][2] - gates[i][2]) / total_distance_m) * winner_ms)
        for i in range(len(gates) - 1)
    ]


def simulate_gate_times(horse: dict, segments_ms: list, venue_surface: str = None) -> list:
    """Return cumulative elapsed_ms for each gate (index 0 = start gate = 0 ms)."""
    multipliers = SPEED_PROFILES[horse["profile"]]
    base_speed  = horse["speed"]
    # Penalise horses whose preferred surface doesn't match the venue
    penalty = 1.0
    if venue_surface and horse["surface"] != venue_surface and horse["surface"] != "Synthetic":
        penalty = random.uniform(1.02, 1.05)

    times, cumulative = [0], 0
    for i, base_ms in enumerate(segments_ms):
        seg = int(
            base_ms
            * multipliers[i % len(multipliers)]
            * base_speed
            * penalty
            * random.uniform(0.97, 1.03)
        )
        cumulative += seg
        times.append(cumulative)
    return times


def weighted_sample_no_replacement(population: list, weights: list, k: int) -> list:
    """Sample k distinct items from population using the given weights."""
    result   = []
    remaining = list(zip(population, weights))
    k = min(k, len(remaining))
    for _ in range(k):
        total = sum(w for _, w in remaining)
        r, cum = random.uniform(0, total), 0.0
        chosen = len(remaining) - 1
        for i, (_, w) in enumerate(remaining):
            cum += w
            if cum >= r:
                chosen = i
                break
        result.append(remaining[chosen][0])
        remaining.pop(chosen)
    return result


def clear_tables(session) -> None:
    for table in [
        "biosensor_readings",
        "test_barn_records", "checkin_records", "workout_records",
        "race_results", "gate_reads", "race_entries", "races",
        "track_path_points", "gate_records", "venue_records",
        "vet_records", "trainers", "owners", "horses",
    ]:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()


# ------------------------------------------------------------------ #
# Seed functions
# ------------------------------------------------------------------ #

def seed_horses(session) -> dict:
    """Seed 30 horses with owners, trainers, and implant vet records."""
    horse_map = {}
    for idx, h in enumerate(HORSES):
        trainer_name = TRAINERS[idx % len(TRAINERS)]
        owner_name   = OWNERS[idx % len(OWNERS)]
        horse = Horse(
            epc=h["epc"],
            name=h["name"],
            breed=h["breed"],
            date_of_birth=h["dob"],
            implant_date="2023-06-01",
            implant_vet="Dr. Harriet Clarke",
        )
        session.add(horse)
        session.add(Owner(  horse_epc=h["epc"], owner_name=owner_name,   from_date="2023-06-01"))
        session.add(Trainer(horse_epc=h["epc"], trainer_name=trainer_name, from_date="2023-06-01"))
        session.add(VetRecord(
            horse_epc=h["epc"],
            event_date="2023-06-01",
            event_type="implant",
            notes="UHF Gen2 glass capsule, lower lip",
            vet_name="Dr. Harriet Clarke",
        ))
        horse_map[h["epc"]] = horse
    session.commit()
    return horse_map


def seed_venues(session) -> dict:
    """Seed 10 venues with programmatically generated gates.

    Returns enriched venue_map {venue_id: dict} with 'gates' and 'segments_ms'.
    """
    venue_map = {}
    for v in VENUES:
        gates       = build_venue_gates(v["distance"])
        segments_ms = compute_segments_ms(gates, v["distance"])
        session.add(VenueRecord(
            venue_id=v["venue_id"],
            name=v["name"],
            total_distance_m=v["distance"],
        ))
        for reader_id, name, dist, is_finish in gates:
            px, py = gate_oval_position(dist, v["distance"])
            session.add(GateRecord(
                venue_id=v["venue_id"],
                reader_id=reader_id,
                name=name,
                distance_m=dist,
                is_finish=is_finish,
                position_x=px,
                position_y=py,
            ))
        venue_map[v["venue_id"]] = {**v, "gates": gates, "segments_ms": segments_ms}
    session.commit()
    return venue_map


def seed_vet_records(session, today: date) -> int:
    """1-2 clearances, 1 vaccination, ~30% treatment per horse over 90 days."""
    start      = today - timedelta(days=90)
    day_count  = (today - start).days
    total      = 0

    for idx, h in enumerate(HORSES):
        vet = VET_NAMES[idx % len(VET_NAMES)]

        # 1-2 pre-race clearances
        for d in sorted(random.sample(range(day_count), random.randint(1, 2))):
            session.add(VetRecord(
                horse_epc=h["epc"],
                event_date=(start + timedelta(days=d)).isoformat(),
                event_type="clearance",
                notes="Cleared to race — no abnormalities detected",
                vet_name=vet,
            ))
            total += 1

        # Annual vaccination
        session.add(VetRecord(
            horse_epc=h["epc"],
            event_date=(start + timedelta(days=random.randint(0, day_count - 1))).isoformat(),
            event_type="vaccination",
            notes="Annual vaccination administered",
            vet_name=vet,
        ))
        total += 1

        # ~30% treatment
        if random.random() < 0.30:
            session.add(VetRecord(
                horse_epc=h["epc"],
                event_date=(start + timedelta(days=random.randint(0, day_count - 1))).isoformat(),
                event_type="treatment",
                notes=random.choice([
                    "Mild tendon strain — rest prescribed",
                    "Respiratory treatment administered",
                    "Hoof abscess treated",
                    "Post-race soreness, anti-inflammatory prescribed",
                ]),
                vet_name=vet,
            ))
            total += 1

    session.commit()
    return total


def seed_races(session, venue_map: dict, today: date) -> tuple:
    """Generate 90 days of race history: 4 races per venue race-day.

    Returns (race_records list, venue_stats dict).
    """
    start        = today - timedelta(days=90)
    race_records = []
    venue_stats  = {v["venue_id"]: {"days": set(), "races": 0, "entries": 0} for v in VENUES}

    current = start
    while current < today:
        dow = current.weekday()  # 0=Mon … 6=Sun

        for v in VENUES:
            if dow not in v["race_days"]:
                continue

            venue_id = v["venue_id"]
            vd       = venue_map[venue_id]
            weights  = [
                3 if h["surface"] == vd["surface"]
                else (2 if h["surface"] == "Synthetic" else 1)
                for h in HORSES
            ]

            for race_num in range(4):
                pt     = POST_TIMES[race_num]
                minute = max(0, min(59, pt.minute + random.randint(-5, 5)))
                race_dt = datetime(current.year, current.month, current.day, pt.hour, minute)

                n_runners = random.randint(8, 12)
                field     = weighted_sample_no_replacement(HORSES, weights, n_runners)

                race = Race(
                    venue_id=venue_id,
                    race_date=race_dt,
                    distance_m=vd["distance"],
                    surface=vd["surface"],
                    conditions=random.choice(RACE_CONDITIONS),
                    status="finished",
                )
                session.add(race)
                session.flush()  # get race.id within this transaction

                # Simulate and sort by finish time
                horse_times = [
                    (h, simulate_gate_times(h, vd["segments_ms"], vd["surface"]), str(i + 1))
                    for i, h in enumerate(field)
                ]
                horse_times.sort(key=lambda x: x[1][-1])

                for position, (h, times, saddle_cloth) in enumerate(horse_times, start=1):
                    epc = h["epc"]
                    session.add(RaceEntry(
                        race_id=race.id,
                        horse_epc=epc,
                        saddle_cloth=saddle_cloth,
                        jockey=random.choice(JOCKEYS),
                    ))
                    for gate_idx, (reader_id, gate_name, gate_dist, _) in enumerate(vd["gates"]):
                        session.add(GateRead(
                            race_id=race.id,
                            horse_epc=epc,
                            reader_id=reader_id,
                            gate_name=gate_name,
                            distance_m=gate_dist,
                            race_elapsed_ms=times[gate_idx],
                            wall_time=None,
                        ))
                    session.add(RaceResult(
                        race_id=race.id,
                        horse_epc=epc,
                        finish_position=position,
                        elapsed_ms=times[-1],
                    ))

                last_ms = horse_times[-1][1][-1]
                race_records.append({
                    "race_id":     race.id,
                    "race_date":   race_dt,
                    "venue_id":    venue_id,
                    "field":       [h["epc"] for h in field],
                    "results":     [(h["epc"], pos) for pos, (h, _, _) in enumerate(horse_times, start=1)],
                    "finish_time": race_dt + timedelta(milliseconds=last_ms + 2000),
                })

                vs = venue_stats[venue_id]
                vs["days"].add(current)
                vs["races"]   += 1
                vs["entries"] += len(field)

                session.commit()  # one commit per race — keeps memory bounded

        current += timedelta(days=1)

    return race_records, venue_stats


def seed_workouts(session, race_records: list, today: date) -> int:
    """12-20 workout records per horse over the past 90 days, skipping race days."""
    start          = today - timedelta(days=90)
    race_day_dates = {r["race_date"].date() for r in race_records}
    horse_names    = [h["name"] for h in HORSES]
    total          = 0

    for idx, h in enumerate(HORSES):
        epc          = h["epc"]
        trainer_name = TRAINERS[idx % len(TRAINERS)]
        n_workouts   = random.randint(12, 20)

        # Candidate dates: every day in range that isn't a race day
        candidates = []
        cursor     = start
        while cursor < today:
            if cursor not in race_day_dates:
                candidates.append(cursor)
            cursor += timedelta(days=1)

        selected = sorted(random.sample(candidates, min(n_workouts, len(candidates))))

        for workout_date in selected:
            distance_m  = random.choice([600.0, 800.0, 1000.0, 1200.0])
            duration_ms = int(
                (distance_m / 600.0) * 38_000 * h["speed"] * random.uniform(0.96, 1.04)
            )
            note = random.choice(WORKOUT_NOTES)
            if "{horse}" in note:
                note = note.replace("{horse}", random.choice(
                    [n for n in horse_names if n != h["name"]]
                ))
            if "{jockey}" in note:
                note = note.replace("{jockey}", random.choice(JOCKEYS))

            session.add(WorkoutRecord(
                horse_epc=epc,
                workout_date=workout_date.isoformat(),
                distance_m=distance_m,
                surface=h["surface"],
                duration_ms=duration_ms,
                track_condition=random.choice(["Fast", "Fast", "Good", "Soft"]),
                trainer_name=trainer_name,
                notes=note,
            ))
            total += 1

    session.commit()
    return total


def seed_checkins(session, race_records: list) -> int:
    """One CheckInRecord per race entry, 45-90 min before post time."""
    total = 0
    for race_info in race_records:
        race_dt = race_info["race_date"]
        race_id = race_info["race_id"]
        for epc in race_info["field"]:
            verified   = random.random() > 0.01  # 99% verified
            scanned_at = race_dt - timedelta(minutes=random.randint(45, 90))
            # Realistic temperature: 37.2-38.8°C; ~5% elevated (>38.5°C)
            temp_c = round(random.gauss(37.9, 0.35), 1)
            temp_c = max(36.5, min(40.0, temp_c))   # clamp to physiological range
            session.add(CheckInRecord(
                horse_epc=epc,
                race_id=race_id,
                scanned_at=scanned_at,
                scanned_by=random.choice(CHECKIN_OFFICIALS),
                location=random.choice(CHECKIN_LOCATIONS),
                verified=verified,
                notes=None if verified else "Identity query raised — resolved manually",
                temperature_c=temp_c,
            ))
            total += 1
    session.commit()
    return total


def seed_test_barn(session, race_records: list) -> int:
    """TestBarnRecord for top 3 finishers in every race."""
    total = 0
    for race_info in race_records:
        race_id     = race_info["race_id"]
        finish_time = race_info["finish_time"]
        top3        = sorted(race_info["results"], key=lambda x: x[1])[:3]

        for epc, position in top3:
            checkin_at  = finish_time + timedelta(minutes=random.randint(5, 15))
            checkout_at = checkin_at  + timedelta(minutes=random.randint(45, 90))
            result      = random.choices(["Clear", "Pending", "Void"], weights=[97, 2, 1])[0]
            sample_id   = f"TB-{race_id:04d}-{position:02d}-{random.randint(1000, 9999)}"
            session.add(TestBarnRecord(
                horse_epc=epc,
                race_id=race_id,
                checkin_at=checkin_at,
                checkin_by="Test Barn Official",
                checkout_at=checkout_at,
                checkout_by="Test Barn Official",
                sample_id=sample_id,
                result=result,
                notes=None,
            ))
            total += 1
    session.commit()
    return total


def seed_track_paths(session, venue_map: dict) -> int:
    """Seed 48-point oval track path for every venue."""
    points = oval_path_points(48)
    total = 0
    for venue_id in venue_map:
        for seq, pt in enumerate(points):
            session.add(TrackPathPoint(venue_id=venue_id, sequence=seq, x=pt["x"], y=pt["y"]))
            total += 1
    session.commit()
    return total


def seed_registry(venue_map: dict) -> None:
    """Hydrate the in-memory GateRegistry so Race Builder works immediately."""
    try:
        from app.gate_registry import registry
        for venue_id, v in venue_map.items():
            registry.create_venue(venue_id, v["name"], v["distance"])
            for reader_id, name, dist, is_finish in v["gates"]:
                registry.add_gate(venue_id, reader_id, name, dist, is_finish)
    except Exception as exc:
        print(f"[seed] Warning: in-memory registry hydration skipped — {exc}")


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def run(force: bool = False) -> None:
    engine  = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check for a known real venue rather than any horse — test fixtures
        # populate horses with fake EPCs, which would otherwise block seeding.
        from app.models import VenueRecord
        real_seeded = session.query(VenueRecord).filter_by(venue_id="CHURCHILL").first()
        if real_seeded and not force:
            print("Real seed data already present (CHURCHILL venue found).")
            print("Run with --force to wipe and re-seed.")
            return

        if real_seeded and force:
            print("[seed] Clearing existing data...")
            clear_tables(session)
        elif not real_seeded:
            # Partial data (e.g. test fixtures) — clear before seeding
            print("[seed] Clearing stale/test data before seeding...")
            clear_tables(session)

        today = datetime.now().date()

        print(f"[seed] Creating {len(VENUES)} venues and gates...")
        venue_map = seed_venues(session)

        print(f"[seed] Creating/updating {len(HORSES)} horses, owners, trainers...")
        seed_horses(session)

        print("[seed] Generating vet records...")
        n_vet = seed_vet_records(session, today)

        print("[seed] Generating 90 days of race history...")
        race_records, venue_stats = seed_races(session, venue_map, today)

        for v in VENUES:
            s = venue_stats[v["venue_id"]]
            print(
                f"[seed]   {v['venue_id']:<14}: "
                f"{len(s['days']):2d} race days, "
                f"{s['races']:3d} races, "
                f"{s['entries']:5d} entries"
            )

        print("[seed] Generating workout records...")
        n_workouts = seed_workouts(session, race_records, today)

        print("[seed] Generating check-in records...")
        n_checkins = seed_checkins(session, race_records)

        print("[seed] Generating test barn records...")
        n_test_barn = seed_test_barn(session, race_records)

        print("[seed] Seeding track path geometry...")
        n_path_pts = seed_track_paths(session, venue_map)

        print("[seed] Seeding in-memory gate registry...")
        seed_registry(venue_map)

        print("[seed] Done.\n")

        # ── Summary ──────────────────────────────────────────────────
        n_races   = len(race_records)
        n_entries = sum(len(r["field"]) for r in race_records)
        n_reads   = sum(
            len(r["field"]) * len(venue_map[r["venue_id"]]["gates"])
            for r in race_records
        )

        print("========== SEED SUMMARY ==========")
        print(f"Venues:            {len(VENUES)}")
        print(f"Horses:            {len(HORSES)}")
        print(f"Races:             {n_races}")
        print(f"Race entries:      {n_entries}")
        print(f"Gate reads:        {n_reads}")
        print(f"Race results:      {n_entries}")
        print(f"Vet records:       {n_vet + len(HORSES)}")   # +implant per horse
        print(f"Workout records:   {n_workouts}")
        print(f"Check-in records:  {n_checkins}")
        print(f"Test barn records: {n_test_barn}")
        print(f"Track path points: {n_path_pts}")
        print("===================================\n")

        print("First 5 horse EPCs for testing Horse Profile:")
        for i, h in enumerate(HORSES[:5]):
            trainer_name = TRAINERS[i % len(TRAINERS)]
            owner_name   = OWNERS[i % len(OWNERS)]
            print(f"  {i + 1}. {h['epc']} — {h['name']} ({trainer_name} / {owner_name})")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed TrackSense database")
    parser.add_argument("--force", action="store_true", help="Wipe and re-seed")
    args = parser.parse_args()
    run(force=args.force)