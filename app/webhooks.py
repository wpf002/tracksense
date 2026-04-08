"""
webhooks.py

Outbound webhook delivery for TrackSense.
Fires when a race finishes, pushing the full result payload to all
active subscribers.
"""

import hashlib
import hmac
import json
import threading
import time
import uuid
from datetime import datetime, timezone

import requests


# ------------------------------------------------------------------ #
# Payload builder
# ------------------------------------------------------------------ #

def _ms_to_str(ms: int | None) -> str | None:
    if ms is None:
        return None
    total_sec = ms // 1000
    mins = total_sec // 60
    secs = total_sec % 60
    milli = ms % 1000
    return f"{mins}:{secs:02d}.{milli:03d}"


def build_race_payload(race_state: dict) -> dict:
    """
    Build the outbound webhook payload from a get_race_state() snapshot.
    Only includes horses that have crossed the finish line, sorted by position.
    """
    finished = [h for h in race_state.get("horses", []) if h.get("finish_position") is not None]
    finished.sort(key=lambda h: h["finish_position"])

    results = []
    prev_elapsed = None
    for horse in finished:
        elapsed_ms = None
        # Pull elapsed_ms from the finish event
        for event in horse.get("events", []):
            if event.get("is_finish"):
                elapsed_ms = event["elapsed_ms"]
                break

        margin_ms = None
        if prev_elapsed is not None and elapsed_ms is not None:
            margin_ms = elapsed_ms - prev_elapsed
        if elapsed_ms is not None:
            prev_elapsed = elapsed_ms

        sectionals = [
            {
                "segment": s["segment"],
                "distance_m": s["distance_m"],
                "elapsed_ms": s["elapsed_ms"],
                "speed_kmh": s.get("speed_kmh"),
            }
            for s in horse.get("sectionals", [])
        ]

        results.append({
            "position": horse["finish_position"],
            "horse_id": horse["horse_id"],
            "display_name": horse["display_name"],
            "saddle_cloth": horse["saddle_cloth"],
            "elapsed_ms": elapsed_ms,
            "elapsed_str": _ms_to_str(elapsed_ms),
            "margin_ms": margin_ms,
            "sectionals": sectionals,
        })

    total_elapsed = race_state.get("elapsed_ms")

    return {
        "event": "race.finished",
        "timestamp": time.time(),
        "venue_id": race_state.get("venue_id"),
        "race_summary": {
            "total_runners": race_state.get("total_expected", len(finished)),
            "total_finished": len(finished),
            "elapsed_ms": total_elapsed,
            "elapsed_str": _ms_to_str(total_elapsed),
        },
        "results": results,
    }


# ------------------------------------------------------------------ #
# Signing
# ------------------------------------------------------------------ #

def sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Returns 'sha256=<hex_digest>'."""
    digest = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


# ------------------------------------------------------------------ #
# Delivery
# ------------------------------------------------------------------ #

def deliver_webhook(subscription, payload: dict, attempt_number: int = 1) -> bool:
    """
    POST payload to subscription.url with HMAC signature header.
    Writes a WebhookDelivery log row after every attempt (success or failure).
    Returns True on 2xx, False otherwise.
    """
    from app.database import SessionLocal
    from app.models import WebhookDelivery

    sub_id = subscription.id
    sub_name = subscription.name
    sub_url = subscription.url

    response_code = None
    response_body = None
    error_message = None
    success = False

    try:
        body = json.dumps(payload, separators=(",", ":")).encode()
        signature = sign_payload(body, subscription.secret)
        headers = {
            "Content-Type": "application/json",
            "X-TrackSense-Signature": signature,
            "X-TrackSense-Event": payload.get("event", "race.finished"),
            "User-Agent": "TrackSense-Webhook/1.0",
        }
        resp = requests.post(sub_url, data=body, headers=headers, timeout=10)
        response_code = resp.status_code
        response_body = resp.text[:4000] if resp.text else None
        success = 200 <= resp.status_code < 300
        status = "OK" if success else "FAILED"
        print(f"[webhook] {status} → {sub_name} ({sub_url}) — HTTP {resp.status_code}")
    except Exception as exc:
        error_message = str(exc)
        print(f"[webhook] ERROR → {sub_name} ({sub_url}) — {exc}")

    # Write delivery log (best-effort — never fail the caller)
    try:
        db = SessionLocal()
        try:
            db.add(WebhookDelivery(
                id=str(uuid.uuid4()),
                subscription_id=sub_id,
                attempted_at=datetime.now(timezone.utc),
                response_code=response_code,
                response_body=response_body,
                success=success,
                attempt_number=attempt_number,
                error_message=error_message,
            ))
            db.commit()
        finally:
            db.close()
    except Exception as log_exc:
        print(f"[webhook] delivery log write failed: {log_exc}")

    return success


# ------------------------------------------------------------------ #
# Fire all active subscribers
# ------------------------------------------------------------------ #

def fire_webhooks(race_state: dict) -> None:
    """
    Called (in a daemon thread) when a race finishes.
    Loads all active race.finished subscriptions and delivers in parallel threads.
    """
    from app.database import SessionLocal
    from app.models import WebhookSubscription

    try:
        payload = build_race_payload(race_state)
        db = SessionLocal()
        try:
            subs = (
                db.query(WebhookSubscription)
                .filter_by(active=True, event_type="race.finished")
                .all()
            )
        finally:
            db.close()

        if not subs:
            return

        for sub in subs:
            threading.Thread(
                target=deliver_webhook,
                args=(sub, payload),
                daemon=True,
            ).start()

    except Exception as exc:
        print(f"[webhook] fire_webhooks error: {exc}")
