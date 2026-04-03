# TrackSense — Project Roadmap

## Phase 1 — Finish-Line Timing Engine ✅ COMPLETE

- [x] Thread-safe in-memory race state engine
- [x] FastAPI REST API (register, arm, reset, submit tag, finish order, status)
- [x] Duplicate read folding (2–4 reads per lip transit → 1 confirmed detection)
- [x] Unknown tag rejection
- [x] Millisecond-accurate finish positions and split times
- [x] Race lifecycle management (IDLE → ARMED → RUNNING → FINISHED)
- [x] Mock reader — 20 horses, realistic race spread, RF noise simulation
- [x] Hardware reader module — serial (pyserial) and TCP (Impinj-ready)
- [x] Docker + docker-compose
- [x] 12 unit tests, all passing
- [x] Hardware reference documentation

---

## Phase 2 — Multi-Gate Full Race Tracking ✅ COMPLETE

- [x] Multi-reader architecture — reads tagged with reader_id (gate identity)
- [x] Dynamic gate registry — define gate positions via API
- [x] Sectional time computation — time between consecutive gate reads per horse
- [x] Speed calculation — distance / sectional time per segment
- [x] Race replay data model — ordered sequence of gate events per horse
- [x] WebSocket endpoint — push live gate events to connected clients
- [x] Multi-reader mock — start + 4 furlongs + finish with horse performance profiles
- [x] 33 unit tests, all passing

---

## Phase 3 — Persistent Database & Horse Identity Platform ✅ COMPLETE

- [x] PostgreSQL schema — horses, owners, trainers, venues, races, race_entries,
      gate_reads, race_results, vet_records
- [x] SQLAlchemy models + Alembic migrations
- [x] All CRUD operations and analytics queries
- [x] Career history, form guide, sectional averages, head-to-head
- [x] Persist race results to database on completion
- [x] Horse profile API
- [x] Redis for live race state
- [x] 29 database layer tests, all passing
- [x] 113 total tests passing

---

## Phase 4 — Frontend Dashboard ✅ COMPLETE

- [x] React 18 + Vite + Tailwind + React Router + Zustand + TanStack Query
- [x] Dark industrial UI — near-black backgrounds, amber/gold accents, monospace data
- [x] Live Race view — WebSocket feed, real-time horse positions, amber row flash
- [x] Race Results — finish order with sectionals, Recharts speed chart
- [x] Horse Registry — search by name or EPC, profile pages
- [x] Race Card Builder — venue selection, gate configuration, field registration
- [x] WS connected/offline indicator, auto-reconnect with exponential backoff
- [x] Vite proxy — no CORS issues in development
- [x] make dev — starts both backend and frontend simultaneously

---

## Phase 5 — Horse Welfare, Biosensor & Operational Workflows

Extends TrackSense from a timing platform into a complete horse welfare and
regulatory compliance system. Inspired by industry workflows (pre-race check-in,
drug testing chain of custody, daily health monitoring) but built for thoroughbred
flat racing rather than the barrel racing / ranch horse market those tools serve.

### 5A — Operational Workflows (Backend + Frontend)

Three new record types tied to the permanent chip identity:

**WorkoutRecord**
Trainers log training sessions against the horse's EPC between races.
Fields: date, distance_m, surface, duration_ms, track_condition, notes, trainer_name
Feeds into: form analysis, pre-race preparation assessment

**CheckInRecord**
Pre-race identity verification. Steward or official scans the chip before the
horse enters the paddock. Confirms the horse on the track matches the race entry.
Fields: race_id, scanned_at, scanned_by, location, verified (bool), notes
Replaces paper-based identity checks at the gate.

**TestBarnRecord**
Post-race drug testing chain of custody. Horse enters test barn, chip is scanned
to log check-in. Sample is collected and logged. Chip scanned again on check-out.
Fields: race_id, checkin_at, checkin_by, checkout_at, checkout_by, sample_id, notes
Provides tamper-proof regulatory audit trail.

- [ ] Add WorkoutRecord, CheckInRecord, TestBarnRecord to app/models.py
- [ ] Add Alembic migration for new tables
- [ ] CRUD operations in app/crud.py
- [ ] API endpoints: POST/GET /horses/{epc}/workouts
- [ ] API endpoints: POST/GET /horses/{epc}/checkins
- [ ] API endpoints: POST /horses/{epc}/testbarn/checkin, POST /horses/{epc}/testbarn/checkout
- [ ] Frontend: Workout log tab on Horse Profile page
- [ ] Frontend: Pre-race check-in step in Race Card Builder (Step 4)
- [ ] Frontend: Test barn log on Horse Profile page
- [ ] Seed script: generate 90 days of workout records per horse

### 5B — Biosensor Integration

A race-day wearable device (girth strap or chest band) transmits live biometric
telemetry during races. The permanent lip chip provides identity; the biosensor
provides the data stream. Both feed into TrackSense.

Fields collected: heart_rate_bpm, body_temp_c, stride_rate, stride_length_m,
gps_lat, gps_lng, timestamp

Architecture:

- Permanent lip chip → horse identity (passive, no battery)
- Race-day biosensor strap → telemetry (active, battery, Bluetooth/cellular)
- Paired at race registration via EPC
- Telemetry stored against race and horse EPC in biometric_reads table

Tasks:

- [ ] BiometricRead model — telemetry per horse per timestamp per race
- [ ] Biosensor ingestion API — POST /races/{race_id}/biometrics
- [ ] Live telemetry WebSocket feed
- [ ] Frontend: biometric overlay on Live Race view (heart rate, temp per horse)
- [ ] Frontend: post-race biometric charts on Race Results page
- [ ] Hardware spec: supported biosensor devices and pairing protocol

### 5C — Thermal Chip Upgrade Path

Lip Chip / HoofLink demonstrated that thermal microchips can read body temperature
at scan time. TrackSense's Phase 5C documents the upgrade path from standard UHF
Gen2 passive chips to thermal-capable chips.

- [ ] Research UHF thermal chip availability (ISO 18000-6C + thermal sensor)
- [ ] Update HARDWARE.md with thermal chip options and scan protocol
- [ ] Add temperature_c field to CheckInRecord (populated when thermal chip present)
- [ ] Frontend: display temperature on pre-race check-in confirmation

---

## Phase 6 — Ecosystem & Integrations

### Goals

- GateSmart receives real sectional performance data
- Public API for third-party consumers
- Mobile app for trackside use
- Export to industry-standard formats

### Phase 6 Tasks

- [ ] Public REST API with JWT authentication and rate limiting
- [ ] API key management for third-party consumers
- [ ] GateSmart integration — push sectional data to Secretariat handicapping engine
- [ ] Industry format export — Racing Australia, BHA, Jockey Club XML/JSON
- [ ] Broadcast data feed — real-time horse position data for TV graphics
- [ ] Mobile-optimised web views for trackside officials (430px breakpoint)
- [ ] Webhook support — push race results to subscriber URLs on race completion
- [ ] Venue operator portal — multi-venue management, race day scheduling

---

## Phase 7 — Hardening & Commercial Readiness

### Phase 7 Tasks

- [ ] Multi-tenancy — each venue/operator is an isolated tenant
- [ ] Role-based access control — steward, trainer, vet, operator, admin
- [ ] Audit log — every official action recorded with timestamp and user
- [ ] High availability — reader redundancy, automatic failover if a gate reader drops
- [ ] Load testing — validate backend under full race day load
- [ ] Hardware installation documentation — full venue deployment guide
- [ ] Pricing and licensing model
- [ ] One-page pitch document for venue operators and racing authorities

---

## Development Principles

- Backend-first. Every feature starts with a tested API endpoint before any UI is built.
- Hardware-accurate. Every assumption about RFID behaviour is grounded in real physics.
- Two-tool workflow: Claude.ai for architecture and decisions, Claude Code for building.
- Full builds over incremental scaffolds. Each phase delivered as a complete, runnable increment.
- Dark industrial UI for all frontend work.
- Build to flip. Architecture decisions account for the product being sold or licensed.