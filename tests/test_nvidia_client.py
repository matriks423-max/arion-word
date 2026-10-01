import json
import pytest
import requests
from engine.llm.base import LLMError
from engine.llm import nvidia_client as nv


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr("engine.llm.base.time.sleep", lambda s: None)


def test_chat_complete_parses_choice(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        assert "chat/completions" in url
        return _Resp(200, {"choices": [{"message": {"content": "hello world"}}]})
    monkeypatch.setattr(nv.requests, "post", fake_post)
    client = nv.NvidiaChat(api_key="k", model="nvidia/nemotron-3-super-120b-a12b")
    assert client.complete("sys", "user") == "hello world"


def test_chat_raises_llmerror_with_status(monkeypatch):
    monkeypatch.setattr(nv.requests, "post", lambda *a, **k: _Resp(503, {"error": "busy"}))
    client = nv.NvidiaChat(api_key="k", model="m")
    with pytest.raises(LLMError) as e:
        client.complete("s", "u")
    assert e.value.status == 503


def test_chat_retired_model_fails_fast_with_reason(monkeypatch):
    calls = []

    def fake_post(*a, **k):
        calls.append(1)
        return _Resp(410, {"detail": "The model 'meta/llama-3.3-70b-instruct' has reached its end of life"})
    monkeypatch.setattr(nv.requests, "post", fake_post)
    with pytest.raises(LLMError) as e:
        nv.NvidiaChat(api_key="k", model="meta/llama-3.3-70b-instruct").complete("s", "u")
    assert e.value.status == 410 and "end of life" in str(e.value)
    assert len(calls) == 1                       # 410 is permanent: no retry


def test_chat_empty_content_is_an_error_not_none(monkeypatch):
    # a reasoning model that spends the whole budget thinking returns content=None
    payload = {"choices": [{"message": {"content": None}, "finish_reason": "length"}]}
    monkeypatch.setattr(nv.requests, "post", lambda *a, **k: _Resp(200, payload))
    with pytest.raises(LLMError) as e:
        nv.NvidiaChat(api_key="k", model="m").complete("s", "u")
    assert "finish_reason=length" in str(e.value)


def test_chat_uses_configured_max_tokens(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.update(max_tokens=json["max_tokens"], timeout=timeout)
        return _Resp(200, {"choices": [{"message": {"content": "{}"}}]})
    monkeypatch.setattr(nv.requests, "post", fake_post)
    nv.NvidiaChat(api_key="k", model="m", max_tokens=16000, timeout=300).complete_json("s", "u", schema={})
    assert seen == {"max_tokens": 16000, "timeout": 300}


def test_chat_network_error_becomes_llmerror(monkeypatch):
    def boom(*a, **k):
        raise requests.Timeout("read timed out")
    monkeypatch.setattr(nv.requests, "post", boom)
    with pytest.raises(LLMError) as e:
        nv.NvidiaChat(api_key="k", model="m").complete("s", "u")
    assert "Timeout" in str(e.value)


def test_embeddings_returns_vectors(monkeypatch):
    def fake_post(url, headers=None, json=None, timeout=None):
        assert "embeddings" in url
        return _Resp(200, {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]})
    monkeypatch.setattr(nv.requests, "post", fake_post)
    client = nv.NvidiaEmbeddings(api_key="k", model="nvidia/nemotron-3-embed-1b")
    assert client.embed(["a", "b"]) == [[0.1, 0.2], [0.3, 0.4]]


def test_embeddings_send_input_type_and_batch(monkeypatch):
    sent = []

    def fake_post(url, headers=None, json=None, timeout=None):
        sent.append((json["input_type"], len(json["input"])))
        return _Resp(200, {"data": [{"embedding": [0.0]} for _ in json["input"]]})
    monkeypatch.setattr(nv.requests, "post", fake_post)
    client = nv.NvidiaEmbeddings(api_key="k")
    assert len(client.embed([f"t{i}" for i in range(300)])) == 300   # NIM caps a request at 256
    client.embed(["q"], input_type="query")
    assert sent == [("passage", 128), ("passage", 128), ("passage", 44), ("query", 1)]


def test_complete_json_names_model_and_snippet_on_bad_json(monkeypatch):
    payload = {"choices": [{"message": {"content": '{"verdict": "issues" "issues": []}'}}]}
    monkeypatch.setattr(nv.requests, "post", lambda *a, **k: _Resp(200, payload))
    with pytest.raises(LLMError) as e:
        nv.NvidiaChat(api_key="k", model="nvidia/x").complete_json("s", "u", schema={})
    assert "nvidia/x" in str(e.value) and '"verdict"' in str(e.value)
