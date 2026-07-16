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


def test_program_client_uses_verified_library_endpoints():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/account/login":
            return httpx.Response(
                200, json={"result": "0000", "data": {"accessToken": "token"}}
            )
        if request.url.path == "/training/program/add":
            return httpx.Response(200, json={"result": "0000", "data": "program-1"})
        return httpx.Response(200, json={"result": "0000", "data": []})

    client = CorosClient(Config(email="athlete@example.com", password="password"))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        assert client.list_programs(1) == []
        assert client.get_program("program-1") == {}
        assert client.create_program({"name": "Easy"}) == "program-1"
        client.delete_program("123456789012345678")
    finally:
        client.close()

    library_requests = [
        request for request in requests if request.url.path != "/account/login"
    ]
    assert library_requests[0].method == "POST"
    assert library_requests[0].url.path == "/training/program/query"
    assert library_requests[0].content == (
        b'{"name":"","supportRestExercise":1,"startNo":0,"limitSize":100,"sportType":1}'
    )
    assert library_requests[1].url.path == "/training/program/detail"
    assert dict(library_requests[1].url.params) == {"id": "program-1"}
    assert library_requests[2].url.path == "/training/program/add"
    assert library_requests[3].url.path == "/training/program/delete"
    assert library_requests[3].content == b'["123456789012345678"]'


def test_schedule_query_includes_rest_exercises():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/account/login":
            return httpx.Response(
                200, json={"result": "0000", "data": {"accessToken": "token"}}
            )
        return httpx.Response(200, json={"result": "0000", "data": {}})

    client = CorosClient(Config(email="athlete@example.com", password="password"))
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        assert client.query_schedule("2026-07-01", "2026-08-31") == {}
    finally:
        client.close()

    assert requests[1].url.path == "/training/schedule/query"
    assert dict(requests[1].url.params) == {
        "startDate": "20260701",
        "endDate": "20260831",
        "supportRestExercise": "1",
    }
