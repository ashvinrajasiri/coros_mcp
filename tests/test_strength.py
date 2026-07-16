import pytest

from coros_mcp.errors import ToolError
from coros_mcp.strength import (
    build_strength_program_payload,
    humanize_overview,
    resolve_exercise,
    search_catalog,
)


def _catalog() -> list[dict]:
    return [
        {
            "id": "1",
            "name": "T1004",
            "overview": "sid_strength_push_ups",
            "muscle": [2],
            "equipment": [1],
            "restValue": 30,
            "sourceUrl": "https://example.com/push.png",
        },
        {
            "id": "2",
            "name": "T1010",
            "overview": "sid_strength_planks",
            "muscle": [1],
            "equipment": [1],
            "restValue": 30,
        },
        {
            "id": "3",
            "name": "T1061",
            "overview": "sid_strength_squats",
            "muscle": [5],
            "equipment": [1],
            "restValue": 45,
        },
    ]


def test_humanize_overview():
    assert humanize_overview("sid_strength_push_ups") == "Push Ups"


def test_search_catalog_matches_human_name():
    results = search_catalog(_catalog(), "push")
    assert len(results) == 1
    assert results[0]["name"] == "Push Ups"
    assert results[0]["id"] == "1"


def test_resolve_exercise_exact_name():
    item = resolve_exercise(_catalog(), "Planks")
    assert item["id"] == "2"
    assert item["code"] == "T1010"


def test_resolve_exercise_ambiguous_raises():
    catalog = _catalog() + [
        {
            "id": "9",
            "name": "T1999",
            "overview": "sid_strength_push_up_plus",
            "muscle": [],
            "equipment": [],
        }
    ]
    with pytest.raises(ToolError) as error:
        resolve_exercise(catalog, "push")
    assert error.value.code == "VALIDATION_ERROR"


def test_build_strength_program_payload():
    payload = build_strength_program_payload(
        "Quick Push",
        [
            {"name": "Push Ups", "reps": 15, "rest_sec": 45},
            {"name": "Planks", "duration_sec": 40},
        ],
        catalog=_catalog(),
        sets=3,
    )
    assert payload["sportType"] == 4
    assert payload["sets"] == 3
    assert payload["name"] == "Quick Push"
    assert len(payload["exercises"]) == 2
    assert payload["exercises"][0]["originId"] == "1"
    assert payload["exercises"][0]["targetType"] == 3
    assert payload["exercises"][0]["targetValue"] == 15
    assert payload["exercises"][0]["restValue"] == 45
    assert payload["exercises"][1]["targetType"] == 2
    assert payload["exercises"][1]["targetValue"] == 40


def test_build_requires_reps_or_duration():
    with pytest.raises(ToolError) as error:
        build_strength_program_payload(
            "Bad",
            [{"name": "Squats"}],
            catalog=_catalog(),
        )
    assert error.value.code == "VALIDATION_ERROR"
