from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from coros_mcp.client import CorosClient
from coros_mcp.config import ConfigError
from coros_mcp.errors import ToolError, error_payload
from coros_mcp.normalize import normalize_activity_list_item, normalize_daily_metrics

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


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
