# TrackSense — Project Roadmap

## Phase 1 — Finish-Line Timing Engine ✅ COMPLETE

The foundation. A single RFID gate at the finish line. Detects horses, records finish order, computes splits.

### Phase 1 Delivered

- [x] Thread-safe in-memory race state engine (`race_state.py`)
- [x] FastAPI REST API (register, arm, reset, submit tag, finish order, status)
- [x] Duplicate read folding (2–4 reads per lip transit → 1 confirmed detection)
- [x] Unknown tag rejection (stray animal implants, noise)
- [x] Millisecond-accurate finish positions and split times
- [x] Race lifecycle management (IDLE → ARMED → RUNNING → FINISHED)
- [x] Mock reader — 20 horses, realistic race spread, RF noise simulation
- [x] Hardware reader module — serial (pyserial) and TCP (Impinj-ready)
- [x] Docker + docker-compose
- [x] 12 unit tests, all passing
- [x] Hardware reference documentation (chip spec, injection procedure, antenna geometry)

---

## Phase 2 — Multi-Gate Full Race Tracking

Extend from a single finish-line gate to a full track instrumentation network. Track every horse's position at every furlong throughout the race.

### Phase 2 Goals

- Real-time position data for every horse from start to finish
- Sectional times per horse per furlong segment
- Speed calculations per section
- Race replay — reconstruct the full race from tag reads
- Live WebSocket feed for external consumers

### Phase 2 Tasks

- [ ] Multi-reader architecture — backend accepts reads tagged with `reader_id` (gate identity)
- [ ] Gate registry — define gate positions (start, furlong 1, furlong 2... finish) with distances
- [ ] Sectional time computation — time between consecutive gate reads per horse
- [ ] Speed calculation — distance / sectional time per segment
- [ ] Race replay data model — ordered sequence of gate events per horse
- [ ] WebSocket endpoint — push live gate events to connected clients
- [ ] Reader synchronisation — ensure all gates share a common clock reference (NTP or GPS-disciplined clock)
- [ ] Multi-reader mock — simulate gates at start + 4 furlongs + finish
- [ ] Update hardware docs for multi-gate deployment

---

## Phase 3 — Persistent Database & Horse Identity Platform

Move from in-memory race state to a full PostgreSQL-backed platform. The lip implant EPC becomes the horse's permanent identity across their career.

### Phase 3 Goals

- Results survive restarts
- Full race history per horse
- Vet records attached to horse identity
- Ownership and trainer records
- Performance analytics

### Phase 3 Tasks

- [ ] PostgreSQL schema design
  - `horses` — EPC, name, breed, date of birth, implant date, implant vet
  - `owners` — ownership records with date ranges
  - `trainers` — trainer assignments per horse
  - `venues` — track registry with gate configurations
  - `races` — race metadata (date, venue, distance, surface, conditions)
  - `race_entries` — horse + race + saddle cloth
  - `gate_reads` — raw tag read log (horse, gate, timestamp, race)
  - `race_results` — official finish positions with sectional times
  - `vet_records` — health events, treatments, clearances tied to horse EPC
- [ ] SQLAlchemy models + Alembic migrations
- [ ] Persist all race results to database on race completion
- [ ] Horse profile API (full career history, stats, vet records)
- [ ] Venue and race card management API
- [ ] Performance analytics queries
  - Career sectional averages per horse
  - Surface and distance performance breakdown
  - Form guide data (last N starts)
  - Head-to-head comparison between horses
- [ ] Redis for live race state (fast in-race reads) with PostgreSQL as the persistent record

---

## Phase 4 — Frontend Dashboard

React 18 web application for race officials, trainers, and venue operators.

### Phase 4 Goals

- Live race view — watch horses progress through gates in real time
- Race results — official finish order with sectionals
- Horse profiles — full career records
- Race card management — build fields, assign chips, arm races
- Stewards tools — result submission, objection workflow

### Phase 4 Tasks

- [ ] Project scaffold — React 18 + Vite + Tailwind + React Router + Zustand + React Query
- [ ] Live race view — WebSocket-driven gate event display, horse positions updating in real time
- [ ] Race results page — finish order, sectional times, speed per segment, gap to winner
- [ ] Horse profile page — career history, sectional trends, ownership
- [ ] Race card builder — create race, add horses, assign saddle cloths, arm
- [ ] Venue configuration — gate layout, reader assignment
- [ ] Stewards panel — official result, objection submission, timing dispute tools
- [ ] Dark industrial UI aesthetic — near-black backgrounds, amber/gold accents, monospace data displays

---

## Phase 5 — Ecosystem & Integrations

Open the platform to external systems and build the GateSmart data bridge.

### Phase 5 Goals

- GateSmart receives real sectional performance data
- Public API for third-party consumers
- Mobile app for trackside use
- Export to industry-standard formats

### Phase 5 Tasks

- [ ] Public REST API with JWT authentication and rate limiting
- [ ] API key management for third-party consumers
- [ ] GateSmart integration — push sectional data to GateSmart horse profiles to feed Secretariat handicapping engine
- [ ] Industry format export — Racing Australia, BHA, Jockey Club XML/JSON schemas
- [ ] Broadcast data feed — real-time horse position data for TV graphics systems
- [ ] Mobile-optimised web views for trackside officials (React, 430px breakpoint)
- [ ] Webhook support — push race results to subscriber URLs on race completion
- [ ] Venue operator portal — multi-venue management, race day scheduling

---

## Phase 6 — Hardening & Commercial Readiness

Make the platform fit for sale or licensing to racing venues and governing bodies.

### Phase 6 Tasks

- [ ] Multi-tenancy — each venue/operator is an isolated tenant
- [ ] Role-based access control — steward, trainer, vet, operator, admin
- [ ] Audit log — every official action recorded with timestamp and user
- [ ] High availability — reader redundancy, automatic failover if a gate reader drops
- [ ] Load testing — validate backend under full race day load (multiple simultaneous races)
- [ ] Hardware installation documentation — full venue deployment guide
- [ ] Pricing and licensing model
- [ ] One-page pitch document for venue operators and racing authorities

---

## Development Principles

- Backend-first. Every feature starts with a tested API endpoint before any UI is built.
- Hardware-accurate. Every assumption about RFID behaviour is grounded in real physics, not approximations.
- Two-tool workflow: Claude.ai for architecture and scaffolding, Claude Code for building and debugging.
- Full builds over incremental scaffolds. Each phase delivered as a complete, runnable increment.
- Dark industrial UI when frontend work begins.
- Build to flip. Architecture decisions account for the product being sold or licensed.
