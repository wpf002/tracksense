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

def deliver_webhook(subscription, payload: dict) -> bool:
    """
    POST payload to subscription.url with HMAC signature header.
    Returns True on 2xx, False otherwise.
    """
    try:
        body = json.dumps(payload, separators=(",", ":")).encode()
        signature = sign_payload(body, subscription.secret)
        headers = {
            "Content-Type": "application/json",
            "X-TrackSense-Signature": signature,
            "X-TrackSense-Event": payload.get("event", "race.finished"),
            "User-Agent": "TrackSense-Webhook/1.0",
        }
        resp = requests.post(subscription.url, data=body, headers=headers, timeout=10)
        success = 200 <= resp.status_code < 300
        status = "OK" if success else "FAILED"
        print(f"[webhook] {status} → {subscription.name} ({subscription.url}) — HTTP {resp.status_code}")
        return success
    except Exception as exc:
        print(f"[webhook] ERROR → {subscription.name} ({subscription.url}) — {exc}")
        return False


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
