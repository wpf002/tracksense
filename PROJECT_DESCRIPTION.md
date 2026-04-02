# TrackSense — Project Description

## What TrackSense Is

TrackSense is a full-stack horse racing intelligence platform built on permanent RFID identification. At its core, every horse carries a UHF Gen2 glass capsule implant (23mm × 3.85mm) injected into the lower lip. This chip is the horse's permanent identity across its entire racing career. Every system in TrackSense — timing, tracking, records, analytics — flows from that single source of truth.

The project begins as a finish-line timing engine and expands outward into a complete race tracking and horse identity platform. The end state is a system that can tell you not just who won, but how every horse ran every meter of every race they've ever competed in, tied permanently to a chip that cannot be lost, forgotten, or misassigned.

---

## The Problem TrackSense Solves

Current horse race timing relies on visual systems — photo finish cameras, manual clockers, and equipment attached to horses before each race. These approaches have several failure points:

- Equipment must be attached and removed per race, introducing human error
- Photo finish resolves close margins visually but doesn't capture sectional data
- No continuous position tracking during a race — only start and finish
- Horse identity is managed separately from timing, creating reconciliation overhead
- Sectional performance data (how fast a horse ran each furlong) is either unavailable or expensive to capture
- Historical performance tied to a chip the horse carries permanently does not exist in most systems

TrackSense addresses all of these with a single permanent implant and a network of RFID reader gates around the track.

---

## How It Works

**The Chip**
Each horse receives a UHF Gen2 glass capsule implant in the lower lip, administered by a licensed veterinarian using a standard 12-gauge injector — the same procedure as a conventional microchip. The chip stores a unique 96-bit EPC (Electronic Product Code) that never changes. This EPC is registered against the horse's identity in the TrackSense platform at the time of implantation.

**The Track Infrastructure**
RFID reader gates are installed at key points around the track:

- Start gate
- Every furlong marker
- The finish line

Each gate consists of two or more circular-polarised UHF antennas mounted at 0.5–0.7m height (lip/nose height at race speed), connected to an Impinj or compatible UHF reader. As a horse passes through a gate, the reader detects the lip implant in an ~8ms transit window at 65 km/h, firing 2–4 reads that the system folds into a single confirmed detection event.

**The Backend**
A FastAPI backend receives tag reads from all gates, maintains race state, computes positions and sectional times, and exposes a REST + WebSocket API. All data is persisted to a database and tied to the horse's permanent chip identity.

**The Platform**
Built on top of the timing engine is a full horse identity and career management platform — race history, vet records, ownership, performance analytics, and integrations with external racing systems and data consumers.

---

## Core Design Principles

**Permanent identity over per-race tagging**
The chip goes in once. Every race, every venue, every vet visit — all tied to the same EPC for the horse's entire career.

**Hardware-accurate, not approximate**
Every technical decision is grounded in the actual physics of UHF RFID through lip tissue at race speed. No shortcuts that would fail under real conditions.

**Backend-first**
The timing engine is the foundation. Frontend dashboards, mobile apps, and integrations are built on top of a solid, tested, API-first backend.

**Build to flip**
TrackSense is designed as a product that can be sold or licensed to racing venues, governing bodies, or timing service providers. The architecture reflects that — clean APIs, multi-venue support, exportable data formats.

---

## Technology Stack

| Layer | Technology |
| --- | --- |
| Backend | FastAPI (Python) |
| Database | PostgreSQL |
| Cache / real-time state | Redis |
| Frontend | React 18 + Vite + Tailwind CSS |
| Real-time feed | WebSockets |
| Hardware interface | pyserial (serial readers) / sllurp (Impinj LLRP) |
| Containerisation | Docker + Docker Compose |
| Authentication | JWT |
| Deployment | Docker on Linux server / VPS |

---

## Who Uses TrackSense

**Race Officials / Stewards**
Authoritative timing data, official result submission, objection and dispute tools.

**Trainers**
Sectional performance data for every horse in their stable, race by race. Understand where in the race a horse gains or loses ground.

**Vets**
Horse identity confirmed by chip read. Attach health records, treatments, and clearances to the permanent horse profile.

**Venue Operators**
Race card management, gate assignment, multi-race day operations, results publication.

**GateSmart (internal integration)**
Real sectional and race performance data fed directly into the AI handicapping engine instead of relying solely on historical form guides.

**Third Parties**
Public API for form guides, tipping services, broadcast graphics, and racing media.

---

## Current State

TrackSense is a fully scaffolded and tested FastAPI backend implementing Phase 1 (finish-line timing). The core race engine is thread-safe, handles duplicate reads, rejects unknown tags, computes split times, and exposes a clean REST API. A mock reader simulates 20 horses with realistic timing and RF behaviour. Hardware reader integration (serial and TCP) is written and ready for physical testing. Docker configuration exists.

The project is ready to move into Phase 2 (multi-gate full race tracking) and parallel database/persistence work.
