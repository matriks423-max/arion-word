import pytest
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
    assert len(hits) == 1
    assert hits[0] in {"char-ren", "char-lyra"}


def test_build_is_idempotent(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren", "clockmaker"))
    r = EmbeddingRetriever(store, FakeEmbeddings(dim=16))
    r.build()
    r.build()
    assert (tmp_canon / "_index" / "embeddings.jsonl").exists()


def test_relevant_raises_when_index_missing_but_canon_nonempty(tmp_canon):
    # non-empty canon + no embeddings index = writer/critic would run blind -> fail loud
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren", "clockmaker"))
    r = EmbeddingRetriever(store, FakeEmbeddings(dim=8))   # never built
    with pytest.raises(RuntimeError):
        r.relevant("anything", k=1)


class _NamedEmbeddings(FakeEmbeddings):
    """FakeEmbeddings that reports a model id and records input types, like NvidiaEmbeddings."""

    def __init__(self, model, dim=8):
        super().__init__(dim=dim)
        self.model = model
        self.input_types = []

    def embed(self, texts, input_type="passage"):
        self.input_types.append(input_type)
        return super().embed(texts, input_type)


def test_index_uses_passage_and_search_uses_query(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren", "clockmaker"))
    client = _NamedEmbeddings("nvidia/nemotron-3-embed-1b")
    r = EmbeddingRetriever(store, client)
    r.build()
    r.relevant("clock", k=1)
    assert client.input_types == ["passage", "query"]


def test_index_from_another_model_is_stale_and_refused(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren", "clockmaker"))
    EmbeddingRetriever(store, _NamedEmbeddings("baai/bge-m3")).build()
    r = EmbeddingRetriever(store, _NamedEmbeddings("nvidia/nemotron-3-embed-1b"))
    assert r.is_stale()
    with pytest.raises(RuntimeError, match="--reindex"):
        r.relevant("anything", k=1)
    r.build()
    assert not r.is_stale()


def test_index_without_model_record_is_stale(tmp_canon):
    # indexes built before the model was recorded came from the retired baai/bge-m3
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren", "clockmaker"))
    r = EmbeddingRetriever(store, _NamedEmbeddings("nvidia/nemotron-3-embed-1b"))
    r.build()
    r.meta_path.unlink()
    assert r.is_stale()


def test_relevant_returns_empty_when_store_empty(tmp_canon):
    store = CanonStore(tmp_canon)                          # no entities, no index
    r = EmbeddingRetriever(store, FakeEmbeddings(dim=8))
    assert r.relevant("anything", k=1) == []
