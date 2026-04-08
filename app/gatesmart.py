"""
gatesmart.py

Outbound integration from TrackSense to GateSmart.
All config is read from environment variables.
All HTTP calls use httpx (async).
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

_METERS_PER_FURLONG = 201.168


# ------------------------------------------------------------------ #
# Horse mapping
# ------------------------------------------------------------------ #

async def post_horse_mapping(
    epc: str,
    horse_name: str,
    racing_api_horse_id: str,
) -> bool:
    """
    POST to GateSmart to link an EPC tag to a racing API horse ID.
    Returns True on HTTP 200, False on any error.
    """
    url = os.getenv("GATESMART_MAP_URL")
    if not url:
        logger.warning("[gatesmart] GATESMART_MAP_URL is not set — horse mapping skipped")
        return False

    body = {
        "racing_api_horse_id": racing_api_horse_id,
        "epc": epc,
        "horse_name": horse_name,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=body)

        if resp.status_code == 200:
            logger.info(
                "[gatesmart] Horse mapping success — epc=%s horse=%s racing_api_horse_id=%s",
                epc, horse_name, racing_api_horse_id,
            )
            return True

        if resp.status_code == 400:
            logger.error(
                "[gatesmart] Horse mapping rejected (400) — %s", resp.text
            )
            return False

        logger.error(
            "[gatesmart] Horse mapping unexpected status %d — %s",
            resp.status_code, resp.text,
        )
        return False

    except Exception as exc:
        logger.error("[gatesmart] Horse mapping error — %s", exc)
        return False


# ------------------------------------------------------------------ #
# Race webhook
# ------------------------------------------------------------------ #

async def fire_race_webhook(payload: dict) -> bool:
    """
    POST the race-finished payload to GateSmart with HMAC-SHA256 signing.
    Retries on network errors only (max 4 attempts: 0s, 1s, 2s, 4s delays).
    Non-retryable on HTTP 400 / 401 / 500.
    Returns True on HTTP 200, False otherwise.
    """
    url = os.getenv("GATESMART_WEBHOOK_URL")
    secret = os.getenv("TRACKSENSE_WEBHOOK_SECRET")

    if not url or not secret:
        logger.warning(
            "[gatesmart] GATESMART_WEBHOOK_URL or TRACKSENSE_WEBHOOK_SECRET not set — webhook skipped"
        )
        return False

    body_bytes = json.dumps(payload).encode()
    sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "X-TrackSense-Signature": f"sha256={sig}",
    }

    delays = [0, 1, 2, 4]
    for attempt, delay in enumerate(delays):
        if delay > 0:
            await asyncio.sleep(delay)

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, content=body_bytes, headers=headers)

            if resp.status_code == 200:
                try:
                    horses_stored = resp.json().get("horses_stored", "?")
                except Exception:
                    horses_stored = "?"
                logger.info(
                    "[gatesmart] Webhook delivered successfully — horses_stored=%s",
                    horses_stored,
                )
                return True

            if resp.status_code == 401:
                logger.error("[gatesmart] HMAC signature rejected by GateSmart")
                return False

            if resp.status_code == 400:
                logger.error(
                    "[gatesmart] Payload rejected by GateSmart — %s", resp.text
                )
                return False

            if resp.status_code == 500:
                logger.error("[gatesmart] GateSmart server error")
                return False

            logger.error("[gatesmart] Unexpected status %d", resp.status_code)
            return False

        except Exception as exc:
            logger.error(
                "[gatesmart] Network error (attempt %d/4) — %s", attempt + 1, exc
            )
            if attempt == len(delays) - 1:
                logger.error("[gatesmart] All retry attempts exhausted")
                return False
            # Will loop and wait for next delay

    return False


# ------------------------------------------------------------------ #
# Payload builder
# ------------------------------------------------------------------ #

def build_race_webhook_payload(
    race_id: str,
    venue_name: str,
    race_name: str,
    distance_furlongs: float,
    completed_at: str,
    results: list,
) -> dict:
    """
    Construct the exact payload dict GateSmart expects for a race.finished event.
    Pure data construction — no external calls.

    Each item in results must be a dict with:
        finish_position, epc, horse_name, total_time_ms, sectionals

    Each sectional must be a dict with:
        gate_name, gate_distance_furlongs, split_time_ms, speed_kmh
    """
    return {
        "race_id": race_id,
        "venue": venue_name,
        "race_name": race_name,
        "distance_furlongs": distance_furlongs,
        "completed_at": completed_at,
        "results": results,
    }


# ------------------------------------------------------------------ #
# Helper — convert in-memory tracker state to GateSmart results list
# ------------------------------------------------------------------ #

def build_gatesmart_results(tracker_state: dict) -> list:
    """
    Convert a RaceTracker.get_race_state() snapshot into the results list
    that build_race_webhook_payload expects.

    Only includes horses that have a finish position.
    Sectional gate_name is derived from the right-hand side of the
    "From → To" segment string (e.g. "Start → 4f" → "4f").
    """
    finished = [
        h for h in tracker_state.get("horses", [])
        if h.get("finish_position") is not None
    ]
    finished.sort(key=lambda h: h["finish_position"])

    results = []
    for horse in finished:
        total_time_ms = None
        for event in horse.get("events", []):
            if event.get("is_finish"):
                total_time_ms = event["elapsed_ms"]
                break

        sectionals = []
        for s in horse.get("sectionals", []):
            seg = s.get("segment", "")
            gate_name = seg.split(" → ")[-1] if " → " in seg else seg
            sectionals.append({
                "gate_name": gate_name,
                "gate_distance_furlongs": round(s["distance_m"] / _METERS_PER_FURLONG, 4),
                "split_time_ms": s["elapsed_ms"],
                "speed_kmh": s.get("speed_kmh") or 0.0,
            })

        results.append({
            "finish_position": horse["finish_position"],
            "epc": horse["horse_id"],
            "horse_name": horse["display_name"],
            "total_time_ms": total_time_ms,
            "sectionals": sectionals,
        })

    return results
