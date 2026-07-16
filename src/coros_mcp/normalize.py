from __future__ import annotations

from datetime import date
from typing import Any

from coros_mcp.errors import ToolError
from coros_mcp.sports import type_to_sport


def to_yyyymmdd(value: str) -> str:
    """Convert a public ISO date into the compact form used by COROS APIs."""
    try:
        return date.fromisoformat(value).strftime("%Y%m%d")
    except ValueError as error:
        raise ToolError(
            f"Invalid date: {value!r}",
            code="VALIDATION_ERROR",
            hint="Use YYYY-MM-DD",
        ) from error


def normalize_activity_list_item(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a COROS activity-list item.

    COROS list responses report ``distance`` in meters; this assumption applies
    only to list items and can be adjusted after live payload verification.
    """
    sport_type = raw.get("sportType")
    try:
        sport = type_to_sport(sport_type) if isinstance(sport_type, int) else None
    except ToolError:
        sport = None

    return {
        "id": _first(raw, "labelId", "activityId", "id"),
        "sport": sport,
        "start": _first(raw, "startTime", "start"),
        "duration_sec": _first(raw, "totalTime", "duration", "durationSec"),
        "distance_m": _first(raw, "distance", "distanceM"),
        "avg_hr": _first(raw, "avgHr", "avgHeartRate"),
        "training_load": _first(raw, "trainingLoad", "trainingEffect"),
        "title": _first(raw, "name", "title"),
    }


def normalize_daily_metrics(raw_day: dict[str, Any]) -> dict[str, Any]:
    """Return available daily-metric fields without requiring a fixed payload."""
    mappings = {
        "date": ("date", "happenDay", "day"),
        "steps": ("steps", "step"),
        "calories": ("calories", "calorie"),
        "rhr": ("rhr", "restingHr", "restHr", "testRhr"),
        "hrv": ("avgSleepHrv", "hrv"),
        "hrv_baseline": ("sleepHrvBase",),
        "fatigue": ("tiredRateNew", "tiredRate"),
        "training_load": ("trainingLoad",),
        "training_load_ratio": ("trainingLoadRatio",),
        "sleep_sec": ("sleepTime", "sleepDuration"),
        "active_time_sec": ("activeTime", "activeDuration", "duration"),
        "distance_m": ("distance",),
    }
    normalized = {
        friendly: value
        for friendly, keys in mappings.items()
        if (value := _first(raw_day, *keys)) is not None
    }
    if "date" in normalized:
        normalized["date"] = str(normalized["date"])
    return normalized


def normalize_scheduled_entry(
    raw: dict[str, Any], program: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Normalize a schedule entity; ``schedule_id`` is the entity id, not a library workout id."""
    program = program or {}
    mappings = {
        "schedule_id": ("scheduleId", "id"),
        "date": ("happenDay", "date", "scheduleDate"),
        "workout_id": ("workoutId", "programId", "trainingId"),
        "name": ("name", "title"),
    }
    normalized = {
        friendly: value
        for friendly, keys in mappings.items()
        if (value := _first(raw, *keys)) is not None
    }
    if "date" in normalized:
        normalized["date"] = str(normalized["date"])
    if "workout_id" not in normalized and (value := program.get("id")) is not None:
        normalized["workout_id"] = value
    if "name" not in normalized and (value := _first(program, "name", "title")) is not None:
        normalized["name"] = value

    sport_data = program.get("sportData")
    sport_type = (
        sport_data.get("sportType")
        if isinstance(sport_data, dict)
        else program.get("sportType", raw.get("sportType"))
    )
    if isinstance(sport_type, int):
        try:
            normalized["sport"] = type_to_sport(sport_type)
        except ToolError:
            pass
    return normalized


def _first(raw: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    return None
