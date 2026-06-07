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
