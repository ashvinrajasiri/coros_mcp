from coros_mcp.normalize import normalize_scheduled_entry


class FakeClient:
    def __init__(self):
        self.queried_ranges: list[tuple[str, str]] = []
        self.update_payloads: list[dict] = []

    def query_schedule(self, start: str, end: str) -> dict:
        self.queried_ranges.append((start, end))
        return {
            "id": "plan-1",
            "maxPlanProgramId": "999999999999999999",
            "entities": [
                {
                    "id": "schedule-entry-1",
                    "happenDay": 20260720,
                    "idInPlan": "999999999999999998",
                    "planProgramId": "plan-program-1",
                }
            ],
            "programs": [
                {
                    "id": "workout-1",
                    "idInPlan": "999999999999999998",
                    "name": "Intervals",
                    "sportData": {"sportType": 100},
                }
            ],
        }

    def get_program(self, workout_id: str) -> dict:
        return {
            "id": workout_id,
            "name": "Long Run",
            "exerciseBarChart": [{"type": 1}],
        }

    def update_schedule(self, payload: dict) -> dict:
        self.update_payloads.append(payload)
        return {}


def test_schedule_workout_uses_next_plan_id_and_add_payload(monkeypatch):
    from coros_mcp import server

    client = FakeClient()
    monkeypatch.setattr(server, "_get_client", lambda: client)

    assert server.schedule_workout("workout-2", "2026-07-21") == {
        "workout_id": "workout-2",
        "date": "2026-07-21",
        "id_in_plan": "1000000000000000000",
    }
    assert client.queried_ranges == [("2026-07-21", "2026-07-21")]
    assert client.update_payloads == [
        {
            "entities": [
                {
                    "happenDay": "20260721",
                    "idInPlan": "1000000000000000000",
                    "sortNo": 0,
                    "dayNo": 0,
                    "sortNoInPlan": 0,
                    "sortNoInSchedule": 0,
                    "exerciseBarChart": [{"type": 1}],
                }
            ],
            "programs": [
                {
                    "id": "workout-2",
                    "name": "Long Run",
                    "exerciseBarChart": [{"type": 1}],
                    "idInPlan": "1000000000000000000",
                }
            ],
            "versionObjects": [{"id": "1000000000000000000", "status": 1}],
            "pbVersion": 2,
        }
    ]


def test_list_scheduled_workouts_returns_normalized_entries(monkeypatch):
    from coros_mcp import server

    client = FakeClient()
    monkeypatch.setattr(server, "_get_client", lambda: client)

    assert server.list_scheduled_workouts("2026-07-01", "2026-08-31") == {
        "scheduled": [
            {
                "schedule_id": "schedule-entry-1",
                "date": "20260720",
                "workout_id": "workout-1",
                "name": "Intervals",
                "sport": "run",
            }
        ]
    }
    assert client.queried_ranges == [("2026-07-01", "2026-08-31")]


def test_unschedule_workout_sends_delete_status(monkeypatch):
    from coros_mcp import server

    client = FakeClient()
    monkeypatch.setattr(server, "_get_client", lambda: client)

    assert server.unschedule_workout("schedule-entry-1") == {
        "schedule_id": "schedule-entry-1"
    }
    assert client.update_payloads == [
        {
            "versionObjects": [
                {
                    "id": "999999999999999998",
                    "planProgramId": "plan-program-1",
                    "planId": "plan-1",
                    "status": 3,
                }
            ],
            "pbVersion": 2,
        }
    ]


def test_multi_month_ranges_are_passed_to_schedule_query(monkeypatch):
    from coros_mcp import server

    client = FakeClient()
    monkeypatch.setattr(server, "_get_client", lambda: client)

    server.list_scheduled_workouts("2026-01-01", "2026-04-30")

    assert client.queried_ranges == [("2026-01-01", "2026-04-30")]


def test_normalize_scheduled_entry_joins_program_fields():
    assert normalize_scheduled_entry(
        {
            "id": "schedule-entry-1",
            "happenDay": 20260720,
            "idInPlan": "plan-program-1",
        },
        {
            "id": "workout-1",
            "idInPlan": "plan-program-1",
            "name": "Intervals",
            "sportData": {"sportType": 100},
        },
    ) == {
        "schedule_id": "schedule-entry-1",
        "date": "20260720",
        "workout_id": "workout-1",
        "name": "Intervals",
        "sport": "run",
    }
