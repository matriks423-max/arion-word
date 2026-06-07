# Arion World — Phase 0b: Generation Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the self-policing episode generation pipeline (retrieve → plan/write → continuity-critic → gate/revise/quarantine → edit → commit patch) on top of the Phase 0a canon foundation, with every LLM dependency injected so the whole thing is unit-tested offline with fakes (zero API spend, no keys required to build).

**Architecture:** Layered + dependency-injected. Transport clients (`AnthropicChat`, `NvidiaChat`, `NvidiaEmbeddings`) wrap network calls and are the ONLY things that touch the network. Domain components (`Writer`, `Editor`, `Critic`, `EmbeddingRetriever`) take a client via their constructor. `EpisodePipeline` composes the domain components + the Phase 0a `CanonStore`/`CanonPatch`. Tests inject `FakeChat`/`FakeEmbeddings` (scripted, deterministic) — no network, no key. A live `engine episode` run is the only thing that needs real keys, and it degrades to a clear error if they're absent.

**Tech Stack:** Python 3.11 · `anthropic` SDK (writer/editor) · `requests` (NVIDIA OpenAI-compatible REST) · `pyyaml` · `pytest`. Verified model ids (from `memory/project_nvidia_llm.md`): critic voters `meta/llama-3.3-70b-instruct`, `mistralai/mistral-nemotron`, `nvidia/llama-3.3-nemotron-super-49b-v1`; embeddings `baai/bge-m3`; NVIDIA endpoint `https://integrate.api.nvidia.com/v1` (`NVIDIA_API_KEY`); writer/editor `claude-opus-4-8` (`ANTHROPIC_API_KEY`).

**Spec:** `docs/superpowers/specs/2026-06-07-arion-world-rebuild-design.md` (§5 pipeline, §3 retrieval/embeddings, §8 error handling).

**Depends on:** Plan 0a (canon store, patch engine, index, retrieval, CLI) — complete.

**Scope note:** This is Plan 0b. It does NOT build the Astro `/read` renderer (Plan 0c) and does NOT publish anywhere.

---

## File Structure

```
pyproject.toml                         # add anthropic, requests deps
models.yaml                            # stage -> provider/model routing
engine/
  llm/
    __init__.py
    base.py                            # ChatClient/EmbeddingClient protocols + retry helper + LLMError
    fakes.py                           # FakeChat, FakeEmbeddings (test doubles)
    nvidia_client.py                   # NvidiaChat + NvidiaEmbeddings (requests)
    anthropic_client.py               # AnthropicChat (structured tool-use output)
    config.py                          # load models.yaml -> build clients (lazy)
  retrieval_embed.py                   # EmbeddingRetriever: build + query entity embeddings
  critic.py                            # Critic panel -> aggregated verdict
  writer.py                            # Writer + Editor (prompt build + structured parse)
  pipelines/
    __init__.py
    episode.py                         # EpisodePipeline orchestration + gate
canon/_schema/episode.schema.json      # new entity type
tests/
  test_llm_base.py  test_nvidia_client.py  test_anthropic_client.py
  test_config.py  test_retrieval_embed.py  test_critic.py
  test_writer.py  test_episode_pipeline.py  test_episode_schema.py
  fixtures/critic_clean.json  fixtures/critic_contradiction.json
```

Episode entity (`canon/episodes/ep-001.yaml`):

```yaml
id: ep-001
type: episode
name: "The Clock That Stopped"
provenance: {introduced_episode: 1, last_changed_episode: 1, source_run: ep001}
number: 1
logline: "..."
summary: "..."
cliffhanger: "..."
scenes: [ {scene_number: 1, prose: "...", ...} ]
```

---

## Task 1: Episode entity type

**Files:**
- Modify: `canon/_schema/base.schema.json` (add `episode` to the type enum)
- Create: `canon/_schema/episode.schema.json`
- Modify: `engine/canon/store.py` (add `episode` to `_TYPE_DIR`)
- Test: `tests/test_episode_schema.py`

- [ ] **Step 1: Write the failing test** (`tests/test_episode_schema.py`)

```python
import pytest
from engine.canon.store import CanonStore, ValidationFailed


def _ep():
    return {
        "id": "ep-001", "type": "episode", "name": "The Clock That Stopped",
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "ep001"},
        "number": 1, "logline": "x", "summary": "y", "cliffhanger": "z",
        "scenes": [{"scene_number": 1, "prose": "..."}],
    }


def test_episode_roundtrip(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_ep())
    assert store.load("ep-001")["number"] == 1
    assert (tmp_canon / "episodes" / "ep-001.yaml").exists()


def test_episode_requires_number_and_scenes(tmp_canon):
    store = CanonStore(tmp_canon)
    bad = _ep(); del bad["scenes"]
    with pytest.raises(ValidationFailed):
        store.save(bad)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_episode_schema.py -v`
Expected: FAIL — `episode` not an allowed type (`ValidationFailed: unknown entity type` / enum error).

- [ ] **Step 3: Add `episode` to the base enum**

In `canon/_schema/base.schema.json`, change the `type` enum to:
```json
"type": { "type": "string", "enum": ["character", "hook", "technique", "world_doc", "episode"] },
```

- [ ] **Step 4: Write `canon/_schema/episode.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "episode.schema.json",
  "allOf": [{ "$ref": "base.schema.json" }],
  "properties": {
    "type": { "const": "episode" },
    "number": { "type": "integer" },
    "logline": { "type": "string" },
    "summary": { "type": "string" },
    "cliffhanger": { "type": "string" },
    "scenes": { "type": "array", "minItems": 1 }
  },
  "required": ["number", "scenes"]
}
```

- [ ] **Step 5: Register the type in `engine/canon/store.py`**

In `_TYPE_DIR`, add the episodes mapping:
```python
_TYPE_DIR = {
    "character": "characters",
    "hook": "hooks",
    "technique": "techniques",
    "world_doc": "world",
    "episode": "episodes",
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_episode_schema.py -v`
Expected: PASS (2 passed). Also run `python -m pytest -q` — all prior tests still green.

- [ ] **Step 7: Commit**

```bash
git add canon/_schema engine/canon/store.py tests/test_episode_schema.py
git commit -m "feat(canon): episode entity type + schema"
```

---

## Task 2: LLM client interfaces + retry

**Files:**
- Create: `engine/llm/__init__.py`, `engine/llm/base.py`
- Test: `tests/test_llm_base.py`

- [ ] **Step 1: Write the failing test** (`tests/test_llm_base.py`)

```python
import pytest
from engine.llm.base import with_retry, LLMError


def test_with_retry_succeeds_after_transient_failures():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise LLMError("503 transient", status=503)
        return "ok"

    assert with_retry(flaky, attempts=5, base_delay=0) == "ok"
    assert calls["n"] == 3


def test_with_retry_does_not_retry_auth_errors():
    calls = {"n": 0}

    def auth_fail():
        calls["n"] += 1
        raise LLMError("401 unauthorized", status=401)

    with pytest.raises(LLMError):
        with_retry(auth_fail, attempts=5, base_delay=0)
    assert calls["n"] == 1   # 401 is not retried


def test_with_retry_raises_after_max_attempts():
    def always_500():
        raise LLMError("500", status=500)

    with pytest.raises(LLMError):
        with_retry(always_500, attempts=3, base_delay=0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_llm_base.py -v`
Expected: FAIL — `ModuleNotFoundError: engine.llm.base`.

- [ ] **Step 3: Write `engine/llm/__init__.py` (empty) and `engine/llm/base.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_llm_base.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/llm/__init__.py engine/llm/base.py tests/test_llm_base.py
git commit -m "feat(llm): client protocols + transient-only retry/backoff"
```

---

## Task 3: Fake clients (test doubles)

**Files:**
- Create: `engine/llm/fakes.py`
- Test: `tests/test_fakes.py`

- [ ] **Step 1: Write the failing test** (`tests/test_fakes.py`)

```python
import pytest
from engine.llm.fakes import FakeChat, FakeEmbeddings


def test_fakechat_returns_scripted_responses_in_order():
    chat = FakeChat(responses=["first", {"k": 1}])
    assert chat.complete("sys", "u") == "first"
    assert chat.complete_json("sys", "u", schema={}) == {"k": 1}


def test_fakechat_records_calls():
    chat = FakeChat(responses=["x"])
    chat.complete("SYS", "USER")
    assert chat.calls[0]["system"] == "SYS"
    assert chat.calls[0]["user"] == "USER"


def test_fakechat_raises_when_exhausted():
    chat = FakeChat(responses=[])
    with pytest.raises(AssertionError):
        chat.complete("s", "u")


def test_fakeembeddings_deterministic_and_dimensioned():
    emb = FakeEmbeddings(dim=8)
    a = emb.embed(["hello"])[0]
    b = emb.embed(["hello"])[0]
    assert a == b and len(a) == 8           # deterministic + fixed dim
    assert emb.embed(["different"])[0] != a
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fakes.py -v`
Expected: FAIL — `ModuleNotFoundError: engine.llm.fakes`.

- [ ] **Step 3: Write `engine/llm/fakes.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fakes.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/llm/fakes.py tests/test_fakes.py
git commit -m "test(llm): scripted FakeChat + deterministic FakeEmbeddings"
```

---

## Task 4: NVIDIA client (chat + embeddings)

**Files:**
- Modify: `pyproject.toml` (add `requests`)
- Create: `engine/llm/nvidia_client.py`
- Test: `tests/test_nvidia_client.py`

- [ ] **Step 1: Add `requests` to `pyproject.toml` dependencies**

```toml
dependencies = ["pyyaml>=6.0", "jsonschema>=4.21", "requests>=2.32", "anthropic>=0.40"]
```
Run: `python -m pip install -e ".[dev]"`

- [ ] **Step 2: Write the failing test** (`tests/test_nvidia_client.py`) — monkeypatch `requests.post`, no network

```python
import json
import pytest
from engine.llm.base import LLMError
from engine.llm import nvidia_client as nv


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_chat_complete_parses_choice(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        assert "chat/completions" in url
        return _Resp(200, {"choices": [{"message": {"content": "hello world"}}]})
    monkeypatch.setattr(nv.requests, "post", fake_post)
    client = nv.NvidiaChat(api_key="k", model="meta/llama-3.3-70b-instruct")
    assert client.complete("sys", "user") == "hello world"


def test_chat_raises_llmerror_with_status(monkeypatch):
    monkeypatch.setattr(nv.requests, "post", lambda *a, **k: _Resp(503, {"error": "busy"}))
    client = nv.NvidiaChat(api_key="k", model="m")
    with pytest.raises(LLMError) as e:
        client.complete("s", "u")
    assert e.value.status == 503


def test_embeddings_returns_vectors(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        assert "embeddings" in url
        return _Resp(200, {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]})
    monkeypatch.setattr(nv.requests, "post", fake_post)
    client = nv.NvidiaEmbeddings(api_key="k", model="baai/bge-m3")
    assert client.embed(["a", "b"]) == [[0.1, 0.2], [0.3, 0.4]]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_nvidia_client.py -v`
Expected: FAIL — `ModuleNotFoundError: engine.llm.nvidia_client`.

- [ ] **Step 4: Write `engine/llm/nvidia_client.py`**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_nvidia_client.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml engine/llm/nvidia_client.py tests/test_nvidia_client.py
git commit -m "feat(llm): NVIDIA chat + embeddings client (OpenAI-compatible REST)"
```

---

## Task 5: Anthropic client (structured tool-use output)

**Files:**
- Create: `engine/llm/anthropic_client.py`
- Test: `tests/test_anthropic_client.py`

- [ ] **Step 1: Write the failing test** (`tests/test_anthropic_client.py`) — inject a fake SDK object, no network

```python
import pytest
from engine.llm.base import LLMError
from engine.llm.anthropic_client import AnthropicChat


class _FakeMessages:
    def __init__(self, blocks, raise_status=None):
        self._blocks = blocks
        self._raise_status = raise_status

    def create(self, **kwargs):
        if self._raise_status:
            raise RuntimeError(f"overloaded {self._raise_status}")
        return type("Msg", (), {"content": self._blocks})()


class _FakeSDK:
    def __init__(self, blocks):
        self.messages = _FakeMessages(blocks)


def _text_block(t):
    return type("B", (), {"type": "text", "text": t})()


def _tool_block(data):
    return type("B", (), {"type": "tool_use", "name": "emit", "input": data})()


def test_complete_returns_text():
    sdk = _FakeSDK([_text_block("hello")])
    client = AnthropicChat(sdk=sdk, model="claude-opus-4-8")
    assert client.complete("sys", "user") == "hello"


def test_complete_json_returns_tool_input():
    sdk = _FakeSDK([_tool_block({"title": "Ep1", "ok": True})])
    client = AnthropicChat(sdk=sdk, model="claude-opus-4-8")
    out = client.complete_json("sys", "user", schema={"type": "object"})
    assert out == {"title": "Ep1", "ok": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_anthropic_client.py -v`
Expected: FAIL — `ModuleNotFoundError: engine.llm.anthropic_client`.

- [ ] **Step 3: Write `engine/llm/anthropic_client.py`**

```python
from __future__ import annotations

import os

from engine.llm.base import LLMError, with_retry


class AnthropicChat:
    """Writer/editor client. Pass `sdk` for tests; otherwise it builds a real anthropic.Anthropic."""

    def __init__(self, sdk=None, model: str = "claude-opus-4-8", api_key: str | None = None):
        if sdk is None:
            import anthropic  # imported lazily so tests need no key/SDK network
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise LLMError("ANTHROPIC_API_KEY not set", status=401)
            sdk = anthropic.Anthropic(api_key=key)
        self.sdk = sdk
        self.model = model

    def _create(self, **kwargs):
        def call():
            try:
                return self.sdk.messages.create(model=self.model, **kwargs)
            except Exception as exc:  # map SDK errors into retryable LLMError
                status = getattr(exc, "status_code", None)
                raise LLMError(str(exc), status=status if status else 500)
        return with_retry(call)

    def complete(self, system: str, user: str, *, max_tokens: int = 4096) -> str:
        msg = self._create(system=system, max_tokens=max_tokens,
                           messages=[{"role": "user", "content": user}])
        for block in msg.content:
            if getattr(block, "type", None) == "text":
                return block.text
        raise LLMError("anthropic: no text block in response")

    def complete_json(self, system: str, user: str, *, schema: dict, max_tokens: int = 4096) -> dict:
        tool = {"name": "emit", "description": "Return the structured result.",
                "input_schema": schema if schema else {"type": "object"}}
        msg = self._create(system=system, max_tokens=max_tokens, tools=[tool],
                           tool_choice={"type": "tool", "name": "emit"},
                           messages=[{"role": "user", "content": user}])
        for block in msg.content:
            if getattr(block, "type", None) == "tool_use":
                return dict(block.input)
        raise LLMError("anthropic: no tool_use block in response")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_anthropic_client.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/llm/anthropic_client.py tests/test_anthropic_client.py
git commit -m "feat(llm): Anthropic chat client with forced tool-use JSON"
```

---

## Task 6: Model routing config

**Files:**
- Create: `models.yaml`
- Create: `engine/llm/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write `models.yaml`**

```yaml
writer:
  provider: anthropic
  model: claude-opus-4-8
  max_tokens: 16000
editor:
  provider: anthropic
  model: claude-opus-4-8
  max_tokens: 16000
critic:
  provider: nvidia
  voters:
    - meta/llama-3.3-70b-instruct
    - mistralai/mistral-nemotron
    - nvidia/llama-3.3-nemotron-super-49b-v1
embeddings:
  provider: nvidia
  model: baai/bge-m3
```

- [ ] **Step 2: Write the failing test** (`tests/test_config.py`)

```python
from pathlib import Path
from engine.llm.config import load_config


def test_load_config_reads_routing(tmp_path):
    (tmp_path / "models.yaml").write_text(
        "writer: {provider: anthropic, model: claude-opus-4-8, max_tokens: 100}\n"
        "critic: {provider: nvidia, voters: [a, b, c]}\n"
        "embeddings: {provider: nvidia, model: baai/bge-m3}\n", encoding="utf-8")
    cfg = load_config(tmp_path / "models.yaml")
    assert cfg["writer"]["model"] == "claude-opus-4-8"
    assert cfg["critic"]["voters"] == ["a", "b", "c"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: engine.llm.config`.

- [ ] **Step 4: Write `engine/llm/config.py`**

```python
from __future__ import annotations

import os
from pathlib import Path

import yaml

from engine.llm.anthropic_client import AnthropicChat
from engine.llm.nvidia_client import NvidiaChat, NvidiaEmbeddings


def load_config(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def build_chat(stage_cfg: dict):
    provider = stage_cfg["provider"]
    if provider == "anthropic":
        return AnthropicChat(model=stage_cfg["model"])
    if provider == "nvidia":
        return NvidiaChat(api_key=os.environ["NVIDIA_API_KEY"], model=stage_cfg["model"])
    raise ValueError(f"unknown provider: {provider}")


def build_critic_voters(critic_cfg: dict) -> list:
    key = os.environ["NVIDIA_API_KEY"]
    return [NvidiaChat(api_key=key, model=m) for m in critic_cfg["voters"]]


def build_embeddings(emb_cfg: dict) -> NvidiaEmbeddings:
    return NvidiaEmbeddings(api_key=os.environ["NVIDIA_API_KEY"], model=emb_cfg["model"])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Commit**

```bash
git add models.yaml engine/llm/config.py tests/test_config.py
git commit -m "feat(llm): models.yaml routing + lazy client builders"
```

---

## Task 7: Embedding retrieval

**Files:**
- Create: `engine/retrieval_embed.py`
- Test: `tests/test_retrieval_embed.py`

- [ ] **Step 1: Write the failing test** (`tests/test_retrieval_embed.py`)

```python
from engine.canon.store import CanonStore
from engine.llm.fakes import FakeEmbeddings
from engine.retrieval_embed import EmbeddingRetriever


def _char(cid, name, desc):
    return {
        "id": cid, "type": "character", "name": name,
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "t"},
        "public": {"description": desc},
    }


def test_build_then_query_returns_relevant(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren", "a clockmaker who fixes broken timepieces"))
    store.save(_char("char-lyra", "Lyra", "a sailor from the eastern reach"))
    r = EmbeddingRetriever(store, FakeEmbeddings(dim=32))
    r.build()                                   # writes canon/_index/embeddings.jsonl
    hits = r.relevant("a broken clock in the workshop", k=1)
    assert hits == ["char-ren"]                 # nearest by cosine


def test_build_is_idempotent(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren", "clockmaker"))
    r = EmbeddingRetriever(store, FakeEmbeddings(dim=16))
    r.build()
    r.build()
    assert (tmp_canon / "_index" / "embeddings.jsonl").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_retrieval_embed.py -v`
Expected: FAIL — `ModuleNotFoundError: engine.retrieval_embed`.

- [ ] **Step 3: Write `engine/retrieval_embed.py`**

```python
from __future__ import annotations

import json
import math

from engine.canon.store import CanonStore
from engine.llm.base import EmbeddingClient


def _text_of(entity: dict) -> str:
    parts = [entity.get("name", "")]
    pub = entity.get("public", {})
    if isinstance(pub, dict):
        parts.append(json.dumps(pub, ensure_ascii=False))
    for k in ("description", "logline", "summary"):
        if k in entity:
            parts.append(str(entity[k]))
    return " ".join(p for p in parts if p)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(y * y for y in b)) or 1e-9
    return dot / (na * nb)


class EmbeddingRetriever:
    def __init__(self, store: CanonStore, client: EmbeddingClient):
        self.store = store
        self.client = client
        self.path = store.root / "_index" / "embeddings.jsonl"

    def build(self) -> int:
        ids, texts = [], []
        for ent in self.store.all_entities():
            ids.append(ent["id"])
            texts.append(_text_of(ent))
        vectors = self.client.embed(texts) if texts else []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for eid, vec in zip(ids, vectors):
                fh.write(json.dumps({"id": eid, "vec": vec}) + "\n")
        return len(ids)

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line]

    def relevant(self, query: str, k: int = 8) -> list[str]:
        rows = self._load()
        if not rows:
            return []
        qvec = self.client.embed([query])[0]
        scored = [(row["id"], _cosine(qvec, row["vec"])) for row in rows]
        scored.sort(key=lambda t: t[1], reverse=True)
        return [eid for eid, _ in scored[:k]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_retrieval_embed.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/retrieval_embed.py tests/test_retrieval_embed.py
git commit -m "feat: embedding retrieval (cosine over bge-m3 vectors, injected client)"
```

---

## Task 8: Continuity critic

**Files:**
- Create: `engine/critic.py`
- Create: `tests/fixtures/critic_clean.json`, `tests/fixtures/critic_contradiction.json`
- Test: `tests/test_critic.py`

The critic asks each NVIDIA voter to return `{"verdict": "clean"|"issues", "issues": [{"severity": "blocking"|"minor", "kind": "...", "detail": "..."}]}`. Aggregation: the episode is **rejected** when the number of voters reporting at least one `blocking` issue is ≥ majority (`ceil(n/2)`). A single false-positive voter cannot stall the loop.

- [ ] **Step 1: Write fixtures**

`tests/fixtures/critic_clean.json`:
```json
{ "verdict": "clean", "issues": [] }
```

`tests/fixtures/critic_contradiction.json`:
```json
{ "verdict": "issues", "issues": [
  { "severity": "blocking", "kind": "dead_character_reuse", "detail": "Serin died in ep 3 but speaks here." }
] }
```

- [ ] **Step 2: Write the failing test** (`tests/test_critic.py`)

```python
import json
from pathlib import Path
from engine.llm.fakes import FakeChat
from engine.critic import Critic

FIX = Path(__file__).parent / "fixtures"
CLEAN = json.loads((FIX / "critic_clean.json").read_text())
BAD = json.loads((FIX / "critic_contradiction.json").read_text())


def test_clean_when_all_voters_clean():
    voters = [FakeChat([CLEAN]), FakeChat([CLEAN]), FakeChat([CLEAN])]
    verdict = Critic(voters).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is True
    assert verdict.issues == []


def test_rejected_when_majority_blocking():
    voters = [FakeChat([BAD]), FakeChat([BAD]), FakeChat([CLEAN])]
    verdict = Critic(voters).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is False
    assert any(i["kind"] == "dead_character_reuse" for i in verdict.issues)


def test_single_false_positive_does_not_stall():
    voters = [FakeChat([BAD]), FakeChat([CLEAN]), FakeChat([CLEAN])]
    verdict = Critic(voters).review(episode={"title": "x"}, canon_context="")
    assert verdict.clean is True            # 1 of 3 < majority -> passes
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_critic.py -v`
Expected: FAIL — `ModuleNotFoundError: engine.critic`.

- [ ] **Step 4: Write `engine/critic.py`**

```python
from __future__ import annotations

import json
import math
from dataclasses import dataclass

from engine.llm.base import ChatClient

_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["clean", "issues"]},
        "issues": {"type": "array"},
    },
    "required": ["verdict", "issues"],
}

SYSTEM = (
    "You are a continuity critic for the Arion World canon. Given a proposed episode and the "
    "relevant existing canon, find any contradiction, retcon, dead-character reuse, "
    "equivalent-exchange/power-creep violation, tone break, or hook-logic error. "
    "Return JSON {\"verdict\": \"clean\"|\"issues\", \"issues\": "
    "[{\"severity\": \"blocking\"|\"minor\", \"kind\": str, \"detail\": str}]}."
)


@dataclass
class Verdict:
    clean: bool
    issues: list[dict]
    raw: list[dict]


class Critic:
    def __init__(self, voters: list[ChatClient]):
        assert voters, "critic needs at least one voter"
        self.voters = voters

    def review(self, episode: dict, canon_context: str) -> Verdict:
        user = (
            f"RELEVANT CANON:\n{canon_context}\n\n"
            f"PROPOSED EPISODE:\n{json.dumps(episode, ensure_ascii=False)[:120000]}"
        )
        results = []
        for voter in self.voters:
            try:
                results.append(voter.complete_json(SYSTEM, user, schema=_VERDICT_SCHEMA))
            except Exception as exc:  # a voter erroring counts as an abstain, logged
                results.append({"verdict": "error", "issues": [], "_error": str(exc)})

        blocking_votes = sum(
            1 for r in results
            if any(i.get("severity") == "blocking" for i in r.get("issues", []))
        )
        majority = math.ceil(len(self.voters) / 2)
        clean = blocking_votes < majority
        all_issues = [i for r in results for i in r.get("issues", [])]
        return Verdict(clean=clean, issues=all_issues, raw=results)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_critic.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add engine/critic.py tests/test_critic.py tests/fixtures
git commit -m "feat: continuity critic panel with majority-blocking aggregation"
```

---

## Task 9: Writer + Editor

**Files:**
- Create: `engine/writer.py`
- Test: `tests/test_writer.py`

`Writer.write()` and `Writer.revise()` call a `ChatClient.complete_json` and return the episode dict (which includes a `patch_ops` list of CanonPatch operation dicts). `Editor.polish()` returns the final episode dict. Prompts are real; tests inject `FakeChat` returning canned episode dicts.

- [ ] **Step 1: Write the failing test** (`tests/test_writer.py`)

```python
from engine.llm.fakes import FakeChat
from engine.writer import Writer, Editor

EP = {
    "title": "The Clock That Stopped", "logline": "x", "summary": "y", "cliffhanger": "z",
    "scenes": [{"scene_number": 1, "prose": "..."}],
    "patch_ops": [{"op": "mark_hook_revealed", "id": "hook-001", "episode": 1}],
}


def test_writer_write_returns_episode_dict():
    w = Writer(FakeChat([EP]))
    out = w.write(episode_number=1, canon_context="canon...")
    assert out["title"] == "The Clock That Stopped"
    assert out["patch_ops"][0]["op"] == "mark_hook_revealed"


def test_writer_revise_includes_issue_feedback_in_prompt():
    chat = FakeChat([EP])
    Writer(chat).revise(episode_number=1, canon_context="c", draft=EP,
                        issues=[{"severity": "blocking", "kind": "tone", "detail": "too edgy"}])
    assert "too edgy" in chat.calls[0]["user"]


def test_editor_polish_returns_episode():
    e = Editor(FakeChat([EP]))
    assert e.polish(EP, canon_context="c")["summary"] == "y"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_writer.py -v`
Expected: FAIL — `ModuleNotFoundError: engine.writer`.

- [ ] **Step 3: Write `engine/writer.py`**

```python
from __future__ import annotations

import json

from engine.llm.base import ChatClient

_EPISODE_SCHEMA = {"type": "object"}  # writer returns a free-form episode dict (validated downstream)

WRITER_SYSTEM = (
    "You are the lead writer for Arion World, a 16+ epic anime fantasy. Equivalent exchange "
    "governs all power; no character or outcome is protected. Write a full episode as JSON: "
    "{title, logline, summary, cliffhanger, scenes:[{scene_number, location, prose, dialogue}], "
    "patch_ops:[canon mutation ops]}. patch_ops use: create_entity, set_field, append_to_list, "
    "add_relationship, mark_hook_revealed, record_death. Stay consistent with the provided canon."
)

EDITOR_SYSTEM = (
    "You are the editor for Arion World. Polish prose quality and internal consistency without "
    "changing plot facts. Return the same JSON episode structure, improved."
)


class Writer:
    def __init__(self, chat: ChatClient):
        self.chat = chat

    def write(self, episode_number: int, canon_context: str) -> dict:
        user = (f"Write Episode {episode_number}.\n\nRELEVANT CANON:\n{canon_context}\n\n"
                "Return the episode JSON described in the system prompt.")
        return self.chat.complete_json(WRITER_SYSTEM, user, schema=_EPISODE_SCHEMA, max_tokens=16000)

    def revise(self, episode_number: int, canon_context: str, draft: dict, issues: list[dict]) -> dict:
        user = (f"Revise Episode {episode_number}. The continuity critic flagged these issues — "
                f"fix ALL of them:\n{json.dumps(issues, ensure_ascii=False)}\n\n"
                f"RELEVANT CANON:\n{canon_context}\n\n"
                f"CURRENT DRAFT:\n{json.dumps(draft, ensure_ascii=False)[:120000]}")
        return self.chat.complete_json(WRITER_SYSTEM, user, schema=_EPISODE_SCHEMA, max_tokens=16000)


class Editor:
    def __init__(self, chat: ChatClient):
        self.chat = chat

    def polish(self, episode: dict, canon_context: str) -> dict:
        user = (f"RELEVANT CANON:\n{canon_context}\n\nEPISODE TO POLISH:\n"
                f"{json.dumps(episode, ensure_ascii=False)[:120000]}")
        return self.chat.complete_json(EDITOR_SYSTEM, user, schema=_EPISODE_SCHEMA, max_tokens=16000)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_writer.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/writer.py tests/test_writer.py
git commit -m "feat: writer (write/revise) + editor over injected chat client"
```

---

## Task 10: Episode pipeline + gate + CLI

**Files:**
- Create: `engine/pipelines/__init__.py`, `engine/pipelines/episode.py`
- Modify: `engine/__main__.py` (add `episode` subcommand)
- Test: `tests/test_episode_pipeline.py`

`EpisodePipeline` composes Writer, Critic, Editor, EmbeddingRetriever, CanonStore. Flow: retrieve canon → write → critic → (revise loop ≤ max_revisions) → if still rejected: quarantine to `pending/episodes/` and return `quarantined`; else editor.polish → build episode entity → apply CanonPatch(patch_ops) → bump counter → build index → return `committed`. Components are injected (fakes in tests).

- [ ] **Step 1: Write the failing test** (`tests/test_episode_pipeline.py`)

```python
import json
from engine.canon.store import CanonStore
from engine.pipelines.episode import EpisodePipeline


class _Writer:
    def __init__(self, episodes): self._eps = list(episodes); self._i = 0
    def _take(self):
        ep = self._eps[min(self._i, len(self._eps) - 1)]; self._i += 1; return ep
    def write(self, episode_number, canon_context): return self._take()
    def revise(self, episode_number, canon_context, draft, issues): return self._take()


class _Editor:
    def polish(self, episode, canon_context): return episode


class _Critic:
    def __init__(self, verdicts): self._v = list(verdicts); self._i = 0
    def review(self, episode, canon_context):
        v = self._v[min(self._i, len(self._v) - 1)]; self._i += 1; return v


class _Retriever:
    def relevant(self, query, k=8): return []


class _V:
    def __init__(self, clean, issues=()): self.clean = clean; self.issues = list(issues)


def _episode(title="Ep One"):
    return {"title": title, "logline": "l", "summary": "s", "cliffhanger": "c",
            "scenes": [{"scene_number": 1, "prose": "..."}], "patch_ops": []}


def _pipeline(tmp_canon, writer, critic):
    store = CanonStore(tmp_canon)
    return store, EpisodePipeline(store=store, writer=writer, critic=critic,
                                  editor=_Editor(), retriever=_Retriever(), max_revisions=2)


def test_clean_episode_is_committed(tmp_canon):
    store, pipe = _pipeline(tmp_canon, _Writer([_episode()]), _Critic([_V(True)]))
    result = pipe.run(episode_number=1)
    assert result["status"] == "committed"
    assert store.load("ep-001")["number"] == 1


def test_revise_then_pass_commits(tmp_canon):
    store, pipe = _pipeline(
        tmp_canon, _Writer([_episode("bad"), _episode("fixed")]),
        _Critic([_V(False, [{"severity": "blocking", "kind": "x", "detail": "d"}]), _V(True)]))
    result = pipe.run(episode_number=1)
    assert result["status"] == "committed"
    assert store.load("ep-001")["name"] == "fixed"


def test_always_failing_is_quarantined_not_committed(tmp_canon):
    store, pipe = _pipeline(
        tmp_canon, _Writer([_episode()]),
        _Critic([_V(False, [{"severity": "blocking", "kind": "x", "detail": "d"}])]))
    result = pipe.run(episode_number=1)
    assert result["status"] == "quarantined"
    assert not store.exists("ep-001")
    assert (tmp_canon.parent / "pending" / "episodes" / "ep-001.json").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_episode_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: engine.pipelines.episode`.

- [ ] **Step 3: Write `engine/pipelines/__init__.py` (empty) and `engine/pipelines/episode.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from engine.canon.store import CanonStore
from engine.canon.patch import CanonPatch
from engine.canon.index import build_index


def _slug_number(n: int) -> str:
    return f"ep-{n:03d}"


class EpisodePipeline:
    def __init__(self, store: CanonStore, writer, critic, editor, retriever, max_revisions: int = 3):
        self.store = store
        self.writer = writer
        self.critic = critic
        self.editor = editor
        self.retriever = retriever
        self.max_revisions = max_revisions

    def _context(self, episode_number: int) -> str:
        ids = self.retriever.relevant(f"episode {episode_number}", k=12)
        ents = []
        for eid in ids:
            try:
                ents.append(self.store.load(eid))
            except KeyError:
                pass
        return json.dumps(ents, ensure_ascii=False)[:120000]

    def _quarantine(self, episode_number: int, episode: dict, issues) -> dict:
        pending = self.store.root.parent / "pending" / "episodes"
        pending.mkdir(parents=True, exist_ok=True)
        path = pending / f"{_slug_number(episode_number)}.json"
        path.write_text(json.dumps({"episode": episode, "issues": issues}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return {"status": "quarantined", "path": str(path), "issues": issues}

    def _commit(self, episode_number: int, episode: dict) -> dict:
        eid = _slug_number(episode_number)
        entity = {
            "id": eid, "type": "episode", "name": episode.get("title", eid),
            "provenance": {"introduced_episode": episode_number,
                           "last_changed_episode": episode_number, "source_run": eid},
            "number": episode_number,
            "logline": episode.get("logline", ""),
            "summary": episode.get("summary", ""),
            "cliffhanger": episode.get("cliffhanger", ""),
            "scenes": episode.get("scenes", []),
        }
        self.store.save(entity)

        patch = CanonPatch(source_run=eid)
        patch.ops = list(episode.get("patch_ops", []))
        if patch.ops:
            patch.apply(self.store)

        state_path = self.store.root / "_state.json"
        state = {"next_episode": episode_number + 1}
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        build_index(self.store)
        return {"status": "committed", "id": eid}

    def run(self, episode_number: int) -> dict:
        context = self._context(episode_number)
        episode = self.writer.write(episode_number=episode_number, canon_context=context)
        verdict = self.critic.review(episode=episode, canon_context=context)

        revisions = 0
        while not verdict.clean and revisions < self.max_revisions:
            episode = self.writer.revise(episode_number=episode_number, canon_context=context,
                                         draft=episode, issues=verdict.issues)
            verdict = self.critic.review(episode=episode, canon_context=context)
            revisions += 1

        if not verdict.clean:
            return self._quarantine(episode_number, episode, verdict.issues)

        episode = self.editor.polish(episode, canon_context=context)
        return self._commit(episode_number, episode)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_episode_pipeline.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Wire the `episode` CLI subcommand into `engine/__main__.py`**

Add this command function and register it (only builds real clients when invoked, so the rest of the CLI stays key-free):

```python
def cmd_episode(args) -> int:
    from engine.llm.config import (load_config, build_chat, build_critic_voters, build_embeddings)
    from engine.retrieval_embed import EmbeddingRetriever
    from engine.critic import Critic
    from engine.writer import Writer, Editor
    from engine.pipelines.episode import EpisodePipeline

    store = CanonStore(Path(args.canon))
    cfg = load_config(Path(args.models))
    retriever = EmbeddingRetriever(store, build_embeddings(cfg["embeddings"]))
    if args.reindex:
        retriever.build()
    pipe = EpisodePipeline(
        store=store,
        writer=Writer(build_chat(cfg["writer"])),
        critic=Critic(build_critic_voters(cfg["critic"])),
        editor=Editor(build_chat(cfg["editor"])),
        retriever=retriever,
    )
    state = store.root / "_state.json"
    import json as _json
    number = _json.loads(state.read_text())["next_episode"] if state.exists() else 1
    result = pipe.run(episode_number=number)
    print(_json.dumps(result, indent=2))
    return 0 if result["status"] == "committed" else 2
```

Register it in `main()` alongside the others:
```python
    ep = sub.add_parser("episode", parents=[parent])
    ep.add_argument("--models", default="models.yaml")
    ep.add_argument("--reindex", action="store_true")
```
and add `"episode": cmd_episode` to the dispatch dict.

- [ ] **Step 6: Run the full suite**

Run: `python -m pytest -q`
Expected: ALL pass (Phase 0a + 0b).

- [ ] **Step 7: Commit**

```bash
git add engine/pipelines engine/__main__.py tests/test_episode_pipeline.py
git commit -m "feat: episode pipeline (gate/revise/quarantine) + episode CLI command"
```

---

## Task 11: Live smoke (guarded — requires real keys)

**Files:**
- Create: `tests/test_live_smoke.py`

- [ ] **Step 1: Write a key-guarded live test** (`tests/test_live_smoke.py`)

```python
import os
import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("NVIDIA_API_KEY")),
    reason="live keys not set",
)


def test_nvidia_embeddings_roundtrip():
    from engine.llm.nvidia_client import NvidiaEmbeddings
    vecs = NvidiaEmbeddings(api_key=os.environ["NVIDIA_API_KEY"]).embed(["hello", "world"])
    assert len(vecs) == 2 and len(vecs[0]) > 100      # bge-m3 dim ~1024
```

- [ ] **Step 2: Run it (skips cleanly without keys)**

Run: `python -m pytest tests/test_live_smoke.py -v`
Expected: SKIPPED (no keys) — or PASS when keys are present.

- [ ] **Step 3: When keys exist, run one real episode**

```bash
NVIDIA_API_KEY=... ANTHROPIC_API_KEY=... python -m engine episode --canon canon --reindex
```
Expected: prints `{"status": "committed", "id": "ep-001"}` and writes `canon/episodes/ep-001.yaml`. If `quarantined`, read `pending/episodes/ep-001.json` for the critic's reasons (do NOT loosen the critic to force a pass — fix the prompt or the canon).

- [ ] **Step 4: Commit**

```bash
git add tests/test_live_smoke.py
git commit -m "test: key-guarded live smoke for NVIDIA/Anthropic"
```

---

## Self-Review (completed by plan author)

**Spec coverage:** §5 retrieve→write→critic→gate→edit→commit → Tasks 7,8,9,10. §5 critic panel (council pattern) → Task 8. §3 embeddings retrieval → Task 7. §8 error handling (retry/backoff, typed errors, structured output, quarantine-not-corrupt) → Tasks 2,4,5,10. Episode persistence as canon → Task 1. (Astro `/read` = Plan 0c; autonomous cron = Phase 1 — both out of scope here.)

**Placeholder scan:** none — every code step is complete; Task 11 step 3 leaves keys as `...` because they are secrets supplied at runtime, not author choices.

**Type consistency:** `ChatClient.complete/complete_json` and `EmbeddingClient.embed` signatures are identical across `base`, `fakes`, `nvidia_client`, `anthropic_client`, and every consumer. `Critic.review(episode, canon_context) -> Verdict(clean, issues, raw)` matches the pipeline's usage. `Writer.write/revise` and `Editor.polish` signatures match `EpisodePipeline.run` and the fakes in `test_episode_pipeline`. `CanonPatch(source_run=...).ops`/`.apply(store)` matches Phase 0a. `_slug_number` zero-pads to match the `ep-001` schema id pattern.

**Exit criterion (Phase 0b):** full `pytest` green with all LLM deps faked (no spend); `engine episode` wired; one live episode commits end-to-end once `ANTHROPIC_API_KEY` + `NVIDIA_API_KEY` are set. Ready for Plan 0c (Astro `/read`).
```
