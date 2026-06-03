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

    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

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

    # workout_records — exercise-timing columns (rider/clocker/splits)
    cols = [r[1] for r in con.execute("PRAGMA table_info(workout_records)").fetchall()]
    workout_add = {
        "rider_name": "VARCHAR(128)",
        "clocker_name": "VARCHAR(128)",
        "timekeeper_name": "VARCHAR(128)",
        "splits_json": "TEXT",
        "source": "VARCHAR(32) NOT NULL DEFAULT 'manual'",
    }
    for col, decl in workout_add.items():
        if col not in cols:
            con.execute(f"ALTER TABLE workout_records ADD COLUMN {col} {decl}")
            con.commit()
            print(f"[schema] Added {col} column to workout_records.")

    # Phase 3 — HISA reporting tables
    for tbl, ddl in [
        ("treatment_records", """
            CREATE TABLE treatment_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                horse_chip_id VARCHAR NOT NULL REFERENCES horses(chip_id),
                treatment_date VARCHAR(10) NOT NULL,
                substance VARCHAR(200) NOT NULL,
                dose VARCHAR(100),
                route VARCHAR(100),
                withdrawal_time_hours INTEGER,
                prescribed_by VARCHAR(128),
                administered_by VARCHAR(128),
                race_id INTEGER REFERENCES races(id),
                notes TEXT,
                is_prohibited BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )"""),
        ("stewards_rulings", """
            CREATE TABLE stewards_rulings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ruling_date DATETIME NOT NULL,
                race_id INTEGER REFERENCES races(id),
                horse_chip_id VARCHAR REFERENCES horses(chip_id),
                jockey_name VARCHAR(128),
                rule_violated VARCHAR(200) NOT NULL,
                description TEXT NOT NULL,
                penalty VARCHAR(200),
                status VARCHAR(32) NOT NULL DEFAULT 'draft',
                deadline_at DATETIME NOT NULL,
                created_by VARCHAR(36) REFERENCES users(id),
                tenant_id VARCHAR(36) REFERENCES tenants(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )"""),
        ("surface_condition_logs", """
            CREATE TABLE surface_condition_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                venue_id VARCHAR NOT NULL REFERENCES venue_records(venue_id),
                logged_date VARCHAR(10) NOT NULL,
                surface_type VARCHAR(32) NOT NULL,
                going_description VARCHAR(64) NOT NULL,
                moisture_pct REAL,
                temperature_c REAL,
                maintenance_notes TEXT,
                logged_by VARCHAR(128),
                tenant_id VARCHAR(36) REFERENCES tenants(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(venue_id, logged_date)
            )"""),
        ("hisa_submissions", """
            CREATE TABLE hisa_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_category VARCHAR(64) NOT NULL,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                source_record_type VARCHAR(64) NOT NULL,
                source_record_id INTEGER NOT NULL,
                horse_chip_id VARCHAR,
                deadline_at DATETIME,
                submitted_at DATETIME,
                payload_json TEXT,
                response_json TEXT,
                submitted_by VARCHAR(36) REFERENCES users(id),
                tenant_id VARCHAR(36) REFERENCES tenants(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )"""),
        ("vet_check_records", """
            CREATE TABLE vet_check_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                horse_chip_id VARCHAR NOT NULL REFERENCES horses(chip_id),
                check_date VARCHAR(10) NOT NULL,
                check_type VARCHAR(32) NOT NULL,
                outcome VARCHAR(32) NOT NULL,
                vet_name VARCHAR(128),
                race_id INTEGER REFERENCES races(id),
                notes TEXT,
                tenant_id VARCHAR(36) REFERENCES tenants(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )"""),
        ("scratch_records", """
            CREATE TABLE scratch_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id INTEGER NOT NULL REFERENCES races(id),
                horse_chip_id VARCHAR NOT NULL REFERENCES horses(chip_id),
                scratch_type VARCHAR(32) NOT NULL,
                declared_by VARCHAR(128),
                reason TEXT,
                declared_at DATETIME NOT NULL,
                tenant_id VARCHAR(36) REFERENCES tenants(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(race_id, horse_chip_id)
            )"""),
        ("riding_crop_violations", """
            CREATE TABLE riding_crop_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id INTEGER NOT NULL REFERENCES races(id),
                horse_chip_id VARCHAR REFERENCES horses(chip_id),
                jockey_name VARCHAR(128) NOT NULL,
                crop_count INTEGER NOT NULL,
                violation_determined BOOLEAN NOT NULL DEFAULT 0,
                penalty VARCHAR(200),
                official_name VARCHAR(128),
                race_date VARCHAR(10),
                notes TEXT,
                tenant_id VARCHAR(36) REFERENCES tenants(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )"""),
    ]:
        if tbl not in tables:
            con.execute(f"CREATE TABLE {tbl} {ddl}")
            con.commit()
            print(f"[schema] Created {tbl} table.")

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
