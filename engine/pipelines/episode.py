from __future__ import annotations

import json

from engine.canon.store import CanonStore
from engine.canon.patch import CanonPatch
from engine.canon.index import build_index


def _slug_number(n: int) -> str:
    return f"ep-{n:03d}"


class EpisodePipeline:
    def __init__(self, store: CanonStore, writer, critic, editor, retriever, max_revisions: int = 3):
        self.store = store
        self.writer = writer
        self.critic = critic
        self.editor = editor
        self.retriever = retriever
        self.max_revisions = max_revisions

    def _context(self, episode_number: int) -> str:
        ids = self.retriever.relevant(f"episode {episode_number}", k=12)
        ents = []
        for eid in ids:
            try:
                ents.append(self.store.load(eid))
            except KeyError:
                pass
        return json.dumps(ents, ensure_ascii=False)[:120000]

    def _quarantine(self, episode_number: int, episode: dict, issues) -> dict:
        pending = self.store.root.parent / "pending" / "episodes"
        pending.mkdir(parents=True, exist_ok=True)
        path = pending / f"{_slug_number(episode_number)}.json"
        path.write_text(json.dumps({"episode": episode, "issues": issues}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return {"status": "quarantined", "path": str(path), "issues": issues}

    def _commit(self, episode_number: int, episode: dict) -> dict:
        eid = _slug_number(episode_number)
        entity = {
            "id": eid, "type": "episode", "name": episode.get("title", eid),
            "provenance": {"introduced_episode": episode_number,
                           "last_changed_episode": episode_number, "source_run": eid},
            "number": episode_number,
            "logline": episode.get("logline", ""),
            "summary": episode.get("summary", ""),
            "cliffhanger": episode.get("cliffhanger", ""),
            "scenes": episode.get("scenes", []),
        }
        self.store.save(entity)

        patch = CanonPatch(source_run=eid)
        patch.ops = list(episode.get("patch_ops", []))
        if patch.ops:
            patch.apply(self.store)

        state_path = self.store.root / "_state.json"
        state = {"next_episode": episode_number + 1}
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        build_index(self.store)
        return {"status": "committed", "id": eid}

    def run(self, episode_number: int) -> dict:
        context = self._context(episode_number)
        episode = self.writer.write(episode_number=episode_number, canon_context=context)
        verdict = self.critic.review(episode=episode, canon_context=context)

        revisions = 0
        while not verdict.clean and revisions < self.max_revisions:
            episode = self.writer.revise(episode_number=episode_number, canon_context=context,
                                         draft=episode, issues=verdict.issues)
            verdict = self.critic.review(episode=episode, canon_context=context)
            revisions += 1

        if not verdict.clean:
            return self._quarantine(episode_number, episode, verdict.issues)

        episode = self.editor.polish(episode, canon_context=context)
        return self._commit(episode_number, episode)
