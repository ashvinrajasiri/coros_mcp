import pytest

from coros_mcp.errors import ToolError
from coros_mcp.normalize import (
    normalize_activity_list_item,
    normalize_daily_metrics,
    normalize_scheduled_entry,
    normalize_workout_detail,
    normalize_workout_summary,
    to_yyyymmdd,
)


def test_to_yyyymmdd_converts_iso_date():
    assert to_yyyymmdd("2024-03-09") == "20240309"


def test_to_yyyymmdd_rejects_invalid_date():
    with pytest.raises(ToolError) as exc_info:
        to_yyyymmdd("2024-02-30")
    assert exc_info.value.code == "VALIDATION_ERROR"
    assert exc_info.value.hint == "Use YYYY-MM-DD"


def test_normalize_activity_basic():
    raw = {
        "labelId": "abc",
        "name": "Morning Run",
        "sportType": 100,
        "totalTime": 3600,
        "distance": 10000.0,
        "avgHr": 140,
        "trainingLoad": 80,
        "startTime": 1710000000,
    }

    out = normalize_activity_list_item(raw)

    assert out["id"] == "abc"
    assert out["sport"] == "run"
    assert out["title"] == "Morning Run"
    assert out["duration_sec"] == 3600
    assert out["distance_m"] == 10000.0
    assert out["avg_hr"] == 140
    assert out["training_load"] == 80


def test_normalizers_are_defensive_with_missing_fields():
    assert normalize_activity_list_item({}) == {
        "id": None,
        "sport": None,
        "start": None,
        "duration_sec": None,
        "distance_m": None,
        "avg_hr": None,
        "training_load": None,
        "title": None,
    }
    assert normalize_daily_metrics({}) == {}
    assert normalize_scheduled_entry({}) == {}


def test_normalize_scheduled_entry_maps_common_fields():
    assert normalize_scheduled_entry(
        {
            "scheduleId": "schedule-1",
            "date": "20240309",
            "programId": "workout-1",
            "name": "Intervals",
            "sportType": 100,
        }
    ) == {
        "schedule_id": "schedule-1",
        "date": "20240309",
        "workout_id": "workout-1",
        "name": "Intervals",
        "sport": "run",
    }


def test_normalize_workout_summary_and_detail_are_compact():
    raw = {
        "id": "workout-1",
        "name": "Easy Run",
        "sportType": 1,
        "exerciseBarChart": [{"huge": True}],
        "sourceUrl": "https://example.com/x.png",
        "exercises": [
            {
                "name": "Warm",
                "targetType": 2,
                "targetValue": 600,
                "intensityPercent": 99999,
                "sourceUrl": "https://example.com/y.png",
            }
        ],
    }
    assert normalize_workout_summary(raw) == {
        "id": "workout-1",
        "name": "Easy Run",
        "sport": "run",
        "step_count": 1,
    }
    detail = normalize_workout_detail(raw)
    assert detail["steps"] == [
        {"name": "Warm", "targetType": 2, "targetValue": 600}
    ]
    assert "exerciseBarChart" not in detail
    assert "sourceUrl" not in detail
    assert "intensityPercent" not in detail["steps"][0]
