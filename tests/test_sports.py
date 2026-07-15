import pytest

from coros_mcp.errors import ToolError
from coros_mcp.sports import sport_to_type, type_to_sport


def test_run_sport_roundtrip():
    assert sport_to_type("run") == 100
    assert type_to_sport(100) == "run"


def test_unknown_sport_raises_validation_error():
    with pytest.raises(ToolError) as error:
        sport_to_type("quidditch")

    assert error.value.code == "VALIDATION_ERROR"
