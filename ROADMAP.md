# TrackSense v2.0 — Roadmap

**Product:** TrackSense is a **HISA compliance platform for US thoroughbred
racing**, built around three operational modules — **race day operations**,
**training center workflows**, and **Jockey Club chip-based identity** — that
generate regulatory submissions automatically as a byproduct of daily operations.

**Market position:** TrackSense sits alongside FinishLynx (photo finish), TPD
(GPS sectionals), and incumbent betting-data providers. It does **not** compete
with them — it becomes the operational and compliance layer *underneath*,
ingesting their outputs and producing HISA-ready submissions from operational data.

See `PROJECT_DESCRIPTION.md` for the product and `docs/PIVOT_NOTES.md` for the
v1.0 → v2.0 story.

## Strategic Shift From v1.0

**Dropped:** UHF Gen2 lip implant architecture · fixed-gate readers · LLRP/sllurp
integration · broadcast TrackMap (60fps animation) · live sectional timing during
races · sllurp/Impinj R220/Times-7 hardware path · hardware procurement and field
test plan.

**Kept:** race lifecycle engine (IDLE → ARMED → RUNNING → FINISHED) · welfare
workflows (workouts, check-ins, test barn, vet records) · biosensor integration
(heart rate, temperature, stride rate) · thermal chip temperature capture ·
multi-tenancy · JWT auth + refresh · API key system with rate limiting · audit log
· user management with RBAC · webhooks (retry, delivery log, HMAC-SHA256 signing) ·
industry-format exports (Racing Australia, BHA, Jockey Club) · mobile-optimised
views and check-in scanner UI · GateSmart webhook integration (reframed — see Phase 1).

**Added:** Jockey Club LF chip identity (handheld scanners, ISO 11784/11785 FDX-B)
· HISA-specific reporting schemas · training center module · refined race day
operations module · compliance dashboard.

## Phase Overview

| Phase | Title | Duration | Status |
|-------|-------|----------|--------|
| 0 | Pivot Documentation | 1 week | ✅ Complete |
| 1 | Strip the UHF/LLRP Architecture | 2 weeks | ✅ Complete |
| 2 | LF Chip Identity Layer | 3 weeks | ✅ Complete |
| 3 | HISA Reporting Module | 5 weeks | 🟡 **IN PROGRESS** |
| 4 | Training Center Module | 4 weeks | ⬜ Not started |
| 5 | Race Day Operations Module | 4 weeks | ⬜ Not started |
| 6 | Go-To-Market | ongoing (parallel to 4–5) | ⬜ Not started |

---

## Phase 0 — Pivot Documentation (1 week) 🟡 IN PROGRESS

Update all project docs to reflect the new direction. **Documentation only — no
code changes.**

**Tasks**
- [x] Rewrite `PROJECT_DESCRIPTION.md` to describe the HISA compliance product
- [x] Rewrite `ROADMAP.md` (this document, copied into the repo)
- [x] Update `README.md` with new product framing
- [x] Archive old hardware docs to `docs/archive/`: `HARDWARE.md`,
      `HARDWARE_INSTALLATION.md`, `HARDWARE_PROCUREMENT.md`,
      `FIELD_TEST_PROTOCOL.md`, and any other UHF/Impinj/sllurp-specific docs
- [x] Create `docs/PIVOT_NOTES.md` documenting the strategic pivot decision and
      what carries over from v1.0

**Acceptance**
- All four primary docs rewritten or created
- Old hardware docs archived with `git mv` (history preserved)
- `PIVOT_NOTES.md` captures the v1.0 → v2.0 story
- No code changes
- All existing tests still pass

---

## Phase 1 — Strip the UHF/LLRP Architecture (2 weeks)

Remove what's no longer part of the product. Keep operations and welfare untouched.

**Tasks**
- [ ] Remove `sllurp` from dependencies (`requirements.txt` or `pyproject.toml`)
- [ ] Remove `hardware/reader.py` LLRP/Impinj implementation
- [ ] Remove the mock UHF reader (`hardware/mock_reader.py` if it exists)
- [ ] Remove fixed-gate reader configuration and the multi-gate full race
      tracking endpoints (positions throughout the race)
- [ ] Remove broadcast TrackMap (60fps animation, fullscreen mode, arc-length
      positioning) — keep a simple race state display only
- [ ] Remove the live WebSocket race state push (in-race visualization, not
      needed for HISA operations)
- [ ] Remove sectional time computation during a race (FinishLynx/TPD territory)
- [ ] Keep race lifecycle, reframe as race day ops state, not timing state
- [ ] Update GateSmart integration: replace the in-race sectional data webhook
      with a workout-data + welfare-data webhook. GateSmart's Secretariat
      handicapping engine consumes training history and welfare flags instead of
      live timing.
- [ ] Delete or archive Alembic migrations that reference dropped tables; add new
      migrations as needed
- [ ] Remove or stub references in `app/server.py`, `app/routes.py`, and frontend
      code that depend on dropped features

**Acceptance**
- `sllurp` removed; no references remain
- All UHF/LLRP/fixed-gate code paths deleted
- Tests pass after deletion (some tests will need removal; expected)
- Frontend builds without dead references
- GateSmart webhook reformulated and documented

---

## Phase 2 — LF Chip Identity Layer (3 weeks)

Pivot from UHF Gen2 lip implants to Jockey Club LF chips with handheld scanners.

> Implemented as `chip_id` (concise) rather than the verbose `jockey_club_chip_id`;
> UI labels it "Chip ID" with subtext naming the Jockey Club LF microchip.

**Tasks**
- [x] Replace the EPC field with the LF chip ID (`chip_id`, 15-digit ISO
      11784/11785 FDX-B) — full PK + FK rename across the data model
- [x] LF handheld scanner integration via the **HID keyboard-wedge** path (Halo,
      Datamars iMax+/GPR+, Microsensys); USB-serial driver deferred
- [x] Migration `017` renames `epc`→`chip_id` / `horse_epc`→`horse_chip_id`; seed
      regenerates horses with 15-digit chip IDs (dev verifies via fresh reseed)
- [x] Check-in workflow: scan chip → `GET /horses/{chip_id}/summary` → identity +
      welfare/compliance flags → record visit
- [x] Horse registration uses chip number as primary identifier (validated)
- [x] Document supported scanner hardware in `docs/SCANNERS.md`
- [x] Update frontend horse profile / check-in views to "Chip ID" terminology

**Acceptance**
- `jockey_club_chip_id` is the primary identifier across the data model
- At least one LF scanner integration working end-to-end (HID keyboard mode is
  sufficient as the v1 path)
- Check-in workflow demonstrates scan → horse record lookup
- Migration runs cleanly; no orphaned EPC data
- `docs/SCANNERS.md` describes supported hardware

---

## Phase 3 — HISA Reporting Module (5 weeks)

Build the compliance-as-byproduct layer. **This is the wedge.**

**Tasks**
- [ ] Create `docs/HISA_RULE_MAPPING.md` — each relevant HISA rule mapped to
      TrackSense data sources and submission endpoints
- [ ] Implement HISA submission schemas for:
  - Rule 2151 / 2154 — Track surface design and slope measurements
  - Rule 2143 — Vaccination and racehorse monitoring
  - Rules 2230s — Veterinary inspections (pre-race, post-race, scratches)
  - Rules 2280 / 2281 — Riding crop usage and violations
  - Stewards' rulings (48-hour submission requirement)
  - Timed and Reported Workouts (workout reporting)
  - Anti-Doping and Medication Control (ADMC) — treatment records, sample chain
    of custody
- [ ] Research and integrate HISA's submission mechanism: programmatic API if it
      exists, otherwise structured export formats matching the portal upload
      requirements
- [ ] Enhance audit trail: every HISA submission references the underlying
      operational events that generated it
- [ ] Build a Compliance Dashboard view: real-time compliance status per rule
      category, missing-data warnings, upcoming reporting deadlines, submission
      history with success/failure tracking
- [ ] Add HISA Officer / Compliance Coordinator role to RBAC
- [ ] Webhook events for compliance state changes (submission sent, error,
      deadline approaching)

**Acceptance**
- All listed HISA rules have a corresponding TrackSense data model and submission
  schema
- Compliance Dashboard live, populated from operational data
- HISA submission flow tested with synthetic data
- Audit trail traces every submission back to its source events
- Role-based access enforced for compliance functions

---

## Phase 4 — Training Center Module (4 weeks)

First go-to-market wedge. Daily operations for facilities training horses between
races.

**Tasks**
- [ ] Daily horse roster view per training center tenant
- [ ] Workout scheduling and recording: manual entry (handheld stopwatch sectional
      times), biosensor capture (heart rate, temperature, stride rate), optional
      treadmill integration where available
- [ ] Treatment records: medications, therapies, rest days, with HISA ADMC
      implications flagged
- [ ] Vet check log: routine, lameness, pre-shipment
- [ ] Owner-facing performance reports, auto-generated weekly and monthly
- [ ] Multi-stable support within a single training center tenant (a training
      center hosts multiple trainers/owners, each isolated)
- [ ] HISA Timed and Reported Workouts submission flow (uses Phase 3 submission
      infrastructure)
- [ ] Mobile-first UI for trackside trainers and grooms

**Acceptance**
- Training center tenant can register, add horses, log a full day of workouts and
  vet checks
- Workouts feed HISA Timed and Reported submissions automatically
- Owner reports generate without manual intervention
- Multi-stable isolation tested
- Mobile UI functional for primary workflows

---

## Phase 5 — Race Day Operations Module (4 weeks)

Refine what exists into a track-day-ready operations product.

**Tasks**
- [ ] Race card builder refinement (most of this already exists; tighten UX)
- [ ] Entry and scratch management with HISA scratch documentation built in
- [ ] Jockey / saddle cloth assignment workflow
- [ ] Pre-race vet check tablet workflow (gate-side mobile UI)
- [ ] Stewards' inquiry recording with 48-hour HISA submission generated
      automatically on save
- [ ] Official results submission to racing authorities (using existing industry
      export formats, extended with HISA)
- [ ] FinishLynx / MYLAPS / TPD results ingestion via API or file import.
      TrackSense receives the finish order and times — it does not produce them.
- [ ] Surface condition daily logging tied to HISA Rule 2151/2154 schemas
- [ ] Operations dashboard for the race day: scheduled races, scratches, vet
      flags, current race status

**Acceptance**
- Full race day can be run in TrackSense end-to-end with FinishLynx as the results
  source
- Stewards' rulings flow into HISA submissions
- Surface logs satisfy Rule 2151/2154 requirements
- Vet check tablet UI works for a gate-side workflow
- Operations dashboard reflects live race day state

---

## Phase 6 — Go-To-Market (ongoing, parallel to Phases 4–5)

Make the product sellable.

**Tasks**
- [ ] One-page marketing site (separate repo or static export from main project)
- [ ] 3-minute demo screencast walking through a HISA compliance scenario
- [ ] HISA pitch deck (PDF)
- [ ] Demo data set that looks like a real US thoroughbred operation (10 horses,
      30 days of workouts, 2 race days, full HISA submissions)
- [ ] Cold outreach kit: email templates, LinkedIn message drafts, FAQ
- [ ] Pricing model: tiered by venue size and module selection (training center /
      track / training-center+track)
- [ ] Paid expert consultation with a former racing secretary or compliance officer
      to validate the pitch before broad outreach

**Acceptance**
- Marketing site live
- Demo video recorded and hosted
- Pitch deck and PDF one-pager finalised
- At least one paid expert call completed and notes documented
- Outreach kit ready for first 20 cold contacts

---

## Key Design Decisions / Open Questions

**Entries & results are INGESTED, not authored (source-of-truth discipline).**
The product's value is aggregating *authoritative* data onto a single pane of glass
keyed to the horse's chip — not re-typing data that already exists elsewhere. In US
thoroughbred racing the **track's race office** writes the card and takes entries
(the racing secretary / InCompass), and **Equibase** is the official entry/result
data provider. So:

- An owner/trainer should **never** author a race card. Their horses' upcoming runs
  must appear **automatically** (ingested from the track race office / Equibase),
  surfaced on the horse page and a "my horses this week" view. Re-entering races by
  hand is duplicate data entry and the opposite of single-pane-of-glass.
- Manual race-card creation is a **track-admin / setup / demo** function only. In the
  app today the "Add Race" Builder is therefore admin-gated and clearly labelled as
  such — it is scaffolding, not the owner/trainer surface.
- **Open question to resolve before Phase 4/5:** do we *mirror* entries/results from a
  feed (Equibase/track) as the source of truth, or *author* them in TrackSense? This
  changes the data model and the entire Phase 5 UX. Validate with a racing
  secretary / compliance officer (pull the Phase 6 expert call forward) before
  building the ingestion vs authoring path.

**Two personas, two surfaces.** Track / racing-secretary (authors cards, runs race
day) vs owner/trainer (consumes — identity, works, treatments, compliance, and
ingested race participation). Keep these distinct; don't show authoring tools to the
consuming persona.

---

## Development Principles

- **Backend-first.** Every feature starts with a tested API endpoint.
- **Compliance as a byproduct.** Officials and trainers do their normal jobs; HISA
  submissions fall out of the captured operational data.
- **Complement, don't compete.** TrackSense ingests FinishLynx (timing) and TPD
  (sectionals) outputs; it owns identity, welfare, and compliance.
- **Reuse the durable core.** Race lifecycle, welfare workflows, biosensor,
  multi-tenancy, audit log, RBAC/JWT, API keys, webhooks, and exports carry over.
- **Multi-tenant from the start.** Tracks and training centers are isolated tenants.
