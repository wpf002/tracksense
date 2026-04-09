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

def _attempt_delivery(subscription, payload: dict) -> tuple[bool, int | None, str | None]:
    """
    Execute a single HTTP POST attempt.
    Returns (success, response_code, error_message).
    Does NOT write to the DB — callers handle logging.
    """
    sub_url = subscription.url
    sub_name = subscription.name

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
        success = 200 <= resp.status_code < 300
        status = "OK" if success else "FAILED"
        print(f"[webhook] {status} → {sub_name} ({sub_url}) — HTTP {resp.status_code}")
        return success, resp.status_code, None
    except Exception as exc:
        print(f"[webhook] ERROR → {sub_name} ({sub_url}) — {exc}")
        return False, None, str(exc)


def _write_delivery_log(
    subscription_id: int,
    attempt_number: int,
    success: bool,
    response_code: int | None,
    response_body: str | None,
    error_message: str | None,
) -> None:
    """Write one WebhookDelivery row. Best-effort — never raises."""
    from app.database import SessionLocal
    from app.models import WebhookDelivery
    try:
        db = SessionLocal()
        try:
            db.add(WebhookDelivery(
                id=str(uuid.uuid4()),
                subscription_id=subscription_id,
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


def deliver_webhook(subscription, payload: dict, attempt_number: int = 1) -> bool:
    """
    POST payload to subscription.url with HMAC signature header.
    Writes a WebhookDelivery log row after every attempt (success or failure).
    Returns True on 2xx, False otherwise.
    """
    success, response_code, error_message = _attempt_delivery(subscription, payload)

    # Capture response body for the log (re-build it — _attempt_delivery didn't return it)
    # response_body isn't needed for retry decisions so we skip it for simplicity.
    _write_delivery_log(
        subscription_id=subscription.id,
        attempt_number=attempt_number,
        success=success,
        response_code=response_code,
        response_body=None,
        error_message=error_message,
    )

    return success


# ------------------------------------------------------------------ #
# Retry delivery with exponential backoff
# ------------------------------------------------------------------ #

_RETRY_DELAYS = [5, 30]   # seconds between attempts 1→2 and 2→3 (3 attempts total)
_MAX_ATTEMPTS = len(_RETRY_DELAYS) + 1   # 3


def deliver_webhook_with_retry(subscription, payload: dict) -> None:
    """
    Deliver a webhook payload with up to 3 attempts (initial + 2 retries) on
    network errors or HTTP 5xx responses. Delays between attempts: 5s, 30s.
    The final attempt is attempt_number 3; after that delivery is abandoned.
    HTTP 4xx responses are not retried.
    Writes a WebhookDelivery row for every attempt.
    """
    for attempt_number in range(1, _MAX_ATTEMPTS + 1):   # 1, 2, 3
        success, response_code, error_message = _attempt_delivery(subscription, payload)

        _write_delivery_log(
            subscription.id,
            attempt_number,
            success,
            response_code,
            None,
            error_message,
        )

        if success:
            return  # Done — stop retrying

        # HTTP 4xx — do not retry
        if response_code is not None and 400 <= response_code < 500:
            print(f"[webhook] HTTP {response_code} — not retrying (4xx)")
            return

        # No more attempts
        if attempt_number == _MAX_ATTEMPTS:
            print(f"[webhook] All retries exhausted for {subscription.name} ({subscription.url})")
            return

        delay = _RETRY_DELAYS[attempt_number - 1]
        print(f"[webhook] Attempt {attempt_number} failed — retrying in {delay}s")
        time.sleep(delay)


# ------------------------------------------------------------------ #
# Fire all active subscribers
# ------------------------------------------------------------------ #

def fire_webhooks(race_state: dict) -> None:
    """
    Called (in a daemon thread) when a race finishes.
    Loads all active race.finished subscriptions and delivers in parallel threads,
    each with exponential-backoff retry.
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
                target=deliver_webhook_with_retry,
                args=(sub, payload),
                daemon=True,
            ).start()

    except Exception as exc:
        print(f"[webhook] fire_webhooks error: {exc}")
