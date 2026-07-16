from coros_mcp.models import WorkoutCreate
from coros_mcp.workouts import (
    coros_steps_to_friendly,
    friendly_to_coros_steps,
    intermediate_to_program_exercises,
)


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
            "steps": [
                {"type": "steady", "duration": 120, "duration_type": "time"}
            ],
        }
    ]


def test_pace_target_maps_to_ms_per_kilometer():
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
    assert steps[0]["target"] == {
        "kind": "pace",
        "target_low": 270_000,
        "target_high": 270_000,
        "intensity_display_unit": 2,
    }


def test_easy_run_pace_min_per_mi_program_exercise():
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
    assert exercise["intensityValue"] == exercise["intensityValueExtend"]


def test_intermediate_steps_become_timed_program_exercises():
    exercises = intermediate_to_program_exercises(
        [
            {"type": "warmup", "duration": 600},
            {"type": "steady", "duration": 1800},
            {"type": "cooldown", "duration": 300},
        ],
        sport="run",
    )

    assert [
        (exercise["exerciseType"], exercise["targetType"], exercise["targetValue"])
        for exercise in exercises
    ] == [(1, 2, 600), (2, 2, 1800), (3, 2, 300)]
    assert [exercise["sortNo"] for exercise in exercises] == [
        16_777_216,
        33_554_432,
        50_331_648,
    ]


def test_distance_duration_remains_distance_for_short_segments():
    workout = WorkoutCreate.model_validate(
        {
            "name": "Strides",
            "sport": "run",
            "steps": [
                {
                    "type": "steady",
                    "duration": {"unit": "distance", "value": 50, "distance_unit": "m"},
                }
            ],
        }
    )

    exercises = intermediate_to_program_exercises(
        friendly_to_coros_steps(workout.steps), sport="run"
    )

    assert exercises[0]["targetType"] == 5
    assert exercises[0]["targetValue"] == 5000


def test_intermediate_repeat_becomes_group_with_timed_children():
    exercises = intermediate_to_program_exercises(
        [
            {
                "type": "repeat",
                "count": 3,
                "steps": [
                    {"type": "steady", "duration": 120},
                    {"type": "recovery", "duration": 60},
                ],
            }
        ],
        sport="run",
    )

    assert exercises[0] == {
        "exerciseType": 0,
        "sortNo": 16_777_216,
        "isGroup": True,
        "sets": 3,
        "groupId": 16_777_216,
    }
    assert [
        (exercise["exerciseType"], exercise["targetType"], exercise["targetValue"])
        for exercise in exercises[1:]
    ] == [(2, 2, 120), (4, 2, 60)]
    assert [exercise["sortNo"] for exercise in exercises[1:]] == [
        16_842_752,
        16_908_288,
    ]


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
