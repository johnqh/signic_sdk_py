"""Tests for the error hierarchy — mirrors errors.test.ts."""

from signic_sdk import (
    SignicAuthError,
    SignicError,
    SignicNetworkError,
    SignicValidationError,
)


class TestSignicError:
    def test_stores_message_operation_and_status_code(self) -> None:
        err = SignicError("something failed", "test_op", 500)
        assert str(err) == "something failed"
        assert err.operation == "test_op"
        assert err.status_code == 500

    def test_status_code_is_none_when_not_provided(self) -> None:
        err = SignicError("fail", "op")
        assert err.status_code is None

    def test_is_instance_of_exception(self) -> None:
        err = SignicError("fail", "op")
        assert isinstance(err, Exception)


class TestSignicAuthError:
    def test_extends_signic_error(self) -> None:
        err = SignicAuthError("unauthorized", "auth", 401)
        assert isinstance(err, SignicError)
        assert isinstance(err, Exception)
        assert err.status_code == 401

    def test_stores_operation(self) -> None:
        err = SignicAuthError("forbidden", "auth", 403)
        assert err.operation == "auth"


class TestSignicNetworkError:
    def test_extends_signic_error_with_no_status_code(self) -> None:
        err = SignicNetworkError("timeout", "fetch")
        assert isinstance(err, SignicError)
        assert err.status_code is None
        assert err.operation == "fetch"


class TestSignicValidationError:
    def test_extends_signic_error(self) -> None:
        err = SignicValidationError("bad input", "validate", 400)
        assert isinstance(err, SignicError)
        assert err.status_code == 400
        assert err.operation == "validate"
