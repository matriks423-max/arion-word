import json
from engine.canon.store import CanonStore
from engine.canon.index import build_index


def _char(cid, name):
    return {
        "id": cid, "type": "character", "name": name,
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "t"},
        "public": {"role": "supporting", "tags": ["caelum"]},
    }


def test_build_index_writes_manifest(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren"))
    store.save(_char("char-lyra", "Lyra"))
    index = build_index(store)
    assert {e["id"] for e in index["entities"]} == {"char-ren", "char-lyra"}
    assert index["by_type"]["character"] == ["char-lyra", "char-ren"]
    # persisted to disk
    written = json.loads((tmp_canon / "_index.json").read_text(encoding="utf-8"))
    assert written["count"] == 2
