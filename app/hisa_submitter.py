"""
hisa_submitter.py — Pluggable delivery layer for assembled HISA submissions.

Research finding: HISA has no public submission API. Only veterinary treatment /
medication records have a sanctioned vendor integration path today (HVMS,
EquiTrace), obtained via private partnership; everything else is portal entry.

This module isolates *how* a submission is delivered behind a small interface so
the rest of the app doesn't care:

  - PortalExportSubmitter  → the default: TrackSense assembles the payload, an
    official downloads it and uploads it to the HISA/HIWU portal manually. We just
    record that it was exported/submitted.
  - PartnerApiSubmitter    → the seam for a future HISA vendor integration for
    treatment records. No partner endpoint is wired yet, so it falls back to
    marking the record and noting that direct submission is not configured. When a
    partnership is established, fill in the HTTP call in `_deliver`.

`get_submitter(rule_category)` picks the right one based on the report type's
channel in hisa_meta.
"""
import json
import os

from app import crud, hisa_meta


class HisaSubmitter:
    """Base interface for delivering an assembled HISA submission."""
    channel = None

    def submit(self, db, submission, user_id=None) -> dict:
        raise NotImplementedError


class PortalExportSubmitter(HisaSubmitter):
    """Manual portal path — mark exported/submitted; official uploads the JSON."""
    channel = hisa_meta.CHANNEL_PORTAL

    def submit(self, db, submission, user_id=None) -> dict:
        crud.mark_submission_submitted(db, submission.id, user_id=user_id)
        return {
            "channel": self.channel,
            "delivered": False,
            "method": "portal_export",
            "message": "Marked exported — upload the payload to the HISA portal manually.",
        }


class PartnerApiSubmitter(HisaSubmitter):
    """Seam for a future HISA vendor integration (treatment records).

    Configure via HISA_PARTNER_API_URL / HISA_PARTNER_API_KEY once a partnership
    exists; until then this safely falls back to marking the record and recording
    that direct submission is not wired.
    """
    channel = hisa_meta.CHANNEL_VENDOR

    def __init__(self, api_url=None, api_key=None):
        self.api_url = api_url
        self.api_key = api_key

    def submit(self, db, submission, user_id=None) -> dict:
        if not self.api_url:
            crud.mark_submission_submitted(db, submission.id, user_id=user_id)
            submission.response_json = json.dumps({
                "note": "PartnerApiSubmitter stub — no HISA partner integration "
                        "configured. Set HISA_PARTNER_API_URL to enable direct submission.",
            })
            db.commit()
            return {
                "channel": self.channel,
                "delivered": False,
                "method": "partner_api_stub",
                "message": "HISA vendor integration not configured — queued for review.",
            }
        return self._deliver(db, submission, user_id=user_id)

    def _deliver(self, db, submission, user_id=None) -> dict:
        # Future: POST submission.payload_json to self.api_url with auth headers,
        # parse the partner response, and store it on submission.response_json.
        raise NotImplementedError("Live HISA partner API submission is not implemented yet")


def get_submitter(rule_category: str) -> HisaSubmitter:
    """Pick the submitter for a report type based on its submission channel."""
    if hisa_meta.is_vendor_submittable(rule_category):
        return PartnerApiSubmitter(
            api_url=os.getenv("HISA_PARTNER_API_URL"),
            api_key=os.getenv("HISA_PARTNER_API_KEY"),
        )
    return PortalExportSubmitter()
