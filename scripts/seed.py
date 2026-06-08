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
    VenueRecord,
    Race, RaceEntry, RaceResult,
    WorkoutRecord, CheckInRecord, TestBarnRecord,
    TreatmentRecord, VetCheckRecord, StewardsRuling,
    SurfaceConditionLog, HISASubmission,
    ScratchRecord,
)
from app import hisa_builder
import json

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

# Clockers / timekeepers who hand-time morning works
CLOCKERS = [
    "Hank Goldberg",  "Toby Callet",   "Maria Sandoval",
    "Eddie Donnelly", "Ray Paulick",   "Dottie Shirreffs",
]

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
    # chip_id = Jockey Club LF microchip (ISO 11784/11785, 15-digit) — demo values
    {"chip_id": "985112000000001", "name": "Secretariat",       "breed": "Thoroughbred", "dob": "2020-03-30", "surface": "Dirt",      "speed": 0.88, "profile": "pacer"},
    {"chip_id": "985112000000002", "name": "Winx",              "breed": "Thoroughbred", "dob": "2011-09-14", "surface": "Turf",      "speed": 0.90, "profile": "closer"},
    {"chip_id": "985112000000003", "name": "Frankel",           "breed": "Thoroughbred", "dob": "2008-02-11", "surface": "Turf",      "speed": 0.91, "profile": "pacer"},
    {"chip_id": "985112000000004", "name": "Black Caviar",      "breed": "Thoroughbred", "dob": "2006-08-18", "surface": "Turf",      "speed": 0.92, "profile": "pacer"},
    {"chip_id": "985112000000005", "name": "American Pharoah",  "breed": "Thoroughbred", "dob": "2012-02-02", "surface": "Dirt",      "speed": 0.93, "profile": "midfield"},
    {"chip_id": "985112000000006", "name": "Justify",           "breed": "Thoroughbred", "dob": "2015-03-28", "surface": "Dirt",      "speed": 0.93, "profile": "midfield"},
    {"chip_id": "985112000000007", "name": "Zenyatta",          "breed": "Thoroughbred", "dob": "2004-04-01", "surface": "Dirt",      "speed": 0.93, "profile": "closer"},
    {"chip_id": "985112000000008", "name": "Enable",            "breed": "Thoroughbred", "dob": "2014-02-19", "surface": "Turf",      "speed": 0.94, "profile": "closer"},
    {"chip_id": "985112000000009", "name": "Sea The Stars",     "breed": "Thoroughbred", "dob": "2006-04-06", "surface": "Turf",      "speed": 0.94, "profile": "midfield"},
    {"chip_id": "985112000000010", "name": "Deep Impact",       "breed": "Thoroughbred", "dob": "2002-03-25", "surface": "Turf",      "speed": 0.94, "profile": "closer"},
    {"chip_id": "985112000000011", "name": "Arrogate",          "breed": "Thoroughbred", "dob": "2013-05-19", "surface": "Dirt",      "speed": 0.95, "profile": "closer"},
    {"chip_id": "985112000000012", "name": "Flightline",        "breed": "Thoroughbred", "dob": "2018-03-02", "surface": "Dirt",      "speed": 0.95, "profile": "pacer"},
    {"chip_id": "985112000000013", "name": "Curlin",            "breed": "Thoroughbred", "dob": "2004-03-30", "surface": "Dirt",      "speed": 0.96, "profile": "midfield"},
    {"chip_id": "985112000000014", "name": "Rachel Alexandra",  "breed": "Thoroughbred", "dob": "2006-02-26", "surface": "Dirt",      "speed": 0.96, "profile": "closer"},
    {"chip_id": "985112000000015", "name": "California Chrome", "breed": "Thoroughbred", "dob": "2011-02-18", "surface": "Dirt",      "speed": 0.96, "profile": "midfield"},
    {"chip_id": "985112000000016", "name": "Gun Runner",        "breed": "Thoroughbred", "dob": "2013-03-20", "surface": "Dirt",      "speed": 0.97, "profile": "pacer"},
    {"chip_id": "985112000000017", "name": "Beholder",          "breed": "Thoroughbred", "dob": "2010-01-21", "surface": "Dirt",      "speed": 0.97, "profile": "closer"},
    {"chip_id": "985112000000018", "name": "Songbird",          "breed": "Thoroughbred", "dob": "2013-02-07", "surface": "Dirt",      "speed": 0.97, "profile": "midfield"},
    {"chip_id": "985112000000019", "name": "Golden Sixty",      "breed": "Thoroughbred", "dob": "2017-01-24", "surface": "Turf",      "speed": 0.97, "profile": "closer"},
    {"chip_id": "985112000000020", "name": "Equinox",           "breed": "Thoroughbred", "dob": "2019-02-23", "surface": "Turf",      "speed": 0.98, "profile": "midfield"},
    {"chip_id": "985112000000021", "name": "Galileo",           "breed": "Thoroughbred", "dob": "1998-03-30", "surface": "Turf",      "speed": 0.98, "profile": "midfield"},
    {"chip_id": "985112000000022", "name": "Orb",               "breed": "Thoroughbred", "dob": "2010-02-28", "surface": "Dirt",      "speed": 0.98, "profile": "closer"},
    {"chip_id": "985112000000023", "name": "Havre de Grace",    "breed": "Thoroughbred", "dob": "2008-02-17", "surface": "Dirt",      "speed": 0.99, "profile": "pacer"},
    {"chip_id": "985112000000024", "name": "Accelerate",        "breed": "Thoroughbred", "dob": "2013-02-25", "surface": "Dirt",      "speed": 0.99, "profile": "closer"},
    {"chip_id": "985112000000025", "name": "McKinzie",          "breed": "Thoroughbred", "dob": "2015-03-08", "surface": "Dirt",      "speed": 0.99, "profile": "midfield"},
    {"chip_id": "985112000000026", "name": "Vino Rosso",        "breed": "Thoroughbred", "dob": "2015-05-01", "surface": "Dirt",      "speed": 1.00, "profile": "pacer"},
    {"chip_id": "985112000000027", "name": "Essential Quality", "breed": "Thoroughbred", "dob": "2018-01-20", "surface": "Dirt",      "speed": 1.00, "profile": "midfield"},
    {"chip_id": "985112000000028", "name": "Tapit Trice",       "breed": "Thoroughbred", "dob": "2020-04-14", "surface": "Dirt",      "speed": 1.00, "profile": "closer"},
    {"chip_id": "985112000000029", "name": "Code of Honor",     "breed": "Thoroughbred", "dob": "2016-03-12", "surface": "Dirt",      "speed": 1.01, "profile": "pacer"},
    {"chip_id": "985112000000030", "name": "Monomoy Girl",      "breed": "Thoroughbred", "dob": "2015-02-04", "surface": "Dirt",      "speed": 1.01, "profile": "closer"},
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
        "hisa_submissions", "stewards_rulings", "surface_condition_logs",
        "riding_crop_violations", "scratch_records",
        "treatment_records", "vet_check_records", "biosensor_readings",
        "test_barn_records", "checkin_records", "workout_records",
        "race_results", "race_entries", "races",
        "venue_records",
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
            chip_id=h["chip_id"],
            name=h["name"],
            breed=h["breed"],
            date_of_birth=h["dob"],
            implant_date="2023-06-01",
            implant_vet="Dr. Harriet Clarke",
        )
        session.add(horse)
        session.add(Owner(  horse_chip_id=h["chip_id"], owner_name=owner_name,   from_date="2023-06-01"))
        session.add(Trainer(horse_chip_id=h["chip_id"], trainer_name=trainer_name, from_date="2023-06-01"))
        session.add(VetRecord(
            horse_chip_id=h["chip_id"],
            event_date="2023-06-01",
            event_type="implant",
            notes="LF microchip (ISO 11784/11785 FDX-B), Jockey Club registration",
            vet_name="Dr. Harriet Clarke",
        ))
        horse_map[h["chip_id"]] = horse
    session.commit()
    return horse_map


def seed_venues(session) -> dict:
    """Seed 10 venues with programmatically generated gates.

    Returns enriched venue_map {venue_id: dict} with 'gates' and 'segments_ms'.
    """
    venue_map = {}
    for v in VENUES:
        # Gate tuples + segment times are still computed (pure helpers) so we can
        # derive realistic per-race finish times for RaceResult — but gates are no
        # longer persisted (the fixed-gate timing layer was removed in Phase 1).
        gates       = build_venue_gates(v["distance"])
        segments_ms = compute_segments_ms(gates, v["distance"])
        session.add(VenueRecord(
            venue_id=v["venue_id"],
            name=v["name"],
            total_distance_m=v["distance"],
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
                horse_chip_id=h["chip_id"],
                event_date=(start + timedelta(days=d)).isoformat(),
                event_type="clearance",
                notes="Cleared to race — no abnormalities detected",
                vet_name=vet,
            ))
            total += 1

        # Annual vaccination
        session.add(VetRecord(
            horse_chip_id=h["chip_id"],
            event_date=(start + timedelta(days=random.randint(0, day_count - 1))).isoformat(),
            event_type="vaccination",
            notes="Annual vaccination administered",
            vet_name=vet,
        ))
        total += 1

        # ~30% treatment
        if random.random() < 0.30:
            session.add(VetRecord(
                horse_chip_id=h["chip_id"],
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
                    chip_id = h["chip_id"]
                    session.add(RaceEntry(
                        race_id=race.id,
                        horse_chip_id=chip_id,
                        saddle_cloth=saddle_cloth,
                        jockey=random.choice(JOCKEYS),
                    ))
                    session.add(RaceResult(
                        race_id=race.id,
                        horse_chip_id=chip_id,
                        finish_position=position,
                        elapsed_ms=times[-1],
                    ))

                last_ms = horse_times[-1][1][-1]
                race_records.append({
                    "race_id":     race.id,
                    "race_date":   race_dt,
                    "venue_id":    venue_id,
                    "field":       [h["chip_id"] for h in field],
                    "results":     [(h["chip_id"], pos) for pos, (h, _, _) in enumerate(horse_times, start=1)],
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
        chip_id          = h["chip_id"]
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
                horse_chip_id=chip_id,
                workout_date=workout_date.isoformat(),
                distance_m=distance_m,
                surface=h["surface"],
                duration_ms=duration_ms,
                track_condition=random.choice(["Fast", "Fast", "Good", "Soft"]),
                trainer_name=trainer_name,
                rider_name=random.choice(JOCKEYS),
                clocker_name=random.choice(CLOCKERS),
                source="manual",
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
        for chip_id in race_info["field"]:
            verified   = random.random() > 0.01  # 99% verified
            scanned_at = race_dt - timedelta(minutes=random.randint(45, 90))
            # Realistic temperature: 37.2-38.8°C; ~5% elevated (>38.5°C)
            temp_c = round(random.gauss(37.9, 0.35), 1)
            temp_c = max(36.5, min(40.0, temp_c))   # clamp to physiological range
            session.add(CheckInRecord(
                horse_chip_id=chip_id,
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

        for chip_id, position in top3:
            checkin_at  = finish_time + timedelta(minutes=random.randint(5, 15))
            checkout_at = checkin_at  + timedelta(minutes=random.randint(45, 90))
            result      = random.choices(["Clear", "Pending", "Void"], weights=[97, 2, 1])[0]
            sample_id   = f"TB-{race_id:04d}-{position:02d}-{random.randint(1000, 9999)}"
            session.add(TestBarnRecord(
                horse_chip_id=chip_id,
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


# ------------------------------------------------------------------ #
# Phase 3–5 demo data: treatments, vet checks, rulings, surface,
# HISA submissions, and today's race card narrative
# ------------------------------------------------------------------ #

DEMO_TREATMENTS = [
    # Regular NSAID use — common, not prohibited
    {"horse_idx": 0, "days_ago": 3, "substance": "Phenylbutazone (Bute)", "dose": "2 g oral", "route": "oral",     "withdrawal": 24, "vet": "Dr. Sarah Chen",   "by": "Dr. Sarah Chen",   "prohibited": False, "notes": "Pre-workout soreness management"},
    {"horse_idx": 1, "days_ago": 5, "substance": "Phenylbutazone (Bute)", "dose": "4.4 mg/kg IV", "route": "IV",   "withdrawal": 48, "vet": "Dr. Marcus Webb",  "by": "Dr. Marcus Webb",  "prohibited": False, "notes": "Post-workout treatment, cleared for race"},
    {"horse_idx": 2, "days_ago": 1, "substance": "Furosemide (Lasix)",    "dose": "250 mg IV",    "route": "IV",   "withdrawal": 24, "vet": "Dr. Priya Nair",   "by": "Dr. Priya Nair",   "prohibited": False, "notes": "Race-day Lasix — approved HISA exemption"},
    {"horse_idx": 4, "days_ago": 7, "substance": "Omeprazole",            "dose": "4 mg/kg oral", "route": "oral", "withdrawal": 0,  "vet": "Dr. Sarah Chen",   "by": "Trainer",          "prohibited": False, "notes": "Gastric ulcer prevention, routine"},
    {"horse_idx": 6, "days_ago": 2, "substance": "Triamcinolone",         "dose": "12 mg IA",     "route": "IA",   "withdrawal": 0,  "vet": "Dr. Marcus Webb",  "by": "Dr. Marcus Webb",  "prohibited": False, "notes": "Right hock joint injection — cleared by vet"},
    {"horse_idx": 9, "days_ago": 4, "substance": "Dexamethasone",         "dose": "20 mg IV",     "route": "IV",   "withdrawal": 48, "vet": "Dr. Priya Nair",   "by": "Dr. Priya Nair",   "prohibited": False, "notes": "Inflammatory response post-workout"},
]

DEMO_VET_CHECKS = [
    # Routine morning checks — most cleared, one flagged
    {"horse_idx": 0,  "days_ago": 0, "check_type": "routine",      "outcome": "cleared",    "vet": "Dr. Sarah Chen",  "notes": "Good movement, sound on all four"},
    {"horse_idx": 1,  "days_ago": 0, "check_type": "routine",      "outcome": "cleared",    "vet": "Dr. Sarah Chen",  "notes": "Bright and alert, normal vitals"},
    {"horse_idx": 2,  "days_ago": 0, "check_type": "pre_shipment", "outcome": "cleared",    "vet": "Dr. Marcus Webb", "notes": "Cleared for transport to Churchill Downs"},
    {"horse_idx": 3,  "days_ago": 0, "check_type": "lameness",     "outcome": "restricted", "vet": "Dr. Marcus Webb", "notes": "Grade 1 left fore lameness detected. Scratched from Race 3 pending reassessment. Re-check scheduled tomorrow morning."},
    {"horse_idx": 4,  "days_ago": 0, "check_type": "routine",      "outcome": "cleared",    "vet": "Dr. Priya Nair",  "notes": "Sound, strong workout Monday. Ready to run."},
    {"horse_idx": 5,  "days_ago": 0, "check_type": "routine",      "outcome": "cleared",    "vet": "Dr. Priya Nair",  "notes": "Normal. No concerns."},
    {"horse_idx": 6,  "days_ago": 1, "check_type": "routine",      "outcome": "cleared",    "vet": "Dr. Sarah Chen",  "notes": "Post-injection check — normal response, moving well"},
    {"horse_idx": 7,  "days_ago": 0, "check_type": "routine",      "outcome": "cleared",    "vet": "Dr. Marcus Webb", "notes": "Fit to run"},
    {"horse_idx": 10, "days_ago": 0, "check_type": "routine",      "outcome": "cleared",    "vet": "Dr. Priya Nair",  "notes": "Ready"},
    {"horse_idx": 11, "days_ago": 0, "check_type": "routine",      "outcome": "cleared",    "vet": "Dr. Sarah Chen",  "notes": "Sound, no issues"},
]


def seed_treatments(session, today: date) -> int:
    """Seed ADMC treatment records for the Phase 3–5 demo."""
    total = 0
    for t in DEMO_TREATMENTS:
        h = HORSES[t["horse_idx"]]
        treatment_date = (today - timedelta(days=t["days_ago"])).isoformat()
        session.add(TreatmentRecord(
            horse_chip_id=h["chip_id"],
            treatment_date=treatment_date,
            substance=t["substance"],
            dose=t["dose"],
            route=t["route"],
            withdrawal_time_hours=t["withdrawal"],
            prescribed_by=t["vet"],
            administered_by=t["by"],
            is_prohibited=t["prohibited"],
            notes=t["notes"],
        ))
        total += 1
    session.commit()
    return total


def seed_vet_checks(session, today: date) -> int:
    """Seed structured vet check records for the Training Center demo."""
    total = 0
    for v in DEMO_VET_CHECKS:
        h = HORSES[v["horse_idx"]]
        check_date = (today - timedelta(days=v["days_ago"])).isoformat()
        session.add(VetCheckRecord(
            horse_chip_id=h["chip_id"],
            check_date=check_date,
            check_type=v["check_type"],
            outcome=v["outcome"],
            vet_name=v["vet"],
            notes=v["notes"],
        ))
        total += 1
    session.commit()
    return total


def seed_demo_race_day(session, today: date) -> dict:
    """
    Seed today's Churchill Downs race card — the flagship demo narrative.

    Race 1 (FINISHED): The Bluegrass Stakes — 8 runners, results in.
    Race 2 (ACTIVE):   The Churchill Sprint — 6 runners, currently running.
    Race 3 (PENDING):  The Louisville Turf — 6 entered, 1 scratch (vet).
    Race 4 (PENDING):  The Kentucky Classic — 7 runners, post time 5pm.

    Demonstrates: entries with jockeys, scratch with HISA doc, results
    ingestion, race lifecycle, pre-race check-ins.
    """
    now = datetime.combine(today, time(12, 0))

    # Race 1 — FINISHED (ran at noon)
    r1 = Race(venue_id="CHURCHILL", name="The Bluegrass Stakes",
              race_date=datetime.combine(today, time(12, 0)),
              distance_m=1800.0, surface="Dirt", conditions="Grade II Stakes — 4yo+", status="finished")
    session.add(r1)
    session.flush()

    r1_field = [
        ("985112000000001", "Secretariat",       "1", "R. Bejarano"),
        ("985112000000005", "American Pharoah",  "2", "I. Ortiz Jr."),
        ("985112000000011", "Arrogate",          "3", "J. Castellano"),
        ("985112000000013", "Curlin",            "4", "L. Saez"),
        ("985112000000015", "California Chrome", "5", "F. Prat"),
        ("985112000000016", "Gun Runner",        "6", "J. Velazquez"),
        ("985112000000024", "Accelerate",        "7", "M. Smith"),
        ("985112000000025", "McKinzie",          "8", "T. Gaffalione"),
    ]
    # Finish order: Secretariat wins, tight margin
    finish_times = [98400, 98900, 99200, 99800, 100100, 100500, 101000, 102200]
    for i, (chip, name, cloth, jockey) in enumerate(r1_field):
        session.add(RaceEntry(race_id=r1.id, horse_chip_id=chip, saddle_cloth=cloth, jockey=jockey))
        session.add(RaceResult(race_id=r1.id, horse_chip_id=chip,
                               finish_position=i+1, elapsed_ms=finish_times[i]))
    session.commit()

    # Race 2 — ACTIVE (currently running, 2pm post)
    r2 = Race(venue_id="CHURCHILL", name="The Churchill Sprint",
              race_date=datetime.combine(today, time(14, 0)),
              distance_m=1200.0, surface="Dirt", conditions="Allowance — 3yo", status="active")
    session.add(r2)
    session.flush()

    r2_field = [
        ("985112000000006", "Justify",        "1", "J. Castellano"),
        ("985112000000007", "Zenyatta",        "2", "M. Smith"),
        ("985112000000012", "Flightline",      "3", "F. Prat"),
        ("985112000000014", "Rachel Alexandra","4", "I. Ortiz Jr."),
        ("985112000000017", "Beholder",        "5", "J. Velazquez"),
        ("985112000000018", "Songbird",        "6", "L. Saez"),
    ]
    for chip, name, cloth, jockey in r2_field:
        session.add(RaceEntry(race_id=r2.id, horse_chip_id=chip, saddle_cloth=cloth, jockey=jockey))
    session.commit()

    # Race 3 — PENDING with a late scratch (Black Caviar — vet flagged)
    r3 = Race(venue_id="CHURCHILL", name="The Louisville Turf",
              race_date=datetime.combine(today, time(15, 30)),
              distance_m=1600.0, surface="Turf", conditions="Stakes — 4yo+ turf", status="pending")
    session.add(r3)
    session.flush()

    r3_field_original = [
        ("985112000000002", "Winx",             "1", "H. Bowman"),
        ("985112000000003", "Frankel",          "2", "T. Queally"),
        ("985112000000004", "Black Caviar",     "3", "L. Nolen"),   # will be scratched
        ("985112000000008", "Enable",           "4", "F. Dettori"),
        ("985112000000009", "Sea The Stars",    "5", "M. Kinane"),
        ("985112000000019", "Golden Sixty",     "6", "Z. Purton"),
    ]
    # Add all entries first
    for chip, name, cloth, jockey in r3_field_original:
        session.add(RaceEntry(race_id=r3.id, horse_chip_id=chip, saddle_cloth=cloth, jockey=jockey))
    session.flush()

    # Scratch Black Caviar — vet-flagged (lameness this morning)
    scratched_chip = "985112000000004"
    entry_to_scratch = session.query(RaceEntry).filter_by(
        race_id=r3.id, horse_chip_id=scratched_chip).first()
    if entry_to_scratch:
        session.delete(entry_to_scratch)
    scratch = ScratchRecord(
        race_id=r3.id,
        horse_chip_id=scratched_chip,
        scratch_type="veterinary",
        declared_by="Dr. Marcus Webb",
        reason="Grade 1 left fore lameness detected at morning inspection. Horse does not meet fitness criteria.",
        declared_at=datetime.combine(today, time(8, 45)),
    )
    session.add(scratch)
    session.commit()

    # Auto HISA scratch submission
    payload = hisa_builder.build_scratch_submission(scratch,
        horse=session.get(Horse, scratched_chip),
        race=r3)
    session.add(HISASubmission(
        rule_category="SCRATCH",
        status="pending",
        source_record_type="ScratchRecord",
        source_record_id=scratch.id,
        horse_chip_id=scratched_chip,
        payload_json=json.dumps(payload),
    ))
    session.commit()

    # Race 4 — PENDING (5pm post)
    r4 = Race(venue_id="CHURCHILL", name="The Kentucky Classic",
              race_date=datetime.combine(today, time(17, 0)),
              distance_m=2012.0, surface="Dirt", conditions="Grade I — 4yo+ route",
              status="pending")
    session.add(r4)
    session.flush()

    r4_field = [
        ("985112000000010", "Deep Impact",       "1", "C. Soumillon"),
        ("985112000000020", "Equinox",           "2", "Y. Kawada"),
        ("985112000000021", "Galileo",           "3", "M. Kinane"),
        ("985112000000022", "Orb",               "4", "J. Rosario"),
        ("985112000000026", "Vino Rosso",        "5", "J. Castellano"),
        ("985112000000027", "Essential Quality", "6", "L. Saez"),
        ("985112000000028", "Tapit Trice",       "7", "J. Velazquez"),
    ]
    for chip, name, cloth, jockey in r4_field:
        session.add(RaceEntry(race_id=r4.id, horse_chip_id=chip, saddle_cloth=cloth, jockey=jockey))
    session.commit()

    return {"race_ids": [r1.id, r2.id, r3.id, r4.id],
            "race_names": ["Bluegrass Stakes", "Churchill Sprint", "Louisville Turf", "Kentucky Classic"]}


def seed_surface_conditions(session, today: date) -> int:
    """Daily track condition logs for Churchill Downs — required for HISA Rule 2151/2154."""
    total = 0
    conditions = [
        (0, "Fast",   12.5, 22.0, "Harrowed twice this morning. No loose material. Good drainage."),
        (1, "Fast",   11.8, 21.5, "Excellent condition. Light maintenance only."),
        (2, "Good",   15.2, 19.0, "Slight overnight dew. Surface settled by 9am."),
        (3, "Good",   14.7, 20.0, "Normal conditions. Turf course firm-good."),
        (4, "Firm",   10.1, 24.0, "Dry stretch. Watered turf course 6am."),
    ]
    for days_ago, going, moisture, temp, notes in conditions:
        log_date = (today - timedelta(days=days_ago)).isoformat()
        # Skip if already exists
        existing = session.query(SurfaceConditionLog).filter_by(
            venue_id="CHURCHILL", logged_date=log_date).first()
        if existing:
            continue
        session.add(SurfaceConditionLog(
            venue_id="CHURCHILL",
            logged_date=log_date,
            surface_type="Dirt",
            going_description=going,
            moisture_pct=moisture,
            temperature_c=temp,
            maintenance_notes=notes,
            logged_by="Track Superintendent J. Morrison",
        ))
        total += 1
    session.commit()
    return total


def seed_stewards_ruling(session, today: date) -> int:
    """A stewards' ruling whose 48h filing deadline has just passed — drives the
    one 'overdue submission' alert on the Compliance dashboard."""
    from datetime import timezone
    ruling_date = datetime.combine(today - timedelta(days=3), time(16, 30)).replace(tzinfo=timezone.utc)
    deadline = ruling_date + timedelta(hours=48)
    ruling = StewardsRuling(
        ruling_date=ruling_date,
        rule_violated="Rule 2230.5 — Careless riding",
        description="Jockey F. Prat aboard Gun Runner caused interference with Accelerate "
                    "(M. Smith) approaching the final turn, resulting in Accelerate being "
                    "checked and losing approximately 2 lengths. Incident reviewed via "
                    "video replay. Objection lodged by rider of Accelerate.",
        penalty="Jockey F. Prat suspended 3 riding days (Days 3–5 of next meeting). "
                "No change in finishing order.",
        jockey_name="F. Prat",
        horse_chip_id="985112000000016",  # Gun Runner
        status="draft",
        deadline_at=deadline,
    )
    session.add(ruling)
    session.flush()
    horse = session.get(Horse, "985112000000016")
    from app.models import Race as RaceModel
    payload = hisa_builder.build_stewards_submission(ruling, horse=horse)
    session.add(HISASubmission(
        rule_category="STEWARDS_RULING",
        status="pending",
        source_record_type="StewardsRuling",
        source_record_id=ruling.id,
        horse_chip_id="985112000000016",
        deadline_at=deadline,
        payload_json=json.dumps(payload),
    ))
    session.commit()
    return 1


def seed_hisa_submissions(session, today: date) -> int:
    """Pre-build HISA submissions from recent workouts, check-ins, and treatments."""
    created = 0

    # Workouts from the past 7 days
    recent_workouts = session.query(WorkoutRecord).filter(
        WorkoutRecord.workout_date >= (today - timedelta(days=7)).isoformat()
    ).limit(30).all()
    for w in recent_workouts:
        if session.query(HISASubmission).filter_by(
                source_record_type="WorkoutRecord", source_record_id=w.id).first():
            continue
        horse = session.get(Horse, w.horse_chip_id)
        payload = hisa_builder.build_workout_submission(w, horse=horse)
        session.add(HISASubmission(
            rule_category="WORKOUTS", status="pending",
            source_record_type="WorkoutRecord", source_record_id=w.id,
            horse_chip_id=w.horse_chip_id, payload_json=json.dumps(payload),
        ))
        created += 1

    # Today's check-ins (pre-race identity verification)
    todays_checkins = session.query(CheckInRecord).filter(
        CheckInRecord.race_id.isnot(None)
    ).order_by(CheckInRecord.scanned_at.desc()).limit(20).all()
    for c in todays_checkins:
        if session.query(HISASubmission).filter_by(
                source_record_type="CheckInRecord", source_record_id=c.id).first():
            continue
        horse = session.get(Horse, c.horse_chip_id)
        payload = hisa_builder.build_checkin_submission(c, horse=horse)
        session.add(HISASubmission(
            rule_category="CHECKIN", status="pending",
            source_record_type="CheckInRecord", source_record_id=c.id,
            horse_chip_id=c.horse_chip_id, payload_json=json.dumps(payload),
        ))
        created += 1

    # All treatment records
    for t in session.query(TreatmentRecord).all():
        if session.query(HISASubmission).filter_by(
                source_record_type="TreatmentRecord", source_record_id=t.id).first():
            continue
        horse = session.get(Horse, t.horse_chip_id)
        payload = hisa_builder.build_treatment_submission(t, horse=horse)
        session.add(HISASubmission(
            rule_category="ADMC_TREATMENT", status="pending",
            source_record_type="TreatmentRecord", source_record_id=t.id,
            horse_chip_id=t.horse_chip_id, payload_json=json.dumps(payload),
        ))
        created += 1

    # Surface condition logs
    for sl in session.query(SurfaceConditionLog).all():
        if session.query(HISASubmission).filter_by(
                source_record_type="SurfaceConditionLog", source_record_id=sl.id).first():
            continue
        payload = hisa_builder.build_surface_submission(sl)
        session.add(HISASubmission(
            rule_category="SURFACE", status="pending",
            source_record_type="SurfaceConditionLog", source_record_id=sl.id,
            payload_json=json.dumps(payload),
        ))
        created += 1

    # ── Realistic status mix ─────────────────────────────────────────────
    # A real compliance desk has most reports already filed and accepted; only
    # the latest race's check-ins and brand-new items are still pending. Assign
    # statuses by recency / race order so the queue reads like a live operation
    # rather than a giant backlog (target: ~10 pending, ~15 submitted, rest
    # accepted, with the one overdue stewards' ruling left pending for the alert).
    from datetime import timezone

    def _filed(days_ago):
        return datetime.now(timezone.utc) - timedelta(days=days_ago)

    # Workouts: most recent day still in flight (submitted), older ones accepted
    wsubs = session.query(HISASubmission, WorkoutRecord).join(
        WorkoutRecord, HISASubmission.source_record_id == WorkoutRecord.id
    ).filter(HISASubmission.rule_category == "WORKOUTS").all()
    if wsubs:
        latest_wd = max(w.workout_date for _, w in wsubs)
        for sub, w in wsubs:
            if w.workout_date == latest_wd:
                sub.status, sub.submitted_at = "submitted", _filed(1)
            else:
                sub.status, sub.submitted_at = "accepted", _filed(random.randint(2, 6))

    # Check-ins: earlier races already filed/accepted, latest race(s) pending
    csubs = session.query(HISASubmission, CheckInRecord).join(
        CheckInRecord, HISASubmission.source_record_id == CheckInRecord.id
    ).filter(HISASubmission.rule_category == "CHECKIN").all()
    if csubs:
        race_ids = {c.race_id for _, c in csubs if c.race_id}
        ordered = [r.id for r in session.query(Race)
                   .filter(Race.id.in_(race_ids)).order_by(Race.race_date).all()]
        cut = max(1, int(len(ordered) * 0.6))
        accepted_races = set(ordered[:cut])
        for sub, c in csubs:
            if c.race_id in accepted_races:
                sub.status, sub.submitted_at = "accepted", _filed(0)
            else:
                sub.status, sub.submitted_at = "pending", None

    # Treatments: newest pending, next filed, rest accepted
    tsubs = session.query(HISASubmission, TreatmentRecord).join(
        TreatmentRecord, HISASubmission.source_record_id == TreatmentRecord.id
    ).filter(HISASubmission.rule_category == "ADMC_TREATMENT") \
     .order_by(TreatmentRecord.treatment_date.desc()).all()
    for i, (sub, _t) in enumerate(tsubs):
        if i == 0:
            sub.status, sub.submitted_at = "pending", None
        elif i == 1:
            sub.status, sub.submitted_at = "submitted", _filed(1)
        else:
            sub.status, sub.submitted_at = "accepted", _filed(random.randint(2, 5))

    # Surface logs: today's pending, the rest accepted
    ssubs = session.query(HISASubmission, SurfaceConditionLog).join(
        SurfaceConditionLog, HISASubmission.source_record_id == SurfaceConditionLog.id
    ).filter(HISASubmission.rule_category == "SURFACE") \
     .order_by(SurfaceConditionLog.logged_date.desc()).all()
    for i, (sub, _sl) in enumerate(ssubs):
        if i == 0:
            sub.status, sub.submitted_at = "pending", None
        else:
            sub.status, sub.submitted_at = "accepted", _filed(random.randint(1, 4))

    # Scratch already filed; stewards' ruling intentionally left pending (overdue)
    for sub in session.query(HISASubmission).filter_by(rule_category="SCRATCH").all():
        sub.status, sub.submitted_at = "submitted", _filed(1)

    session.commit()
    return created


def seed_demo_checkins(session, today: date, race_ids: list) -> int:
    """Pre-race check-ins for today's race card horses."""
    total = 0
    todays_horses = [
        "985112000000001", "985112000000005", "985112000000011", "985112000000013",
        "985112000000015", "985112000000016", "985112000000024", "985112000000025",
        "985112000000006", "985112000000007", "985112000000012", "985112000000014",
        "985112000000017", "985112000000018",
        "985112000000002", "985112000000003", "985112000000008", "985112000000009", "985112000000019",
    ]
    officials = ["Head Steward Williams", "Assistant Steward Davis", "Gate Official Rodriguez"]
    for i, chip in enumerate(todays_horses):
        race_id = race_ids[min(i // 6, len(race_ids) - 1)]
        session.add(CheckInRecord(
            horse_chip_id=chip,
            race_id=race_id,
            scanned_at=datetime.combine(today, time(7 + i // 6, 15 + (i % 10) * 3)),
            scanned_by=officials[i % len(officials)],
            location="Paddock Gate B",
            verified=True,
            temperature_c=round(37.8 + random.uniform(-0.3, 0.5), 1),
        ))
        total += 1
    session.commit()
    return total


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def run(force: bool = False) -> None:
    engine  = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check that ALL real venues are present — not just any venue.
        # Test fixtures create venues like TESTTRACK/V1/MAP_TRACK that would
        # fool a simple non-zero count, so we require every expected venue_id.
        from app.models import VenueRecord
        real_venue_ids = {v["venue_id"] for v in VENUES}
        present_ids = {
            row.venue_id
            for row in session.query(VenueRecord)
                               .filter(VenueRecord.venue_id.in_(real_venue_ids))
                               .all()
        }
        fully_seeded = (present_ids == real_venue_ids)

        if fully_seeded and not force:
            print(f"Real seed data already present (all {len(real_venue_ids)} venues found).")
            print("Run with --force to wipe and re-seed.")
            return

        if fully_seeded and force:
            print("[seed] Clearing existing data...")
            clear_tables(session)
        else:
            missing = real_venue_ids - present_ids
            print(f"[seed] Missing {len(missing)} real venue(s) — clearing stale/test data before seeding...")
            clear_tables(session)

        today = datetime.now().date()

        print(f"[seed] Creating {len(VENUES)} venues...")
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

        print("[seed] Seeding treatment records (ADMC)...")
        n_treatments = seed_treatments(session, today)

        print("[seed] Seeding vet check records (Training Center)...")
        n_vet_checks = seed_vet_checks(session, today)

        print("[seed] Seeding today's Churchill Downs race card...")
        demo_day = seed_demo_race_day(session, today)

        print("[seed] Seeding today's race check-ins...")
        n_demo_checkins = seed_demo_checkins(session, today, demo_day["race_ids"])

        print("[seed] Seeding surface condition logs (HISA Rule 2151/2154)...")
        n_surface = seed_surface_conditions(session, today)

        print("[seed] Seeding stewards' ruling (48h deadline)...")
        seed_stewards_ruling(session, today)

        print("[seed] Pre-building HISA submissions...")
        n_hisa = seed_hisa_submissions(session, today)

        print("[seed] Done.\n")

        # ── Summary ──────────────────────────────────────────────────
        n_races   = len(race_records) + 4  # +4 today's demo card
        n_entries = sum(len(r["field"]) for r in race_records)

        print("========== SEED SUMMARY ==========")
        print(f"Venues:            {len(VENUES)}")
        print(f"Horses:            {len(HORSES)}")
        print(f"Races:             {n_races} (incl. today's card)")
        print(f"Race entries:      {n_entries}")
        print(f"Race results:      {n_entries}")
        print(f"Vet records:       {n_vet + len(HORSES)}")   # +implant per horse
        print(f"Workout records:   {n_workouts}")
        print(f"Vet checks:        {n_vet_checks}")
        print(f"Treatment records: {n_treatments}")
        print(f"Check-in records:  {n_checkins + n_demo_checkins}")
        print(f"Test barn records: {n_test_barn}")
        print(f"Surface logs:      {n_surface} (Churchill, 5 days)")
        print(f"HISA submissions:  {n_hisa} (pre-built)")
        print(f"")
        print(f"TODAY'S RACE CARD — Churchill Downs:")
        for name in demo_day["race_names"]:
            print(f"  · {name}")
        print("===================================\n")

        print("First 5 horse chip IDs for testing Horse Profile:")
        for i, h in enumerate(HORSES[:5]):
            trainer_name = TRAINERS[i % len(TRAINERS)]
            owner_name   = OWNERS[i % len(OWNERS)]
            print(f"  {i + 1}. {h['chip_id']} — {h['name']} ({trainer_name} / {owner_name})")

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