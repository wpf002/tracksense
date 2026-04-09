
import time
import random
import requests
import threading

BACKEND_URL = "http://localhost:8001"

# Authenticated session — populated by login() at startup
_session = requests.Session()


def login(username: str = "admin", password: str = "tracksense"):
    """Log in and attach Bearer token to the shared session."""
    r = requests.post(f"{BACKEND_URL}/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    token = r.json()["access_token"]
    _session.headers.update({"Authorization": f"Bearer {token}"})
    print(f"[mock] Authenticated as '{username}'.")

JOCKEYS = [
    "John Velazquez",   "Frankie Dettori",  "Irad Ortiz Jr.",   "Ryan Moore",
    "Javier Castellano","Joel Rosario",     "Mike Smith",       "Victor Espinoza",
    "Luis Saez",        "Flavien Prat",     "William Buick",    "Oisin Murphy",
    "James McDonald",   "Christophe Soumillon", "Gary Stevens", "Pat Day",
    "Tyler Gaffalione", "Rafael Bejarano",  "Corey Nakatani",   "Mickael Barzalona",
]

HORSES = [
    {"horse_id": "E200681100000001AABB0001", "display_name": "Secretariat",       "saddle_cloth": "1",  "profile": "pacer",    "jockey": "Ron Turcotte"},
    {"horse_id": "E200681100000001AABB0002", "display_name": "Winx",              "saddle_cloth": "2",  "profile": "closer",   "jockey": "Hugh Bowman"},
    {"horse_id": "E200681100000001AABB0003", "display_name": "Frankel",           "saddle_cloth": "3",  "profile": "pacer",    "jockey": "Tom Queally"},
    {"horse_id": "E200681100000001AABB0004", "display_name": "Black Caviar",      "saddle_cloth": "4",  "profile": "pacer",    "jockey": "Luke Nolen"},
    {"horse_id": "E200681100000001AABB0005", "display_name": "American Pharoah",  "saddle_cloth": "5",  "profile": "midfield", "jockey": "Victor Espinoza"},
    {"horse_id": "E200681100000001AABB0006", "display_name": "Justify",           "saddle_cloth": "6",  "profile": "midfield", "jockey": "Mike Smith"},
    {"horse_id": "E200681100000001AABB0007", "display_name": "Zenyatta",          "saddle_cloth": "7",  "profile": "closer",   "jockey": "Mike Smith"},
    {"horse_id": "E200681100000001AABB0008", "display_name": "Enable",            "saddle_cloth": "8",  "profile": "closer",   "jockey": "Frankie Dettori"},
    {"horse_id": "E200681100000001AABB0009", "display_name": "Sea The Stars",     "saddle_cloth": "9",  "profile": "midfield", "jockey": "Mick Kinane"},
    {"horse_id": "E200681100000001AABB000A", "display_name": "Deep Impact",       "saddle_cloth": "10", "profile": "closer",   "jockey": "Yutaka Take"},
    {"horse_id": "E200681100000001AABB000B", "display_name": "Arrogate",          "saddle_cloth": "11", "profile": "closer",   "jockey": "Mike Smith"},
    {"horse_id": "E200681100000001AABB000C", "display_name": "Flightline",        "saddle_cloth": "12", "profile": "pacer",    "jockey": "Flavien Prat"},
    {"horse_id": "E200681100000001AABB000D", "display_name": "Curlin",            "saddle_cloth": "13", "profile": "midfield", "jockey": "Robby Albarado"},
    {"horse_id": "E200681100000001AABB000E", "display_name": "Rachel Alexandra",  "saddle_cloth": "14", "profile": "closer",   "jockey": "Calvin Borel"},
    {"horse_id": "E200681100000001AABB000F", "display_name": "California Chrome", "saddle_cloth": "15", "profile": "midfield", "jockey": "Victor Espinoza"},
    {"horse_id": "E200681100000001AABB0010", "display_name": "Gun Runner",        "saddle_cloth": "16", "profile": "pacer",    "jockey": "Florent Geroux"},
    {"horse_id": "E200681100000001AABB0011", "display_name": "Beholder",          "saddle_cloth": "17", "profile": "closer",   "jockey": "Gary Stevens"},
    {"horse_id": "E200681100000001AABB0012", "display_name": "Songbird",          "saddle_cloth": "18", "profile": "midfield", "jockey": "Mike Smith"},
    {"horse_id": "E200681100000001AABB0013", "display_name": "Golden Sixty",      "saddle_cloth": "19", "profile": "closer",   "jockey": "Vincent Ho"},
    {"horse_id": "E200681100000001AABB0014", "display_name": "Equinox",           "saddle_cloth": "20", "profile": "midfield", "jockey": "Christophe Soumillon"},
]

# Track gates: (reader_id, name, distance_m, is_finish)
GATES = [
    ("GATE-START",  "Start",       0.0,    False),
    ("GATE-F2",     "Furlong 2",   402.0,  False),
    ("GATE-F4",     "Furlong 4",   804.0,  False),
    ("GATE-F6",     "Furlong 6",   1207.0, False),
    ("GATE-FINISH", "Finish",      1609.0, True),
]

VENUE_ID = "MOCK-TRACK"
NOISE_TAGS = ["E200681100000001FFFF0099", "E200681100000001FFFF0098"]


# ------------------------------------------------------------------ #
# Speed profiles
# Sectional time multipliers per gate segment.
# Base time for the full race ~98s. Multipliers tune each segment.
# pacer:    fast early, slow late
# closer:   slow early, fast late
# midfield: consistent throughout
# ------------------------------------------------------------------ #

SPEED_PROFILES = {
    "pacer":    [0.92, 0.96, 1.02, 1.08, 1.12],  # burns out late
    "closer":   [1.10, 1.05, 1.00, 0.95, 0.88],  # finds stride late
    "midfield": [1.00, 1.00, 1.00, 1.00, 1.00],  # consistent
}

BASE_SEGMENT_TIMES = [
    5.0,   # Start → F2  (402m, horses accelerating)
    19.5,  # F2 → F4     (402m, settling into rhythm)
    19.5,  # F4 → F6     (402m, mid-race)
    20.0,  # F6 → Finish (402m, final furlong effort)
]


def segment_times_for_horse(horse: dict) -> list[float]:
    """
    Generate realistic gate arrival times for a horse based on its profile.
    Returns cumulative seconds from gun to each gate.
    """
    profile = horse.get("profile", "midfield")
    multipliers = SPEED_PROFILES[profile]

    # Add individual horse variation
    base_ability = random.uniform(0.95, 1.05)

    times = [0.0]  # Start gate at t=0
    cumulative = 0.0
    for i, base in enumerate(BASE_SEGMENT_TIMES):
        segment = base * multipliers[i] * base_ability
        segment += random.uniform(-0.3, 0.3)  # race-day variation
        cumulative += segment
        times.append(cumulative)

    return times


def wait_for_backend(retries: int = 15, delay: float = 1.0) -> bool:
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


def setup_venue():
    """Create the venue and gates via the API."""
    # Create venue
    r = _session.post(f"{BACKEND_URL}/venues", json={
        "venue_id": VENUE_ID,
        "name": "Mock Race Track",
        "total_distance_m": 1609.0,
    })
    if r.status_code not in (200, 409):  # 409 = already exists, fine
        r.raise_for_status()

    # Add gates
    for reader_id, name, distance_m, is_finish in GATES:
        r = _session.post(f"{BACKEND_URL}/venues/{VENUE_ID}/gates", json={
            "reader_id": reader_id,
            "name": name,
            "distance_m": distance_m,
            "is_finish": is_finish,
        })
        # Ignore if gate already exists
        if r.status_code not in (200, 400):
            r.raise_for_status()

    print(f"[mock] Venue '{VENUE_ID}' configured with {len(GATES)} gates.")


def register_field():
    r = _session.post(f"{BACKEND_URL}/race/register", json={
        "venue_id": VENUE_ID,
        "horses": [
            {"horse_id": h["horse_id"], "display_name": h["display_name"], "saddle_cloth": h["saddle_cloth"], "jockey": h.get("jockey", "")}
            for h in HORSES
        ],
    })
    r.raise_for_status()
    print(f"[mock] Registered {r.json()['registered']} horses.")


def arm():
    _session.post(f"{BACKEND_URL}/race/arm").raise_for_status()
    print("[mock] Race armed.")


def emit_tag(tag_id: str, reader_id: str) -> dict:
    r = _session.post(f"{BACKEND_URL}/tags/submit", json={
        "tag_id": tag_id,
        "reader_id": reader_id,
    }, timeout=3)
    r.raise_for_status()
    return r.json()


def simulate_race():
    print("\n[mock] ========== TRACKSENSE MULTI-GATE RACE ==========")
    print(f"[mock] Field: {len(HORSES)} runners")
    print(f"[mock] Gates: {len(GATES)}")
    print("[mock] Chip: UHF Gen2 glass capsule — lower lip implant")
    print("[mock] Profiles: pacer / closer / midfield\n")

    race_start = time.time()

    def run_horse(horse: dict):
        tag_id = horse["horse_id"]
        name = horse["display_name"]
        cloth = horse["saddle_cloth"]
        gate_times = segment_times_for_horse(horse)

        for i, (reader_id, gate_name, _, _) in enumerate(GATES):
            target = race_start + gate_times[i]
            wait = target - time.time()
            if wait > 0:
                time.sleep(wait)

            # Lip implant transit: 2–4 reads in ~8ms window
            result = emit_tag(tag_id, reader_id)

            if result.get("ok") and not result.get("duplicate"):
                elapsed = result.get("elapsed_ms", 0)
                mins = elapsed // 60000
                secs = (elapsed % 60000) / 1000
                finish_str = f" ← PLACE {result['finish_position']}" if result.get("is_finish") and result.get("finish_position") else ""
                print(f"[mock]  #{cloth:>2} {name:<22} [{gate_name:<12}] {mins}:{secs:06.3f}{finish_str}")

            # Remaining reads in transit window
            for _ in range(random.randint(1, 3)):
                time.sleep(random.uniform(0.001, 0.008))
                emit_tag(tag_id, reader_id)

            # Occasional stray animal implant
            if random.random() < 0.05:
                time.sleep(random.uniform(0.01, 0.05))
                emit_tag(random.choice(NOISE_TAGS), reader_id)

    threads = [
        threading.Thread(target=run_horse, args=(horse,), daemon=True)
        for horse in HORSES
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print("\n[mock] All horses finished.")


def print_results():
    time.sleep(0.5)
    r = _session.get(f"{BACKEND_URL}/race/state")
    data = r.json()

    print("\n[mock] ========== FINISH ORDER ==========")
    finished = [h for h in data["horses"] if h["finish_position"]]
    finished.sort(key=lambda h: h["finish_position"])

    for h in finished:
        finish_event = next((e for e in h["events"] if e["is_finish"]), None)
        elapsed_str = finish_event["elapsed_str"] if finish_event else "?"
        print(f"  {h['finish_position']:>2}. #{h['saddle_cloth']:>2} {h['display_name']:<22} {elapsed_str}")

    print("\n[mock] ========== SECTIONAL TIMES ==========")
    for h in finished[:5]:  # Top 5 sectionals
        print(f"\n  {h['display_name']} (#{h['saddle_cloth']})")
        for s in h["sectionals"]:
            print(f"    {s['segment']:<30} {s['elapsed_str']}  {s['speed_kmh']} km/h")

    print("\n=============================================\n")


def run():
    if not wait_for_backend():
        print("[mock] ERROR: Backend never came up.")
        return

    login()
    setup_venue()
    register_field()
    arm()
    time.sleep(0.5)
    simulate_race()
    print_results()


if __name__ == "__main__":
    run()