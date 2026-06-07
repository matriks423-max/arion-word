from __future__ import annotations

import json
from collections import defaultdict

from engine.canon.store import CanonStore


def _tags(entity: dict) -> list[str]:
    pub = entity.get("public", {})
    tags = pub.get("tags", []) if isinstance(pub, dict) else []
    return list(tags) if isinstance(tags, list) else []


def build_index(store: CanonStore) -> dict:
    entities = []
    by_type: dict[str, list[str]] = defaultdict(list)
    for ent in store.all_entities():
        entry = {
            "id": ent["id"],
            "type": ent["type"],
            "name": ent["name"],
            "tags": _tags(ent),
            "relationships": ent.get("relationships", {}),
            "last_changed_episode": ent.get("provenance", {}).get("last_changed_episode"),
        }
        entities.append(entry)
        by_type[ent["type"]].append(ent["id"])

    index = {
        "count": len(entities),
        "entities": sorted(entities, key=lambda e: e["id"]),
        "by_type": {k: sorted(v) for k, v in by_type.items()},
    }
    (store.root / "_index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return index
