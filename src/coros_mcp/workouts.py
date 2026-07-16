from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from coros_mcp.errors import ToolError
from coros_mcp.models import Duration, Target, WorkoutStep
from coros_mcp.pace import parse_pace_target

_SECONDS_PER_TIME_UNIT = {"sec": 1, "min": 60}
_CENTIMETERS_PER_DISTANCE_UNIT = {"m": 100, "km": 100_000, "mi": 160_934.4}


def friendly_to_coros_steps(
    steps: Sequence[WorkoutStep], *, pace_store_as: str | None = None
) -> list[dict[str, Any]]:
    """Map friendly steps into the stable intermediate COROS-shaped convention.

    Timed and distance durations use the ``duration`` key in seconds and
    centimeters respectively. Targets are nested under ``target`` with
    ``target_low`` and optional ``target_high`` keys. Task 7 will adapt this
    convention to the live COROS API payload.
    """
    return [
        _friendly_step_to_coros(step, pace_store_as=pace_store_as) for step in steps
    ]


def intermediate_to_program_exercises(
    steps: Sequence[dict[str, Any]], *, sport: str
) -> list[dict[str, Any]]:
    """Convert stable intermediate steps into COROS library-program exercises.

    Pace targets are always seconds per kilometer.
    intensityDisplayUnit is the Hub dropdown: 1=min/km, 2=min/mi.
    """
    if sport not in {"run", "bike", "strength"}:
        raise ToolError(
            f"Cannot map library-program steps for sport: {sport}",
            code="UNSUPPORTED_SPORT_STEP",
            hint="Use run, bike, or strength.",
        )

    exercises: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        sort_no = 16_777_216 * index
        if step["type"] == "repeat":
            _append_repeat_exercises(exercises, step, sort_no, sport)
        else:
            exercises.append(_program_exercise(step, sort_no, sport))
    return exercises


def build_program_payload(
    name: str,
    sport_type: int,
    sport: str,
    steps: Sequence[dict[str, Any]],
    *,
    distance_unit: str = "km",
) -> dict[str, Any]:
    """Build the payload accepted by ``/training/program/add``."""
    exercises = intermediate_to_program_exercises(steps, sport=sport)
    total_seconds, total_centimeters = _estimated_totals(steps)
    # COROS program ``unit``: 0 = metric, 1 = imperial (matches login account.unit).
    program_unit = 1 if distance_unit == "mi" else 0
    return {
        "name": name,
        "sportType": sport_type,
        "unit": program_unit,
        "pbVersion": 8,
        "overview": "",
        "estimatedTime": total_seconds,
        "estimatedDistance": total_centimeters,
        "distanceDisplayUnit": 1 if distance_unit == "mi" else 2,
        "estimatedType": 6 if total_centimeters else 0,
        "targetType": 5 if total_centimeters else 2,
        "targetValue": total_centimeters if total_centimeters else total_seconds,
        "simple": False,
        "access": 1,
        "exerciseNum": len(exercises),
        "totalSets": len(exercises),
        "exercises": exercises,
    }


def coros_steps_to_friendly(steps: Sequence[dict[str, Any]]) -> list[WorkoutStep]:
    """Map intermediate COROS-shaped steps back to friendly Pydantic models."""
    return [_coros_step_to_friendly(step) for step in steps]


def _friendly_step_to_coros(
    step: WorkoutStep, *, pace_store_as: str | None = None
) -> dict[str, Any]:
    if step.type == "repeat":
        if step.count is None or step.count < 1 or not step.steps:
            raise ToolError(
                "Repeat steps require a positive count and nested steps.",
                code="VALIDATION_ERROR",
                hint="Provide count >= 1 and at least one nested step.",
            )
        return {
            "type": "repeat",
            "count": step.count,
            "steps": friendly_to_coros_steps(step.steps, pace_store_as=pace_store_as),
        }

    mapped: dict[str, Any] = {"type": step.type}
    if step.duration is not None:
        mapped["duration"] = _duration_to_coros(step.duration)
        mapped["duration_type"] = step.duration.unit
    if step.target is not None:
        mapped["target"] = _target_to_coros(step.target, pace_store_as=pace_store_as)
    return mapped


def _duration_to_coros(duration: Duration) -> int | float:
    if duration.unit == "open":
        if duration.value is not None:
            raise ToolError(
                "Open duration cannot specify a value.",
                code="VALIDATION_ERROR",
                hint="Remove duration.value for an open duration.",
            )
        return 0

    if duration.value is None or duration.value <= 0:
        raise ToolError(
            "Timed and distance durations require a positive value.",
            code="VALIDATION_ERROR",
            hint="Provide duration.value greater than zero.",
        )

    if duration.unit == "time":
        unit = duration.time_unit or "min"
        return _compact_number(duration.value * _SECONDS_PER_TIME_UNIT[unit])

    unit = duration.distance_unit or "m"
    return _compact_number(duration.value * _CENTIMETERS_PER_DISTANCE_UNIT[unit])


def _target_to_coros(
    target: Target, *, pace_store_as: str | None = None
) -> dict[str, Any]:
    if target.kind == "pace":
        return parse_pace_target(
            target.low, target.high, unit=target.unit, store_as=pace_store_as  # type: ignore[arg-type]
        )

    mapped = {"kind": target.kind, "target_low": target.low}
    if target.high is not None:
        mapped["target_high"] = target.high
    if target.unit is not None:
        mapped["unit"] = target.unit
    return mapped


def _append_repeat_exercises(
    exercises: list[dict[str, Any]], step: dict[str, Any], parent_sort: int, sport: str
) -> None:
    exercises.append(
        {
            "exerciseType": 0,
            "sortNo": parent_sort,
            "isGroup": True,
            "sets": step["count"],
            "groupId": parent_sort,
        }
    )
    for index, child in enumerate(step["steps"], start=1):
        if child["type"] == "repeat":
            raise ToolError(
                "Nested repeat groups are not supported by COROS programs.",
                code="UNSUPPORTED_SPORT_STEP",
                hint="Use a single repeat level.",
            )
        exercise = _program_exercise(child, parent_sort + 65_536 * index, sport)
        exercise.update({"isGroup": False, "sets": 1, "groupId": parent_sort})
        exercises.append(exercise)


def _program_exercise(step: dict[str, Any], sort_no: int, sport: str) -> dict[str, Any]:
    step_type = step["type"]
    exercise_type = {
        "warmup": 1,
        "cooldown": 3,
        "recovery": 4,
        "training": 2,
        "interval": 2,
        "steady": 2,
    }.get(step_type)
    if exercise_type is None:
        raise ToolError(
            f"Unsupported {sport} workout step: {step_type}",
            code="UNSUPPORTED_SPORT_STEP",
            hint="Use warmup, training, interval, steady, cooldown, recovery, or repeat.",
        )

    duration_type = step.get("duration_type")
    origin_id, template_name, overview = _exercise_template(
        step_type, sport, duration_type=duration_type if isinstance(duration_type, str) else None
    )
    target_type, target_value = _duration_target(
        step.get("duration", 0), duration_type if isinstance(duration_type, str) else None
    )
    exercise = {
        "exerciseType": exercise_type,
        "targetType": target_type,
        "targetValue": target_value,
        "intensityType": 0,
        "intensityValue": 0,
        "intensityValueExtend": 0,
        "sortNo": sort_no,
        "originId": origin_id,
        "name": template_name,
        "overview": overview,
    }
    if target := step.get("target"):
        intensity_type = {"hr": 2, "pace": 3, "power": 6}.get(target["kind"])
        if intensity_type is None:
            raise ToolError(
                f"Unsupported intensity target: {target['kind']}",
                code="UNSUPPORTED_SPORT_STEP",
                hint="Use hr, pace, or power.",
            )
        low = target["target_low"]
        high = target.get("target_high", low)
        updates: dict[str, Any] = {
            "intensityType": intensity_type,
            "intensityValue": _compact_number(low),
            "intensityValueExtend": _compact_number(high),
            "isIntensityPercent": False,
            "hrType": 0,
        }
        if target["kind"] == "pace":
            updates["intensityDisplayUnit"] = target.get("intensity_display_unit", 1)
        exercise.update(updates)
    return exercise


def _exercise_template(
    step_type: str, sport: str, *, duration_type: str | None = None
) -> tuple[str, str, str]:
    # Time-based warm/cool use non-_dist overviews; distance uses _dist variants.
    use_dist = duration_type == "distance"
    templates = {
        "warmup": (
            "425895398452936705",
            "T1120",
            "sid_run_warm_up_dist" if use_dist else "sid_run_warm_up",
        ),
        "cooldown": (
            "425895456971866112",
            "T1122",
            "sid_run_cool_down_dist" if use_dist else "sid_run_cool_down",
        ),
        "recovery": (
            "425895398452936705",
            "T1123",
            "sid_run_cool_down_dist" if use_dist else "sid_run_cool_down",
        ),
        "training": ("426109589008859136", "T3001", "sid_run_training"),
        "interval": ("426109589008859136", "T3001", "sid_run_training"),
        "steady": ("426109589008859136", "T3001", "sid_run_training"),
    }
    origin_id, name, overview = templates[step_type]
    if sport == "bike" and step_type in {"training", "interval", "steady"}:
        overview = "sid_bike_training"
    return origin_id, name, overview


def _duration_target(
    duration: int | float, duration_type: str | None = None
) -> tuple[int, int | float]:
    if not duration:
        return 1, 0
    if duration_type == "distance":
        return 5, duration
    if duration_type == "time":
        return 2, duration
    # Keep supporting intermediates saved before duration_type was introduced.
    return (5, duration) if duration >= 10_000 else (2, duration)


def _estimated_totals(steps: Sequence[dict[str, Any]]) -> tuple[int | float, int | float]:
    seconds: int | float = 0
    centimeters: int | float = 0
    for step in steps:
        if step["type"] == "repeat":
            nested_seconds, nested_centimeters = _estimated_totals(step["steps"])
            seconds += nested_seconds * step["count"]
            centimeters += nested_centimeters * step["count"]
            continue
        duration = step.get("duration", 0)
        if step.get("duration_type") == "distance" or (
            step.get("duration_type") is None and duration >= 10_000
        ):
            centimeters += duration
        else:
            seconds += duration
    return _compact_number(seconds), _compact_number(centimeters)


def _coros_step_to_friendly(step: dict[str, Any]) -> WorkoutStep:
    step_type = step["type"]
    if step_type == "repeat":
        return WorkoutStep(
            type="repeat",
            count=step["count"],
            steps=coros_steps_to_friendly(step["steps"]),
        )

    duration = None
    if "duration" in step:
        duration = Duration(unit="time", value=step["duration"] / 60, time_unit="min")
    return WorkoutStep(type=step_type, duration=duration)


def _compact_number(value: int | float) -> int | float:
    return int(value) if isinstance(value, float) and value.is_integer() else value
