"""Human-friendly pace parsing for COROS run/bike program steps.

COROS stores pace intensity as milliseconds per kilometer in ``intensityValue``
/ ``intensityValueExtend``, with ``intensityType=3`` (pace) and
``intensityDisplayUnit=2`` (km). Values are always stored as ms/km even when the
user specifies miles; COROS converts at display time.
"""

from __future__ import annotations

import re
from typing import Any

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
_KM_UNITS = {"km", "kilometer", "kilometers", "k", "min_per_km", ""}


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
        low_ms = _mmss_to_ms_per_km(str(low), unit)
        if high is None:
            return _intensity_fields(low_ms, low_ms)
        high_ms = _mmss_to_ms_per_km(str(high), unit)
        return _intensity_fields(*sorted((low_ms, high_ms)))

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
    low_ms = _pace_to_ms_per_km(min1, sec1, match["unit"])

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
        high_ms = _pace_to_ms_per_km(int(min2_raw), sec2, match["unit"])
    else:
        high_ms = low_ms

    return _intensity_fields(*sorted((low_ms, high_ms)))


def _parse_numeric_pace(
    low: float, high: float | int | None, *, unit: str | None
) -> dict[str, Any]:
    """Interpret numeric pace as total seconds per km or per mi when unit says so."""
    normalized = (unit or "min_per_km").strip().lower()
    if normalized in _MI_UNITS:
        low_ms = _seconds_per_unit_to_ms_per_km(low, per_mile=True)
        high_ms = (
            _seconds_per_unit_to_ms_per_km(float(high), per_mile=True)
            if high is not None
            else low_ms
        )
    else:
        low_ms = _seconds_per_unit_to_ms_per_km(low, per_mile=False)
        high_ms = (
            _seconds_per_unit_to_ms_per_km(float(high), per_mile=False)
            if high is not None
            else low_ms
        )
    return _intensity_fields(*sorted((low_ms, high_ms)))


def _mmss_to_ms_per_km(value: str, unit: str | None) -> int:
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
        return _pace_to_ms_per_km(int(minutes), sec, unit)
    except ValueError as error:
        raise ToolError(
            f"Invalid pace: {value!r}",
            code="VALIDATION_ERROR",
            hint="Use MM:SS, for example '9:30'.",
        ) from error


def _pace_to_ms_per_km(minutes: int, seconds: float, unit: str | None) -> int:
    ms_per_unit = int(round((minutes * 60 + seconds) * 1000))
    unit_raw = (unit or "min_per_km").strip().lower()
    if unit_raw in _MI_UNITS or unit_raw == "m":
        return int(round(ms_per_unit * 1000.0 / _METERS_PER_MILE))
    if unit_raw in _KM_UNITS:
        return ms_per_unit
    raise ToolError(
        f"Unsupported pace unit: {unit!r}",
        code="UNSUPPORTED_SPORT_STEP",
        hint="Use min_per_km or min_per_mi.",
    )


def _seconds_per_unit_to_ms_per_km(seconds: float, *, per_mile: bool) -> int:
    if seconds <= 0:
        raise ToolError(
            "Pace must be positive.",
            code="VALIDATION_ERROR",
            hint="Use a positive pace value.",
        )
    ms = int(round(seconds * 1000))
    if per_mile:
        return int(round(ms * 1000.0 / _METERS_PER_MILE))
    return ms


def _intensity_fields(fast_ms: int, slow_ms: int) -> dict[str, Any]:
    return {
        "kind": "pace",
        "target_low": fast_ms,
        "target_high": slow_ms,
        "intensity_display_unit": 2,
    }
