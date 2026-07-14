import pytest

from internship_search.retry import (
    is_transient_http_status,
    is_transient_runtime_error,
    retry_call,
    transient_http_status_from_message,
)


def test_is_transient_http_status_matches_retryable_codes():
    assert is_transient_http_status(503)
    assert is_transient_http_status(429)
    assert not is_transient_http_status(404)


def test_transient_http_status_from_message_parses_gemini_error():
    message = "Gemini API HTTP 503: service unavailable"
    assert transient_http_status_from_message(message) == 503


def test_is_transient_runtime_error_detects_gemini_http_and_network_failures():
    assert is_transient_runtime_error(RuntimeError("Gemini API HTTP 503: unavailable"))
    assert is_transient_runtime_error(RuntimeError("Gemini API request failed: timed out"))
    assert not is_transient_runtime_error(RuntimeError("Gemini API HTTP 400: bad request"))


def test_retry_call_retries_transient_errors_then_succeeds():
    attempts = {"count": 0}
    delays: list[float] = []

    def flaky_operation():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("Gemini API HTTP 503: unavailable")
        return "ok"

    result = retry_call(
        flaky_operation,
        max_attempts=3,
        base_delay_seconds=0.5,
        sleep=delays.append,
    )

    assert result == "ok"
    assert attempts["count"] == 3
    assert delays == [0.5, 1.0]


def test_retry_call_does_not_retry_non_transient_errors():
    attempts = {"count": 0}

    def failing_operation():
        attempts["count"] += 1
        raise RuntimeError("Gemini API HTTP 400: bad request")

    with pytest.raises(RuntimeError, match="HTTP 400"):
        retry_call(failing_operation, max_attempts=3, sleep=lambda _: None)

    assert attempts["count"] == 1
