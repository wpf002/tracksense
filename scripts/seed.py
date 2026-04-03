"""
scripts/seed.py

Seed the TrackSense database with realistic demo data.

Defaults to SQLite (tracksense.db) when DATABASE_URL is not set.
Override: DATABASE_URL=postgresql://... python -m scripts.seed

Run from project root:
    python -m scripts.seed
    python -m scripts.seed --force    # wipe and re-seed
"""

import os
import sys
import random
import argparse
from datetime import datetime, timedelta

# Must set before importing app modules so database.py picks it up
os.environ.setdefault("DATABASE_URL", "sqlite:///./tracksense.db")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
import app.models  # noqa: F401 — registers all ORM classes
from app.models import (
    Horse, Owner, Trainer, VetRecord,
    VenueRecord, GateRecord,
    Race, RaceEntry, GateRead, RaceResult,
    WorkoutRecord, CheckInRecord, TestBarnRecord,
)

DATABASE_URL = os.environ["DATABASE_URL"]

# ------------------------------------------------------------------ #
# Seed data definitions
# ------------------------------------------------------------------ #

TRAINERS = [
    "James Cummings",
    "Chris Waller",
    "Peter Moody",
    "Gai Waterhouse",
    "Ciaron Maher",
]

OWNERS = [
    "Godolphin",
    "Coolmore Australia",
    "Hawkes Racing",
    "Bjorn Baker Racing",
    "Anthony Freedman",
    "Lindsay Park",
    "Ciaron Maher Racing",
    "Gai Waterhouse Racing",
    "Winx Syndicate",
    "Phoenix Thoroughbreds",
]

HORSES = [
    # epc, name, breed, dob, surface_pref, base_speed (0.9=fast,1.1=slow), profile, trainer_idx, owner_idx
    {"epc": "E200681100000001AABB0001", "name": "Thunderstrike",  "breed": "Thoroughbred", "dob": "2020-09-14", "surface": "Turf",      "speed": 0.92, "profile": "pacer",    "trainer": 0, "owner": 0},
    {"epc": "E200681100000001AABB0002", "name": "Iron Duchess",   "breed": "Thoroughbred", "dob": "2019-11-02", "surface": "Turf",      "speed": 0.94, "profile": "closer",   "trainer": 1, "owner": 1},
    {"epc": "E200681100000001AABB0003", "name": "Crimson Tempo",  "breed": "Thoroughbred", "dob": "2020-08-22", "surface": "Dirt",      "speed": 0.96, "profile": "pacer",    "trainer": 0, "owner": 2},
    {"epc": "E200681100000001AABB0004", "name": "Silent Verdict", "breed": "Thoroughbred", "dob": "2019-10-07", "surface": "Turf",      "speed": 0.98, "profile": "midfield", "trainer": 2, "owner": 3},
    {"epc": "E200681100000001AABB0005", "name": "Pale Monarch",   "breed": "Thoroughbred", "dob": "2021-01-15", "surface": "Turf",      "speed": 0.95, "profile": "closer",   "trainer": 1, "owner": 4},
    {"epc": "E200681100000001AABB0006", "name": "Westward Bound", "breed": "Thoroughbred", "dob": "2020-12-03", "surface": "Synthetic", "speed": 1.00, "profile": "midfield", "trainer": 3, "owner": 5},
    {"epc": "E200681100000001AABB0007", "name": "Night Protocol", "breed": "Thoroughbred", "dob": "2019-07-19", "surface": "Turf",      "speed": 0.93, "profile": "pacer",    "trainer": 2, "owner": 6},
    {"epc": "E200681100000001AABB0008", "name": "Ember Ridge",    "breed": "Thoroughbred", "dob": "2021-03-08", "surface": "Turf",      "speed": 1.01, "profile": "midfield", "trainer": 4, "owner": 7},
    {"epc": "E200681100000001AABB0009", "name": "Gold Inference", "breed": "Thoroughbred", "dob": "2020-06-25", "surface": "Turf",      "speed": 0.97, "profile": "closer",   "trainer": 3, "owner": 8},
    {"epc": "E200681100000001AABB000A", "name": "Saltwind Glory", "breed": "Thoroughbred", "dob": "2019-09-11", "surface": "Turf",      "speed": 1.02, "profile": "midfield", "trainer": 1, "owner": 9},
    {"epc": "E200681100000001AABB000B", "name": "Carrion Comfort","breed": "Thoroughbred", "dob": "2020-11-30", "surface": "Dirt",      "speed": 0.99, "profile": "pacer",    "trainer": 0, "owner": 0},
    {"epc": "E200681100000001AABB000C", "name": "River Oath",     "breed": "Thoroughbred", "dob": "2021-02-14", "surface": "Turf",      "speed": 0.96, "profile": "closer",   "trainer": 4, "owner": 1},
    {"epc": "E200681100000001AABB000D", "name": "Desert Patience","breed": "Thoroughbred", "dob": "2019-08-05", "surface": "Dirt",      "speed": 1.03, "profile": "midfield", "trainer": 2, "owner": 2},
    {"epc": "E200681100000001AABB000E", "name": "The Long Shadow","breed": "Thoroughbred", "dob": "2020-04-17", "surface": "Turf",      "speed": 0.94, "profile": "closer",   "trainer": 3, "owner": 3},
    {"epc": "E200681100000001AABB000F", "name": "Forged in Dust", "breed": "Thoroughbred", "dob": "2021-06-09", "surface": "Turf",      "speed": 0.98, "profile": "pacer",    "trainer": 1, "owner": 4},
    {"epc": "E200681100000001AABB0010", "name": "Lady Contention","breed": "Thoroughbred", "dob": "2020-01-28", "surface": "Turf",      "speed": 1.01, "profile": "midfield", "trainer": 4, "owner": 5},
    {"epc": "E200681100000001AABB0011", "name": "Copper Writ",    "breed": "Thoroughbred", "dob": "2019-12-10", "surface": "Synthetic", "speed": 0.97, "profile": "closer",   "trainer": 0, "owner": 6},
    {"epc": "E200681100000001AABB0012", "name": "Northern Clause","breed": "Thoroughbred", "dob": "2021-05-03", "surface": "Turf",      "speed": 1.00, "profile": "midfield", "trainer": 2, "owner": 7},
    {"epc": "E200681100000001AABB0013", "name": "Mirefall",       "breed": "Thoroughbred", "dob": "2020-07-21", "surface": "Turf",      "speed": 0.95, "profile": "pacer",    "trainer": 3, "owner": 8},
    {"epc": "E200681100000001AABB0014", "name": "Last Argument",  "breed": "Thoroughbred", "dob": "2019-10-14", "surface": "Turf",      "speed": 0.99, "profile": "closer",   "trainer": 4, "owner": 9},
]

VENUES = [
    {
        "venue_id": "FLEMINGTON",
        "name": "Flemington Racecourse",
        "distance": 1609.0,
        "gates": [
            ("GATE-START",  "Start",     0.0,    False),
            ("GATE-F2",     "Furlong 2", 402.0,  False),
            ("GATE-F4",     "Furlong 4", 804.0,  False),
            ("GATE-F6",     "Furlong 6", 1207.0, False),
            ("GATE-FINISH", "Finish",    1609.0, True),
        ],
        "segments_ms": [5000, 19500, 19500, 20000],
    },
    {
        "venue_id": "CAULFIELD",
        "name": "Caulfield Racecourse",
        "distance": 1200.0,
        "gates": [
            ("GATE-START",  "Start",     0.0,    False),
            ("GATE-F2",     "Furlong 2", 400.0,  False),
            ("GATE-F4",     "Furlong 4", 800.0,  False),
            ("GATE-FINISH", "Finish",    1200.0, True),
        ],
        "segments_ms": [5000, 19000, 19000],
    },
    {
        "venue_id": "RANDWICK",
        "name": "Royal Randwick Racecourse",
        "distance": 1200.0,
        "gates": [
            ("GATE-START",  "Start",     0.0,    False),
            ("GATE-F2",     "Furlong 2", 400.0,  False),
            ("GATE-F4",     "Furlong 4", 800.0,  False),
            ("GATE-FINISH", "Finish",    1200.0, True),
        ],
        "segments_ms": [5000, 19000, 19000],
    },
    {
        "venue_id": "MOONEE_VALLEY",
        "name": "Moonee Valley Racecourse",
        "distance": 1600.0,
        "gates": [
            ("GATE-START",  "Start",     0.0,    False),
            ("GATE-F2",     "Furlong 2", 402.0,  False),
            ("GATE-F4",     "Furlong 4", 804.0,  False),
            ("GATE-F6",     "Furlong 6", 1207.0, False),
            ("GATE-FINISH", "Finish",    1600.0, True),
        ],
        "segments_ms": [5000, 19500, 19500, 19500],
    },
    {
        "venue_id": "ROSEHILL",
        "name": "Rosehill Gardens Racecourse",
        "distance": 1400.0,
        "gates": [
            ("GATE-START",  "Start",     0.0,    False),
            ("GATE-F2",     "Furlong 2", 402.0,  False),
            ("GATE-F4",     "Furlong 4", 804.0,  False),
            ("GATE-F6",     "Furlong 6", 1100.0, False),
            ("GATE-FINISH", "Finish",    1400.0, True),
        ],
        "segments_ms": [5000, 19500, 18000, 15000],
    },
    {
        "venue_id": "EAGLE_FARM",
        "name": "Eagle Farm Racecourse",
        "distance": 1400.0,
        "gates": [
            ("GATE-START",  "Start",     0.0,    False),
            ("GATE-F2",     "Furlong 2", 402.0,  False),
            ("GATE-F4",     "Furlong 4", 804.0,  False),
            ("GATE-F6",     "Furlong 6", 1100.0, False),
            ("GATE-FINISH", "Finish",    1400.0, True),
        ],
        "segments_ms": [5000, 19000, 18000, 15000],
    },
]

# (venue_idx, distance_m, race_date, field_indices)
RACE_SCHEDULE = [
    (0, 1609.0, "2026-01-10T14:30:00", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),      # FLEMINGTON
    (1, 1200.0, "2026-01-17T15:00:00", [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]),  # CAULFIELD
    (2, 1200.0, "2026-01-24T14:00:00", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]),      # RANDWICK
    (3, 1600.0, "2026-01-31T15:00:00", [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]),  # MOONEE_VALLEY
    (4, 1400.0, "2026-02-07T14:30:00", [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]),  # ROSEHILL
    (5, 1400.0, "2026-02-14T15:00:00", [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]),  # EAGLE_FARM
    (0, 1609.0, "2026-02-21T14:00:00", [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]),  # FLEMINGTON
    (1, 1200.0, "2026-02-28T15:00:00", [1, 3, 5, 7, 9, 11, 13, 15, 17, 19]),  # CAULFIELD
    (0, 1609.0, "2026-03-07T14:30:00", [0, 1, 2, 3, 4, 5, 9, 10, 14, 15]),   # FLEMINGTON
    (1, 1200.0, "2026-03-28T15:00:00", [6, 7, 8, 11, 12, 13, 16, 17, 18, 19]), # CAULFIELD
]

SPEED_PROFILES = {
    "pacer":    [0.92, 0.96, 1.02, 1.08, 1.12],
    "closer":   [1.10, 1.05, 1.00, 0.95, 0.88],
    "midfield": [1.00, 1.00, 1.00, 1.00, 1.00],
}

WORKOUT_NOTES = [
    "Strong gallop, pulled up well",
    "Easy canter, feel good",
    "Barrier trial — jumped cleanly",
    "Quiet morning, just stretching the legs",
    "Worked in company — held pace well",
    "Solid hit-out, trainer pleased",
    "Sweated up slightly, otherwise good",
    "Good tempo throughout",
    "Rider reports horse travelling well",
    "Light work ahead of race prep",
]

CHECKIN_OFFICIALS = ["Head Steward", "Assistant Steward", "Gate Official"]
CHECKIN_LOCATIONS = ["Paddock Check-In", "Mounting Yard", "Pre-Parade Ring"]


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def simulate_gate_times(horse: dict, segments_ms: list[int]) -> list[int]:
    """Return cumulative elapsed_ms for each gate (index 0 = start = 0)."""
    profile = horse["profile"]
    base_speed = horse["speed"]
    multipliers = SPEED_PROFILES[profile]
    times = [0]
    cumulative = 0
    for i, base_ms in enumerate(segments_ms):
        seg = int(base_ms * multipliers[i] * base_speed * random.uniform(0.97, 1.03))
        cumulative += seg
        times.append(cumulative)
    return times


def clear_tables(session):
    """Delete all seeded data in safe reverse-FK order."""
    for table in [
        "test_barn_records", "checkin_records", "workout_records",
        "race_results", "gate_reads", "race_entries", "races",
        "gate_records", "venue_records",
        "vet_records", "trainers", "owners", "horses",
    ]:
        session.execute(text(f"DELETE FROM {table}"))
    session.commit()
    print("  Cleared existing data.")


# ------------------------------------------------------------------ #
# Seed functions
# ------------------------------------------------------------------ #

def seed_horses(session) -> dict:
    """Returns {epc: Horse} mapping."""
    horse_map = {}
    for h in HORSES:
        horse = Horse(
            epc=h["epc"],
            name=h["name"],
            breed=h["breed"],
            date_of_birth=h["dob"],
            implant_date="2023-01-15",
            implant_vet="Dr. Harriet Clarke",
        )
        session.add(horse)
        trainer_name = TRAINERS[h["trainer"]]
        owner_name = OWNERS[h["owner"]]
        session.add(Owner(horse_epc=h["epc"], owner_name=owner_name, from_date="2023-01-15"))
        session.add(Trainer(horse_epc=h["epc"], trainer_name=trainer_name, from_date="2023-01-15"))
        session.add(VetRecord(
            horse_epc=h["epc"],
            event_date="2023-01-15",
            event_type="implant",
            notes="UHF Gen2 glass capsule, lower lip",
            vet_name="Dr. Harriet Clarke",
        ))
        horse_map[h["epc"]] = horse
    session.commit()
    return horse_map


def seed_venues(session) -> dict:
    """Returns {venue_id: venue_data} mapping (includes gate info)."""
    venue_map = {}
    for v in VENUES:
        venue = VenueRecord(
            venue_id=v["venue_id"],
            name=v["name"],
            total_distance_m=v["distance"],
        )
        session.add(venue)
        for reader_id, name, dist, is_finish in v["gates"]:
            session.add(GateRecord(
                venue_id=v["venue_id"],
                reader_id=reader_id,
                name=name,
                distance_m=dist,
                is_finish=is_finish,
            ))
        venue_map[v["venue_id"]] = v
    session.commit()
    return venue_map


def seed_races(session, venue_map) -> list[dict]:
    """
    Seed races, entries, gate reads, and results.
    Returns list of dicts with race metadata for use by welfare seeding.
    """
    race_records = []

    for venue_idx, distance_m, race_date_str, field_indices in RACE_SCHEDULE:
        venue_data = VENUES[venue_idx]
        venue_id = venue_data["venue_id"]
        race_date = datetime.fromisoformat(race_date_str)

        race = Race(
            venue_id=venue_id,
            race_date=race_date,
            distance_m=distance_m,
            surface="turf",
            status="finished",
        )
        session.add(race)
        session.flush()  # get race.id

        field = [HORSES[i] for i in field_indices]
        gates = venue_data["gates"]
        segments_ms = venue_data["segments_ms"]

        # Simulate gate times for each horse
        horse_times = []
        for i, h in enumerate(field):
            times = simulate_gate_times(h, segments_ms)
            saddle_cloth = str(i + 1)
            horse_times.append((h, times, saddle_cloth))

        # Sort by finish time → assign positions
        horse_times.sort(key=lambda x: x[1][-1])

        for position, (h, times, saddle_cloth) in enumerate(horse_times, start=1):
            epc = h["epc"]

            session.add(RaceEntry(
                race_id=race.id,
                horse_epc=epc,
                saddle_cloth=saddle_cloth,
            ))

            for gate_idx, (reader_id, gate_name, gate_dist, _) in enumerate(gates):
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

        session.commit()

        race_records.append({
            "race_id": race.id,
            "race_date": race_date,
            "venue_id": venue_id,
            "field": [h["epc"] for h in field],
            "results": [(h["epc"], pos + 1) for pos, (h, _, _) in enumerate(horse_times)],
            "finish_time": race_date + timedelta(seconds=horse_times[-1][1][-1] / 1000 + 2),
        })

    return race_records


def seed_workouts(session, race_records: list[dict]) -> int:
    """Generate 8–15 workout records per horse over the past 90 days."""
    today = datetime(2026, 4, 3)
    start_date = today - timedelta(days=90)

    # Collect all race dates as a set of date strings to avoid
    race_day_dates = {r["race_date"].date() for r in race_records}

    total = 0
    for h in HORSES:
        epc = h["epc"]
        trainer_name = TRAINERS[h["trainer"]]
        n_workouts = random.randint(8, 15)

        # Generate candidate dates (skip race days)
        candidates = []
        cursor = start_date
        while cursor < today:
            if cursor.date() not in race_day_dates:
                candidates.append(cursor.date())
            cursor += timedelta(days=1)

        selected_dates = sorted(random.sample(candidates, min(n_workouts, len(candidates))))

        for workout_date in selected_dates:
            distance_m = random.choice([600.0, 800.0, 1000.0, 1200.0])
            # ~40 seconds per 600m, scaled by distance and horse speed
            base_ms = int((distance_m / 600.0) * 40000 * h["speed"] * random.uniform(0.97, 1.03))
            track_cond = random.choice(["Fast", "Fast", "Good", "Soft"])

            # Occasionally reference a stablemate in notes
            note = random.choice(WORKOUT_NOTES)
            if "in company" in note:
                other = random.choice([x["name"] for x in HORSES if x["epc"] != epc])
                note = f"Worked with {other} — held pace well"

            session.add(WorkoutRecord(
                horse_epc=epc,
                workout_date=workout_date.isoformat(),
                distance_m=distance_m,
                surface=h["surface"],
                duration_ms=base_ms,
                track_condition=track_cond,
                trainer_name=trainer_name,
                notes=note,
            ))
            total += 1

    session.commit()
    return total


def seed_checkins(session, race_records: list[dict]) -> int:
    """Create one CheckInRecord per race entry."""
    total = 0
    for race_info in race_records:
        race_date = race_info["race_date"]
        race_id = race_info["race_id"]
        for epc in race_info["field"]:
            offset_mins = random.randint(45, 90)
            scanned_at = race_date - timedelta(minutes=offset_mins)
            verified = random.random() > 0.01  # 99% verified
            session.add(CheckInRecord(
                horse_epc=epc,
                race_id=race_id,
                scanned_at=scanned_at,
                scanned_by=random.choice(CHECKIN_OFFICIALS),
                location=random.choice(CHECKIN_LOCATIONS),
                verified=verified,
                notes=None if verified else "Identity query raised — resolved manually",
            ))
            total += 1

    session.commit()
    return total


def seed_test_barn(session, race_records: list[dict]) -> int:
    """Create TestBarnRecord for roughly top 3 finishers in each race."""
    total = 0
    for race_info in race_records:
        race_id = race_info["race_id"]
        finish_time = race_info["finish_time"]
        results_sorted = sorted(race_info["results"], key=lambda x: x[1])
        top_finishers = [epc for epc, pos in results_sorted[:3]]

        for epc in top_finishers:
            position = next(pos for e, pos in results_sorted if e == epc)
            checkin_offset = timedelta(minutes=random.randint(5, 15))
            checkin_at = finish_time + checkin_offset
            checkout_offset = timedelta(minutes=random.randint(45, 90))
            checkout_at = checkin_at + checkout_offset
            rand = random.random()
            result = "Clear" if rand < 0.97 else ("Pending" if rand < 0.99 else "Void")
            sample_id = f"TB-{race_id:04d}-{position:02d}-{random.randint(1000, 9999)}"

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


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #

def run(force: bool = False):
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if already seeded
    existing = session.query(Horse).count()
    if existing > 0 and not force:
        print(f"Database already contains {existing} horses.")
        print("Run with --force to wipe and re-seed.")
        session.close()
        return

    if existing > 0 and force:
        print("Wiping existing data...")
        clear_tables(session)

    print("Seeding TrackSense database...")
    print(f"  Database: {DATABASE_URL}\n")

    print(f"  Seeding {len(HORSES)} horses...")
    seed_horses(session)

    print(f"  Seeding {len(VENUES)} venues...")
    seed_venues(session)

    print(f"  Seeding {len(RACE_SCHEDULE)} races...")
    race_records = seed_races(session, {v["venue_id"]: v for v in VENUES})

    print("  Seeding workout records...")
    n_workouts = seed_workouts(session, race_records)

    print("  Seeding check-in records...")
    n_checkins = seed_checkins(session, race_records)

    print("  Seeding test barn records...")
    n_test_barn = seed_test_barn(session, race_records)

    session.close()

    total_entries = sum(len(r["field"]) for r in race_records)
    total_reads = sum(
        len(r["field"]) * len(VENUES[vi]["gates"])
        for vi, _, _, fi in RACE_SCHEDULE
        for r in [{"field": fi}]
    )

    print("\n========================================")
    print("  TrackSense seed complete")
    print("========================================")
    print(f"  Horses:            {len(HORSES)}")
    print(f"  Venues:            {len(VENUES)}")
    print(f"  Races:             {len(RACE_SCHEDULE)}")
    print(f"  Race entries:      {total_entries}")
    print(f"  Gate reads:        {total_reads}")
    print(f"  Race results:      {total_entries}")
    print(f"  Workout records:   {n_workouts}")
    print(f"  Check-in records:  {n_checkins}")
    print(f"  Test barn records: {n_test_barn}")
    print("========================================\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed TrackSense database")
    parser.add_argument("--force", action="store_true", help="Wipe and re-seed")
    args = parser.parse_args()
    run(force=args.force)