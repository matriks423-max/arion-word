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
