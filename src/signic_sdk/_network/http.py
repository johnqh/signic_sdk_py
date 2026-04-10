"""Async HTTP utilities wrapping :mod:`httpx`.

All functions return an :class:`~signic_sdk.types.HttpResponse` with parsed JSON.
On failure, they raise the appropriate :class:`~signic_sdk.errors.SignicError` subclass:

- Connection/timeout failure -> :class:`~signic_sdk.errors.SignicNetworkError`
- Non-JSON response -> :class:`~signic_sdk.errors.SignicError`
- 401/403 -> :class:`~signic_sdk.errors.SignicAuthError`
- 400/422 -> :class:`~signic_sdk.errors.SignicValidationError`
- Other non-2xx -> :class:`~signic_sdk.errors.SignicError`
"""

from __future__ import annotations

from typing import Any

import httpx

from signic_sdk.errors import (
    SignicAuthError,
    SignicError,
    SignicNetworkError,
    SignicValidationError,
)
from signic_sdk.types import HttpResponse


async def _request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict[str, str],
    body: Any | None = None,
) -> HttpResponse:
    """Internal request executor.

    Handles the fetch, JSON parsing, and error classification. The operation
    name is derived from the last URL path segment (used in error messages).
    """
    operation = url.rstrip("/").split("/")[-1] or "request"

    kwargs: dict[str, Any] = {"headers": headers}
    if body is not None:
        kwargs["json"] = body

    try:
        response = await client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise SignicNetworkError(
            f"Failed to {operation}: {exc}",
            operation,
        ) from exc

    try:
        data: dict[str, Any] = response.json()
    except Exception as exc:
        raise SignicError(
            f"Failed to {operation}: Invalid JSON response",
            operation,
            response.status_code,
        ) from exc

    ok = 200 <= response.status_code < 300
    if not ok:
        raise handle_api_error(response.status_code, data, operation)

    return HttpResponse(status=response.status_code, data=data, ok=ok)


async def http_get(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> HttpResponse:
    """Send a GET request and parse the JSON response."""
    return await _request(client, "GET", url, headers)


async def http_post(
    client: httpx.AsyncClient,
    url: str,
    body: Any,
    headers: dict[str, str],
) -> HttpResponse:
    """Send a POST request with a JSON body and parse the JSON response."""
    return await _request(client, "POST", url, headers, body)


async def http_put(
    client: httpx.AsyncClient,
    url: str,
    body: Any,
    headers: dict[str, str],
) -> HttpResponse:
    """Send a PUT request with a JSON body and parse the JSON response."""
    return await _request(client, "PUT", url, headers, body)


def handle_api_error(
    status: int,
    response_data: Any,
    operation: str,
) -> SignicError:
    """Classify an HTTP error status into the appropriate SignicError subclass.

    Used internally by :func:`_request` when the response status is not 2xx.
    """
    data = response_data if isinstance(response_data, dict) else {}
    error_message: str = data.get("error") or data.get("message") or "Unknown error"
    full_message = f"Failed to {operation}: {error_message}"

    if status in (401, 403):
        return SignicAuthError(full_message, operation, status)
    if status in (400, 422):
        return SignicValidationError(full_message, operation, status)
    return SignicError(full_message, operation, status)
