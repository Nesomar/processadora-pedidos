"""Helper de espera por processamento assincrono (research.md #2)."""

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def poll_until(
    fn: Callable[[], T],
    timeout: float = 30.0,
    interval: float = 0.5,
    description: str = "",
) -> T:
    """Chama `fn()` ate devolver um valor truthy, ou levanta `AssertionError` no timeout."""
    deadline = time.monotonic() + timeout
    last_value: T | None = None
    while time.monotonic() < deadline:
        last_value = fn()
        if last_value:
            return last_value
        time.sleep(interval)
    raise AssertionError(
        f"timeout ({timeout}s) esperando: {description} — ultimo valor observado: {last_value!r}"
    )
