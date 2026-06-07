import pytest
from engine.canon.store import CanonStore
from engine.canon.patch import CanonPatch, PatchError


def _char(cid, name, ep=1):
    return {
        "id": cid, "type": "character", "name": name,
        "provenance": {"introduced_episode": ep, "last_changed_episode": ep, "source_run": "test"},
        "public": {"role": "supporting"},
    }


def _hook(hid):
    return {
        "id": hid, "type": "hook", "name": hid, "description": "x",
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "test"},
        "planted_episode": 1, "payoff_episode": 88, "category": "world_lore", "revealed": False,
    }


def test_create_entity(tmp_canon):
    store = CanonStore(tmp_canon)
    CanonPatch(source_run="ep002").create_entity(_char("char-ren", "Ren")).apply(store)
    assert store.load("char-ren")["name"] == "Ren"


def test_set_field_and_append(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren"))
    (CanonPatch(source_run="ep002")
        .set_field("char-ren", "public.role", "mentor")
        .append_to_list("char-ren", "public.titles", "Clockkeeper")
        .apply(store))
    ren = store.load("char-ren")
    assert ren["public"]["role"] == "mentor"
    assert ren["public"]["titles"] == ["Clockkeeper"]
    assert ren["provenance"]["last_changed_episode"] == "ep002"


def test_add_relationship_requires_target(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren"))
    with pytest.raises(PatchError):
        CanonPatch(source_run="ep002").add_relationship("char-ren", "mentor_of", "char-ghost").apply(store)


def test_mark_hook_revealed(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_hook("hook-001"))
    CanonPatch(source_run="ep088").mark_hook_revealed("hook-001", 88).apply(store)
    assert store.load("hook-001")["revealed"] is True


def test_apply_is_atomic_on_failure(tmp_canon):
    """A patch that fails partway must leave the store untouched."""
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren"))
    patch = (CanonPatch(source_run="ep002")
             .set_field("char-ren", "public.role", "traitor")
             .create_entity(_char("char-ren", "Ren")))   # duplicate id -> fails
    with pytest.raises(PatchError):
        patch.apply(store)
    assert store.load("char-ren")["public"]["role"] == "supporting"   # rolled back


def test_rollback_unlinks_newly_created_on_later_op_failure(tmp_canon):
    """A create that succeeds, then a later op that fails, must delete the created file."""
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren"))
    patch = (CanonPatch(source_run="ep002")
             .create_entity(_char("char-new", "New"))            # writes the file
             .add_relationship("char-new", "knows", "char-ghost"))  # ghost missing -> fails
    with pytest.raises(PatchError):
        patch.apply(store)
    assert not store.exists("char-new")                          # created file unlinked
    assert store.load("char-ren")["public"]["role"] == "supporting"  # pre-existing untouched
