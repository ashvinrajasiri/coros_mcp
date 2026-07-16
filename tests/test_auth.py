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


def test_headers_raises_unauthorized_without_token():
    session = AuthSession(Config(email="athlete@example.com", password="password"))

    with pytest.raises(ToolError) as error:
        session.headers()

    assert error.value.code == "UNAUTHORIZED"


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
    headers = session.headers()
    assert headers["accesstoken"] == "cached-token"
    assert headers["accessToken"] == "cached-token"
    assert headers["content-type"] == "application/json"
    assert json.loads(headers["yfheader"]) == {"userId": "user-123"}
    assert json.loads(cache_path.read_text()) == {
        "access_token": "cached-token",
        "user_id": "user-123",
        "region": "us",
    }


def test_session_loads_and_clears_valid_token_cache(tmp_path):
    cache_path = tmp_path / "token.json"
    cache_path.write_text(
        json.dumps({"access_token": "from-cache", "user_id": "user-123", "region": "us"})
    )
    session = AuthSession(
        Config(email="athlete@example.com", password="password", token_cache=str(cache_path))
    )

    assert session.headers()["accesstoken"] == "from-cache"
    session.clear()
    with pytest.raises(ToolError) as error:
        session.headers()
    assert error.value.code == "UNAUTHORIZED"
    assert not cache_path.exists()


def test_session_loads_camel_case_cache_for_compatibility(tmp_path):
    cache_path = tmp_path / "token.json"
    cache_path.write_text(
        json.dumps({"accessToken": "legacy-token", "userId": "user-456", "region": "us"})
    )
    session = AuthSession(
        Config(email="athlete@example.com", password="password", token_cache=str(cache_path))
    )

    assert session.headers()["accesstoken"] == "legacy-token"
    assert session.user_id == "user-456"


def test_session_ignores_cache_when_region_mismatch(tmp_path):
    cache_path = tmp_path / "token.json"
    cache_path.write_text(
        json.dumps({"access_token": "eu-token", "user_id": "user-123", "region": "eu"})
    )
    session = AuthSession(
        Config(
            email="athlete@example.com",
            password="password",
            region="us",
            token_cache=str(cache_path),
        )
    )

    with pytest.raises(ToolError) as error:
        session.headers()
    assert error.value.code == "UNAUTHORIZED"


@pytest.mark.parametrize(
    ("response", "status_code"),
    [
        ({"result": "1001", "data": {}}, 200),
        (None, 500),
    ],
)
def test_login_failure_raises_auth_failed(response, status_code):
    config = Config(email="athlete@example.com", password="password")

    def login_handler(_request: httpx.Request) -> httpx.Response:
        if response is None:
            return httpx.Response(status_code)
        return httpx.Response(status_code, json=response)

    session = AuthSession(config)
    with httpx.Client(transport=httpx.MockTransport(login_handler)) as client:
        with pytest.raises(ToolError) as error:
            session.login(client)

    assert error.value.code == "AUTH_FAILED"
