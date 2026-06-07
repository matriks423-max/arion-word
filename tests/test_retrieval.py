from engine.canon.store import CanonStore
from engine.canon.index import build_index
from engine.canon.retrieval import Retriever


def _char(cid, name, tags=None, rels=None):
    e = {
        "id": cid, "type": "character", "name": name,
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "t"},
        "public": {"role": "supporting", "tags": tags or []},
    }
    if rels:
        e["relationships"] = rels
    return e


def test_by_type_and_by_tag(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren", tags=["caelum"]))
    store.save(_char("char-lyra", "Lyra", tags=["echo"]))
    build_index(store)
    r = Retriever(store)
    assert r.by_type("character") == ["char-lyra", "char-ren"]
    assert r.by_tag("caelum") == ["char-ren"]


def test_related(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-lyra", "Lyra"))
    store.save(_char("char-ren", "Ren", rels={"knows": ["char-lyra"]}))
    build_index(store)
    r = Retriever(store)
    assert r.related("char-ren") == ["char-lyra"]
