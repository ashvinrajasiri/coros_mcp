from __future__ import annotations

from coros_mcp.errors import ToolError

# Values commonly used by COROS community exporters. They remain isolated here
# so a later live-payload verification can adjust a code without affecting tools.
SPORT_TYPES = {
    "run": 100,
    "indoor_run": 101,
    "trail_run": 102,
    "hike": 150,
    "bike": 200,
    "indoor_bike": 201,
    "strength": 300,
    "swim": 400,
    "pool_swim": 400,
    "open_water": 401,
    "walk": 900,
}

PROGRAM_SPORT_TYPES = {
    "run": 1,
    "bike": 2,
    "strength": 4,
}

_TYPE_TO_SPORT = {
    sport_type: sport
    for sport, sport_type in SPORT_TYPES.items()
    if sport in {"run", "indoor_run", "trail_run", "hike", "bike", "indoor_bike", "strength", "swim", "open_water", "walk"}
}


def sport_to_type(sport: str) -> int:
    normalized = sport.strip().lower()
    try:
        return SPORT_TYPES[normalized]
    except KeyError as error:
        raise ToolError(
            f"Unsupported sport: {sport}",
            code="VALIDATION_ERROR",
            hint=f"Use one of: {', '.join(sorted(SPORT_TYPES))}",
        ) from error


def program_sport_to_type(sport: str) -> int:
    """Return the COROS library-program sport type, distinct from activities."""
    normalized = sport.strip().lower()
    try:
        return PROGRAM_SPORT_TYPES[normalized]
    except KeyError as error:
        raise ToolError(
            f"Unsupported program sport: {sport}",
            code="VALIDATION_ERROR",
            hint=f"Use one of: {', '.join(sorted(PROGRAM_SPORT_TYPES))}",
        ) from error


def type_to_sport(sport_type: int) -> str:
    try:
        return _TYPE_TO_SPORT[sport_type]
    except KeyError as error:
        raise ToolError(
            f"Unsupported COROS sport type: {sport_type}",
            code="VALIDATION_ERROR",
            hint="Use a known COROS sportType value.",
        ) from error
