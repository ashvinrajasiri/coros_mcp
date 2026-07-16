import pytest

from coros_mcp.config import ConfigError
from coros_mcp.errors import ToolError


class FakeClient:
    def get_day_detail(self, start: str, end: str) -> dict:
        assert (start, end) == ("2024-03-09", "2024-03-10")
        return {
            "dayList": [
                {"date": "20240309", "restingHr": 48, "trainingLoad": 75},
                {"date": "20240310", "sleepTime": 28800},
            ]
        }

    def query_activities(self, start: str, end: str) -> dict:
        assert (start, end) == ("2024-03-09", "2024-03-10")
        return {
            "dataList": [
                {
                    "labelId": "activity-1",
                    "sportType": 100,
                    "name": "Morning Run",
                    "distance": 5000,
                }
            ]
        }

    def get_activity(self, activity_id: str) -> dict:
        assert activity_id == "activity-1"
        return {
            "labelId": "activity-1",
            "sportType": 100,
            "name": "Morning Run",
            "distance": 5000,
        }


def test_get_daily_metrics_normalizes_requested_range(monkeypatch):
    from coros_mcp import server

    monkeypatch.setattr(server, "_get_client", FakeClient)

    assert server.get_daily_metrics("2024-03-09", "2024-03-10") == {
        "days": [
            {"date": "20240309", "rhr": 48, "training_load": 75},
            {"date": "20240310", "sleep_sec": 28800},
        ]
    }


def test_get_daily_metrics_uses_start_date_when_end_date_is_omitted(monkeypatch):
    from coros_mcp import server

    class SingleDayClient(FakeClient):
        def get_day_detail(self, start: str, end: str) -> dict:
            assert (start, end) == ("2024-03-09", "2024-03-09")
            return {"dataList": []}

    monkeypatch.setattr(server, "_get_client", SingleDayClient)

    assert server.get_daily_metrics("2024-03-09") == {"days": []}


def test_list_activities_normalizes_data_list(monkeypatch):
    from coros_mcp import server

    monkeypatch.setattr(server, "_get_client", FakeClient)

    assert server.list_activities("2024-03-09", "2024-03-10") == {
        "activities": [
            {
                "id": "activity-1",
                "sport": "run",
                "start": None,
                "duration_sec": None,
                "distance_m": 5000,
                "avg_hr": None,
                "training_load": None,
                "title": "Morning Run",
            }
        ]
    }


def test_get_activity_normalizes_detail(monkeypatch):
    from coros_mcp import server

    monkeypatch.setattr(server, "_get_client", FakeClient)

    assert server.get_activity("activity-1")["id"] == "activity-1"


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            ToolError("API unavailable", code="COROS_API_ERROR", hint="Try later"),
            {"error": "API unavailable", "code": "COROS_API_ERROR", "hint": "Try later"},
        ),
        (
            ConfigError("missing credentials"),
            {
                "error": "missing credentials",
                "code": "AUTH_FAILED",
                "hint": "Set COROS_EMAIL/PASSWORD in the MCP host env",
            },
        ),
    ],
)
def test_tools_return_standard_error_payload(monkeypatch, error, expected):
    from coros_mcp import server

    def raise_error():
        raise error

    monkeypatch.setattr(server, "_get_client", raise_error)

    assert server.get_activity("activity-1") == expected
