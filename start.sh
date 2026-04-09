#!/usr/bin/env bash
# TrackSense dev launcher — starts backend + frontend and opens browser

set -e
cd "$(dirname "$0")"

# ── Kill anything already on our ports ────────────────────────────────────────
echo "Stopping any existing services on ports 8001 / 5173..."
lsof -ti:8001 | xargs kill -9 2>/dev/null || true
lsof -ti:5173 | xargs kill -9 2>/dev/null || true
sleep 0.5

# ── Kill all children when this script exits (Ctrl-C) ─────────────────────────
trap 'echo ""; echo "Shutting down..."; kill 0' SIGINT SIGTERM EXIT

# ── Apply any missing schema columns (safe no-op if already present) ─────────
echo "Checking database schema..."
.venv/bin/python - <<'PYEOF'
import sqlite3, os
db = "tracksense.db"
if os.path.exists(db):
    con = sqlite3.connect(db)

    # race_entries.jockey
    cols = [r[1] for r in con.execute("PRAGMA table_info(race_entries)").fetchall()]
    if "jockey" not in cols:
        con.execute("ALTER TABLE race_entries ADD COLUMN jockey VARCHAR(128)")
        con.commit()
        print("[schema] Added jockey column to race_entries.")

    # checkin_records.temperature_c (Item 3)
    cols = [r[1] for r in con.execute("PRAGMA table_info(checkin_records)").fetchall()]
    if "temperature_c" not in cols:
        con.execute("ALTER TABLE checkin_records ADD COLUMN temperature_c REAL")
        con.commit()
        print("[schema] Added temperature_c column to checkin_records.")

    # track_path_points table (Item 1)
    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if "track_path_points" not in tables:
        con.execute("""
            CREATE TABLE track_path_points (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venue_id VARCHAR NOT NULL REFERENCES venue_records(venue_id) ON DELETE CASCADE,
                sequence INTEGER NOT NULL,
                x REAL NOT NULL,
                y REAL NOT NULL,
                UNIQUE(venue_id, sequence)
            )
        """)
        con.commit()
        print("[schema] Created track_path_points table.")

    # biosensor_readings table (Item 2)
    if "biosensor_readings" not in tables:
        con.execute("""
            CREATE TABLE biosensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                horse_epc VARCHAR NOT NULL REFERENCES horses(epc),
                race_id INTEGER REFERENCES races(id),
                recorded_at DATETIME NOT NULL,
                heart_rate_bpm INTEGER,
                temperature_c REAL,
                stride_hz REAL,
                source VARCHAR(64) NOT NULL DEFAULT 'wearable'
            )
        """)
        con.commit()
        print("[schema] Created biosensor_readings table.")

    con.close()
PYEOF

# ── Seed DB if empty ─────────────────────────────────────────────────────────
echo "Checking seed data..."
# Require ALL 10 real venues to be present — test fixtures create venues with
# different IDs (TESTTRACK, V1, MAP_TRACK, etc.) that would fool a simple count.
REAL_SEED=$(.venv/bin/python - <<'PYEOF'
import sqlite3, os
REAL_VENUE_IDS = {
    'CHURCHILL','SARATOGA','SANTA_ANITA','BELMONT','KEENELAND',
    'OAKLAWN','DEL_MAR','LA_DOWNS','FLEMINGTON','ASCOT',
}
if os.path.exists("tracksense.db"):
    con = sqlite3.connect("tracksense.db")
    placeholders = ','.join('?' * len(REAL_VENUE_IDS))
    row = con.execute(
        f"SELECT COUNT(*) FROM venue_records WHERE venue_id IN ({placeholders})",
        list(REAL_VENUE_IDS),
    ).fetchone()
    con.close()
    # 1 = fully seeded, 0 = needs seeding
    print(1 if row[0] == len(REAL_VENUE_IDS) else 0)
else:
    print(0)
PYEOF
)
if [[ "$REAL_SEED" -eq 0 ]]; then
  echo "Seeding database with real race data..."
  DATABASE_URL=sqlite:///./tracksense.db .venv/bin/python -m scripts.seed
fi

# ── Backend ───────────────────────────────────────────────────────────────────
echo "Starting backend  → http://localhost:8001"
TRACKSENSE_INIT_DB=1 DATABASE_URL=sqlite:///./tracksense.db \
  .venv/bin/uvicorn app.server:app --reload --port 8001 2>&1 | sed 's/^/[backend] /' &

# ── Verify backend is up (fail loudly if it doesn't start) ───────────────────
echo "Verifying backend..."
BACKEND_UP=0
for i in $(seq 1 30); do
  if curl -sf http://localhost:8001/health >/dev/null 2>&1; then
    BACKEND_UP=1
    break
  fi
  sleep 0.5
done

if [[ $BACKEND_UP -eq 0 ]]; then
  echo ""
  echo "ERROR: Backend failed to start after 15 seconds."
  echo "Check [backend] output above for errors."
  exit 1
fi

echo "Backend verified."

# ── Frontend ──────────────────────────────────────────────────────────────────
echo "Starting frontend → http://localhost:5173"
npm --prefix frontend run dev 2>&1 | sed 's/^/[frontend] /' &

# ── Wait for frontend then open browser ───────────────────────────────────────
sleep 2
open http://localhost:5173/login

echo ""
echo "============================================================"
echo "  TrackSense is running"
echo "  App:     http://localhost:5173/login"
echo "  Login:   admin / tracksense"
echo "============================================================"
echo ""
echo "Press Ctrl+C to stop all services."
wait
