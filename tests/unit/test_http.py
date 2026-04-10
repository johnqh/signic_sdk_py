"""Tests for the HTTP utilities — mirrors http.test.ts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from signic_sdk._network.http import handle_api_error, http_get, http_post, http_put
from signic_sdk.errors import (
    SignicAuthError,
    SignicError,
    SignicNetworkError,
    SignicValidationError,
)

if TYPE_CHECKING:
    from pytest_httpx import HTTPXMock


class TestHttpGet:
    async def test_returns_parsed_json_on_success(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"success": True})
        async with httpx.AsyncClient() as client:
            result = await http_get(client, "https://api.test/data", {"Accept": "application/json"})
        assert result.ok is True
        assert result.data == {"success": True}
        assert result.status == 200

    async def test_raises_network_error_on_connection_failure(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_exception(httpx.ConnectError("DNS lookup failed"))
        async with httpx.AsyncClient() as client:
            with pytest.raises(SignicNetworkError):
                await http_get(client, "https://api.test/data", {})

    async def test_raises_on_non_ok_status(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"error": "not found"}, status_code=404)
        async with httpx.AsyncClient() as client:
            with pytest.raises(SignicError):
                await http_get(client, "https://api.test/missing", {})

    async def test_raises_on_invalid_json(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(text="not json", status_code=200)
        async with httpx.AsyncClient() as client:
            with pytest.raises(SignicError, match="Invalid JSON"):
                await http_get(client, "https://api.test/bad-json", {})


class TestHttpPost:
    async def test_sends_json_body_and_returns_parsed_response(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"id": "123"})
        async with httpx.AsyncClient() as client:
            result = await http_post(
                client,
                "https://api.test/create",
                {"name": "test"},
                {"Content-Type": "application/json"},
            )
        assert result.data == {"id": "123"}
        request = httpx_mock.get_requests()[0]
        assert request.method == "POST"
        assert json.loads(request.content) == {"name": "test"}


class TestHttpPut:
    async def test_sends_put_request_with_json_body(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"success": True, "updated": 1})
        async with httpx.AsyncClient() as client:
            result = await http_put(
                client,
                "https://api.test/update/1",
                {"seen": True},
                {"Content-Type": "application/json"},
            )
        assert result.data["updated"] == 1
        request = httpx_mock.get_requests()[0]
        assert request.method == "PUT"
        assert json.loads(request.content) == {"seen": True}


class TestHandleApiError:
    def test_returns_auth_error_for_401(self) -> None:
        err = handle_api_error(401, {"error": "unauthorized"}, "auth")
        assert isinstance(err, SignicAuthError)
        assert err.status_code == 401

    def test_returns_auth_error_for_403(self) -> None:
        err = handle_api_error(403, {"error": "forbidden"}, "auth")
        assert isinstance(err, SignicAuthError)

    def test_returns_validation_error_for_400(self) -> None:
        err = handle_api_error(400, {"error": "bad request"}, "validate")
        assert isinstance(err, SignicValidationError)
        assert err.status_code == 400

    def test_returns_validation_error_for_422(self) -> None:
        err = handle_api_error(422, {"error": "invalid"}, "validate")
        assert isinstance(err, SignicValidationError)

    def test_returns_base_error_for_other_status_codes(self) -> None:
        err = handle_api_error(500, {"error": "server error"}, "fetch")
        assert isinstance(err, SignicError)
        assert not isinstance(err, SignicAuthError)
        assert not isinstance(err, SignicValidationError)
        assert err.status_code == 500

    def test_handles_none_response_data(self) -> None:
        err = handle_api_error(500, None, "fetch")
        assert "Unknown error" in str(err)
