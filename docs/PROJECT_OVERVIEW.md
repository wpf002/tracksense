# TrackSense — Project Overview

> A current, detailed technical + product overview of TrackSense.
> Companion to `PROJECT_DESCRIPTION.md` (product vision) and `ROADMAP.md` (phases).

## 1. What it is

**TrackSense is a HISA compliance platform for U.S. Thoroughbred racing.** It runs
the everyday operational workflows of a racetrack and training center — horse
identity checks, veterinary and treatment records, timed workouts, pre-race
inspections, post-race sampling — and assembles the regulatory submissions the
**Horseracing Integrity and Safety Authority (HISA)** requires as a *byproduct* of
that operational data, rather than as a separate paperwork burden.

The core thesis: officials, vets, and trainers do their normal jobs in TrackSense;
the data they capture is structured so the corresponding HISA report can be
generated and filed automatically. Compliance isn't a separate product surface —
it's a side effect of good operational record-keeping.

The product is a **mid-pivot v2.0**: it began as a UHF race-timing system
(fixed-gate RFID, live sectional timing) and was deliberately repositioned to a
compliance/record-keeping platform. The UHF/hardware path was dropped; the durable
backend (auth, multi-tenancy, webhooks, exports, welfare workflows) was kept.

## 2. Market positioning

Complementary infrastructure, **not** a timing competitor:

| System | Owns | TrackSense relationship |
|---|---|---|
| **FinishLynx** | Official photo-finish order | Consumes the result; does not time races |
| **TPD** | GPS in-running sectionals | Does not produce position data |
| **TrackSense** | Identity, welfare, treatment, compliance records | Fills the regulatory/operational gap underneath both |

The wedge is **identity-anchored compliance**: turning routine vet/treatment/
workout activity into ready-to-file HISA submissions.

## 3. Architecture & tech stack

**Backend** — Python / **FastAPI** (0.115), **SQLAlchemy 2.0** (typed `Mapped`
models), **Alembic** migrations (25 versions), **Pydantic 2**. Auth via **JWT**
(python-jose) + **bcrypt**, plus an **API-key** system with **Redis**-backed rate
limiting. Runs on **uvicorn**. Database is **PostgreSQL** in production
(`psycopg2`) and **SQLite** in local dev.

**Frontend** — **React 18 + Vite**, **React Router**, **TanStack Query** (server
state), **Zustand** (client state), **Axios** (with a dev proxy to the API),
**Recharts** (biosensor/temperature charts), **Tailwind CSS** with a custom dark
"timing console" theme.

**Deploy** — Dockerized (the image runs uvicorn); hosted on **Railway** with
managed Postgres. Local dev is a single `./start.sh` that seeds the DB, runs schema
patches, and launches backend + frontend. Tests via **pytest**.

## 4. The three modules & features

**1) Race Day Operations** (`/live`, `/builder`, `/results`)
- Race-card builder (track, post time, distance, surface, conditions)
- Race lifecycle: IDLE → ARMED → RUNNING → FINISHED
- Entries, scratches (incl. veterinary scratches), paddock identity verification
- Results ingestion (FinishLynx / MYLAPS / manual), finish order, margins
- Post-race test-barn sample check-in/checkout (chain of custody)
- Riding-crop violation logging

**2) Training Center Workflows** (`/training`, `/horses`)
- Daily roster of every covered horse with a status snapshot: last workout, latest
  vet check, open treatments, pending HISA items
- Timed-workout logging (date, distance, surface, time, rider/clocker/splits)
- Veterinary checks and treatment/medication records
- Per-horse profile: career/form, race history, workouts, vet records, treatments,
  check-ins, **biosensor telemetry** (heart rate, body temp, stride frequency),
  temperature alerts, head-to-head comparison, and an **owner report**

**3) Chip-Based Identity** (`/mobile/checkin`)
- Mobile check-in screen: scan/enter a horse's microchip (ISO 11784/11785) to
  verify identity before paddock entry, with welfare/compliance flags and thermal
  temperature capture

**Compliance Dashboard** (`/compliance`)
- The HISA submission queue with pending/overdue/submitted/accepted stats,
  filters, payload viewer, and the build/submit actions

## 5. Data model (25 tables)

- **Identity & people:** `horses`, `owners`, `trainers`, `tenants`, `users`
- **Racing:** `venue_records`, `races`, `race_entries`, `race_results`
- **Welfare / regulatory records:** `vet_records`, `vet_check_records`,
  `treatment_records`, `workout_records`, `checkin_records`, `test_barn_records`,
  `biosensor_readings`, `scratch_records`, `surface_condition_logs`,
  `stewards_rulings`, `riding_crop_violations`
- **Compliance:** `hisa_submissions` (one per operational record, with
  rule_category, status, deadline, payload JSON)
- **Infrastructure:** `audit_log`, `webhook_subscriptions`, `webhook_deliveries`,
  `api_keys`

## 6. Backend API surface (~80 endpoints, grouped)

- **Auth:** login, refresh, register, change-password, `/auth/me`
- **Horses:** CRUD, summary, career, form, compare, checkins, workouts, vet,
  vet-checks, treatments, testbarn, biosensor (read + ingest + bulk), temperature
  history/alerts, owner-report
- **Races:** CRUD, entries, results ingest, scratch, status, biosensor,
  crop-violations, and **industry exports** (`/export/bha`,
  `/export/jockey-club`, `/export/racing-australia`)
- **Training:** `/training/roster`
- **Compliance (HISA):** `/hisa/submissions`, `/hisa/report-types`,
  `/hisa/build-all`, `/hisa/submit/{id}`, `/stewards/rulings`, surface conditions
- **Venues, Tenants, Admin/users, Webhooks, API keys**

## 7. Roles & cross-cutting infrastructure

- **RBAC:** `super_admin`, `admin`, `compliance`, `trainer`, `viewer` (enforced by
  FastAPI dependencies like `require_compliance_or_admin`)
- **Multi-tenancy:** per-organization isolation via `tenant_id` on records
- **Audit log:** every official action timestamped and attributed
- **Webhooks:** subscriptions with retry, delivery log, HMAC-SHA256 signing (incl.
  a GateSmart integration that pushes workout/welfare data to a downstream
  handicapping engine)
- **API keys** with rate limiting; **industry-format exports** (BHA, Jockey Club,
  Racing Australia)

## 8. The HISA compliance engine

Each operational record (workout, treatment, check-in, sample, surface log,
ruling, scratch) maps to a HISA report category. `hisa_builder.py` assembles a
structured JSON payload per record; `/hisa/build-all` scans recent records and
creates `pending` submissions; officials review, download, and either submit or
export them.

The engine is hardened against real HISA requirements (validated via a fact-checked
research pass):

- **`app/hisa_meta.py`** — a registry mapping each report type to its *responsible
  party*, *filing deadline*, and *submission channel*. Key finding: **only
  veterinary treatment records have a real third-party vendor submission path
  today** (à la HVMS/EquiTrace); everything else is portal entry by the track,
  regulatory vet, HIWU, or stewards. The Compliance UI reflects this (Submit → for
  treatment, Export → for portal-only).
- **`build_treatment_submission`** emits the full **ADMC Rule 2251(b)** structure
  (responsible person, attending vet + contact, diagnosis, condition, structured
  medications with date/time/route/frequency/duration, procedures).
- **Horse identity:** HISA keys a Covered Horse by **name + year of birth + dam +
  owner**, with coverage starting at the first timed workout — *not* the microchip.
  The model carries `dam_name` and `covered_since`; the chip is an internal/
  operational reference only.
- **`app/hisa_submitter.py`** — a pluggable delivery layer
  (`PortalExportSubmitter` today; `PartnerApiSubmitter` stub for a future HISA
  partnership).
- The build is **scoped to the current race meeting**, and the seed produces a
  **realistic status mix** (~63 submissions: ~10 pending, 1 overdue, rest
  submitted/accepted) so the dashboard reads like a live operation.

## 9. Identity & hardware approach

Identity is a **deliberate point-of-care scan** of the existing ISO 11784/11785 LF
microchip with a commodity handheld reader — no new implant, no fixed-gate
readers, no race-speed RF. The v1.0 UHF/Impinj/sllurp path was explicitly dropped.

## 10. Integration seams (for the roadmap)

Clean interfaces so future steps plug in without rewrites:

- **Step 3 (real data):** `app/ingestion.py` — `DataSource` interface; seed is the
  current provider, CSV import is the stub.
- **Step 4 (hardware):** `hardware/reader.py` — `MicrochipReader` (mock + serial
  stub) and `ResultsSource` (manual + FinishLynx/MYLAPS stub), env-selected.
- **Step 5 (biosensors):** ingest endpoint exists; seeded with a realistic
  pre-race wearable timeseries so the Horse Profile charts render.

## 11. Current status — honest assessment

- **Phases 0–4 complete; Phase 5 (Race Day Ops) in progress; Phase 6 (GTM) not
  started.**
- It is a **polished, working prototype on synthetic data.** The seed generates
  ~30 horses, ~1,000 races of history, and a realistic compliance queue.
- **Not yet real:** no live HISA submission (no public API exists — it's
  portal/partnership-only), no real hardware integration (`hardware/` holds
  interfaces + mocks), and the biosensor wearable feed is seeded, not live.
- **Riskiest unknowns to validate with HISA directly:** the vendor-onboarding
  mechanism for treatment-record submission, and the exact reporter/deadline/
  fields for workouts and stewards' rulings (flagged `confirmed: false` in the
  registry).

## 12. Running it locally

```bash
./start.sh
# Backend  → http://localhost:8001
# Frontend → http://localhost:5173
# Login    → admin / tracksense
```
