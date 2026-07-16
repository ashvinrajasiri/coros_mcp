"""Human-friendly pace parsing for COROS run/bike program steps.

COROS stores pace as milliseconds in a distance unit:

- ``intensityDisplayUnit=1`` → miles → ms per mile
- ``intensityDisplayUnit=2`` → km → ms per kilometer

Input may be mi or km. Values are converted to ``COROS_DISTANCE_UNIT``
(default ``km``) so the watch matches the athlete's COROS app units.
"""

from __future__ import annotations

import os
import re
from typing import Any, Literal

from coros_mcp.errors import ToolError

_METERS_PER_MILE = 1609.344

_PACE_RE = re.compile(
    r"""
    ^\s*
    (?P<min1>\d+):(?P<sec1>\d{1,2}(?:\.\d+)?)
    (?:\s*[-–]\s*(?P<min2>\d+):(?P<sec2>\d{1,2}(?:\.\d+)?))?
    \s*/?\s*
    (?P<unit>km|kilometer|kilometers|k|mi|mile|miles|m(?:ile)?)?
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)

_MI_UNITS = {"mi", "mile", "miles", "m", "min_per_mi"}
_KM_UNITS = {"km", "kilometer", "kilometers", "k", "min_per_km"}

_DISPLAY_UNIT_MI = 1
_DISPLAY_UNIT_KM = 2

DistanceUnit = Literal["km", "mi"]


def distance_unit_preference() -> DistanceUnit:
    """Return the unit COROS workouts should store/display (from env)."""
    raw = os.environ.get("COROS_DISTANCE_UNIT", "km").strip().lower()
    if raw in {"mi", "mile", "miles", "imperial"}:
        return "mi"
    if raw in {"km", "kilometer", "kilometers", "metric", ""}:
        return "km"
    raise ToolError(
        f"Invalid COROS_DISTANCE_UNIT: {raw!r}",
        code="VALIDATION_ERROR",
        hint="Use COROS_DISTANCE_UNIT=km or mi (match your COROS app setting).",
    )


def parse_pace_target(
    low: str | float | int,
    high: str | float | int | None = None,
    *,
    unit: str | None = None,
    store_as: DistanceUnit | None = None,
) -> dict[str, Any]:
    """Parse friendly pace input into COROS intensity fields."""
    preferred = store_as or distance_unit_preference()

    if isinstance(low, str):
        text = low.strip()
        if "/" in text or (high is None and re.search(r"[-–]", text)):
            return _finalize(_parse_pace_string_raw(text), preferred)

    if isinstance(low, str) and ":" in str(low):
        input_unit = _normalize_input_unit(unit)
        low_ms = _mmss_to_ms(str(low))
        high_ms = _mmss_to_ms(str(high)) if high is not None else low_ms
        return _finalize((low_ms, high_ms, input_unit), preferred)

    if isinstance(low, (int, float)):
        input_unit = _normalize_input_unit(unit)
        low_ms = _seconds_to_ms(float(low))
        high_ms = _seconds_to_ms(float(high)) if high is not None else low_ms
        return _finalize((low_ms, high_ms, input_unit), preferred)

    raise ToolError(
        f"Invalid pace: {low!r}",
        code="VALIDATION_ERROR",
        hint="Use MM:SS with min_per_mi/min_per_km, e.g. '5:45' + unit 'min_per_km'.",
    )


def _parse_pace_string_raw(text: str) -> tuple[int, int, DistanceUnit]:
    match = _PACE_RE.match(text.strip())
    if not match:
        raise ToolError(
            f"Invalid pace: {text!r}",
            code="VALIDATION_ERROR",
            hint="Use formats like '9:30/mi', '5:45/km', or '5:30-5:45/km'.",
        )

    min1 = int(match["min1"])
    sec1 = float(match["sec1"])
    if sec1 >= 60:
        raise ToolError(
            f"Invalid pace seconds in {text!r}",
            code="VALIDATION_ERROR",
            hint="Seconds must be 0-59.",
        )
    input_unit = _normalize_input_unit(match["unit"])
    low_ms = _pace_parts_to_ms(min1, sec1)

    min2_raw = match["min2"]
    sec2_raw = match["sec2"]
    if min2_raw is not None:
        sec2 = float(sec2_raw)
        if sec2 >= 60:
            raise ToolError(
                f"Invalid pace seconds in {text!r}",
                code="VALIDATION_ERROR",
                hint="Seconds must be 0-59.",
            )
        high_ms = _pace_parts_to_ms(int(min2_raw), sec2)
    else:
        high_ms = low_ms

    return low_ms, high_ms, input_unit


def _finalize(
    parsed: tuple[int, int, DistanceUnit], preferred: DistanceUnit
) -> dict[str, Any]:
    low_ms, high_ms, input_unit = parsed
    low_ms = _convert_ms(low_ms, from_unit=input_unit, to_unit=preferred)
    high_ms = _convert_ms(high_ms, from_unit=input_unit, to_unit=preferred)
    display_unit = _DISPLAY_UNIT_MI if preferred == "mi" else _DISPLAY_UNIT_KM
    return _intensity_fields(*sorted((low_ms, high_ms)), display_unit)


def _convert_ms(ms: int, *, from_unit: DistanceUnit, to_unit: DistanceUnit) -> int:
    if from_unit == to_unit:
        return ms
    if from_unit == "mi" and to_unit == "km":
        return int(round(ms * 1000.0 / _METERS_PER_MILE))
    return int(round(ms * _METERS_PER_MILE / 1000.0))


def _normalize_input_unit(unit: str | None) -> DistanceUnit:
    if unit is None or str(unit).strip() == "":
        # Bare MM:SS with no unit → interpret using athlete preference.
        return distance_unit_preference()
    unit_raw = str(unit).strip().lower()
    if unit_raw in _MI_UNITS:
        return "mi"
    if unit_raw in _KM_UNITS:
        return "km"
    raise ToolError(
        f"Unsupported pace unit: {unit!r}",
        code="UNSUPPORTED_SPORT_STEP",
        hint="Use min_per_mi or min_per_km.",
    )


def _mmss_to_ms(value: str) -> int:
    minutes, separator, seconds = value.strip().partition(":")
    if not separator:
        raise ToolError(
            f"Invalid pace: {value!r}",
            code="VALIDATION_ERROR",
            hint="Use MM:SS, for example '5:45'.",
        )
    try:
        sec = float(seconds)
        if sec < 0 or sec >= 60:
            raise ValueError("seconds out of range")
        return _pace_parts_to_ms(int(minutes), sec)
    except ValueError as error:
        raise ToolError(
            f"Invalid pace: {value!r}",
            code="VALIDATION_ERROR",
            hint="Use MM:SS, for example '5:45'.",
        ) from error


def _pace_parts_to_ms(minutes: int, seconds: float) -> int:
    return int(round((minutes * 60 + seconds) * 1000))


def _seconds_to_ms(seconds: float) -> int:
    if seconds <= 0:
        raise ToolError(
            "Pace must be positive.",
            code="VALIDATION_ERROR",
            hint="Use a positive pace value.",
        )
    return int(round(seconds * 1000))


def _intensity_fields(fast_ms: int, slow_ms: int, display_unit: int) -> dict[str, Any]:
    return {
        "kind": "pace",
        "target_low": fast_ms,
        "target_high": slow_ms,
        "intensity_display_unit": display_unit,
    }
