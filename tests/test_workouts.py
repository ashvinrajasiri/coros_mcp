from coros_mcp.models import WorkoutCreate
from coros_mcp.workouts import coros_steps_to_friendly, friendly_to_coros_steps


def test_simple_timed_interval_maps_duration_seconds():
    workout = WorkoutCreate.model_validate(
        {
            "name": "Easy",
            "sport": "run",
            "steps": [
                {
                    "type": "warmup",
                    "duration": {"unit": "time", "value": 10, "time_unit": "min"},
                },
                {
                    "type": "steady",
                    "duration": {"unit": "time", "value": 30, "time_unit": "min"},
                },
                {
                    "type": "cooldown",
                    "duration": {"unit": "time", "value": 5, "time_unit": "min"},
                },
            ],
        }
    )

    steps = friendly_to_coros_steps(workout.steps)

    assert isinstance(steps, list)
    assert len(steps) == 3
    assert steps[0]["duration"] == 600


def test_repeat_nest_preserves_count_and_mapped_child_steps():
    workout = WorkoutCreate.model_validate(
        {
            "name": "Intervals",
            "sport": "run",
            "steps": [
                {
                    "type": "repeat",
                    "count": 4,
                    "steps": [
                        {
                            "type": "steady",
                            "duration": {
                                "unit": "time",
                                "value": 2,
                                "time_unit": "min",
                            },
                        }
                    ],
                }
            ],
        }
    )

    steps = friendly_to_coros_steps(workout.steps)

    assert steps == [
        {
            "type": "repeat",
            "count": 4,
            "steps": [{"type": "steady", "duration": 120}],
        }
    ]


def test_pace_target_maps_to_seconds_per_kilometer():
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

    assert steps[0]["duration"] == 100000
    assert steps[0]["target"] == {"kind": "pace", "target_low": 270}


def test_simple_timed_steps_roundtrip_to_friendly_models():
    friendly_steps = coros_steps_to_friendly(
        [
            {"type": "warmup", "duration": 600},
            {"type": "steady", "duration": 1800},
            {"type": "cooldown", "duration": 300},
        ]
    )

    assert [step.model_dump(exclude_none=True) for step in friendly_steps] == [
        {
            "type": "warmup",
            "duration": {
                "unit": "time",
                "value": 10,
                "time_unit": "min",
                "distance_unit": "m",
            },
        },
        {
            "type": "steady",
            "duration": {
                "unit": "time",
                "value": 30,
                "time_unit": "min",
                "distance_unit": "m",
            },
        },
        {
            "type": "cooldown",
            "duration": {
                "unit": "time",
                "value": 5,
                "time_unit": "min",
                "distance_unit": "m",
            },
        },
    ]
