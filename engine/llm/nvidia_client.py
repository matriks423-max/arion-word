from __future__ import annotations

import json

import requests

from engine.llm.base import LLMError, with_retry

BASE_URL = "https://integrate.api.nvidia.com/v1"


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


class NvidiaChat:
    def __init__(self, api_key: str, model: str, base_url: str = BASE_URL, timeout: int = 90):
        self.api_key, self.model, self.base_url, self.timeout = api_key, model, base_url, timeout

    def _post(self, system: str, user: str, max_tokens: int) -> str:
        def call():
            r = requests.post(
                f"{self.base_url}/chat/completions",
                headers=_headers(self.api_key),
                json={
                    "model": self.model,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": user}],
                    "max_tokens": max_tokens, "temperature": 0.7,
                },
                timeout=self.timeout,
            )
            if r.status_code != 200:
                raise LLMError(f"NVIDIA {self.model} {r.status_code}: {r.text[:200]}", status=r.status_code)
            return r.json()["choices"][0]["message"]["content"]
        return with_retry(call)

    def complete(self, system: str, user: str, *, max_tokens: int = 4096) -> str:
        return self._post(system, user, max_tokens)

    def complete_json(self, system: str, user: str, *, schema: dict, max_tokens: int = 4096) -> dict:
        guard = system + "\n\nReturn ONLY valid JSON. No prose, no markdown fences."
        raw = self._post(guard, user, max_tokens)
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start < 0 or end <= start:
            raise LLMError(f"NVIDIA {self.model}: no JSON object in response")
        return json.loads(raw[start:end])


class NvidiaEmbeddings:
    def __init__(self, api_key: str, model: str = "baai/bge-m3", base_url: str = BASE_URL, timeout: int = 60):
        self.api_key, self.model, self.base_url, self.timeout = api_key, model, base_url, timeout

    def embed(self, texts: list[str]) -> list[list[float]]:
        def call():
            r = requests.post(
                f"{self.base_url}/embeddings",
                headers=_headers(self.api_key),
                json={"model": self.model, "input": texts, "input_type": "passage"},
                timeout=self.timeout,
            )
            if r.status_code != 200:
                raise LLMError(f"NVIDIA embeddings {r.status_code}: {r.text[:200]}", status=r.status_code)
            return [d["embedding"] for d in r.json()["data"]]
        return with_retry(call)
