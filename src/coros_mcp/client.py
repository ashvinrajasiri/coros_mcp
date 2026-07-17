from __future__ import annotations

from collections.abc import Mapping
import json
from typing import Any

import httpx

from coros_mcp.auth import AuthSession, base_url_for_region
from coros_mcp.config import Config, load_config
from coros_mcp.errors import ToolError
from coros_mcp.normalize import to_yyyymmdd

_AUTH_RESULT_CODES = {"401", "1003", "1004", "1005", "UNAUTHORIZED"}


class CorosClient:
    """Small synchronous client for the undocumented COROS Training Hub API."""

    def __init__(self, config: Config | None = None):
        self._config = config or load_config()
        self._auth = AuthSession(self._config)
        self._client = httpx.Client(timeout=60.0)
        self._base_url = base_url_for_region(self._config.region)

    def ensure_auth(self) -> None:
        try:
            self._auth.headers()
        except ToolError as error:
            if error.code != "UNAUTHORIZED":
                raise
            self._auth.login(self._client)
        if self._auth.account_unit is None:
            self._auth.refresh_account_unit(self._client)

    @property
    def distance_unit(self) -> str:
        """km or mi from account settings (or COROS_DISTANCE_UNIT override)."""
        self.ensure_auth()
        return self._auth.distance_unit

    def close(self) -> None:
        self._client.close()

    def get_day_detail(self, start: str, end: str) -> dict:
        return self._as_dict(
            self._request(
                "GET",
                "/analyse/dayDetail/query",
                params=_day_params(start, end),
            )
        )

    def query_activities(
        self, start: str, end: str, page: int = 1, size: int = 50
    ) -> dict:
        return self._as_dict(
            self._request(
                "GET",
                "/activity/query",
                params={
                    **_day_params(start, end),
                    "pageNumber": page,
                    "size": size,
                },
            )
        )

    def get_activity(self, activity_id: str) -> dict:
        # Assumption: this endpoint accepts list-item labelId values. Confirm
        # against a live payload before exposing activity detail in a tool.
        return self._as_dict(
            self._request("GET", "/activity/detail", params={"labelId": activity_id})
        )

    def list_programs(self, sport_type: int | None = None) -> list[dict]:
        payload: dict[str, Any] = {
            "name": "",
            "supportRestExercise": 1,
            "startNo": 0,
            "limitSize": 100,
        }
        if sport_type is not None:
            payload["sportType"] = sport_type
        data = self._request("POST", "/training/program/query", json=payload)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, Mapping):
            for key in ("dataList", "list", "items", "programs"):
                values = data.get(key)
                if isinstance(values, list):
                    return [item for item in values if isinstance(item, dict)]
        return []

    def get_program(self, program_id: str) -> dict:
        return self._as_dict(
            self._request(
                "GET", "/training/program/detail", params={"id": program_id}
            )
        )

    def create_program(self, payload: dict) -> str:
        data = self._request("POST", "/training/program/add", json=payload)
        if isinstance(data, Mapping):
            for key in ("id", "programId", "program_id", "labelId"):
                if data.get(key) is not None:
                    return str(data[key])
        if isinstance(data, (str, int)):
            return str(data)
        raise ToolError(
            "COROS API did not return a created program id",
            code="COROS_API_ERROR",
            hint="Try creating the workout again.",
        )

    def list_exercises(self, sport_type: int = 4) -> list[dict]:
        """Fetch the Training Hub exercise catalog (sport_type 4 = strength)."""
        data = self._request(
            "GET",
            "/training/exercise/query",
            params={"sportType": sport_type},
        )
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, Mapping):
            for key in ("dataList", "list", "items", "exercises"):
                values = data.get(key)
                if isinstance(values, list):
                    return [item for item in values if isinstance(item, dict)]
        return []

    def delete_program(self, program_id: str) -> None:
        self.delete_programs([program_id])

    def delete_programs(self, program_ids: list[str]) -> None:
        """Delete one or more library programs (COROS accepts a JSON id array)."""
        ids = [str(program_id) for program_id in program_ids if program_id]
        if not ids:
            return
        # Stay under typical request body sizes when clearing large libraries.
        chunk_size = 25
        for start in range(0, len(ids), chunk_size):
            chunk = ids[start : start + chunk_size]
            self._request(
                "POST",
                "/training/program/delete",
                content=json.dumps(chunk),
            )

    def query_schedule(self, start: str, end: str) -> dict:
        # Schedule uses startDate/endDate; analyse/activity use startDay/endDay.
        return self._as_dict(
            self._request(
                "GET",
                "/training/schedule/query",
                params={**_date_params(start, end), "supportRestExercise": 1},
            )
        )

    def update_schedule(self, payload: dict) -> dict:
        return self._as_dict(
            self._request("POST", "/training/schedule/update", json=payload)
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
        content: str | bytes | None = None,
    ) -> Any:
        for attempt in range(2):
            self.ensure_auth()
            try:
                response = self._client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers=self._auth.headers(),
                    params=params,
                    json=json,
                    content=content,
                )
            except httpx.HTTPError as error:
                raise ToolError(
                    "COROS API request failed",
                    code="COROS_API_ERROR",
                    hint="Check your COROS connection and try again.",
                ) from error

            if _is_auth_response(response):
                self._auth.clear()
                if attempt == 0:
                    continue
            return _check_response(response)

        raise AssertionError("unreachable")

    @staticmethod
    def _as_dict(value: Any) -> dict:
        return value if isinstance(value, dict) else {}


def _date_params(start: str, end: str) -> dict[str, str]:
    return {"startDate": to_yyyymmdd(start), "endDate": to_yyyymmdd(end)}


def _day_params(start: str, end: str) -> dict[str, str]:
    return {"startDay": to_yyyymmdd(start), "endDay": to_yyyymmdd(end)}


def _is_auth_response(response: httpx.Response) -> bool:
    if response.status_code == 401:
        return True
    try:
        payload = response.json()
    except ValueError:
        return False
    if not isinstance(payload, dict):
        return False
    result = str(payload.get("result", "")).upper()
    if result in _AUTH_RESULT_CODES:
        return True
    message = " ".join(
        str(payload.get(key, "")) for key in ("message", "msg", "error")
    ).lower()
    return "token" in message and any(
        marker in message for marker in ("invalid", "expired", "unauthorized")
    )


def _check_response(response: httpx.Response) -> Any:
    """Validate a COROS envelope and return its data value."""
    try:
        payload = response.json()
    except ValueError as error:
        raise ToolError(
            "COROS API returned invalid JSON",
            code="COROS_API_ERROR",
            hint="Try again later.",
        ) from error

    if not isinstance(payload, dict) or response.status_code >= 400:
        raise ToolError(
            "COROS API request failed",
            code="COROS_API_ERROR",
            hint="Try again later.",
        )
    if payload.get("result") != "0000":
        raise ToolError(
            str(payload.get("message") or payload.get("msg") or "COROS API error"),
            code="COROS_API_ERROR",
            hint="Check the request and try again.",
        )
    return payload.get("data")
