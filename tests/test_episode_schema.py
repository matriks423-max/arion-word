import pytest
from engine.canon.store import CanonStore, ValidationFailed


def _ep():
    return {
        "id": "ep-001", "type": "episode", "name": "The Clock That Stopped",
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "ep001"},
        "number": 1, "logline": "x", "summary": "y", "cliffhanger": "z",
        "scenes": [{"scene_number": 1, "prose": "..."}],
    }


def test_episode_roundtrip(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_ep())
    assert store.load("ep-001")["number"] == 1
    assert (tmp_canon / "episodes" / "ep-001.yaml").exists()


def test_episode_requires_number_and_scenes(tmp_canon):
    store = CanonStore(tmp_canon)
    bad = _ep(); del bad["scenes"]
    with pytest.raises(ValidationFailed):
        store.save(bad)
