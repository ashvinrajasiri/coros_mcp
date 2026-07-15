from coros_mcp.errors import ToolError, error_payload


def test_error_payload_shape():
    err = ToolError("bad login", code="AUTH_FAILED", hint="Check credentials")
    assert error_payload(err) == {
        "error": "bad login",
        "code": "AUTH_FAILED",
        "hint": "Check credentials",
    }
