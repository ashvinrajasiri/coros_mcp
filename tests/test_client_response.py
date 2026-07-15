import httpx
import pytest

from coros_mcp.client import CorosClient, _check_response
from coros_mcp.config import Config
from coros_mcp.errors import ToolError


def test_check_response_returns_data_payload():
    response = httpx.Response(200, json={"result": "0000", "data": {"steps": 1234}})

    assert _check_response(response) == {"steps": 1234}


def test_check_response_raises_coros_api_error_for_failure_result():
    response = httpx.Response(200, json={"result": "1001", "message": "Invalid request"})

    with pytest.raises(ToolError) as error:
        _check_response(response)

    assert error.value.code == "COROS_API_ERROR"


def test_get_day_detail_converts_dates_and_returns_data():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/account/login":
            return httpx.Response(
                200, json={"result": "0000", "data": {"accessToken": "token"}}
            )
        return httpx.Response(200, json={"result": "0000", "data": {"days": []}})

    client = CorosClient(Config(email="athlete@example.com", password="password"))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        assert client.get_day_detail("2024-03-09", "2024-03-10") == {"days": []}
    finally:
        client.close()

    assert requests[1].url.path == "/analyse/dayDetail/query"
    assert dict(requests[1].url.params) == {
        "startDate": "20240309",
        "endDate": "20240310",
    }


def test_get_day_detail_retries_once_after_401():
    requests: list[httpx.Request] = []
    login_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal login_count
        requests.append(request)
        if request.url.path == "/account/login":
            login_count += 1
            return httpx.Response(
                200,
                json={"result": "0000", "data": {"accessToken": f"token-{login_count}"}},
            )
        if login_count == 1:
            return httpx.Response(401, json={"result": "401"})
        return httpx.Response(200, json={"result": "0000", "data": {"days": ["retried"]}})

    client = CorosClient(Config(email="athlete@example.com", password="password"))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        assert client.get_day_detail("2024-03-09", "2024-03-09") == {
            "days": ["retried"]
        }
    finally:
        client.close()

    assert login_count == 2
    assert [request.url.path for request in requests] == [
        "/account/login",
        "/analyse/dayDetail/query",
        "/account/login",
        "/analyse/dayDetail/query",
    ]
