"""
app/exports_router.py

Industry-format export endpoints for race results.

Supported formats:
  - Racing Australia XML   GET /races/{id}/export/racing-australia
  - BHA JSON               GET /races/{id}/export/bha
  - Jockey Club XML        GET /races/{id}/export/jockey-club

All endpoints require JWT or API key authentication.
Returns 404 if the race does not exist.
Returns 409 if the race has no results yet (not finished).
"""

from datetime import timezone
from xml.etree.ElementTree import Element, SubElement, tostring, indent
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud
from app.api_keys_router import require_jwt_or_api_key

router = APIRouter()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_finished_race(race_id: int, db: Session):
    """Return race or raise 404/409."""
    race = crud.get_race(db, race_id)
    if not race:
        raise HTTPException(status_code=404, detail=f"Race {race_id} not found")
    if race.status != "finished" or not race.results:
        raise HTTPException(
            status_code=409,
            detail=f"Race {race_id} has no results yet (status={race.status})",
        )
    return race


def _elapsed_to_time_str(elapsed_ms: int) -> str:
    """Convert milliseconds to m:ss.mmm string, e.g. 1:23.456"""
    total_s = elapsed_ms / 1000.0
    minutes = int(total_s // 60)
    seconds = total_s % 60
    return f"{minutes}:{seconds:06.3f}"


def _race_date_str(race) -> str:
    if race.race_date:
        dt = race.race_date
        if dt.tzinfo is None:
            return dt.strftime("%Y-%m-%d")
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
    return ""


def _race_datetime_str(race) -> str:
    if race.race_date:
        dt = race.race_date
        if dt.tzinfo is None:
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return ""


# ─── Racing Australia XML ──────────────────────────────────────────────────────

@router.get("/races/{race_id}/export/racing-australia",
            summary="Export race results in Racing Australia XML format")
def export_racing_australia(
    race_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_jwt_or_api_key),
):
    """
    Racing Australia Results XML (simplified RA schema).

    Root element: <RaceResults>
      Attributes: schemaVersion, exportedAt
      Child: <Race> with race metadata
        Children: <Result> per finishing position
    """
    race = _get_finished_race(race_id, db)
    sorted_results = sorted(race.results, key=lambda r: r.finish_position)

    root = Element("RaceResults")
    root.set("schemaVersion", "1.0")
    root.set("exportedAt", _race_datetime_str(race))

    race_el = SubElement(root, "Race")
    race_el.set("id", str(race.id))
    race_el.set("name", race.name or f"Race {race.id}")
    race_el.set("date", _race_date_str(race))
    race_el.set("venueId", race.venue_id)
    race_el.set("distanceM", str(race.distance_m))
    race_el.set("surface", race.surface or "")
    race_el.set("conditions", race.conditions or "")
    race_el.set("status", race.status)

    for r in sorted_results:
        # Resolve horse name
        horse = crud.get_horse(db, r.horse_epc)
        result_el = SubElement(race_el, "Result")
        result_el.set("finishPosition", str(r.finish_position))
        result_el.set("horseEpc", r.horse_epc)
        result_el.set("horseName", horse.name if horse else "")
        result_el.set("elapsedMs", str(r.elapsed_ms))
        result_el.set("finishTime", _elapsed_to_time_str(r.elapsed_ms))

    indent(root, space="  ")
    xml_bytes = b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="unicode").encode("utf-8")

    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="race_{race_id}_ra.xml"'},
    )


# ─── BHA JSON ─────────────────────────────────────────────────────────────────

@router.get("/races/{race_id}/export/bha",
            summary="Export race results in BHA JSON format")
def export_bha(
    race_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_jwt_or_api_key),
):
    """
    British Horseracing Authority Results JSON (simplified BHA schema).

    {
      "schema": "BHA-Results-v1",
      "race": { ... },
      "finishers": [ { "position": 1, "horseId": "...", "horseName": "...", ... } ]
    }
    """
    race = _get_finished_race(race_id, db)
    sorted_results = sorted(race.results, key=lambda r: r.finish_position)

    finishers = []
    for r in sorted_results:
        horse = crud.get_horse(db, r.horse_epc)
        finishers.append({
            "position": r.finish_position,
            "horseId": r.horse_epc,
            "horseName": horse.name if horse else None,
            "elapsedMs": r.elapsed_ms,
            "finishTime": _elapsed_to_time_str(r.elapsed_ms),
        })

    payload = {
        "schema": "BHA-Results-v1",
        "race": {
            "id": race.id,
            "name": race.name or f"Race {race.id}",
            "date": _race_date_str(race),
            "venueId": race.venue_id,
            "distanceMetres": race.distance_m,
            "going": race.conditions,
            "surface": race.surface,
            "status": race.status,
        },
        "finishers": finishers,
    }

    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="race_{race_id}_bha.json"'},
    )


# ─── Jockey Club XML ──────────────────────────────────────────────────────────

@router.get("/races/{race_id}/export/jockey-club",
            summary="Export race results in Jockey Club XML format")
def export_jockey_club(
    race_id: int,
    db: Session = Depends(get_db),
    _auth=Depends(require_jwt_or_api_key),
):
    """
    Jockey Club Results XML (simplified JC schema).

    Root element: <JockeyClubResults>
      Child: <MeetingDetails> with venue/date
      Child: <RaceCard> with race details
        Children: <HorseResult> per finishing position
    """
    race = _get_finished_race(race_id, db)
    sorted_results = sorted(race.results, key=lambda r: r.finish_position)

    root = Element("JockeyClubResults")
    root.set("schemaVersion", "2.0")

    meeting = SubElement(root, "MeetingDetails")
    SubElement(meeting, "VenueId").text = race.venue_id
    SubElement(meeting, "MeetingDate").text = _race_date_str(race)

    race_card = SubElement(root, "RaceCard")
    SubElement(race_card, "RaceId").text = str(race.id)
    SubElement(race_card, "RaceName").text = race.name or f"Race {race.id}"
    SubElement(race_card, "Distance").text = str(race.distance_m)
    SubElement(race_card, "Surface").text = race.surface or ""
    SubElement(race_card, "GoingDescription").text = race.conditions or ""
    SubElement(race_card, "Status").text = race.status

    for r in sorted_results:
        horse = crud.get_horse(db, r.horse_epc)
        hr = SubElement(race_card, "HorseResult")
        SubElement(hr, "FinishPosition").text = str(r.finish_position)
        SubElement(hr, "HorseIdentifier").text = r.horse_epc
        SubElement(hr, "HorseName").text = horse.name if horse else ""
        SubElement(hr, "ElapsedMilliseconds").text = str(r.elapsed_ms)
        SubElement(hr, "FinishTime").text = _elapsed_to_time_str(r.elapsed_ms)

    indent(root, space="  ")
    xml_bytes = b'<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding="unicode").encode("utf-8")

    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="race_{race_id}_jc.xml"'},
    )
