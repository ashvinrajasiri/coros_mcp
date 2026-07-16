"""Human-friendly pace parsing for COROS run/bike program steps.

COROS stores pace as milliseconds **in the selected distance unit**:

- ``intensityDisplayUnit=1`` → miles → ``intensityValue`` is ms per mile
- ``intensityDisplayUnit=2`` → km → ``intensityValue`` is ms per kilometer

Example: easy 9:30/mi → intensityValue=570000, intensityDisplayUnit=1
Example: tempo 4:30/km → intensityValue=270000, intensityDisplayUnit=2
"""

from __future__ import annotations

import re
from typing import Any

from coros_mcp.errors import ToolError

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


def parse_pace_target(
    low: str | float | int,
    high: str | float | int | None = None,
    *,
    unit: str | None = None,
) -> dict[str, Any]:
    """Parse friendly pace input into COROS intensity fields."""
    if isinstance(low, str):
        text = low.strip()
        # Full pace string includes unit or range, e.g. "9:30/mi" or "4:05-4:15/km".
        if "/" in text or (high is None and re.search(r"[-–]", text)):
            return _parse_pace_string(text)

    if isinstance(low, str) and ":" in str(low):
        display_unit = _display_unit_for(unit)
        low_ms = _mmss_to_ms(str(low))
        if high is None:
            return _intensity_fields(low_ms, low_ms, display_unit)
        high_ms = _mmss_to_ms(str(high))
        return _intensity_fields(*sorted((low_ms, high_ms)), display_unit)

    if isinstance(low, (int, float)):
        return _parse_numeric_pace(float(low), high, unit=unit)

    raise ToolError(
        f"Invalid pace: {low!r}",
        code="VALIDATION_ERROR",
        hint="Use MM:SS with min_per_mi/min_per_km, e.g. '9:30' + unit 'min_per_mi'.",
    )


def _parse_pace_string(text: str) -> dict[str, Any]:
    match = _PACE_RE.match(text.strip())
    if not match:
        raise ToolError(
            f"Invalid pace: {text!r}",
            code="VALIDATION_ERROR",
            hint="Use formats like '9:30/mi', '4:30/km', or '4:30-4:45/km'.",
        )

    min1 = int(match["min1"])
    sec1 = float(match["sec1"])
    if sec1 >= 60:
        raise ToolError(
            f"Invalid pace seconds in {text!r}",
            code="VALIDATION_ERROR",
            hint="Seconds must be 0-59.",
        )
    unit = match["unit"]
    display_unit = _display_unit_for(unit)
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

    return _intensity_fields(*sorted((low_ms, high_ms)), display_unit)


def _parse_numeric_pace(
    low: float, high: float | int | None, *, unit: str | None
) -> dict[str, Any]:
    """Interpret numeric pace as total seconds per the given unit."""
    display_unit = _display_unit_for(unit)
    low_ms = _seconds_to_ms(low)
    high_ms = _seconds_to_ms(float(high)) if high is not None else low_ms
    return _intensity_fields(*sorted((low_ms, high_ms)), display_unit)


def _mmss_to_ms(value: str) -> int:
    minutes, separator, seconds = value.strip().partition(":")
    if not separator:
        raise ToolError(
            f"Invalid pace: {value!r}",
            code="VALIDATION_ERROR",
            hint="Use MM:SS, for example '9:30'.",
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
            hint="Use MM:SS, for example '9:30'.",
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


def _display_unit_for(unit: str | None) -> int:
    """Return COROS intensityDisplayUnit for a pace unit (1=mi, 2=km)."""
    # Default to miles — matches US/Canada Training Hub accounts like the author's.
    if unit is None or str(unit).strip() == "":
        return _DISPLAY_UNIT_MI
    unit_raw = str(unit).strip().lower()
    if unit_raw in _MI_UNITS:
        return _DISPLAY_UNIT_MI
    if unit_raw in _KM_UNITS:
        return _DISPLAY_UNIT_KM
    raise ToolError(
        f"Unsupported pace unit: {unit!r}",
        code="UNSUPPORTED_SPORT_STEP",
        hint="Use min_per_mi or min_per_km.",
    )


def _intensity_fields(fast_ms: int, slow_ms: int, display_unit: int) -> dict[str, Any]:
    return {
        "kind": "pace",
        "target_low": fast_ms,
        "target_high": slow_ms,
        "intensity_display_unit": display_unit,
    }
