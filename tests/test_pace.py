import os

import pytest

from coros_mcp.errors import ToolError
from coros_mcp.models import WorkoutCreate
from coros_mcp.pace import parse_pace_target
from coros_mcp.workouts import friendly_to_coros_steps, intermediate_to_program_exercises


def test_mi_input_converts_to_km_when_preference_is_km(monkeypatch):
    monkeypatch.setenv("COROS_DISTANCE_UNIT", "km")
    result = parse_pace_target("9:30", unit="min_per_mi")
    # 9:30/mi ≈ 5:54/km → ~354182 ms/km
    assert 353_000 <= result["target_low"] <= 355_000
    assert result["intensity_display_unit"] == 2


def test_km_pace_stores_ms_per_km(monkeypatch):
    monkeypatch.setenv("COROS_DISTANCE_UNIT", "km")
    result = parse_pace_target("5:45", unit="min_per_km")
    assert result["target_low"] == 345_000
    assert result["intensity_display_unit"] == 2


def test_mi_preference_keeps_ms_per_mile(monkeypatch):
    monkeypatch.setenv("COROS_DISTANCE_UNIT", "mi")
    result = parse_pace_target("5:10/mi")
    assert result["target_low"] == 310_000
    assert result["intensity_display_unit"] == 1


def test_bare_mmss_uses_distance_unit_preference(monkeypatch):
    monkeypatch.setenv("COROS_DISTANCE_UNIT", "km")
    result = parse_pace_target("5:45")
    assert result["target_low"] == 345_000
    assert result["intensity_display_unit"] == 2


def test_pace_range_converts_and_orders(monkeypatch):
    monkeypatch.setenv("COROS_DISTANCE_UNIT", "km")
    result = parse_pace_target("5:45", "5:10", unit="min_per_mi")
    assert result["target_low"] < result["target_high"]
    assert result["intensity_display_unit"] == 2


def test_invalid_pace_raises(monkeypatch):
    monkeypatch.setenv("COROS_DISTANCE_UNIT", "km")
    with pytest.raises(ToolError) as error:
        parse_pace_target("not-a-pace", unit="min_per_km")
    assert error.value.code == "VALIDATION_ERROR"


def test_easy_run_program_exercise_metric(monkeypatch):
    monkeypatch.setenv("COROS_DISTANCE_UNIT", "km")
    workout = WorkoutCreate.model_validate(
        {
            "name": "Easy",
            "sport": "run",
            "steps": [
                {
                    "type": "steady",
                    "duration": {"unit": "time", "value": 30, "time_unit": "min"},
                    "target": {"kind": "pace", "low": "9:30", "unit": "min_per_mi"},
                }
            ],
        }
    )
    exercises = intermediate_to_program_exercises(
        friendly_to_coros_steps(workout.steps), sport="run"
    )
    exercise = exercises[0]
    assert exercise["intensityType"] == 3
    assert exercise["intensityDisplayUnit"] == 2
    assert 353_000 <= exercise["intensityValue"] <= 355_000
