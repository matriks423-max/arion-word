import json
from engine.canon.store import CanonStore
from render.export import export_site


def _char(cid, name):
    return {
        "id": cid, "type": "character", "name": name,
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "t"},
        "public": {"role": "protagonist", "description": "a street resonant"},
        "canon": {"secret": "is actually Shattered"},
    }


def _hook(hid):
    return {
        "id": hid, "type": "hook", "name": hid, "description": "secret clock detail",
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "t"},
        "planted_episode": 1, "payoff_episode": 88, "category": "character_secret", "revealed": False,
    }


def test_export_emits_public_only(tmp_canon, tmp_path):
    store = CanonStore(tmp_canon)
    store.save(_char("char-kairo", "Kairo"))
    store.save(_hook("hook-001"))
    out = tmp_path / "data"
    export_site(store, out)

    chars = json.loads((out / "characters.json").read_text(encoding="utf-8"))
    assert chars[0]["name"] == "Kairo"
    assert chars[0]["role"] == "protagonist"
    blob = (out / "characters.json").read_text(encoding="utf-8")
    assert "Shattered" not in blob          # canon-layer secret never leaks
    assert "secret" not in blob


def test_export_excludes_hooks_entirely(tmp_canon, tmp_path):
    store = CanonStore(tmp_canon)
    store.save(_hook("hook-001"))
    out = tmp_path / "data"
    export_site(store, out)
    assert not (out / "hooks.json").exists()     # hooks are internal, never shipped


def _world_doc():
    return {
        "id": "world-curses", "type": "world_doc", "name": "Curses",
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "t"},
        "data": {
            "overview": "Curses are resonance modifications.",
            "a_curse": {
                "name": "Sleepless",
                "public_effect": "never sleeps",
                "hidden_truth": "the bearer is slowly becoming Shattered",
                "the_real_veilkeeper_secret": "they know the Opening succeeded",
            },
        },
    }


def test_world_doc_spoiler_keys_redacted(tmp_canon, tmp_path):
    store = CanonStore(tmp_canon)
    store.save(_world_doc())
    out = tmp_path / "data"
    export_site(store, out)
    blob = (out / "world.json").read_text(encoding="utf-8")
    assert "overview" in blob and "public_effect" in blob      # public lore kept
    assert "Shattered" not in blob                              # hidden_truth value gone
    assert "the Opening succeeded" not in blob                  # veilkeeper secret gone
    assert "hidden_truth" not in blob and "secret" not in blob  # spoiler keys gone
