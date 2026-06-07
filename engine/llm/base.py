from __future__ import annotations

import time
from typing import Protocol


class LLMError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


# Status codes worth retrying (transient). 401/403/404/400 are not.
_RETRYABLE = {429, 500, 502, 503, 504}


def with_retry(fn, attempts: int = 4, base_delay: float = 0.5):
    """Call fn(), retrying only on transient LLMError.status with exponential backoff."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except LLMError as exc:
            last = exc
            if exc.status is not None and exc.status not in _RETRYABLE:
                raise
            if i == attempts - 1:
                raise
            if base_delay:
                time.sleep(base_delay * (2 ** i))
    raise last  # pragma: no cover


class ChatClient(Protocol):
    def complete(self, system: str, user: str, *, max_tokens: int = 4096) -> str: ...
    def complete_json(self, system: str, user: str, *, schema: dict, max_tokens: int = 4096) -> dict: ...


class EmbeddingClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
