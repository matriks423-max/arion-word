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
