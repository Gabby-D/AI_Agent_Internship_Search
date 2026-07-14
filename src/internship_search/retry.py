"""Retry helpers for transient provider failures."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

TRANSIENT_HTTP_STATUS_CODES = {429, 500, 502, 503, 504}
HTTP_STATUS_PATTERN = re.compile(r"HTTP (\d{3})")


def is_transient_http_status(status_code: int) -> bool:
    return status_code in TRANSIENT_HTTP_STATUS_CODES


def transient_http_status_from_message(message: str) -> int | None:
    match = HTTP_STATUS_PATTERN.search(message)
    if match is None:
        return None
    return int(match.group(1))


def is_transient_runtime_error(error: Exception) -> bool:
    message = str(error)
    status_code = transient_http_status_from_message(message)
    if status_code is not None:
        return is_transient_http_status(status_code)
    lowered = message.lower()
    return "gemini api request failed" in lowered or "timed out" in lowered


def retry_call(
    operation: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay_seconds: float = 1.0,
    sleep: Callable[[float], None] | None = None,
    is_retryable: Callable[[Exception], bool] | None = None,
) -> T:
    should_retry = is_retryable or is_transient_runtime_error
    pause = sleep or (lambda seconds: None)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except Exception as error:  # noqa: BLE001 - caller decides final handling.
            last_error = error
            if attempt >= max_attempts or not should_retry(error):
                raise
            pause(base_delay_seconds * (2 ** (attempt - 1)))

    if last_error is not None:
        raise last_error
    raise RuntimeError("retry_call finished without a result.")
