from coros_mcp.errors import ToolError


class FakeClient:
    def __init__(self):
        self.created_payload: dict | None = None
        self.deleted_id: str | None = None
        self.list_arg: int | None = None

    @property
    def distance_unit(self) -> str:
        return "km"

    def list_programs(self, sport_type: int | None = None) -> list[dict]:
        self.list_arg = sport_type
        return [{"id": "workout-1", "name": "Morning Run"}]

    def get_program(self, program_id: str) -> dict:
        return {"id": program_id, "name": "Morning Run"}

    def create_program(self, payload: dict) -> str:
        self.created_payload = payload
        return "workout-1"

    def delete_program(self, program_id: str) -> None:
        self.deleted_id = program_id


def test_create_workout_maps_run_steps_and_creates_program(monkeypatch):
    from coros_mcp import server

    client = FakeClient()
    monkeypatch.setattr(server, "_get_client", lambda: client)

    result = server.create_workout(
        "Easy Run",
        "run",
        [
            {
                "type": "steady",
                "duration": {"unit": "time", "value": 30, "time_unit": "min"},
            }
        ],
    )

    assert result == {
        "id": "workout-1",
        "name": "Easy Run",
        "sport": "run",
        "distance_unit": "km",
    }
    assert client.created_payload is not None
    assert client.created_payload["sportType"] == 1
    assert client.created_payload["exercises"][0]["targetType"] == 2
    assert client.created_payload["exercises"][0]["targetValue"] == 1800


def test_create_workout_returns_error_payload_for_invalid_step(monkeypatch):
    from coros_mcp import server

    monkeypatch.setattr(server, "_get_client", FakeClient)

    assert server.create_workout(
        "Bad",
        "run",
        [{"type": "steady", "duration": {"unit": "time", "value": 0}}],
    )["code"] == "VALIDATION_ERROR"


def test_delete_workout_deletes_single_id(monkeypatch):
    from coros_mcp import server

    client = FakeClient()
    monkeypatch.setattr(server, "_get_client", lambda: client)

    assert server.delete_workout("123456789012345678") == {"id": "123456789012345678"}
    assert client.deleted_id == "123456789012345678"


def test_list_and_get_workouts_delegate_filters(monkeypatch):
    from coros_mcp import server

    client = FakeClient()
    monkeypatch.setattr(server, "_get_client", lambda: client)

    assert server.list_workouts("run", "Morning") == {
        "workouts": [{"id": "workout-1", "name": "Morning Run"}]
    }
    assert client.list_arg == 1
    assert server.get_workout("workout-1") == {"id": "workout-1", "name": "Morning Run"}


def test_library_tools_return_standard_error_payload(monkeypatch):
    from coros_mcp import server

    def raise_error():
        raise ToolError("API unavailable", code="COROS_API_ERROR", hint="Try later")

    monkeypatch.setattr(server, "_get_client", raise_error)

    assert server.delete_workout("workout-1") == {
        "error": "API unavailable",
        "code": "COROS_API_ERROR",
        "hint": "Try later",
    }
