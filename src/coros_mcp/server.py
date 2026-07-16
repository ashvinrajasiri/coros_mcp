from __future__ import annotations

from datetime import date as calendar_date, timedelta
from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from coros_mcp.client import CorosClient
from coros_mcp.config import ConfigError
from coros_mcp.errors import ToolError, error_payload
from coros_mcp.models import WorkoutCreate
from coros_mcp.normalize import (
    normalize_activity_list_item,
    normalize_daily_metrics,
    normalize_scheduled_entry,
    to_yyyymmdd,
)
from coros_mcp.sports import program_sport_to_type
from coros_mcp.workouts import build_program_payload, friendly_to_coros_steps

load_dotenv()

mcp = FastMCP("coros_mcp")

_client: CorosClient | None = None


def _get_client() -> CorosClient:
    global _client
    if _client is None:
        _client = CorosClient()
    return _client


def _reset_client() -> None:
    """Clear the module-level client singleton (for tests)."""
    global _client
    _client = None


def _data_list(response: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    for key in keys or ("dataList",):
        values = response.get(key, [])
        if isinstance(values, list):
            return [value for value in values if isinstance(value, dict)]
    return []


@mcp.tool()
def get_daily_metrics(start_date: str, end_date: str | None = None) -> dict:
    """Read daily COROS metrics (HRV, RHR, load, fatigue, sleep-as-available) for a date or range (YYYY-MM-DD). Coaching logic stays in the agent. Watch sync is via COROS app after calendar writes."""
    try:
        response = _get_client().get_day_detail(start_date, end_date or start_date)
        return {
            "days": [
                normalize_daily_metrics(day)
                for day in _data_list(response, "dayList", "dataList", "list")
            ]
        }
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _config_error_payload(error)


@mcp.tool()
def list_activities(start_date: str, end_date: str) -> dict:
    """List completed COROS activities in a date range (YYYY-MM-DD)."""
    try:
        response = _get_client().query_activities(start_date, end_date)
        return {
            "activities": [
                normalize_activity_list_item(activity)
                for activity in _data_list(response, "dataList", "list")
            ]
        }
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _config_error_payload(error)


@mcp.tool()
def get_activity(activity_id: str) -> dict:
    """Get one completed activity by id."""
    try:
        return normalize_activity_list_item(_get_client().get_activity(activity_id))
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _config_error_payload(error)


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
        return _config_error_payload(error)


@mcp.tool()
def get_workout(workout_id: str) -> dict:
    """Get one library workout by id."""
    try:
        return _get_client().get_program(workout_id)
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _config_error_payload(error)


@mcp.tool()
def create_workout(name: str, sport: str, steps: list[dict]) -> dict:
    """Create a library workout from sport-agnostic steps. Agent owns coaching.

    Pace targets: use MM:SS with unit min_per_km or min_per_mi.
    Stored unit auto-matches the athlete's COROS account setting (override with
    COROS_DISTANCE_UNIT if needed). Sync via COROS app after scheduling.
    """
    try:
        workout = WorkoutCreate.model_validate(
            {"name": name, "sport": sport, "steps": steps}
        )
        normalized_sport = workout.sport.strip().lower()
        program_sport_type = program_sport_to_type(normalized_sport)
        client = _get_client()
        pace_unit = client.distance_unit
        intermediate_steps = friendly_to_coros_steps(
            workout.steps, pace_store_as=pace_unit
        )
        payload = build_program_payload(
            workout.name, program_sport_type, normalized_sport, intermediate_steps
        )
        workout_id = client.create_program(payload)
        return {
            "id": workout_id,
            "name": workout.name,
            "sport": normalized_sport,
            "distance_unit": pace_unit,
        }
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
        return _config_error_payload(error)


@mcp.tool()
def delete_workout(workout_id: str) -> dict:
    """Delete one library workout by id."""
    try:
        _get_client().delete_program(workout_id)
        return {"id": workout_id}
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _config_error_payload(error)


@mcp.tool()
def list_scheduled_workouts(start_date: str, end_date: str) -> dict:
    """List calendar entries YYYY-MM-DD..YYYY-MM-DD; schedule_id is an entry id, not a library workout id."""
    try:
        plan = _get_client().query_schedule(start_date, end_date)
        programs = _schedule_programs_by_id(plan.get("programs"))
        entities = plan.get("entities")
        return {
            "scheduled": [
                normalize_scheduled_entry(
                    entity, programs.get(str(entity.get("idInPlan")))
                )
                for entity in entities
                if isinstance(entity, dict)
            ]
            if isinstance(entities, list)
            else []
        }
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _config_error_payload(error)


@mcp.tool()
def schedule_workout(workout_id: str, date: str) -> dict:
    """Schedule a library workout on YYYY-MM-DD (including far-future dates); it appears after COROS app syncs to watch."""
    try:
        client = _get_client()
        plan = client.query_schedule(date, date)
        program = client.get_program(workout_id)
        id_in_plan = str(int(plan.get("maxPlanProgramId") or 0) + 1)
        payload = {
            "entities": [
                {
                    "happenDay": to_yyyymmdd(date),
                    "idInPlan": id_in_plan,
                    "sortNo": 0,
                    "dayNo": 0,
                    "sortNoInPlan": 0,
                    "sortNoInSchedule": 0,
                    "exerciseBarChart": program.get("exerciseBarChart") or [],
                }
            ],
            "programs": [{**program, "idInPlan": id_in_plan}],
            "versionObjects": [{"id": id_in_plan, "status": 1}],
            "pbVersion": 2,
        }
        client.update_schedule(payload)
        return {"workout_id": workout_id, "date": date, "id_in_plan": id_in_plan}
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _config_error_payload(error)


@mcp.tool()
def unschedule_workout(schedule_id: str) -> dict:
    """Remove one calendar entry by the schedule_id returned from list_scheduled_workouts."""
    try:
        client = _get_client()
        today = calendar_date.today()
        entity = None
        plan: dict[str, Any] | None = None
        # Query in ~60-day chunks — a single huge range can timeout on COROS.
        window_start = today - timedelta(days=30)
        window_end = today + timedelta(days=400)
        cursor = window_start
        while cursor <= window_end:
            chunk_end = min(cursor + timedelta(days=60), window_end)
            candidate_plan = client.query_schedule(
                cursor.isoformat(), chunk_end.isoformat()
            )
            entities = candidate_plan.get("entities")
            if isinstance(entities, list):
                match = next(
                    (
                        item
                        for item in entities
                        if isinstance(item, dict)
                        and str(item.get("id")) == str(schedule_id)
                    ),
                    None,
                )
                if match is not None:
                    entity = match
                    plan = candidate_plan
                    break
            cursor = chunk_end + timedelta(days=1)

        if entity is None or plan is None:
            raise ToolError(
                f"Scheduled workout {schedule_id!r} was not found in the searchable calendar window.",
                code="NOT_FOUND",
                hint="List scheduled workouts to obtain a current schedule_id.",
            )
        version_object: dict[str, Any] = {
            "id": str(entity["idInPlan"]),
            "status": 3,
        }
        if entity.get("planProgramId") is not None:
            version_object["planProgramId"] = str(entity["planProgramId"])
        if plan.get("id") is not None:
            version_object["planId"] = plan["id"]
        client.update_schedule(
            {
                "versionObjects": [version_object],
                "pbVersion": 2,
            }
        )
        return {"schedule_id": schedule_id}
    except ToolError as error:
        return error_payload(error)
    except ConfigError as error:
        return _config_error_payload(error)


def _schedule_programs_by_id(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    return {
        str(program["idInPlan"]): program
        for program in value
        if isinstance(program, dict) and program.get("idInPlan") is not None
    }


def _config_error_payload(error: ConfigError) -> dict:
    message = str(error)
    if "REGION" in message:
        return error_payload(
            ToolError(
                message,
                code="VALIDATION_ERROR",
                hint="COROS_REGION must be one of: us, eu, cn",
            )
        )
    return error_payload(
        ToolError(
            message,
            code="AUTH_FAILED",
            hint="Set COROS_EMAIL/PASSWORD in the MCP host env",
        )
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
