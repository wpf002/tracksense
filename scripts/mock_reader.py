"""
mock_reader.py

Simulates a real UHF RFID reader at a horse race finish line.

Realistic behaviors this mock reproduces:
1. Horses don't all finish at the same moment — timing follows a rough
   race spread (winner ~60s, backmarkers up to ~90s from gun).
2. The RFID reader sees each tag multiple times as the horse passes
   the antenna beam — we emit 2-5 duplicate reads per horse.
3. Occasionally an unknown tag fires (nearby paddock tag, maintenance
   tag on the rail) — the backend should ignore it gracefully.
4. A small random delay is added per read to simulate serial latency.

This script is designed to be replaceable 1:1 by hardware/reader.py
which will read from a real reader over USB/serial instead.
"""

import time
import random
import requests
import threading
from dataclasses import dataclass

BACKEND_URL = "http://localhost:8000"
SUBMIT_URL = f"{BACKEND_URL}/tags/submit"
REGISTER_URL = f"{BACKEND_URL}/race/register"
ARM_URL = f"{BACKEND_URL}/race/arm"
STATUS_URL = f"{BACKEND_URL}/race/status"

# ------------------------------------------------------------------ #
# Horse field — 20 runners
# Saddle cloths, display names, and tag IDs that would be on the
# microchip transponder or race-day tag attached to the horse/equipment.
# ------------------------------------------------------------------ #

HORSES = [
    {"horse_id": "TAG-001", "display_name": "Thunderstrike",       "saddle_cloth": "1"},
    {"horse_id": "TAG-002", "display_name": "Iron Duchess",        "saddle_cloth": "2"},
    {"horse_id": "TAG-003", "display_name": "Crimson Tempo",       "saddle_cloth": "3"},
    {"horse_id": "TAG-004", "display_name": "Silent Verdict",      "saddle_cloth": "4"},
    {"horse_id": "TAG-005", "display_name": "Pale Monarch",        "saddle_cloth": "5"},
    {"horse_id": "TAG-006", "display_name": "Westward Bound",      "saddle_cloth": "6"},
    {"horse_id": "TAG-007", "display_name": "Night Protocol",      "saddle_cloth": "7"},
    {"horse_id": "TAG-008", "display_name": "Ember Ridge",         "saddle_cloth": "8"},
    {"horse_id": "TAG-009", "display_name": "Gold Inference",      "saddle_cloth": "9"},
    {"horse_id": "TAG-010", "display_name": "Saltwind Glory",      "saddle_cloth": "10"},
    {"horse_id": "TAG-011", "display_name": "Carrion Comfort",     "saddle_cloth": "11"},
    {"horse_id": "TAG-012", "display_name": "River Oath",          "saddle_cloth": "12"},
    {"horse_id": "TAG-013", "display_name": "Desert Patience",     "saddle_cloth": "13"},
    {"horse_id": "TAG-014", "display_name": "The Long Shadow",     "saddle_cloth": "14"},
    {"horse_id": "TAG-015", "display_name": "Forged in Dust",      "saddle_cloth": "15"},
    {"horse_id": "TAG-016", "display_name": "Lady Contention",     "saddle_cloth": "16"},
    {"horse_id": "TAG-017", "display_name": "Copper Writ",         "saddle_cloth": "17"},
    {"horse_id": "TAG-018", "display_name": "Northern Clause",     "saddle_cloth": "18"},
    {"horse_id": "TAG-019", "display_name": "Mirefall",            "saddle_cloth": "19"},
    {"horse_id": "TAG-020", "display_name": "Last Argument",       "saddle_cloth": "20"},
]

# Stray/unknown tag IDs that simulate adjacent paddock reads
NOISE_TAGS = ["MAINT-001", "PADDOCK-07", "RAIL-INSPECT-3"]

# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def wait_for_backend(retries: int = 15, delay: float = 1.0):
    """Poll until backend is up."""
    for i in range(retries):
        try:
            r = requests.get(f"{BACKEND_URL}/health", timeout=2)
            if r.status_code == 200:
                print("[mock] Backend is up.")
                return True
        except Exception:
            pass
        print(f"[mock] Waiting for backend... ({i+1}/{retries})")
        time.sleep(delay)
    return False


def register_field():
    """Push the horse field to the backend."""
    r = requests.post(REGISTER_URL, json={"horses": HORSES}, timeout=5)
    r.raise_for_status()
    data = r.json()
    print(f"[mock] Registered {data['registered']} horses.")


def arm():
    r = requests.post(ARM_URL, timeout=5)
    r.raise_for_status()
    print("[mock] Race armed. Waiting for first tag...")


def emit_tag(tag_id: str, reader_id: str = "MOCK-READER-1") -> dict:
    """Submit a single tag read."""
    r = requests.post(
        SUBMIT_URL,
        json={"tag_id": tag_id, "reader_id": reader_id},
        timeout=3,
    )
    r.raise_for_status()
    return r.json()


def emit_noise():
    """Randomly fire a stray tag to test unknown-tag handling."""
    tag = random.choice(NOISE_TAGS)
    result = emit_tag(tag)
    print(f"[mock] [NOISE] Stray tag: {tag} → {result.get('reason', 'handled')}")


# ------------------------------------------------------------------ #
# Race simulation
# ------------------------------------------------------------------ #

def simulate_race():
    """
    Drive 20 horses across the finish line with realistic timing.

    Race spread model (flat 1-mile race):
    - Winner arrives at ~60 seconds
    - Field spreads over ~25 seconds after the winner
    - We use a weighted random sort to decide finish order
    - Duplicate reads: 2–5 per horse (reader sees tag multiple times)
    - ~15% chance of a noise tag firing between real reads
    """

    print("\n[mock] ========== TRACKSENSE MOCK RACE ==========")
    print(f"[mock] Field: {len(HORSES)} runners")
    print("[mock] Simulating UHF RFID finish-line reads...\n")

    # Assign finish times: winner ~60s, each subsequent horse adds 0.3–2.5s
    finish_order = list(HORSES)
    random.shuffle(finish_order)

    finish_times = []
    t = 60.0
    for horse in finish_order:
        finish_times.append((horse, t))
        t += random.uniform(0.3, 2.5)

    # Wait until it's time to fire each horse
    race_start = time.time()

    def fire_horse(horse: dict, finish_t: float):
        # Wait until this horse's finish time
        target = race_start + finish_t
        sleep_duration = target - time.time()
        if sleep_duration > 0:
            time.sleep(sleep_duration)

        tag_id = horse["horse_id"]
        name = horse["display_name"]
        cloth = horse["saddle_cloth"]
        duplicate_reads = random.randint(2, 5)

        # First read — the real one
        result = emit_tag(tag_id)
        if result.get("duplicate"):
            # Already recorded, shouldn't happen in simulation but handle it
            print(f"[mock]  #{cloth:>2} {name:<22} — already recorded (pos {result['position']})")
        elif result.get("ok"):
            pos = result["position"]
            elapsed = result["elapsed_ms"]
            mins = elapsed // 60000
            secs = (elapsed % 60000) / 1000
            print(f"[mock]  #{cloth:>2} {name:<22} → PLACE {pos:>2} | {mins}:{secs:06.3f}")
        else:
            print(f"[mock]  #{cloth:>2} {name:<22} → REJECTED: {result.get('reason')}")

        # Duplicate reads (simulate tag staying in beam for a moment)
        for _ in range(duplicate_reads - 1):
            time.sleep(random.uniform(0.01, 0.08))
            emit_tag(tag_id)  # Backend folds these silently

        # Occasionally emit noise
        if random.random() < 0.15:
            time.sleep(random.uniform(0.005, 0.02))
            emit_noise()

    # Fire all horses in parallel threads (they arrive independently)
    threads = []
    for horse, ft in finish_times:
        t = threading.Thread(target=fire_horse, args=(horse, ft), daemon=True)
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    print("\n[mock] All tags received. Race complete.")


# ------------------------------------------------------------------ #
# Entry point
# ------------------------------------------------------------------ #

def run():
    if not wait_for_backend():
        print("[mock] ERROR: Backend never came up. Exiting.")
        return

    register_field()
    arm()

    # Small pause so armed state is confirmed
    time.sleep(0.5)

    simulate_race()

    # Fetch and print final results
    time.sleep(0.5)
    r = requests.get(f"{BACKEND_URL}/race/finish-order", timeout=5)
    data = r.json()

    print("\n[mock] ========== OFFICIAL FINISH ORDER ==========")
    for entry in data["results"]:
        split = f" (+{entry['split_str']})" if entry.get("split_str") else ""
        print(
            f"  {entry['position']:>2}. #{entry['saddle_cloth']:>2} "
            f"{entry['display_name']:<22} "
            f"{entry['elapsed_str']}{split}"
            f"  [{entry['raw_reads']} reads]"
        )
    print("=================================================\n")


if __name__ == "__main__":
    run()
