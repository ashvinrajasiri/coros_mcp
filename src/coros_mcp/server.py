from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from coros_mcp.client import CorosClient
from coros_mcp.config import ConfigError
from coros_mcp.errors import ToolError, error_payload
from coros_mcp.models import WorkoutCreate
from coros_mcp.normalize import normalize_activity_list_item, normalize_daily_metrics
from coros_mcp.sports import program_sport_to_type
from coros_mcp.workouts import build_program_payload, friendly_to_coros_steps

load_dotenv()

mcp = FastMCP("coros_mcp")


def _get_client() -> CorosClient:
    return CorosClient()


def _data_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    values = response.get("dataList", [])
    return [value for value in values if isinstance(value, dict)] if isinstance(values, list) else []


@mcp.tool()
def get_daily_metrics(start_date: str, end_date: str | None = None) -> dict:
    """Read daily COROS metrics (HRV, RHR, load, fatigue, sleep-as-available) for a date or range (YYYY-MM-DD). Coaching logic stays in the agent. Watch sync is via COROS app after calendar writes."""
    try:
        response = _get_client().get_day_detail(start_date, end_date or start_date)
        return {"days": [normalize_daily_metrics(day) for day in _data_list(response)]}
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return error_payload(
            ToolError(
                str(error),
                code="AUTH_FAILED",
                hint="Set COROS_EMAIL/PASSWORD in the MCP host env",
            )
        )


@mcp.tool()
def list_activities(start_date: str, end_date: str) -> dict:
    """List completed COROS activities in a date range (YYYY-MM-DD)."""
    try:
        response = _get_client().query_activities(start_date, end_date)
        return {
            "activities": [
                normalize_activity_list_item(activity) for activity in _data_list(response)
            ]
        }
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return error_payload(
            ToolError(
                str(error),
                code="AUTH_FAILED",
                hint="Set COROS_EMAIL/PASSWORD in the MCP host env",
            )
        )


@mcp.tool()
def get_activity(activity_id: str) -> dict:
    """Get one completed activity by id."""
    try:
        return normalize_activity_list_item(_get_client().get_activity(activity_id))
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return error_payload(
            ToolError(
                str(error),
                code="AUTH_FAILED",
                hint="Set COROS_EMAIL/PASSWORD in the MCP host env",
            )
        )


@mcp.tool()
def list_workouts(
    sport: str | None = None, name_contains: str | None = None
) -> dict:
    """List library workouts, optionally filtered by program sport and name."""
    try:
        sport_type = program_sport_to_type(sport) if sport is not None else None
        workouts = _get_client().list_programs(sport_type=sport_type)
        if name_contains is not None:
            name_filter = name_contains.lower()
            workouts = [
                workout
                for workout in workouts
                if name_filter in str(workout.get("name", "")).lower()
            ]
        return {
            "workouts": workouts
        }
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _auth_error_payload(error)


@mcp.tool()
def get_workout(workout_id: str) -> dict:
    """Get one library workout by id."""
    try:
        return _get_client().get_program(workout_id)
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _auth_error_payload(error)


@mcp.tool()
def create_workout(name: str, sport: str, steps: list[dict]) -> dict:
    """Create a library workout from sport-agnostic steps. Agent owns coaching. Sync to watch via COROS app after scheduling."""
    try:
        workout = WorkoutCreate.model_validate(
            {"name": name, "sport": sport, "steps": steps}
        )
        normalized_sport = workout.sport.strip().lower()
        program_sport_type = program_sport_to_type(normalized_sport)
        intermediate_steps = friendly_to_coros_steps(workout.steps)
        payload = build_program_payload(
            workout.name, program_sport_type, normalized_sport, intermediate_steps
        )
        workout_id = _get_client().create_program(payload)
        return {"id": workout_id, "name": workout.name, "sport": normalized_sport}
    except ValidationError as error:
        return error_payload(
            ToolError(
                "Invalid workout input.",
                code="VALIDATION_ERROR",
                hint=str(error.errors()[0]["msg"]),
            )
        )
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _auth_error_payload(error)


@mcp.tool()
def delete_workout(workout_id: str) -> dict:
    """Delete one library workout by id."""
    try:
        _get_client().delete_program(workout_id)
        return {"id": workout_id}
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _auth_error_payload(error)


def _auth_error_payload(error: ConfigError) -> dict:
    return error_payload(
        ToolError(
            str(error),
            code="AUTH_FAILED",
            hint="Set COROS_EMAIL/PASSWORD in the MCP host env",
        )
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
