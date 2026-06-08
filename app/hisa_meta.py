"""
hisa_meta.py — Single source of truth for HISA report-type metadata.

Every operational record TrackSense turns into a HISA submission belongs to a
report category. This registry records, per category: a human label, the party
actually responsible for filing it to HISA, the filing deadline, and the
SUBMISSION CHANNEL — i.e. whether a third-party software vendor can submit it
programmatically today.

Per regulatory research (HISA Rule Series 2000/3000/9000, the HIWU ADMC program,
and HISA's own Veterinary Advisory + FAQ): only veterinary treatment / medication
records (Rule 2251) have a sanctioned vendor submission path today (live examples:
HVMS, EquiTrace). Every other record type is portal entry by the racetrack /
regulatory vet / HIWU / stewards — so TrackSense can only ASSEMBLE and EXPORT
those payloads for manual upload, not auto-submit them.

`confirmed: False` flags categories whose exact reporter/deadline/fields were not
pinned down in the research and must be verified with HISA before relying on them.
"""

# Submission channels
CHANNEL_VENDOR = "vendor"   # a software vendor can submit programmatically (HISA partner integration)
CHANNEL_PORTAL = "portal"   # manual HISA/HIWU portal entry only — TrackSense exports the payload

REPORT_TYPES = {
    "ADMC_TREATMENT": {
        "label": "Vet Treatment / Medication",
        "responsible_party": "Attending Veterinarian",
        "deadline": "Within 24 hours of treatment",
        "channel": CHANNEL_VENDOR,
        "rule_ref": "ADMC Rule 2251(b)",
        "confirmed": True,
    },
    "ADMC_SAMPLE": {
        "label": "ADMC Sample / Chain of Custody",
        "responsible_party": "HIWU Sample Collection Personnel",
        "deadline": "Race day",
        "channel": CHANNEL_PORTAL,
        "rule_ref": "HIWU ADMC Program",
        "confirmed": True,
    },
    "CHECKIN": {
        "label": "Pre-race Veterinary Inspection",
        "responsible_party": "Regulatory Veterinarian",
        "deadline": "Day of inspection",
        "channel": CHANNEL_PORTAL,
        "rule_ref": "Racetrack Safety Rule 2280",
        "confirmed": True,
    },
    "WORKOUTS": {
        "label": "Timed & Reported Workout",
        "responsible_party": "Racetrack / Clocker",
        "deadline": "Per Racetrack Safety Program",
        "channel": CHANNEL_PORTAL,
        "rule_ref": "Racetrack Safety Rule Series 2000",
        "confirmed": False,  # exact reporter/deadline/fields not pinned down — verify with HISA
    },
    "SURFACE": {
        "label": "Track Surface / Maintenance Log",
        "responsible_party": "Racetrack",
        "deadline": "Within 1 week of test",
        "channel": CHANNEL_PORTAL,
        "rule_ref": "Racetrack Safety Rule 2151",
        "confirmed": True,
    },
    "STEWARDS_RULING": {
        "label": "Stewards' Ruling",
        "responsible_party": "Stewards",
        "deadline": "Per adjudication rules",
        "channel": CHANNEL_PORTAL,
        "rule_ref": "Rule Series 8000",
        "confirmed": False,
    },
    "SCRATCH": {
        "label": "Scratch",
        "responsible_party": "Regulatory Vet (notifies) → Stewards",
        "deadline": "Race day",
        "channel": CHANNEL_PORTAL,
        "rule_ref": "Racetrack Safety Rule 2135",
        "confirmed": True,
    },
    "CROP_VIOLATION": {
        "label": "Riding Crop Violation",
        "responsible_party": "Stewards / Officials",
        "deadline": "Race day",
        "channel": CHANNEL_PORTAL,
        "rule_ref": "Racetrack Safety Rule 2280",
        "confirmed": True,
    },
}

_DEFAULT = {
    "label": "HISA Submission",
    "responsible_party": "—",
    "deadline": "—",
    "channel": CHANNEL_PORTAL,
    "rule_ref": "—",
    "confirmed": False,
}


def meta_for(rule_category: str) -> dict:
    """Return the registry entry for a rule category (falls back to a safe default)."""
    return REPORT_TYPES.get(rule_category, _DEFAULT)


def is_vendor_submittable(rule_category: str) -> bool:
    """True only for report types a software vendor can submit programmatically today."""
    return meta_for(rule_category)["channel"] == CHANNEL_VENDOR
