# TrackSense

**A HISA compliance platform for US thoroughbred racing.** TrackSense runs the
everyday operational workflows of racetracks and training centers — horse
identity checks via the mandated Jockey Club LF microchip, veterinary and
treatment records, timed workouts, pre-race inspections, and post-race sample
chain of custody — and assembles the regulatory submissions the Horseracing
Integrity and Safety Authority (HISA) requires as a **byproduct** of that data.
It complements FinishLynx (official timing) and TPD (GPS sectionals) rather than
competing with them; its wedge is identity-anchored compliance record-keeping.

> **Status:** mid-pivot from a v1.0 UHF race-timing product to this v2.0
> compliance platform. See `ROADMAP.md` for the six-phase plan and
> `docs/PIVOT_NOTES.md` for the background. v1.0 hardware docs are retained under
> `docs/archive/`.

## Quick Start (Development)

```bash
./start.sh
```

This starts everything and opens the app:

- **Backend** (FastAPI) → <http://localhost:8001>
- **Frontend** (React + Vite) → <http://localhost:5173>
- Auto-seeds the dev database (SQLite) with sample data if empty
- **Login:** `admin` / `tracksense`

Run the tests:

```bash
pytest -q
```

Build the frontend:

```bash
cd frontend && npm run build
```

## The Three Modules

1. **Race Day Operations** — paddock identity verification, pre-race veterinary
   inspection, scratches, and post-race test-barn sample chain of custody.
2. **Training Center Workflows** — daily treatment/veterinary records and timed
   workout logging for covered horses.
3. **Jockey Club Chip-Based Identity** — every covered horse scanned via its
   existing LF microchip (ISO 11784/11785), read with a commodity handheld
   scanner; the chip is TrackSense's internal join key. (HISA's own registration
   identity is name + year of birth + dam + owner, coverage starting at the first
   timed workout — the chip is a scan/identity tool, not the regulatory key.)

## Architecture Summary

```text
Handheld LF scanner + officials/vets/trainers  →  FastAPI backend  →  React frontend
       (identity & record capture)                (JWT/RBAC, multi-tenant)   (operations + compliance UI)
                                                          │
                                          PostgreSQL (SQLite in dev) via SQLAlchemy
                                          HISA submission assembly · audit log · webhooks · exports
```

- **Backend:** FastAPI (Python 3.12), SQLAlchemy + Alembic, JWT + RBAC,
  multi-tenancy, audit log, webhooks, industry exports.
- **Frontend:** React 19 + Vite + Tailwind, Zustand + TanStack Query.
- **Identity:** point-of-care LF microchip scan — no fixed-gate readers, no
  race-speed RF, no UHF implants.

## Documentation

- **[PROJECT_DESCRIPTION.md](PROJECT_DESCRIPTION.md)** — full product description,
  ecosystem positioning, and the data-captured → HISA-requirement mapping.
- **[ROADMAP.md](ROADMAP.md)** — the six-phase pivot plan (Phases 0–6).
- **[docs/PIVOT_NOTES.md](docs/PIVOT_NOTES.md)** — why the product pivoted and
  what carries over.
- **[docs/archive/](docs/archive/)** — retained v1.0 hardware documentation
  (pre-pivot, reference only).
