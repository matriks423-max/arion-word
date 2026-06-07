import pytest
from engine.canon.store import CanonStore, ValidationFailed


def _valid_character():
    return {
        "id": "char-kairo-voss",
        "type": "character",
        "name": "Kairo Voss",
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "test"},
        "public": {"role": "protagonist"},
    }


def test_save_then_load_roundtrip(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_valid_character())
    loaded = store.load("char-kairo-voss")
    assert loaded["name"] == "Kairo Voss"
    assert (tmp_canon / "characters" / "char-kairo-voss.yaml").exists()


def test_save_rejects_invalid_entity(tmp_canon):
    store = CanonStore(tmp_canon)
    bad = _valid_character()
    del bad["public"]            # violates character schema
    with pytest.raises(ValidationFailed):
        store.save(bad)


def test_list_ids_and_exists(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_valid_character())
    assert store.exists("char-kairo-voss")
    assert "char-kairo-voss" in store.list_ids()
    assert store.list_ids(entity_type="character") == ["char-kairo-voss"]


def test_load_missing_raises(tmp_canon):
    store = CanonStore(tmp_canon)
    with pytest.raises(KeyError):
        store.load("char-nobody")
