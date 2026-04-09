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
    cols = [r[1] for r in con.execute("PRAGMA table_info(race_entries)").fetchall()]
    if "jockey" not in cols:
        con.execute("ALTER TABLE race_entries ADD COLUMN jockey VARCHAR(128)")
        con.commit()
        print("[schema] Added jockey column to race_entries.")
    con.close()
PYEOF

# ── Seed DB if empty ─────────────────────────────────────────────────────────
echo "Checking seed data..."
HORSE_COUNT=$(.venv/bin/python - <<'PYEOF'
import sqlite3, os
if os.path.exists("tracksense.db"):
    con = sqlite3.connect("tracksense.db")
    print(con.execute("SELECT COUNT(*) FROM horses").fetchone()[0])
    con.close()
else:
    print(0)
PYEOF
)
if [[ "$HORSE_COUNT" -eq 0 ]]; then
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
