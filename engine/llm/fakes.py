from __future__ import annotations

import hashlib


class FakeChat:
    """Scripted ChatClient. Returns `responses` in order; records calls."""

    def __init__(self, responses: list):
        self._responses = list(responses)
        self._i = 0
        self.calls: list[dict] = []

    def _next(self, system: str, user: str):
        self.calls.append({"system": system, "user": user})
        assert self._i < len(self._responses), "FakeChat exhausted"
        out = self._responses[self._i]
        self._i += 1
        return out

    def complete(self, system: str, user: str, *, max_tokens: int = 4096) -> str:
        return self._next(system, user)

    def complete_json(self, system: str, user: str, *, schema: dict, max_tokens: int = 4096) -> dict:
        return self._next(system, user)


class FakeEmbeddings:
    """Deterministic EmbeddingClient: hashes text into a fixed-dim unit-ish vector."""

    def __init__(self, dim: int = 16):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode("utf-8")).digest()
            vec = [((h[i % len(h)]) / 255.0) for i in range(self.dim)]
            out.append(vec)
        return out
