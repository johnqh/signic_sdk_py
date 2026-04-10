"""Error hierarchy for the Signic SDK.

All SDK errors inherit from :class:`SignicError`, which carries the
operation name and optional HTTP status code for diagnostics.

Error classification by HTTP status:
- 401/403 -> :class:`SignicAuthError`
- 400/422 -> :class:`SignicValidationError`
- Network failure (no response) -> :class:`SignicNetworkError`
- Other -> :class:`SignicError`
"""


class SignicError(Exception):
    """Base error class for all Signic SDK errors.

    Attributes:
        operation: The SDK operation that failed (e.g. "get_unread_emails", "connect").
        status_code: HTTP status code from the API response, if applicable.
    """

    def __init__(self, message: str, operation: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.operation = operation
        self.status_code = status_code


class SignicAuthError(SignicError):
    """Thrown on authentication or authorization failures (HTTP 401/403).

    Also thrown when calling methods that require :meth:`SignicClient.connect`
    before use.
    """

    def __init__(self, message: str, operation: str, status_code: int | None = None) -> None:
        super().__init__(message, operation, status_code)


class SignicNetworkError(SignicError):
    """Thrown when a network request fails entirely (DNS failure, timeout, no response).

    Has no ``status_code`` since no HTTP response was received.
    """

    def __init__(self, message: str, operation: str) -> None:
        super().__init__(message, operation)


class SignicValidationError(SignicError):
    """Thrown on input validation failures (HTTP 400/422).

    Typically indicates malformed request parameters.
    """

    def __init__(self, message: str, operation: str, status_code: int | None = None) -> None:
        super().__init__(message, operation, status_code)
