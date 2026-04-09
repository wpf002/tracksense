# TrackSense

## What It Is

TrackSense is a full-stack horse racing intelligence platform built around
permanent RFID microchip identification. Every horse receives a UHF Gen2 glass
capsule implant (23mm × 3.85mm) injected into the lower lip by a licensed vet.
That chip — storing a 96-bit EPC — is the horse's permanent, unforgeable identity
for its entire career. Every system in TrackSense flows from that single source
of truth: timing, tracking, health, welfare, regulatory compliance, analytics.

---

## The Problem It Solves

Current race timing and horse identity management fails in several ways:

- Race equipment (transponders, bibs) must be attached and removed per race, introducing human error and misassignment
- Photo finish resolves close margins but captures no sectional data
- No continuous position tracking during a race — only start and finish
- Horse identity is managed separately from timing, requiring manual reconciliation
- Pre-race identity verification is paper-based
- Drug testing chain of custody is paper-based and prone to error
- Training data lives in trainer notebooks, disconnected from race performance
- Health records are fragmented across vets, trainers, and governing bodies

TrackSense solves all of these with one permanent implant and a network of
gate readers, APIs, and workflows built around it.

---

## How the Simulation Maps to Real Hardware

The development simulation is a 1:1 replica of real hardware behaviour.

### Simulation path

```text
mock_multi_reader.py
  → Thread per horse, waits for gate arrival time
  → POST /tags/submit { tag_id: EPC, reader_id: "GATE-F4" }
```

### Real hardware path

```text
hardware/reader.py (SerialReader / TCPReader / LLRPReader)
  → RFID antenna reads lip chip as horse passes at ~65 km/h
  → POST /tags/submit { tag_id: EPC, reader_id: "GATE-F4" }
```

Same endpoint. Same payload. Same backend logic. The only difference is what
triggers the HTTP call. Switching to real hardware is a one-line config change.

### Simulation faithfully reproduces real RF behaviours

- **2–4 reads per gate transit** (~8ms window at race speed) — the backend deduplicates them into one confirmed detection event, exactly as it will in production
- **Noise tags** — stray reads from non-race chips in the RF environment
- **Speed profiles** — pacer / closer / midfield timing mirrors real race sectional patterns

### Recommended hardware

- **Antenna:** Impinj R420 or R220 (enterprise UHF, excellent multi-tag reads)
- **Tag:** UHF Gen2 ISO 18000-6C glass capsule — 3–8m read range, handles race speed. NOTE: standard vet LF microchips (ISO 11784/11785) have only 10–15cm range and are NOT suitable for finish-line detection
- **Placement:** Two antennas per gate, RHCP circular polarisation, mounted at ~1.2m (girth height), pointing inward across the track

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                        HARDWARE LAYER                        │
│  UHF antenna gates (Start, Furlong 2/4/6/8, Finish)         │
│  SerialReader / TCPReader / LLRPReader (Impinj LLRP)         │
└────────────────────────┬────────────────────────────────────┘
                         │ POST /tags/submit
┌────────────────────────▼────────────────────────────────────┐
│                        BACKEND (FastAPI)                      │
│                                                               │
│  RaceTracker — thread-safe in-memory race state              │
│    • Duplicate folding (2–4 reads → 1 gate event)            │
│    • Sectional time + speed computation                       │
│    • Finish position assignment                               │
│                                                               │
│  GateRegistry — venue + gate config (in-memory, DB-backed)   │
│  REST API — register, arm, reset, submit, state, results      │
│  WebSocket — live gate events pushed to connected clients     │
│  JWT auth — all write endpoints protected                     │
│  API keys — third-party read access with rate limiting        │
│  Webhooks — push race results to subscriber URLs              │
│  Audit log — every official action timestamped                │
│  Multi-tenancy — venue isolation                              │
│                                                               │
│  PostgreSQL (SQLite in dev) — persisted via SQLAlchemy        │
│    Horses, Owners, Trainers, VetRecords                       │
│    Venues, Gates, Races, RaceEntries (+ jockey)               │
│    GateReads, RaceResults, WorkoutRecords                     │
│    CheckInRecords, TestBarnRecords                            │
│    ApiKeys, WebhookSubscriptions, AuditLog                    │
└────────────────────────┬────────────────────────────────────┘
                         │ REST + WebSocket
┌────────────────────────▼────────────────────────────────────┐
│                      FRONTEND (React + Vite)                  │
│                                                               │
│  Live Race   — real-time horse positions via WebSocket        │
│                jockey column, amber row flash on gate event   │
│  Results     — finish order, sectional times, speed chart     │
│                jockey column                                  │
│  Horse Registry — search by name or EPC, full career profile  │
│  Race Builder — venue/gate selection, field registration      │
│  Admin       — user management, webhooks, API keys            │
│                                                               │
│  Tailwind dark UI — near-black backgrounds, amber accents,    │
│  monospace timing font                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Layer            | Technology                                       |
|------------------|--------------------------------------------------|
| Backend          | FastAPI (Python 3.12)                            |
| Database         | PostgreSQL (prod) / SQLite (dev)                 |
| ORM              | SQLAlchemy + Alembic migrations                  |
| Frontend         | React 19 + Vite + Tailwind CSS                   |
| State            | Zustand + TanStack Query                         |
| Real-time        | WebSockets (native FastAPI)                      |
| Auth             | JWT (python-jose) + bcrypt                       |
| Hardware         | pyserial (serial/USB) + sllurp (Impinj LLRP)     |
| Simulation       | scripts/mock_multi_reader.py                     |
| Dev launcher     | start.sh (schema check, auto-seed, health check) |
| Containerisation | Docker + Docker Compose                          |

---

## Real Seed Data

The development database is seeded with real-world racing data:

**30 champion racehorses** — Secretariat, Winx, Frankel, Black Caviar,
American Pharoah, Justify, Zenyatta, Enable, Sea The Stars, Deep Impact,
Arrogate, Flightline, Curlin, Rachel Alexandra, California Chrome, Gun Runner,
Beholder, Songbird, Golden Sixty, Equinox, and more

**Jockeys** — Each horse paired with their real jockey (Ron Turcotte on
Secretariat, Hugh Bowman on Winx, Tom Queally on Frankel, etc.)

**10 real venues** with accurate distances:

- Churchill Downs (2012m dirt) — Fri/Sat
- Saratoga Race Course (1809m dirt) — Wed/Sat
- Belmont Park (2414m dirt) — Fri/Sat
- Keeneland Race Course (1809m dirt) — Thu/Sat
- Santa Anita Park (1809m dirt) — Thu/Sat
- Oaklawn Park (1609m dirt) — Thu/Sat
- Del Mar (1609m turf) — Fri/Sat
- Louisiana Downs (1409m dirt) — Wed/Sat
- Flemington Racecourse (2040m turf) — Fri/Sat
- Royal Ascot (2012m turf) — Thu/Sat

**Real trainers** — Bob Baffert, Todd Pletcher, Steve Asmussen, Chad Brown,
Chris Waller, Aidan O'Brien, John Gosden, Charlie Appleby, and others

**Real owners** — Godolphin, Coolmore Stud, Juddmonte Farms, WinStar Farm,
Stonestreet Stables, Sheikh Mohammed Al Maktoum, Khalid Abdullah, and others

**90 days of race history** — ~1,024 races, ~10,000+ entries, gate reads,
sectional times, workout logs, vet records, check-in and test barn records

---

## Running Locally

```bash
./start.sh
```

This single command:

1. Kills any existing processes on ports 8001 / 5173
2. Adds any missing DB columns (safe no-op if schema is current)
3. Starts the FastAPI backend on <http://localhost:8001>
4. Verifies backend health — exits with a clear error if it fails to start
5. Auto-seeds the DB with real race data if it is empty
6. Starts the React frontend on <http://localhost:5173>
7. Opens the browser to the login page

**Login:** admin / tracksense

---

## Completed Phases

| Phase | Description                                            | Status   |
|-------|--------------------------------------------------------|----------|
| 1     | Finish-line timing engine, duplicate folding, REST API | Complete |
| 2     | Multi-gate tracking, sectionals, WebSocket feed        | Complete |
| 3     | PostgreSQL persistence, horse identity platform        | Complete |
| 4     | React frontend — Live Race, Results, Registry, Builder | Complete |
| 5A    | Welfare workflows — workouts, check-in, test barn      | Complete |
| 6     | API keys, webhooks, GateSmart integration, audit log   | Complete |
| 7     | Multi-tenancy, JWT auth, LLRP reader, rate limiting    | Complete |

---

## Immediate Next Work

- TrackMap: replace SVG placeholder with accurate per-venue geometry; horse positions driven by server-reported gate distances, not client interpolation — must reach broadcast-quality bar
- Biosensor integration: race-day wearable (heart rate, temp, stride) paired to lip chip EPC at registration, telemetry stored per race
- Thermal chip upgrade path: temperature reading at scan time via thermal-capable UHF Gen2 chips (ISO 18000-6C + thermal sensor)
- Mobile-optimised views for trackside officials

---

## Competitive Position

**Lip Chip / HoofLink** (<https://lipchipllc.com>) — closest existing product.
Lip-implant microchips with health records and temperature monitoring,
focused on barrel racing / ranch horses using LF chips with Bluetooth
short-range scanning. Does not support finish-line detection at race speed,
sectional timing, or thoroughbred flat racing.

TrackSense occupies the gap: UHF finish-line detection at full race speed,
multi-gate sectional tracking, complete horse welfare workflows, and real-time
broadcast-ready data — purpose-built for thoroughbred flat racing.

---

## Build-to-Flip Architecture

TrackSense is designed to be sold or licensed to racing venues, governing
bodies, or timing service providers. The architecture reflects this:
clean REST + WebSocket APIs, multi-venue / multi-tenant isolation,
exportable data formats, API key access for third parties, webhook
delivery to subscriber systems, and a complete audit trail.
