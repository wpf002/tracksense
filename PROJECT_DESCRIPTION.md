# TrackSense

## What It Is

TrackSense is a **HISA compliance platform for US thoroughbred racing**. It runs
the everyday operational workflows of a racetrack and training center — horse
identity checks, veterinary and treatment records, timed workouts, pre-race
inspections, and post-race sample collection — and generates the regulatory
submissions the **Horseracing Integrity and Safety Authority (HISA)** requires
as a **byproduct of that operational data**, instead of as a separate paperwork
burden.

The platform is organized around three modules:

1. **Race Day Operations** — paddock identity verification, pre-race veterinary
   inspection, scratches, and post-race test-barn sample chain of custody.
2. **Training Center Workflows** — daily treatment and veterinary records, timed
   workout logging, and horse-in-training status for every covered horse.
3. **Jockey Club Chip-Based Identity** — every covered horse is scanned via the
   LF microchip already mandated by The Jockey Club, read with a commodity
   handheld scanner. Within TrackSense the chip is the operational join key that
   ties every record together. Note: the microchip is **not** HISA's own
   registration identifier — HISA keys a Covered Horse by name + year of birth +
   dam + owner, with coverage beginning at the horse's first timed-and-reported
   workout (see "Identity" below).

Compliance is not a separate product surface. Officials and trainers do their
normal jobs through TrackSense; the data they capture is structured so the
corresponding HISA submission can be assembled and filed automatically.

---

## Where It Sits in the Ecosystem

TrackSense is **complementary infrastructure**, not a timing or tracking competitor:

| System | Owns | TrackSense relationship |
|--------|------|-------------------------|
| **FinishLynx** | Official photo-finish order of finish | TrackSense does **not** time races or call the finish. It consumes the official result. |
| **TPD (Total Performance Data)** | GPS/positional in-running sectionals | TrackSense does **not** produce GPS sectionals or live position data. |
| **TrackSense** | Identity, welfare, treatment, and compliance record-keeping | Fills the regulatory/operational gap neither of the above addresses. |

The wedge is identity-anchored compliance: nobody else turns the mandatory
microchip plus routine vet/treatment/workout activity into ready-to-file HISA
submissions. TrackSense becomes the **operational and compliance layer
underneath** these systems — ingesting their outputs (e.g. FinishLynx finish
order/times) rather than reproducing them.

---

## Identity: Existing Mandated LF Microchips

TrackSense uses the **LF (134.2 kHz, ISO 11784/11785) microchip already required
by The Jockey Club** for registration of every thoroughbred foal. There is no new
implant, no novel chip, and no specialized antenna infrastructure:

- The chip is **already in the horse** as a condition of registration.
- It is read by **commodity handheld scanners** (the same class of reader used in
  any veterinary clinic), at arm's length, while the horse stands still.
- A scan returns the chip's ID, which TrackSense resolves to the horse's registry
  identity and its complete record history.

This is a deliberate departure from the prior product direction. TrackSense does
**not** depend on UHF Gen2 lip implants, fixed-gate finish-line readers, or
race-speed RF detection. Identity is a deliberate, point-of-care scan by an
official or vet — not an automatic gate read.

**The microchip is an identity/scan tool, not HISA's registration key.**
Regulatory research (HISA Rule Series 2000/9000) found that HISA registers a
Covered Horse by **name + year of birth + dam + owner ID**, and coverage begins
on the date of the horse's **first timed-and-reported workout** — the Registration
Rule does not mandate a microchip standard or a Jockey Club / HISA horse ID.
TrackSense therefore uses the chip as the internal operational join key and a
convenient point-of-care scan, while modeling the horse's HISA identity by those
canonical fields (`dam_name`, `covered_since`, year of birth) in the data layer.

---

## Data Captured → HISA Rules Satisfied

Every record type maps to one or more HISA rules across the **Racetrack Safety
Program** and the **Anti-Doping and Medication Control (ADMC) Program**. The
mapping below is the target for the Phase 3 reporting module; the authoritative,
endpoint-level mapping will live in `docs/HISA_RULE_MAPPING.md`.

| Data captured in TrackSense | HISA rule(s) it feeds |
|-----------------------------|-----------------------|
| **Surface condition / track geometry logs** (daily surface condition, slope/design measurements) | **Rule 2151 / 2154** — track surface design and slope measurements |
| **Vaccination & monitoring records** (vaccination status, racehorse monitoring) | **Rule 2143** — vaccination and racehorse monitoring |
| **Veterinary inspections** (pre-race, post-race, scratches, fit-to-run) | **Rules 2230s** — veterinary inspections |
| **Riding-crop usage / violations** (crop use recorded against a ride) | **Rules 2280 / 2281** — riding crop usage and violations |
| **Stewards' inquiries & rulings** (inquiry, finding, disposition) | **Stewards' rulings** — 48-hour submission requirement |
| **Timed workout logs** (date, distance, surface, time, location) | **Timed and Reported Workouts** — workout reporting |
| **Treatment & medication records** (substance, dose, route, date, administering vet) | **ADMC** — treatment records |
| **Test-barn sample chain of custody** (check-in, sample collection, custody handoffs, check-out) | **ADMC** — sample chain of custody |
| **Horse identity & registration link** (chip scan → registry ID, covered-horse status) | Identity verification underpinning all of the above |
| **Biosensor / wearable telemetry** (heart rate, temperature, stride) | Supporting welfare & safety monitoring data |

> **Note:** rule numbers above come from the v2.0 roadmap and should be
> re-verified against the current HISA rulebook (exact section numbers, reporting
> windows, and submission formats) when Phase 3 builds each submission schema.
> Phase 3 (HISA Reporting Module) owns `docs/HISA_RULE_MAPPING.md` and the precise
> per-rule data-source → submission-endpoint mapping.

---

## What Carries Over From the Existing Codebase

The pivot keeps the durable backend the prior phases already built and tested.
These remain the foundation of v2.0:

- **Race lifecycle engine** — IDLE → ARMED → RUNNING → FINISHED (reframed as race
  day operations state, not timing state).
- **Welfare workflows** — workouts, check-ins, test barn, vet records.
- **Biosensor integration** — heart rate, temperature, stride rate.
- **Thermal chip temperature capture.**
- **Multi-tenancy** — per-organization isolation (tracks, training centers).
- **JWT auth + refresh** and **user management with RBAC**.
- **API key system** with rate limiting.
- **Audit log** — every official action timestamped and attributed.
- **Webhooks** — retry, delivery log, HMAC-SHA256 signing.
- **Industry-format exports** — Racing Australia, BHA, Jockey Club.
- **Mobile-optimised views** and the check-in scanner UI.
- **GateSmart webhook integration** — reframed: instead of in-race sectional data,
  it pushes workout + welfare data so GateSmart's Secretariat handicapping engine
  consumes training history and welfare flags (see Phase 1 in `ROADMAP.md`).

## What's New in v2.0

- **Jockey Club LF chip identity** — handheld scanners, ISO 11784/11785 FDX-B.
- **HISA-specific reporting schemas.**
- **Training center module.**
- **Refined race day operations module.**
- **Compliance dashboard.**

## What the Prior Product Direction Dropped

See `docs/PIVOT_NOTES.md` for the full story. In short, v2.0 removes the UHF Gen2
lip-implant architecture, fixed-gate readers, the LLRP/sllurp integration, the
broadcast TrackMap (60fps animation), live in-race sectional timing, the
sllurp/Impinj R220/Times-7 hardware path, and the hardware procurement and field
test plan. Identity becomes a point-of-care LF chip scan rather than an automatic
UHF gate read. The detailed v1.0 hardware documents are preserved under
`docs/archive/` for reference.

---

## Architecture (Summary)

```text
┌─────────────────────────────────────────────────────────────┐
│  CAPTURE LAYER                                                │
│  Handheld LF microchip scanner (ISO 11784/11785)             │
│  Officials / vets / trainers entering records via the app    │
│  Optional race-day biosensor wearable (telemetry)            │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API (JWT / RBAC)
┌────────────────────────▼────────────────────────────────────┐
│  BACKEND (FastAPI, Python 3.12)                               │
│   • Horse identity resolution (chip ID → registry → records)  │
│   • Welfare workflows: workouts, check-ins, test barn         │
│   • Veterinary & treatment records                            │
│   • Race lifecycle (entries, results)                         │
│   • HISA submission assembly (Phase 3)                        │
│   • Multi-tenancy · Audit log · Webhooks · Industry exports   │
│   • PostgreSQL (SQLite in dev) via SQLAlchemy                 │
└────────────────────────┬────────────────────────────────────┘
                         │ REST
┌────────────────────────▼────────────────────────────────────┐
│  FRONTEND (React 19 + Vite + Tailwind)                        │
│   • Horse profile & identity                                  │
│   • Training center: treatments, workouts, vet records        │
│   • Race day: paddock check-in, pre-race inspection, test barn│
│   • Compliance dashboard / submission review (Phase 3)        │
│   • Admin: users, webhooks, API keys                          │
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
| Auth             | JWT (python-jose) + bcrypt, role-based access    |
| Integrations     | Webhooks (outbound), industry-format exports     |
| Dev launcher     | start.sh (schema check, auto-seed, health check) |
| Containerisation | Docker + Docker Compose                          |

---

## Running Locally

```bash
./start.sh
```

This single command starts the FastAPI backend on
<http://localhost:8001>, auto-seeds the development database if empty, and
starts the React frontend on <http://localhost:5173>.

**Login:** `admin` / `tracksense`

See `README.md` for more detail and `ROADMAP.md` for the six-phase pivot plan.
