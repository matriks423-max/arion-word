import json
from pathlib import Path
from engine.canon.store import CanonStore
from engine.migrate import migrate_characters, migrate_hooks, migrate_techniques, migrate_world_doc


def test_migrate_characters(tmp_canon, tmp_path):
    src = tmp_path / "characters.json"
    src.write_text(json.dumps({
        "_philosophy": "ignore me",
        "main_cast": {
            "Kairo Voss": {"role": "protagonist", "age": 19, "description": "street Resonant",
                            "secret_flag": "is Shattered"}
        }
    }), encoding="utf-8")
    store = CanonStore(tmp_canon)
    ids = migrate_characters(src, store)
    assert ids == ["char-kairo-voss"]
    k = store.load("char-kairo-voss")
    assert k["name"] == "Kairo Voss"
    assert k["public"]["role"] == "protagonist"
    assert k["canon"]["secret_flag"] == "is Shattered"   # full original kept in canon layer


def test_migrate_characters_dedups_colliding_ids(tmp_canon, tmp_path):
    src = tmp_path / "characters.json"
    src.write_text(json.dumps({
        "main_cast": {"Kael": {"role": "a"}},
        "side_cast": {"Kael": {"role": "b"}},   # same slug -> would clobber without dedup
    }), encoding="utf-8")
    store = CanonStore(tmp_canon)
    ids = migrate_characters(src, store)
    assert len(ids) == 2 and len(set(ids)) == 2   # both preserved with distinct ids
    assert store.exists("char-kael") and store.exists("char-kael-2")


def test_migrate_hooks(tmp_canon, tmp_path):
    src = tmp_path / "future_hooks.json"
    src.write_text(json.dumps({"hooks": [
        {"id": "hook_001", "description": "clock 3:12", "planted_episode": 1,
         "payoff_episode": 88, "payoff_description": "Ren is Shattered",
         "revealed": False, "category": "character_secret"}
    ]}), encoding="utf-8")
    store = CanonStore(tmp_canon)
    ids = migrate_hooks(src, store)
    assert ids == ["hook-001"]
    assert store.load("hook-001")["payoff_episode"] == 88


def test_migrate_world_doc(tmp_canon, tmp_path):
    src = tmp_path / "curses.json"
    src.write_text(json.dumps({"_copyright": "x", "mechanics": {"what_a_curse_is": "..."}}), encoding="utf-8")
    store = CanonStore(tmp_canon)
    wid = migrate_world_doc(src, store)
    assert wid == "world-curses"
    doc = store.load("world-curses")
    assert doc["type"] == "world_doc"
    assert "mechanics" in doc["data"]
    assert doc["data"]["_copyright"] == "x"   # lossless: nothing dropped from data
