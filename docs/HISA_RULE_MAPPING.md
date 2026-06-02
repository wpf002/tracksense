# HISA Rule Mapping

This document maps each relevant HISA program rule to the TrackSense data source
that generates the submission and the API endpoint that assembles the payload.

**Programs:** Racetrack Safety Program (RSP) and Anti-Doping and Medication
Control (ADMC). Rule citations follow the HISA Rules effective 2023-07-01.
Verify exact section numbers and field requirements against the current HISA
rulebook before live portal submission — this mapping is based on publicly
available rule names and field requirements.

**Submission mechanism (v1):** structured JSON export for manual portal upload.
A programmatic HISA API is not publicly documented; live integration is post-pilot.

---

## Timed and Reported Workouts

| Field | Source |
|-------|--------|
| HISA program | Racetrack Safety Program |
| Rule reference | Timed and Reported Workouts |
| Requirement | All timed workouts at a licensed track must be reported within 48 hours |
| TrackSense source | `WorkoutRecord` |
| Required fields | `horse_chip_id`, `workout_date`, `distance_m`, `duration_ms`, `surface`, `trainer_name` |
| Optional enrichment | `rider_name`, `clocker_name`, `timekeeper_name`, `track_condition`, `splits_json` |
| Submission endpoint | `POST /hisa/submit/{id}` (built by `POST /hisa/build-all`) |
| Builder function | `hisa_builder.build_workout_submission` |
| API to create records | `POST /horses/{chip_id}/workouts` |
| Gap / caveat | Exact field names in HISA portal TBD; clocker/timekeeper confirmation recommended |

---

## ADMC — Treatment / Medication Records

| Field | Source |
|-------|--------|
| HISA program | Anti-Doping and Medication Control (ADMC) |
| Rule reference | ADMC Program — treatment and medication records |
| Requirement | All controlled substances administered to a covered horse must be reported |
| TrackSense source | `TreatmentRecord` |
| Required fields | `horse_chip_id`, `treatment_date`, `substance`, `dose`, `route`, `prescribed_by` |
| Key flag | `is_prohibited` — flag for prohibited/restricted substances |
| Submission endpoint | `POST /hisa/submit/{id}` (built by `POST /hisa/build-all`) |
| Builder function | `hisa_builder.build_treatment_submission` |
| API to create records | `POST /horses/{chip_id}/treatments` |
| Gap / caveat | Prohibited substance list and withdrawal times must be cross-referenced with HISA ADMC prohibited list |

---

## ADMC — Sample Chain of Custody

| Field | Source |
|-------|--------|
| HISA program | Anti-Doping and Medication Control (ADMC) |
| Rule reference | ADMC Program — post-race sample collection |
| Requirement | Documented chain of custody from collection to lab analysis |
| TrackSense source | `TestBarnRecord` |
| Required fields | `horse_chip_id`, `race_id`, `sample_id`, `checkin_at`, `checkin_by`, `checkout_at`, `checkout_by`, `result` |
| Submission endpoint | `POST /hisa/submit/{id}` (built by `POST /hisa/build-all`) |
| Builder function | `hisa_builder.build_sample_submission` |
| API to create records | `POST /horses/{chip_id}/testbarn/checkin` + `POST /testbarn/{id}/checkout` |

---

## Stewards' Rulings (48-Hour Requirement)

| Field | Source |
|-------|--------|
| HISA program | Racetrack Safety Program |
| Rule reference | Stewards' rulings — 48-hour submission |
| Requirement | All official rulings must be submitted to HISA within 48 hours of issuance |
| TrackSense source | `StewardsRuling` |
| Required fields | `ruling_date`, `rule_violated`, `description`, `deadline_at` (auto-set to ruling_date + 48h) |
| Optional fields | `race_id`, `horse_chip_id`, `jockey_name`, `penalty` |
| Auto-submission tracking | Creating a ruling via `POST /stewards/rulings` automatically creates a `HISASubmission` with `deadline_at` |
| Submission endpoint | `POST /hisa/submit/{id}` |
| Builder function | `hisa_builder.build_stewards_submission` |
| Gap / caveat | Rule 2280/2281 (riding crop) violations — deferred to Phase 5 (race-day operations context required) |

---

## Rule 2151/2154 — Track Surface & Slope

| Field | Source |
|-------|--------|
| HISA program | Racetrack Safety Program |
| Rule reference | 2151/2154 — track design, surface, and safety standards |
| Requirement | Daily track condition must be logged; surface type and going reported |
| TrackSense source | `SurfaceConditionLog` |
| Required fields | `venue_id`, `logged_date`, `surface_type`, `going_description` |
| Optional fields | `moisture_pct`, `temperature_c`, `maintenance_notes`, `logged_by` |
| Submission endpoint | `POST /hisa/submit/{id}` (built by `POST /hisa/build-all`) |
| Builder function | `hisa_builder.build_surface_submission` |
| API to create records | `POST /venues/{venue_id}/surface-conditions` |
| Gap / caveat | Slope angle measurements (% grade) are not yet captured — would require survey equipment integration or manual entry field addition |

---

## Pre-Race Identity Verification (Check-In)

| Field | Source |
|-------|--------|
| HISA program | Racetrack Safety Program |
| Rule reference | Rule 2143 / general identity verification requirement |
| Requirement | Chip ID verified against race entry before paddock entry |
| TrackSense source | `CheckInRecord` (where `race_id IS NOT NULL`) |
| Required fields | `horse_chip_id`, `race_id`, `scanned_at`, `scanned_by`, `verified` |
| Optional | `temperature_c`, `location`, `notes` |
| Submission endpoint | `POST /hisa/submit/{id}` (built by `POST /hisa/build-all`) |
| Builder function | `hisa_builder.build_checkin_submission` |
| API to create records | `POST /horses/{chip_id}/checkins` (Quick Check-In screen) |

---

## Deferred Rules (Out of Phase 3 Scope)

| Rule | Reason deferred | Target phase |
|------|----------------|--------------|
| Rule 2280/2281 — riding crop | Needs race-day console + video evidence reference | Phase 5 |
| Post-race vet inspection | Needs race-day state machine (clearance/scratch workflow) | Phase 5 |
| Rule 2143 full vaccination | Requires vaccination scheduling + expiry tracking | Phase 4 |
| Injury / fatality reports | Needs race-day incident capture | Phase 5 |

---

## Compliance Dashboard Coverage

At Phase 3 completion, the Compliance Dashboard (`/compliance`) shows:

| Submission type | Source table | Coverage |
|-----------------|-------------|---------|
| Workouts | `WorkoutRecord` | ✅ Full |
| ADMC treatments | `TreatmentRecord` | ✅ Full |
| ADMC sample chain | `TestBarnRecord` | ✅ Full |
| Stewards' rulings | `StewardsRuling` | ✅ Full (auto-deadline) |
| Surface conditions | `SurfaceConditionLog` | ✅ Full |
| Pre-race check-ins | `CheckInRecord` | ✅ Partial (race-linked only) |

Missing data warnings flag: horses with no workout records this month, venues
with no surface log this week, workouts missing clocker name.
