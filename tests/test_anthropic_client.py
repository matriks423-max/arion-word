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


class _RaisingMessages:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        raise ValueError("malformed kwargs")   # no status_code -> a programming error


class _RaisingSDK:
    def __init__(self):
        self.messages = _RaisingMessages()


def test_non_api_error_fails_fast_not_retried():
    sdk = _RaisingSDK()
    client = AnthropicChat(sdk=sdk, model="claude-opus-4-8")
    with pytest.raises(LLMError) as e:
        client.complete("s", "u")
    assert e.value.status == 400           # non-retryable
    assert sdk.messages.calls == 1         # NOT retried 4x as a fake 500
