"""Shared AI retry helpers."""

from __future__ import annotations

import random
import sys
import time
from collections.abc import Callable
from typing import TypeVar

from noise_remix.errors import AIRequestError

T = TypeVar("T")


def is_transient_ai_error(exc: Exception) -> bool:
    text = str(exc).upper()
    markers = (
        "503",
        "429",
        "UNAVAILABLE",
        "RESOURCE_EXHAUSTED",
        "HIGH DEMAND",
        "TRY AGAIN LATER",
        "TEMPORARILY",
        "DEADLINE_EXCEEDED",
        "INTERNAL",
        "OVERLOADED",
        "RATE LIMIT",
        "TOO MANY REQUESTS",
    )
    return any(marker in text for marker in markers)


def retry_delay_seconds(*, attempt: int, base: float, maximum: float) -> float:
    delay = min(maximum, base * (2 ** (attempt - 1)))
    return delay + delay * random.uniform(0.0, 0.25)


def call_with_retries(
    *,
    operation: Callable[[], T],
    max_retries: int,
    retry_base_seconds: float,
    retry_max_seconds: float,
    provider_label: str,
) -> T:
    attempts = max_retries + 1
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if not is_transient_ai_error(exc) or attempt >= attempts:
                if is_transient_ai_error(exc):
                    raise AIRequestError(
                        f"{provider_label} request failed after {attempts} attempts "
                        f"(still overloaded or unavailable): {exc}"
                    ) from exc
                raise AIRequestError(f"{provider_label} request failed: {exc}") from exc
            delay = retry_delay_seconds(
                attempt=attempt,
                base=retry_base_seconds,
                maximum=retry_max_seconds,
            )
            print(
                f"→ {provider_label} overloaded/unavailable "
                f"(attempt {attempt}/{attempts}); retrying in {delay:.1f}s...",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise AIRequestError(f"{provider_label} request failed: {last_exc}") from last_exc
