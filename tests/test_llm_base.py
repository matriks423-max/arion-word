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
