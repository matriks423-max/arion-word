from __future__ import annotations

import json
from pathlib import Path

from engine.canon.store import CanonStore

# entity types that are safe to ship to readers (hooks are internal-only)
_PUBLIC_TYPES = {"character", "technique", "world_doc", "episode"}

# v1 world-docs have no public/canon split, so their `data` blob mixes public lore with
# gradual-reveal spoilers. Any key whose name contains one of these tokens is a payoff the
# audience must NOT see yet. Redacted recursively at the export chokepoint.
# (Phase 1 replaces this heuristic with explicit per-entity public layers.)
_SPOILER_TOKENS = ("secret", "hidden", "truth", "suppress", "nobody", "unrevealed",
                   "spoiler", "real_identity", "_reveal", "future_")


def _is_spoiler_key(key: str) -> bool:
    k = key.lower()
    return any(tok in k for tok in _SPOILER_TOKENS)


def _redact(value):
    """Recursively drop spoiler-bearing keys from nested world-doc data."""
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items() if not _is_spoiler_key(k)}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _public_view(entity: dict) -> dict:
    """Strip to audience-safe fields. NEVER includes the `canon` (secret) layer."""
    base = {"id": entity["id"], "type": entity["type"], "name": entity["name"]}
    pub = entity.get("public", {})
    if isinstance(pub, dict):
        base.update(pub)
    if entity["type"] == "technique":
        for k in ("branch", "description", "game_mechanic_concept"):
            if k in entity:
                base[k] = entity[k]
    if entity["type"] == "world_doc":
        base["data"] = _redact(entity.get("data", {}))
    if entity["type"] == "episode":
        for k in ("number", "logline", "summary", "cliffhanger", "scenes"):
            if k in entity:
                base[k] = entity[k]
    return base


def export_site(store: CanonStore, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    buckets: dict[str, list] = {"characters": [], "techniques": [], "world": [], "episodes": []}
    type_to_bucket = {"character": "characters", "technique": "techniques",
                      "world_doc": "world", "episode": "episodes"}

    for ent in store.all_entities():
        if ent["type"] not in _PUBLIC_TYPES:
            continue                                   # hooks excluded
        buckets[type_to_bucket[ent["type"]]].append(_public_view(ent))

    buckets["episodes"].sort(key=lambda e: e.get("number", 0))
    counts = {}
    for bucket, items in buckets.items():
        (out_dir / f"{bucket}.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
        counts[bucket] = len(items)
    return counts
