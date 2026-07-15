import json

import httpx
import pytest

from coros_mcp.auth import AuthSession, base_url_for_region, hash_password
from coros_mcp.config import Config
from coros_mcp.errors import ToolError


def test_hash_password_md5_hex():
    assert hash_password("password") == "5f4dcc3b5aa765d61d8327deb882cf99"


def test_base_url_us():
    assert base_url_for_region("us") == "https://teamapi.coros.com"


def test_base_url_eu():
    assert base_url_for_region("eu") == "https://teameuapi.coros.com"


def test_base_url_invalid_region_raises_validation_error():
    with pytest.raises(ToolError) as error:
        base_url_for_region("invalid")

    assert error.value.code == "VALIDATION_ERROR"


def test_login_saves_token_cache_and_uses_hashed_password(tmp_path):
    cache_path = tmp_path / "token.json"
    config = Config(
        email="athlete@example.com",
        password="password",
        token_cache=str(cache_path),
    )
    captured_request: httpx.Request | None = None

    def login_handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_request
        captured_request = request
        return httpx.Response(
            200,
            json={
                "result": "0000",
                "data": {"accessToken": "cached-token", "userId": "user-123"},
            },
        )

    session = AuthSession(config)
    with httpx.Client(transport=httpx.MockTransport(login_handler)) as client:
        session.login(client)

    assert captured_request is not None
    assert captured_request.method == "POST"
    assert str(captured_request.url) == "https://teamapi.coros.com/account/login"
    assert json.loads(captured_request.content) == {
        "account": "athlete@example.com",
        "accountType": 2,
        "pwd": hash_password("password"),
    }
    assert b"password" not in captured_request.content
    assert session.headers() == {
        "accesstoken": "cached-token",
        "content-type": "application/json",
    }
    assert json.loads(cache_path.read_text()) == {
        "accessToken": "cached-token",
        "userId": "user-123",
    }


def test_session_loads_and_clears_valid_token_cache(tmp_path):
    cache_path = tmp_path / "token.json"
    cache_path.write_text(json.dumps({"accessToken": "from-cache", "userId": "user-123"}))
    session = AuthSession(
        Config(email="athlete@example.com", password="password", token_cache=str(cache_path))
    )

    assert session.headers()["accesstoken"] == "from-cache"
    session.clear()
    assert session.headers() == {"content-type": "application/json"}
    assert not cache_path.exists()
