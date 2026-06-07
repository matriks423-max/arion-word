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
            except Exception as exc:
                status = getattr(exc, "status_code", None)
                if status is not None:                       # genuine API status error
                    raise LLMError(str(exc), status=status)
                name = type(exc).__name__.lower()
                transient = any(t in name for t in ("connection", "timeout"))
                # Programming/serialization errors (no status, not transient) must NOT be retried.
                raise LLMError(str(exc), status=503 if transient else 400)
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
