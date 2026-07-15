from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from coros_mcp.errors import ToolError
from coros_mcp.models import Duration, Target, WorkoutStep

_SECONDS_PER_TIME_UNIT = {"sec": 1, "min": 60}
_CENTIMETERS_PER_DISTANCE_UNIT = {"m": 100, "km": 100_000, "mi": 160_934.4}


def friendly_to_coros_steps(steps: Sequence[WorkoutStep]) -> list[dict[str, Any]]:
    """Map friendly steps into the stable intermediate COROS-shaped convention.

    Timed and distance durations use the ``duration`` key in seconds and
    centimeters respectively. Targets are nested under ``target`` with
    ``target_low`` and optional ``target_high`` keys. Task 7 will adapt this
    convention to the live COROS API payload.
    """
    return [_friendly_step_to_coros(step) for step in steps]


def coros_steps_to_friendly(steps: Sequence[dict[str, Any]]) -> list[WorkoutStep]:
    """Map intermediate COROS-shaped steps back to friendly Pydantic models."""
    return [_coros_step_to_friendly(step) for step in steps]


def _friendly_step_to_coros(step: WorkoutStep) -> dict[str, Any]:
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
            "steps": friendly_to_coros_steps(step.steps),
        }

    mapped: dict[str, Any] = {"type": step.type}
    if step.duration is not None:
        mapped["duration"] = _duration_to_coros(step.duration)
    if step.target is not None:
        mapped["target"] = _target_to_coros(step.target)
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


def _target_to_coros(target: Target) -> dict[str, Any]:
    if target.kind == "pace":
        if target.unit not in {None, "min_per_km"}:
            raise ToolError(
                f"Unsupported pace unit: {target.unit}",
                code="UNSUPPORTED_SPORT_STEP",
                hint="Use pace targets with unit 'min_per_km'.",
            )
        mapped = {"kind": "pace", "target_low": _pace_to_seconds_per_km(target.low)}
        if target.high is not None:
            mapped["target_high"] = _pace_to_seconds_per_km(target.high)
        return mapped

    mapped = {"kind": target.kind, "target_low": target.low}
    if target.high is not None:
        mapped["target_high"] = target.high
    if target.unit is not None:
        mapped["unit"] = target.unit
    return mapped


def _pace_to_seconds_per_km(value: str | float | int) -> int:
    if isinstance(value, (int, float)):
        if value <= 0:
            raise ToolError(
                "Pace must be positive.",
                code="VALIDATION_ERROR",
                hint="Use a positive seconds-per-kilometer pace.",
            )
        return int(value)

    minutes, separator, seconds = value.strip().partition(":")
    try:
        total_seconds = int(minutes) * 60 + int(seconds)
    except ValueError as error:
        raise ToolError(
            f"Invalid pace: {value}",
            code="VALIDATION_ERROR",
            hint="Use MM:SS, for example '4:30'.",
        ) from error
    if not separator or total_seconds <= 0 or not 0 <= int(seconds) < 60:
        raise ToolError(
            f"Invalid pace: {value}",
            code="VALIDATION_ERROR",
            hint="Use MM:SS, for example '4:30'.",
        )
    return total_seconds


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


def _compact_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value
