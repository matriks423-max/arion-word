from engine.canon.store import CanonStore
from engine.pipelines.episode import EpisodePipeline


class _Writer:
    def __init__(self, episodes): self._eps = list(episodes); self._i = 0
    def _take(self):
        ep = self._eps[min(self._i, len(self._eps) - 1)]; self._i += 1; return ep
    def write(self, episode_number, canon_context): return self._take()
    def revise(self, episode_number, canon_context, draft, issues): return self._take()


class _Editor:
    def polish(self, episode, canon_context): return episode


class _Critic:
    def __init__(self, verdicts): self._v = list(verdicts); self._i = 0
    def review(self, episode, canon_context):
        v = self._v[min(self._i, len(self._v) - 1)]; self._i += 1; return v


class _Retriever:
    def relevant(self, query, k=8): return []


class _V:
    def __init__(self, clean, issues=()): self.clean = clean; self.issues = list(issues)


def _episode(title="Ep One"):
    return {"title": title, "logline": "l", "summary": "s", "cliffhanger": "c",
            "scenes": [{"scene_number": 1, "prose": "..."}], "patch_ops": []}


def _pipeline(tmp_canon, writer, critic):
    store = CanonStore(tmp_canon)
    return store, EpisodePipeline(store=store, writer=writer, critic=critic,
                                  editor=_Editor(), retriever=_Retriever(), max_revisions=2)


def test_clean_episode_is_committed(tmp_canon):
    store, pipe = _pipeline(tmp_canon, _Writer([_episode()]), _Critic([_V(True)]))
    result = pipe.run(episode_number=1)
    assert result["status"] == "committed"
    assert store.load("ep-001")["number"] == 1


def test_revise_then_pass_commits(tmp_canon):
    store, pipe = _pipeline(
        tmp_canon, _Writer([_episode("bad"), _episode("fixed")]),
        _Critic([_V(False, [{"severity": "blocking", "kind": "x", "detail": "d"}]), _V(True)]))
    result = pipe.run(episode_number=1)
    assert result["status"] == "committed"
    assert store.load("ep-001")["name"] == "fixed"


def test_always_failing_is_quarantined_not_committed(tmp_canon):
    store, pipe = _pipeline(
        tmp_canon, _Writer([_episode()]),
        _Critic([_V(False, [{"severity": "blocking", "kind": "x", "detail": "d"}])]))
    result = pipe.run(episode_number=1)
    assert result["status"] == "quarantined"
    assert not store.exists("ep-001")
    assert (tmp_canon.parent / "pending" / "episodes" / "ep-001.json").exists()
