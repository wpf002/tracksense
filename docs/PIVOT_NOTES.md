# TrackSense Pivot Notes — v1.0 → v2.0

This document records why TrackSense changed direction, what the original
product was, and what we keep versus remove. It exists so future contributors
understand the reasoning, not just the result.

---

## The Original v1.0 Vision

TrackSense v1.0 was a **UHF Gen2 lip-implant race-timing platform**. The core bet:

- Every thoroughbred would receive a **UHF Gen2 glass-capsule implant** in the
  lower lip, storing a 96-bit EPC as a permanent, unforgeable identity.
- **Fixed-gate finish-line readers** (Impinj R220/R420 via LLRP/sllurp, Times-7
  antennas) would detect that chip at race speed (~65 km/h) as the horse passed.
- The platform would produce **live in-race sectional timing**, finish-order
  detection, and a **broadcast-quality TrackMap** of horse positions.
- Identity, timing, welfare, and analytics would all flow from that one implant.

The pitch was "one permanent chip + a network of gate readers replaces
transponders, bibs, paper identity checks, and disconnected timing."

---

## Why It Didn't Work

The v1.0 thesis ran into four hard problems:

1. **The chip doesn't exist commercially.** A UHF Gen2 implant rated for in-body
   placement and reliable read-through-tissue at race speed is not an off-the-shelf
   product. The architecture depended on hardware that would have to be invented,
   validated, and approved — an enormous cost and risk before any value ships.
2. **FinishLynx already owns official timing.** Photo-finish is the accepted,
   regulated source of the official order of finish. Displacing it is neither
   necessary nor realistic; tracks will not swap their finish authority for a
   novel RF system.
3. **TPD already owns GPS sectionals.** Total Performance Data provides positional
   in-running and sectional data via GPS. The "sectional timing" and "broadcast
   TrackMap" value props overlapped with an entrenched incumbent.
4. **No unmet hardware need.** The market did not have a gap that a new finish-line
   RF system filled. We were proposing expensive, unproven hardware against two
   established players who already cover timing and tracking.

In short: the hardware was speculative, and the two things it would have done
well were already done well by others.

---

## The v2.0 Reframing

The pivot keeps the part of the market that **is** underserved: **HISA
compliance**. Since HISA's Racetrack Safety and ADMC programs came into force,
tracks and training centers carry a heavy, paper-heavy regulatory burden —
identity verification, vet and treatment records, workout reporting, pre-race
inspections, and sample chain of custody — with no integrated system that turns
daily operations into ready-to-file submissions.

TrackSense v2.0 is a **HISA compliance platform** built on three modules:

- **Race Day Operations** — paddock identity verification, pre-race inspection,
  scratches, post-race test-barn chain of custody.
- **Training Center Workflows** — daily treatment/vet records and timed workouts.
- **Jockey Club Chip-Based Identity** — the **existing mandated LF microchip**
  (ISO 11784/11785), read with a **commodity handheld scanner**, as the single
  key tying every record together.

Crucially, identity becomes a **deliberate point-of-care scan** by an official or
vet — not an automatic UHF gate read. No new implant. No fixed-gate readers. No
race-speed RF. And TrackSense **complements** FinishLynx (timing) and TPD
(sectionals) instead of competing with them. Compliance submissions are produced
as a **byproduct** of the operational data officials and trainers already capture.

---

## What Carries Over From v1.0 Code

The backend the prior phases built and tested is largely reusable. v2.0 keeps:

- **Race lifecycle engine** (IDLE → ARMED → RUNNING → FINISHED), reframed as race
  day operations state rather than timing state.
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
- **GateSmart webhook integration**, reframed in Phase 1: it pushes workout +
  welfare data (not in-race sectionals) so GateSmart's Secretariat handicapping
  engine consumes training history and welfare flags.

These map cleanly onto the new compliance product; they're the foundation, not
throwaway.

---

## What Gets Removed in Phase 1

Phase 1 (a separate, code-changing phase — **not** this documentation phase)
strips the UHF/timing assumptions the pivot abandons:

- **`sllurp` dependency** — removed entirely.
- **UHF / LLRP reader integration** — `hardware/reader.py` (Impinj/LLRP, serial,
  TCP) and the mock UHF reader.
- **Fixed-gate reader configuration** and the **multi-gate full-race tracking
  endpoints** (positions throughout the race).
- **Broadcast TrackMap** — 60fps animation, fullscreen mode, arc-length
  positioning (replaced by a simple race state display).
- **Live WebSocket race-state push** — in-race visualization, not needed for HISA
  operations.
- **Sectional time computation during a race** — FinishLynx/TPD territory.

The race lifecycle stays, reframed as race day ops state. GateSmart's webhook is
reformulated to carry workout + welfare data. Identity is rebuilt in Phase 2
around the LF chip scan. See `ROADMAP.md` for the full sequence.

> **Phase 0 scope reminder:** this phase is documentation only. No code, tests,
> or dependencies are changed. Code-level references to UHF / lip implants /
> sllurp that still appear in comments or docstrings are intentionally left in
> place and will be cleaned up in Phase 1.
