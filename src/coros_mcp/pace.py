"""Human-friendly pace parsing for COROS run/bike program steps.

COROS stores absolute pace as **seconds per kilometer** in
``intensityValue`` / ``intensityValueExtend`` (``intensityType=3``).

``intensityDisplayUnit`` only controls the Training Hub dropdown label
(from the Hub ``intensityUnitName`` enum):

- ``1`` → min/km
- ``2`` → min/mi

Input may be mi or km. Values are converted to seconds/km; the display
unit follows the athlete preference (account setting / ``COROS_DISTANCE_UNIT``).
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

# Training Hub intensityUnitName enum.
_DISPLAY_UNIT_KM = 1  # min/km
_DISPLAY_UNIT_MI = 2  # min/mi

DistanceUnit = Literal["km", "mi"]


def distance_unit_preference(store_as: DistanceUnit | None = None) -> DistanceUnit:
    """Return preferred *display* unit for paces (dropdown label).

    Prefer an explicit ``store_as`` (from the authenticated COROS account).
    ``COROS_DISTANCE_UNIT`` remains an optional override via callers that pass
    ``store_as`` from config. Bare env reads are only a last-resort fallback
    for unit tests that don't wire a client.
    """
    if store_as in {"km", "mi"}:
        return store_as
    raw = os.environ.get("COROS_DISTANCE_UNIT", "").strip().lower()
    if raw in {"mi", "mile", "miles", "imperial"}:
        return "mi"
    if raw in {"km", "kilometer", "kilometers", "metric"}:
        return "km"
    return "km"


def parse_pace_target(
    low: str | float | int,
    high: str | float | int | None = None,
    *,
    unit: str | None = None,
    store_as: DistanceUnit | None = None,
) -> dict[str, Any]:
    """Parse friendly pace input into COROS intensity fields (seconds/km)."""
    preferred = store_as or distance_unit_preference()

    if isinstance(low, str):
        text = low.strip()
        if "/" in text or (high is None and re.search(r"[-–]", text)):
            return _finalize(_parse_pace_string_raw(text, preferred=preferred), preferred)

    if isinstance(low, str) and ":" in str(low):
        input_unit = _normalize_input_unit(unit, preferred=preferred)
        low_s = _mmss_to_seconds(str(low))
        high_s = _mmss_to_seconds(str(high)) if high is not None else low_s
        return _finalize((low_s, high_s, input_unit), preferred)

    if isinstance(low, (int, float)):
        input_unit = _normalize_input_unit(unit, preferred=preferred)
        low_s = _positive_seconds(float(low))
        high_s = _positive_seconds(float(high)) if high is not None else low_s
        return _finalize((low_s, high_s, input_unit), preferred)

    raise ToolError(
        f"Invalid pace: {low!r}",
        code="VALIDATION_ERROR",
        hint="Use MM:SS with min_per_mi/min_per_km, e.g. '5:45' + unit 'min_per_km'.",
    )


def _parse_pace_string_raw(
    text: str, *, preferred: DistanceUnit
) -> tuple[float, float, DistanceUnit]:
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
    input_unit = _normalize_input_unit(match["unit"], preferred=preferred)
    low_s = _pace_parts_to_seconds(min1, sec1)

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
        high_s = _pace_parts_to_seconds(int(min2_raw), sec2)
    else:
        high_s = low_s

    return low_s, high_s, input_unit


def _finalize(
    parsed: tuple[float, float, DistanceUnit], preferred: DistanceUnit
) -> dict[str, Any]:
    """Convert input to seconds/km and set display unit for the Hub dropdown."""
    low_s, high_s, input_unit = parsed
    low_s = _convert_seconds(low_s, from_unit=input_unit, to_unit="km")
    high_s = _convert_seconds(high_s, from_unit=input_unit, to_unit="km")
    display_unit = _DISPLAY_UNIT_MI if preferred == "mi" else _DISPLAY_UNIT_KM
    return _intensity_fields(*sorted((low_s, high_s)), display_unit)


def _convert_seconds(
    seconds: float, *, from_unit: DistanceUnit, to_unit: DistanceUnit
) -> float:
    if from_unit == to_unit:
        return seconds
    if from_unit == "mi" and to_unit == "km":
        return seconds * 1000.0 / _METERS_PER_MILE
    return seconds * _METERS_PER_MILE / 1000.0


def _normalize_input_unit(
    unit: str | None, *, preferred: DistanceUnit
) -> DistanceUnit:
    if unit is None or str(unit).strip() == "":
        return preferred
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


def _mmss_to_seconds(value: str) -> float:
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
        return _pace_parts_to_seconds(int(minutes), sec)
    except ValueError as error:
        raise ToolError(
            f"Invalid pace: {value!r}",
            code="VALIDATION_ERROR",
            hint="Use MM:SS, for example '5:45'.",
        ) from error


def _pace_parts_to_seconds(minutes: int, seconds: float) -> float:
    return minutes * 60 + seconds


def _positive_seconds(seconds: float) -> float:
    if seconds <= 0:
        raise ToolError(
            "Pace must be positive.",
            code="VALIDATION_ERROR",
            hint="Use a positive pace value.",
        )
    return seconds


def _intensity_fields(
    fast_seconds: float, slow_seconds: float, display_unit: int
) -> dict[str, Any]:
    return {
        "kind": "pace",
        "target_low": int(round(fast_seconds)),
        "target_high": int(round(slow_seconds)),
        "intensity_display_unit": display_unit,
    }
