"""Strength workout helpers: catalog search + program payload building."""

from __future__ import annotations

import re
from typing import Any

from coros_mcp.errors import ToolError

_STRENGTH_SPORT_TYPE = 4
_TARGET_REPS = 3
_TARGET_TIME = 2

_OVERVIEW_PREFIXES = ("sid_strength_", "sid_")


def humanize_overview(overview: str | None) -> str:
    """Turn ``sid_strength_push_ups`` into ``Push Ups``."""
    text = (overview or "").strip()
    for prefix in _OVERVIEW_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    words = [part for part in re.split(r"[_\s]+", text) if part]
    return " ".join(word.capitalize() for word in words) if words else text


def normalize_catalog_exercise(raw: dict[str, Any]) -> dict[str, Any]:
    overview = raw.get("overview")
    return {
        "id": str(raw.get("id") or ""),
        "code": raw.get("name") or "",
        "name": humanize_overview(str(overview) if overview else None)
        or str(raw.get("name") or ""),
        "overview": overview or "",
        "muscle_ids": list(raw.get("muscle") or []),
        "equipment_ids": list(raw.get("equipment") or []),
        "default_rest_sec": raw.get("restValue"),
        "source_url": raw.get("sourceUrl"),
    }


def search_catalog(
    exercises: list[dict[str, Any]],
    query: str,
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Case-insensitive substring search over human name, overview, and T-code."""
    needle = query.strip().lower()
    if not needle:
        raise ToolError(
            "Search query must not be empty.",
            code="VALIDATION_ERROR",
            hint="Try a name like 'push' or 'squat'.",
        )
    if limit < 1:
        raise ToolError(
            "limit must be >= 1",
            code="VALIDATION_ERROR",
            hint="Use a positive limit.",
        )

    scored: list[tuple[int, dict[str, Any]]] = []
    for raw in exercises:
        item = normalize_catalog_exercise(raw)
        haystacks = [
            item["name"].lower(),
            str(item["overview"]).lower(),
            str(item["code"]).lower(),
        ]
        if not any(needle in hay for hay in haystacks):
            continue
        # Prefer exact / prefix matches on the human name.
        name = item["name"].lower()
        score = 0
        if name == needle:
            score = 0
        elif name.startswith(needle):
            score = 1
        elif needle in name:
            score = 2
        else:
            score = 3
        scored.append((score, item))

    # Prefer tighter matches, then shorter names ("Planks" before "Plank Jacks").
    scored.sort(key=lambda pair: (pair[0], len(pair[1]["name"]), pair[1]["name"]))
    return [item for _, item in scored[:limit]]


def resolve_exercise(
    exercises: list[dict[str, Any]], query: str
) -> dict[str, Any]:
    """Resolve one catalog exercise by human name / overview / T-code."""
    matches = search_catalog(exercises, query, limit=10)
    if not matches:
        raise ToolError(
            f"No strength exercise matched {query!r}.",
            code="NOT_FOUND",
            hint="Call search_strength_exercises to find a catalog name.",
        )
    needle = query.strip().lower()
    exact = [
        item
        for item in matches
        if item["name"].lower() == needle
        or str(item["code"]).lower() == needle
        or str(item["overview"]).lower() == needle
        or str(item["overview"]).lower() == f"sid_strength_{needle.replace(' ', '_')}"
    ]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        names = ", ".join(item["name"] for item in exact[:5])
        raise ToolError(
            f"Ambiguous strength exercise {query!r}: {names}.",
            code="VALIDATION_ERROR",
            hint="Use a more specific name or the catalog id/code.",
        )
    if len(matches) == 1:
        return matches[0]
    names = ", ".join(item["name"] for item in matches[:5])
    raise ToolError(
        f"Ambiguous strength exercise {query!r}. Matches: {names}.",
        code="VALIDATION_ERROR",
        hint="Pick one exact catalog name from search_strength_exercises.",
    )


def build_strength_program_payload(
    name: str,
    exercises: list[dict[str, Any]],
    *,
    catalog: list[dict[str, Any]],
    sets: int = 1,
) -> dict[str, Any]:
    """Build ``/training/program/add`` payload for a strength circuit."""
    if not name.strip():
        raise ToolError(
            "Workout name is required.",
            code="VALIDATION_ERROR",
            hint="Provide a non-empty name.",
        )
    if not exercises:
        raise ToolError(
            "At least one strength exercise is required.",
            code="VALIDATION_ERROR",
            hint="Pass exercises like {name, reps} or {name, duration_sec}.",
        )
    if sets < 1:
        raise ToolError(
            "sets must be >= 1",
            code="VALIDATION_ERROR",
            hint="Use the number of times to repeat the full circuit.",
        )

    built: list[dict[str, Any]] = []
    total_duration = 0
    for index, step in enumerate(exercises):
        resolved, target_type, target_value, rest = _normalize_step(step, catalog)
        if target_type == _TARGET_TIME:
            total_duration += target_value
        total_duration += rest
        built.append(
            {
                "access": 0,
                "createTimestamp": 0,
                "defaultOrder": index,
                "exerciseType": 2,
                "id": index + 1,
                "intensityCustom": 0,
                "intensityDisplayUnit": 6,
                "intensityMultiplier": 0,
                "intensityPercent": 0,
                "intensityPercentExtend": 0,
                "intensityType": 1,
                "intensityValue": 0,
                "intensityValueExtend": 0,
                "isDefaultAdd": 0,
                "isGroup": False,
                "isIntensityPercent": False,
                "hrType": 0,
                "name": resolved["code"] or resolved["name"],
                "originId": resolved["id"],
                "overview": resolved["overview"] or "sid_strength_training",
                "part": [0],
                "groupId": "",
                "restType": 1,
                "restValue": rest,
                "sets": 1,
                "sortNo": index,
                "sourceUrl": resolved.get("source_url") or "",
                "sportType": _STRENGTH_SPORT_TYPE,
                "status": 1,
                "targetDisplayUnit": 0,
                "targetType": target_type,
                "targetValue": target_value,
                "userId": 0,
                "videoInfos": [],
                "videoUrl": "",
            }
        )

    total_duration *= sets
    return {
        "access": 1,
        "authorId": "0",
        "createTimestamp": 0,
        "distance": "0",
        "duration": total_duration,
        "essence": 0,
        "estimatedType": 0,
        "estimatedValue": 0,
        "exerciseNum": len(built),
        "exercises": built,
        "id": "0",
        "idInPlan": "0",
        "name": name.strip(),
        "overview": "",
        "pbVersion": 2,
        "referExercise": {"intensityType": 1, "hrType": 0, "valueType": 1},
        "sets": sets,
        "simple": False,
        "sourceId": "425868113867882496",
        "sportType": _STRENGTH_SPORT_TYPE,
        "star": 0,
        "subType": 65535,
        "targetType": 0,
        "targetValue": 0,
        "totalSets": sets,
        "unit": 0,
        "userId": "0",
        "version": 0,
    }


def _normalize_step(
    step: dict[str, Any], catalog: list[dict[str, Any]]
) -> tuple[dict[str, Any], int, int, int]:
    if not isinstance(step, dict):
        raise ToolError(
            "Each strength exercise must be an object.",
            code="VALIDATION_ERROR",
            hint="Use {name, reps} or {name, duration_sec}.",
        )

    query = step.get("name") or step.get("exercise") or step.get("code")
    origin_id = step.get("origin_id") or step.get("id")
    if origin_id:
        resolved = _resolve_by_id(catalog, str(origin_id))
    elif query:
        resolved = resolve_exercise(catalog, str(query))
    else:
        raise ToolError(
            "Strength exercise needs name or origin_id.",
            code="VALIDATION_ERROR",
            hint="Example: {\"name\": \"Push Ups\", \"reps\": 12}.",
        )

    rest = int(step.get("rest_sec") or step.get("rest_seconds") or 60)
    if rest < 0:
        raise ToolError(
            "rest_sec must be >= 0",
            code="VALIDATION_ERROR",
            hint="Use seconds of rest after the exercise.",
        )

    if step.get("reps") is not None:
        reps = int(step["reps"])
        if reps < 1:
            raise ToolError(
                "reps must be >= 1",
                code="VALIDATION_ERROR",
                hint="Provide a positive rep count.",
            )
        return resolved, _TARGET_REPS, reps, rest

    duration = step.get("duration_sec") or step.get("seconds") or step.get("duration")
    if duration is not None:
        seconds = int(duration)
        if seconds < 1:
            raise ToolError(
                "duration_sec must be >= 1",
                code="VALIDATION_ERROR",
                hint="Provide timed hold/work duration in seconds.",
            )
        return resolved, _TARGET_TIME, seconds, rest

    raise ToolError(
        f"Exercise {resolved['name']!r} needs reps or duration_sec.",
        code="VALIDATION_ERROR",
        hint='Example: {"name": "Plank", "duration_sec": 45}.',
    )


def _resolve_by_id(catalog: list[dict[str, Any]], origin_id: str) -> dict[str, Any]:
    for raw in catalog:
        if str(raw.get("id")) == origin_id:
            return normalize_catalog_exercise(raw)
    raise ToolError(
        f"No strength exercise with id {origin_id!r}.",
        code="NOT_FOUND",
        hint="Call search_strength_exercises to find a catalog id.",
    )
