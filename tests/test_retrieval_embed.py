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
