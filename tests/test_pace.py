import pytest

from coros_mcp.errors import ToolError
from coros_mcp.models import WorkoutCreate
from coros_mcp.pace import parse_pace_target
from coros_mcp.workouts import friendly_to_coros_steps, intermediate_to_program_exercises


def test_mi_pace_stores_ms_per_mile_with_display_unit_1():
    result = parse_pace_target("9:30", unit="min_per_mi")
    assert result["target_low"] == 570_000
    assert result["target_high"] == 570_000
    assert result["intensity_display_unit"] == 1


def test_mi_pace_slash_form():
    result = parse_pace_target("8:00/mi")
    assert result["target_low"] == 480_000
    assert result["intensity_display_unit"] == 1


def test_km_pace_stores_ms_per_km_with_display_unit_2():
    result = parse_pace_target("4:05", unit="min_per_km")
    assert result["target_low"] == 245_000
    assert result["intensity_display_unit"] == 2


def test_hm_pace_matches_live_library_encoding():
    """Live COROS library uses ms/mi + displayUnit 1 (e.g. 5:10/mi → 310000)."""
    result = parse_pace_target("5:10/mi")
    assert result["target_low"] == 310_000
    assert result["intensity_display_unit"] == 1


def test_pace_range_orders_fast_to_slow():
    result = parse_pace_target("5:45", "5:10", unit="min_per_mi")
    assert result["target_low"] == 310_000
    assert result["target_high"] == 345_000
    assert result["intensity_display_unit"] == 1


def test_default_unit_is_miles_when_omitted():
    result = parse_pace_target("9:30")
    assert result["target_low"] == 570_000
    assert result["intensity_display_unit"] == 1


def test_invalid_pace_raises():
    with pytest.raises(ToolError) as error:
        parse_pace_target("not-a-pace", unit="min_per_mi")
    assert error.value.code == "VALIDATION_ERROR"


def test_easy_run_program_exercise_matches_live_encoding():
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
    assert exercise["intensityDisplayUnit"] == 1
    assert exercise["intensityValue"] == 570_000
    assert exercise["intensityValueExtend"] == 570_000


def test_km_tempo_program_exercise():
    workout = WorkoutCreate.model_validate(
        {
            "name": "Tempo",
            "sport": "run",
            "steps": [
                {
                    "type": "steady",
                    "duration": {"unit": "distance", "value": 1, "distance_unit": "km"},
                    "target": {"kind": "pace", "low": "4:30", "unit": "min_per_km"},
                }
            ],
        }
    )
    steps = friendly_to_coros_steps(workout.steps)
    assert steps[0]["target"] == {
        "kind": "pace",
        "target_low": 270_000,
        "target_high": 270_000,
        "intensity_display_unit": 2,
    }
    exercises = intermediate_to_program_exercises(steps, sport="run")
    assert exercises[0]["intensityDisplayUnit"] == 2
    assert exercises[0]["intensityValue"] == 270_000
