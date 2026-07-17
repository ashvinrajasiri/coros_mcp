from __future__ import annotations

from datetime import date
from typing import Any

from coros_mcp.errors import ToolError
from coros_mcp.sports import PROGRAM_SPORT_TYPES, type_to_sport

_PROGRAM_TYPE_TO_SPORT = {value: key for key, value in PROGRAM_SPORT_TYPES.items()}

# Fields kept on each exercise when returning a compact workout detail.
_SLIM_EXERCISE_KEYS = (
    "name",
    "overview",
    "sortNo",
    "targetType",
    "targetValue",
    "intensityType",
    "intensityValue",
    "intensityValueExtend",
    "intensityDisplayUnit",
    "restValue",
    "repeatTimes",
    "originId",
    "sets",
)


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

    sport = _program_sport(program) or _program_sport(raw)
    if sport is not None:
        normalized["sport"] = sport
    return normalized


def normalize_workout_summary(raw: dict[str, Any]) -> dict[str, Any]:
    """Compact library-workout row for list responses (token-cheap)."""
    exercises = raw.get("exercises")
    step_count = len(exercises) if isinstance(exercises, list) else None
    summary: dict[str, Any] = {
        "id": str(_first(raw, "id", "programId") or ""),
        "name": _first(raw, "name", "title"),
        "sport": _program_sport(raw),
    }
    if step_count is not None:
        summary["step_count"] = step_count
    return summary


def normalize_workout_detail(raw: dict[str, Any]) -> dict[str, Any]:
    """Compact workout detail: summary + slim steps (no charts/URLs)."""
    detail = normalize_workout_summary(raw)
    exercises = raw.get("exercises")
    if isinstance(exercises, list):
        detail["steps"] = [
            _slim_exercise(item) for item in exercises if isinstance(item, dict)
        ]
        detail["step_count"] = len(detail["steps"])
    return detail


def _program_sport(raw: dict[str, Any]) -> str | None:
    sport_data = raw.get("sportData")
    sport_type: Any
    if isinstance(sport_data, dict):
        sport_type = sport_data.get("sportType", raw.get("sportType"))
    else:
        sport_type = raw.get("sportType")
    if not isinstance(sport_type, int):
        return None
    try:
        return type_to_sport(sport_type)
    except ToolError:
        return _PROGRAM_TYPE_TO_SPORT.get(sport_type)


def _slim_exercise(raw: dict[str, Any]) -> dict[str, Any]:
    slim = {
        key: raw[key] for key in _SLIM_EXERCISE_KEYS if raw.get(key) is not None
    }
    # Strength sets sometimes nest under sets/exercises — keep one level only.
    nested = raw.get("sets") or raw.get("exercises")
    if isinstance(nested, list) and nested:
        slim["sets"] = [
            _slim_exercise(item) for item in nested if isinstance(item, dict)
        ]
    return slim


def _first(raw: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    return None
