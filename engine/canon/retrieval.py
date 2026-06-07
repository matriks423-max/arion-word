from __future__ import annotations

import json

from engine.canon.store import CanonStore


class Retriever:
    """Offline retrieval over canon/_index.json. (Embedding retrieval lands in Plan 0b.)"""

    def __init__(self, store: CanonStore):
        self.store = store
        self._index = json.loads((store.root / "_index.json").read_text(encoding="utf-8"))

    def by_type(self, entity_type: str) -> list[str]:
        return list(self._index.get("by_type", {}).get(entity_type, []))

    def by_tag(self, tag: str) -> list[str]:
        return sorted(e["id"] for e in self._index["entities"] if tag in e.get("tags", []))

    def related(self, entity_id: str) -> list[str]:
        for e in self._index["entities"]:
            if e["id"] == entity_id:
                out: list[str] = []
                for targets in e.get("relationships", {}).values():
                    out.extend(targets)
                return sorted(set(out))
        return []
