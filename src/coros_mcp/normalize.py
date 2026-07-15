from __future__ import annotations

from datetime import date
from typing import Any

from coros_mcp.errors import ToolError
from coros_mcp.sports import type_to_sport


def to_yyyymmdd(value: str) -> str:
    """Convert a public ISO date into the compact form used by COROS APIs."""
    return date.fromisoformat(value).strftime("%Y%m%d")


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
        "date": ("date", "day"),
        "steps": ("steps", "step"),
        "calories": ("calories", "calorie"),
        "resting_hr": ("restingHr", "restHr"),
        "sleep_sec": ("sleepTime", "sleepDuration"),
        "training_load": ("trainingLoad",),
        "active_time_sec": ("activeTime", "activeDuration"),
    }
    return {
        friendly: value
        for friendly, keys in mappings.items()
        if (value := _first(raw_day, *keys)) is not None
    }


def normalize_scheduled_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize common schedule fields when supplied by a COROS response."""
    mappings = {
        "schedule_id": ("scheduleId", "id"),
        "date": ("date", "scheduleDate"),
        "workout_id": ("workoutId", "programId", "trainingId"),
        "name": ("name", "title"),
    }
    normalized = {
        friendly: value
        for friendly, keys in mappings.items()
        if (value := _first(raw, *keys)) is not None
    }
    sport_type = raw.get("sportType")
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
