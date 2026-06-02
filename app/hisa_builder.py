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

def build_treatment_submission(treatment, horse=None) -> dict:
    """
    HISA Anti-Doping and Medication Control (ADMC) — Treatment Record.
    Required: substance, dose, route, date, administering vet.
    """
    return {
        "hisa_report_type": "ADMC_TREATMENT",
        "generated_at": _now_iso(),
        "horse": {
            "jockey_club_chip_id": treatment.horse_chip_id,
            "name": horse.name if horse else None,
        },
        "treatment": {
            "date": treatment.treatment_date,
            "substance": treatment.substance,
            "dose": treatment.dose,
            "route": treatment.route,
            "withdrawal_time_hours": treatment.withdrawal_time_hours,
            "prescribed_by": treatment.prescribed_by,
            "administered_by": treatment.administered_by,
            "is_prohibited_substance": treatment.is_prohibited,
            "race_id": treatment.race_id,
            "notes": treatment.notes,
        },
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
