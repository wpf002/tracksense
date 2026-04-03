# TrackSense — Project Description

## What TrackSense Is

TrackSense is a full-stack horse racing intelligence platform built on permanent RFID identification. At its core, every horse carries a UHF Gen2 glass capsule implant (23mm × 3.85mm) injected into the lower lip. This chip is the horse's permanent identity across its entire career. Every system in TrackSense — timing, tracking, records, analytics — flows from that single source of truth.

The project begins as a finish-line timing engine and expands outward into a complete race tracking, horse identity, and horse welfare platform. The end state is a system that can tell you not just who won, but how every horse ran every metre of every race they've ever competed in, what their training looked like in the weeks before, what their health status is today, and whether they were properly cleared and checked in before they set foot on the track — all tied permanently to a chip that cannot be lost, forgotten, or misassigned.

---

## The Problem TrackSense Solves

Current horse race timing and identity management has several failure points:

- Equipment must be attached and removed per race, introducing human error
- Photo finish resolves close margins visually but doesn't capture sectional data
- No continuous position tracking during a race — only start and finish
- Horse identity is managed separately from timing, creating reconciliation overhead
- Sectional performance data is either unavailable or expensive to capture
- Pre-race identity verification is manual and paper-based
- Drug testing chain of custody is paper-based and prone to error
- Training workout data lives in trainer notebooks, not connected to race performance
- Health records are fragmented across vets, trainers, and racing authorities
- Temperature and vitals monitoring requires separate equipment with no link to horse identity

TrackSense addresses all of these with a single permanent implant and a network of systems built around it.

---

## How It Works

**The Chip**
Each horse receives a UHF Gen2 glass capsule implant in the lower lip, administered by a licensed veterinarian using a standard 12-gauge injector. The chip stores a unique 96-bit EPC (Electronic Product Code) that never changes. This EPC is registered against the horse's identity in the TrackSense platform at the time of implantation.

In Phase 5, thermal-capable chips will enable body temperature reading at scan time, linking health monitoring directly to identity.

**The Track Infrastructure**
RFID reader gates are installed at key points around the track — start gate, every furlong marker, and the finish line. Each gate consists of two or more circular-polarised UHF antennas mounted at 0.5–0.7m height (lip/nose height at race speed). As a horse passes through a gate, the reader detects the lip implant in an ~8ms transit window at 65 km/h, firing 2–4 reads that the system folds into a single confirmed detection event.

**The Pre-Race Workflow**
Before racing, horses are scanned with a handheld reader to confirm identity matches the race entry (Check-In). Horses entering the test barn post-race are scanned in and out for drug testing chain of custody. All of this is tied to the permanent EPC.

**The Training Record**
Between races, trainers log workouts against the horse's chip identity — date, distance, surface, time, and notes. This data feeds into performance analysis and form guides.

**The Backend**
A FastAPI backend receives tag reads from all gates, maintains race state, computes positions and sectional times, and exposes a REST + WebSocket API. All data is persisted to PostgreSQL and tied to the horse's permanent chip identity.

**The Platform**
Built on top of the timing engine is a full horse identity and career management platform — race history, workout logs, vet records, check-in history, test barn records, ownership, performance analytics, and integrations with external racing systems.

---

## Core Design Principles

**Permanent identity over per-race tagging**
The chip goes in once. Every race, every vet visit, every workout, every drug test — all tied to the same EPC for the horse's entire career.

**Hardware-accurate, not approximate**
Every technical decision is grounded in the actual physics of UHF RFID through lip tissue at race speed. No shortcuts that would fail under real conditions.

**Backend-first**
The timing engine is the foundation. Frontend dashboards, mobile apps, and integrations are built on top of a solid, tested, API-first backend.

**Complete horse welfare picture**
TrackSense is not just a timing system. It is the permanent record of a horse's health, training, performance, and regulatory compliance — from first implant to final race.

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
Authoritative timing data, official result submission, pre-race check-in verification, objection and dispute tools.

**Trainers**
Sectional performance data for every horse in their stable, race by race. Log workouts. Understand where in the race a horse gains or loses ground. Connect training patterns to race outcomes.

**Vets**
Horse identity confirmed by chip read. Attach health records, treatments, temperature logs, Coggins results, and clearances to the permanent horse profile.

**Venue Operators**
Race card management, gate assignment, multi-race day operations, results publication.

**Regulatory / Drug Testing**
Test barn check-in and check-out tied to chip identity. Tamper-proof chain of custody for post-race samples.

**GateSmart (internal integration)**
Real sectional and race performance data fed directly into the AI handicapping engine.

**Third Parties**
Public API for form guides, tipping services, broadcast graphics, and racing media.

---

## Competitive Landscape

**Lip Chip / HoofLink** (lipchipllc.com) is the closest existing product — a lip-implant microchip system with health records, temperature monitoring, and event check-in. Their focus is barrel racing and ranch horses using LF (low-frequency) chips with close-range Bluetooth scanning. They do not support finish-line detection at race speed, sectional timing, or thoroughbred flat racing.

TrackSense occupies the gap: UHF finish-line detection at race speed, full multi-gate tracking, sectional analytics, and the complete horse welfare workflow — all in one platform, purpose-built for thoroughbred racing.

---

## Current State

TrackSense has completed Phases 1–4:

- Phase 1: Finish-line timing engine — thread-safe, duplicate folding, REST API
- Phase 2: Multi-gate tracking — dynamic venue/gate config, sectionals, WebSocket feed
- Phase 3: PostgreSQL persistence — full horse identity platform, career analytics
- Phase 4: React frontend — Live Race, Results, Horse Registry, Race Builder

Phase 5 work is underway with workout logging, pre-race check-in, and test barn models added to the database layer.
