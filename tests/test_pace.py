import pytest

from coros_mcp.errors import ToolError
from coros_mcp.pace import parse_pace_target


def test_km_pace_to_ms_per_km():
    result = parse_pace_target("4:05", unit="min_per_km")
    assert result["target_low"] == 245_000
    assert result["target_high"] == 245_000
    assert result["intensity_display_unit"] == 2


def test_mi_pace_converts_to_ms_per_km():
    result = parse_pace_target("8:00/mi")
    assert 298_000 <= result["target_low"] <= 298_500
    assert result["intensity_display_unit"] == 2


def test_easy_run_pace_min_per_mi():
    result = parse_pace_target("9:30", high=None, unit="min_per_mi")
    # 9:30/mi ≈ 354 sec/km → ~354000 ms/km
    assert 353_000 <= result["target_low"] <= 355_000


def test_pace_range_orders_fast_to_slow():
    result = parse_pace_target("4:15", "4:05", unit="min_per_km")
    assert result["target_low"] == 245_000
    assert result["target_high"] == 255_000


def test_invalid_pace_raises():
    with pytest.raises(ToolError) as error:
        parse_pace_target("not-a-pace", unit="min_per_km")
    assert error.value.code == "VALIDATION_ERROR"
