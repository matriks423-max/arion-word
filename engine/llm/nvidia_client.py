from __future__ import annotations

import json

import requests

from engine.llm.base import LLMError, with_retry

BASE_URL = "https://integrate.api.nvidia.com/v1"

# NIM rejects more than 256 inputs per embeddings request.
_EMBED_BATCH = 128


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _post(url: str, api_key: str, body: dict, timeout: int, what: str) -> dict:
    try:
        r = requests.post(url, headers=_headers(api_key), json=body, timeout=timeout)
    except requests.RequestException as exc:  # timeout / connection reset: transient
        raise LLMError(f"{what}: {type(exc).__name__}: {exc}") from exc
    if r.status_code != 200:
        raise LLMError(f"{what} {r.status_code}: {r.text[:200]}", status=r.status_code)
    return r.json()


class NvidiaChat:
    """Reasoning models (Nemotron 3, gpt-oss) spend thinking tokens out of max_tokens;
    a budget that runs out before the answer returns content=None. Give critic voters
    room via the `max_tokens` stage setting in models.yaml."""

    def __init__(self, api_key: str, model: str, base_url: str = BASE_URL, timeout: int = 90,
                 max_tokens: int = 4096):
        self.api_key, self.model, self.base_url, self.timeout = api_key, model, base_url, timeout
        self.max_tokens = max_tokens

    def _post(self, system: str, user: str, max_tokens: int | None) -> str:
        def call():
            data = _post(
                f"{self.base_url}/chat/completions", self.api_key,
                {
                    "model": self.model,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": user}],
                    "max_tokens": max_tokens or self.max_tokens, "temperature": 0.7,
                },
                self.timeout, f"NVIDIA {self.model}",
            )
            choice = (data.get("choices") or [{}])[0]
            content = (choice.get("message") or {}).get("content")
            if not content:
                # HTTP 200 but unusable (e.g. reasoning used the whole budget): retrying
                # the same request will not help, so status=200 makes it non-retryable.
                raise LLMError(f"NVIDIA {self.model}: empty content "
                               f"(finish_reason={choice.get('finish_reason')})", status=200)
            return content
        return with_retry(call)

    def complete(self, system: str, user: str, *, max_tokens: int | None = None) -> str:
        return self._post(system, user, max_tokens)

    def complete_json(self, system: str, user: str, *, schema: dict, max_tokens: int | None = None) -> dict:
        guard = system + "\n\nReturn ONLY valid JSON. No prose, no markdown fences."
        raw = self._post(guard, user, max_tokens)
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start < 0 or end <= start:
            raise LLMError(f"NVIDIA {self.model}: no JSON object in response: {raw[:200]!r}", status=200)
        try:
            return json.loads(raw[start:end])
        except json.JSONDecodeError as exc:
            raise LLMError(f"NVIDIA {self.model}: invalid JSON ({exc}): {raw[start:start + 200]!r}",
                           status=200) from exc


class NvidiaEmbeddings:
    """nvidia/nemotron-3-embed-1b is asymmetric: documents must be embedded with
    input_type="passage" and searches with input_type="query". Without it a Latvian
    sentence scored the same against its English translation as against an
    unrelated Russian recipe."""

    def __init__(self, api_key: str, model: str = "nvidia/nemotron-3-embed-1b",
                 base_url: str = BASE_URL, timeout: int = 60):
        self.api_key, self.model, self.base_url, self.timeout = api_key, model, base_url, timeout

    def embed(self, texts: list[str], input_type: str = "passage") -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH):
            batch = texts[i:i + _EMBED_BATCH]

            def call(batch=batch):
                data = _post(
                    f"{self.base_url}/embeddings", self.api_key,
                    {"model": self.model, "input": batch, "input_type": input_type,
                     "encoding_format": "float", "truncate": "END"},
                    self.timeout, f"NVIDIA embeddings {self.model}",
                )
                return [d["embedding"] for d in data["data"]]
            vectors.extend(with_retry(call))
        return vectors
