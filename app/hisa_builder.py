"""
hisa_builder.py

Pure functions that assemble HISA submission payloads from TrackSense operational
records. Each function takes an ORM record (or dict) and returns a Python dict
that gets JSON-serialised into HISASubmission.payload_json.

IMPORTANT: These payloads are structured to be HISA-compatible based on publicly
known rule requirements (rule number, required fields, timing). The exact portal
upload format must be verified against the HISA portal before live submission.
v1 ships the value — officials review and download the JSON, then upload manually.
"""

from datetime import datetime, timezone


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _date_str(dt) -> str:
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)


# ------------------------------------------------------------------ #
# HISA Timed and Reported Workouts
# ------------------------------------------------------------------ #

def build_workout_submission(workout, horse=None) -> dict:
    """
    HISA Racetrack Safety Program — Timed and Reported Workouts.
    Required: horse chip ID, date, distance, time, surface, trainer.
    """
    return {
        "hisa_report_type": "TIMED_REPORTED_WORKOUT",
        "generated_at": _now_iso(),
        "horse": {
            "jockey_club_chip_id": workout.horse_chip_id,
            "name": horse.name if horse else None,
        },
        "workout": {
            "date": workout.workout_date,
            "distance_m": workout.distance_m,
            "surface": workout.surface,
            "track_condition": workout.track_condition,
            "duration_ms": workout.duration_ms,
            "duration_seconds": round(workout.duration_ms / 1000, 2) if workout.duration_ms else None,
            "trainer": workout.trainer_name,
            "exercise_rider": workout.rider_name,
            "clocker": workout.clocker_name,
            "timekeeper": workout.timekeeper_name,
            "source": workout.source,
            "notes": workout.notes,
        },
    }


# ------------------------------------------------------------------ #
# ADMC — Treatment / Medication Record
# ------------------------------------------------------------------ #

def _current_trainer(horse) -> str:
    """Best-effort current trainer name (the HISA 'Responsible Person')."""
    if horse is None:
        return None
    trainers = getattr(horse, "trainers", None) or []
    # prefer an open assignment (no to_date), else the last one on file
    current = next((t for t in trainers if getattr(t, "to_date", None) in (None, "")), None)
    current = current or (trainers[-1] if trainers else None)
    return getattr(current, "trainer_name", None) if current else None


def build_treatment_submission(treatment, horse=None) -> dict:
    """
    HISA Anti-Doping and Medication Control (ADMC) — Treatment Record (Rule 2251(b)).

    The attending veterinarian must submit, within 24 hours, the ~11 enumerated
    fields below. Horse identity uses HISA's keys (name + year of birth + dam),
    not the microchip; the microchip is included only as an operational reference.
    """
    dob = getattr(horse, "date_of_birth", None) if horse else None
    return {
        "hisa_report_type": "ADMC_TREATMENT",
        "rule_reference": "Rule 2251(b)",
        "generated_at": _now_iso(),
        # (01) identity of the Covered Horse — HISA keys: name + year of birth + dam
        "covered_horse": {
            "name": horse.name if horse else None,
            "year_of_birth": (str(dob)[:4] if dob else None),
            "dam_name": getattr(horse, "dam_name", None) if horse else None,
            "covered_since": getattr(horse, "covered_since", None) if horse else None,
            "microchip_ref": treatment.horse_chip_id,  # operational reference only, not the HISA key
        },
        # (02) Responsible Person (trainer)
        "responsible_person": _current_trainer(horse),
        # (03) veterinarian + (04) contact info
        "veterinarian": {
            "name": treatment.prescribed_by or treatment.administered_by,
            "phone": getattr(treatment, "vet_phone", None),
            "email": getattr(treatment, "vet_email", None),
        },
        # (05) unsoundness / diagnostic responses, (06) clinical diagnosis, (07) condition treated
        "diagnosis": getattr(treatment, "diagnosis", None),
        "condition_treated": getattr(treatment, "condition_treated", None),
        # (08) medications with date & time of dose, route, frequency, duration
        "medications": [
            {
                "substance": treatment.substance,
                "dose": treatment.dose,
                "route": treatment.route,
                "date": treatment.treatment_date,
                "time": getattr(treatment, "treatment_time", None),
                "frequency": getattr(treatment, "frequency", None),
                "duration": getattr(treatment, "duration", None),
                "withdrawal_time_hours": treatment.withdrawal_time_hours,
                "is_prohibited_substance": treatment.is_prohibited,
            }
        ],
        # (09)/(10) non-surgical & surgical procedures with timing
        "procedures": getattr(treatment, "procedure", None),
        # (11) other health / welfare information
        "other_information": treatment.notes,
        "administered_by": treatment.administered_by,
        "race_id": treatment.race_id,
    }


# ------------------------------------------------------------------ #
# ADMC — Sample Chain of Custody (Test Barn)
# ------------------------------------------------------------------ #

def build_sample_submission(testbarn, horse=None) -> dict:
    """
    HISA Anti-Doping and Medication Control (ADMC) — Sample Chain of Custody.
    """
    return {
        "hisa_report_type": "ADMC_SAMPLE_CHAIN",
        "generated_at": _now_iso(),
        "horse": {
            "jockey_club_chip_id": testbarn.horse_chip_id,
            "name": horse.name if horse else None,
        },
        "sample": {
            "race_id": testbarn.race_id,
            "sample_id": testbarn.sample_id,
            "checkin_at": _date_str(testbarn.checkin_at),
            "checkin_by": testbarn.checkin_by,
            "checkout_at": _date_str(testbarn.checkout_at),
            "checkout_by": testbarn.checkout_by,
            "result": testbarn.result,
            "notes": testbarn.notes,
        },
    }


# ------------------------------------------------------------------ #
# Stewards' Ruling — 48-hour submission
# ------------------------------------------------------------------ #

def build_stewards_submission(ruling, horse=None) -> dict:
    """
    HISA Racetrack Safety Program — Stewards' Ruling (48-hour requirement).
    """
    return {
        "hisa_report_type": "STEWARDS_RULING",
        "generated_at": _now_iso(),
        "ruling": {
            "ruling_date": _date_str(ruling.ruling_date),
            "deadline_at": _date_str(ruling.deadline_at),
            "race_id": ruling.race_id,
            "rule_violated": ruling.rule_violated,
            "description": ruling.description,
            "penalty": ruling.penalty,
            "jockey_name": ruling.jockey_name,
        },
        "horse": {
            "jockey_club_chip_id": ruling.horse_chip_id,
            "name": horse.name if horse else None,
        } if ruling.horse_chip_id else None,
    }


# ------------------------------------------------------------------ #
# Rule 2151/2154 — Track Surface Condition
# ------------------------------------------------------------------ #

def build_surface_submission(surface_log) -> dict:
    """
    HISA Racetrack Safety Program — Rule 2151/2154 Surface Condition Report.
    """
    return {
        "hisa_report_type": "SURFACE_CONDITION",
        "rule_reference": "2151/2154",
        "generated_at": _now_iso(),
        "venue_id": surface_log.venue_id,
        "surface": {
            "logged_date": surface_log.logged_date,
            "surface_type": surface_log.surface_type,
            "going_description": surface_log.going_description,
            "moisture_pct": surface_log.moisture_pct,
            "temperature_c": surface_log.temperature_c,
            "maintenance_notes": surface_log.maintenance_notes,
            "logged_by": surface_log.logged_by,
        },
    }


# ------------------------------------------------------------------ #
# Pre-race Identity Verification (Check-In)
# ------------------------------------------------------------------ #

def build_checkin_submission(checkin, horse=None) -> dict:
    """
    HISA Racetrack Safety Program — Pre-race identity verification / check-in.
    """
    return {
        "hisa_report_type": "CHECKIN_IDENTITY",
        "generated_at": _now_iso(),
        "horse": {
            "jockey_club_chip_id": checkin.horse_chip_id,
            "name": horse.name if horse else None,
        },
        "checkin": {
            "race_id": checkin.race_id,
            "scanned_at": _date_str(checkin.scanned_at),
            "scanned_by": checkin.scanned_by,
            "location": checkin.location,
            "verified": checkin.verified,
            "temperature_c": checkin.temperature_c,
            "notes": checkin.notes,
        },
    }


# ------------------------------------------------------------------ #
# Phase 5 — Race Day Operations
# ------------------------------------------------------------------ #

def build_scratch_submission(scratch, horse=None, race=None) -> dict:
    """HISA Racetrack Safety Program — Scratch documentation."""
    return {
        "hisa_report_type": "SCRATCH",
        "generated_at": _now_iso(),
        "horse": {
            "jockey_club_chip_id": scratch.horse_chip_id,
            "name": horse.name if horse else None,
        },
        "scratch": {
            "race_id": scratch.race_id,
            "venue_id": race.venue_id if race else None,
            "race_date": race.race_date.isoformat() if race and race.race_date else None,
            "scratch_type": scratch.scratch_type,
            "declared_by": scratch.declared_by,
            "reason": scratch.reason,
            "declared_at": _date_str(scratch.declared_at),
        },
    }


def build_crop_violation_submission(violation, horse=None, race=None) -> dict:
    """HISA Racetrack Safety Program — Rule 2280/2281 Riding Crop Violation."""
    return {
        "hisa_report_type": "RIDING_CROP_VIOLATION",
        "rule_reference": "2280/2281",
        "generated_at": _now_iso(),
        "race": {
            "race_id": violation.race_id,
            "venue_id": race.venue_id if race else None,
            "race_date": violation.race_date or (race.race_date.isoformat() if race and race.race_date else None),
        },
        "horse": {
            "jockey_club_chip_id": violation.horse_chip_id,
            "name": horse.name if horse else None,
        } if violation.horse_chip_id else None,
        "violation": {
            "jockey_name": violation.jockey_name,
            "crop_count": violation.crop_count,
            "violation_determined": violation.violation_determined,
            "penalty": violation.penalty,
            "official_name": violation.official_name,
            "notes": violation.notes,
        },
    }
