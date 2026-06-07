from __future__ import annotations

import json
from pathlib import Path

from engine.canon.ids import entity_id, slugify
from engine.canon.store import CanonStore

SOURCE_RUN = "migration-v1"
_PUBLIC_KEYS = {"role", "age", "description", "power_tier", "public_role", "public_description"}

# world_doc source files (everything that is not characters/hooks/techniques)
WORLD_DOC_FILES = [
    "universe.json", "curses.json", "continents.json", "races.json",
    "crafting_arts.json", "caelum_city.json", "chroniclers.json",
    "season1_soil.json", "story_philosophy.json", "visual_style.json",
    "character_visual_state.json",
]


def _prov(ep=1):
    return {"introduced_episode": ep, "last_changed_episode": ep, "source_run": SOURCE_RUN}


def migrate_characters(src: Path, store: CanonStore) -> list[str]:
    data = json.loads(src.read_text(encoding="utf-8"))
    ids: list[str] = []
    for group, members in data.items():
        if group.startswith("_") or not isinstance(members, dict):
            continue
        for name, original in members.items():
            if not isinstance(original, dict):
                continue
            cid = entity_id("character", name)
            public = {k: original[k] for k in _PUBLIC_KEYS if k in original}
            if "role" not in public:
                public["role"] = group
            entity = {
                "id": cid, "type": "character", "name": name,
                "provenance": _prov(), "public": public, "canon": original,
            }
            store.save(entity)
            ids.append(cid)
    return ids


def migrate_hooks(src: Path, store: CanonStore) -> list[str]:
    data = json.loads(src.read_text(encoding="utf-8"))
    ids: list[str] = []
    for hook in data.get("hooks", []):
        raw_id = str(hook.get("id", "")).replace("_", "-")
        hid = raw_id if raw_id.startswith("hook-") else f"hook-{slugify(raw_id)}"
        entity = {
            "id": hid, "type": "hook", "name": hid,
            "provenance": _prov(hook.get("planted_episode", 1)),
            "description": hook.get("description", ""),
            "planted_episode": hook.get("planted_episode", 1),
            "payoff_episode": hook.get("payoff_episode", 999),
            "payoff_description": hook.get("payoff_description", ""),
            "category": hook.get("category", "world_lore"),
            "revealed": bool(hook.get("revealed", False)),
        }
        store.save(entity)
        ids.append(hid)
    return ids


def migrate_techniques(src: Path, store: CanonStore) -> list[str]:
    data = json.loads(src.read_text(encoding="utf-8"))
    ids: list[str] = []
    for tech in data.get("techniques", []):
        name = tech.get("name") or str(tech.get("id"))
        tid = entity_id("technique", name)
        entity = {
            "id": tid, "type": "technique", "name": name,
            "provenance": _prov(),
            "branch": tech.get("branch", "Unknown"),
            "tier": tech.get("tier", 1),
            "description": tech.get("description", ""),
            "cost": tech.get("cost", ""),
            "game_mechanic_concept": tech.get("game_mechanic_concept", ""),
            "canon": tech,
        }
        store.save(entity)
        ids.append(tid)
    return ids


def migrate_world_doc(src: Path, store: CanonStore) -> str:
    data = json.loads(src.read_text(encoding="utf-8"))
    base = src.stem
    name = data.get("world_name") or base.replace("_", " ").title()
    wid = entity_id("world_doc", base)
    entity = {
        "id": wid, "type": "world_doc", "name": name,
        "provenance": _prov(), "data": data,
    }
    store.save(entity)
    return wid


def migrate_all(src_dir: Path, store: CanonStore) -> dict:
    src_dir = Path(src_dir)
    report = {"characters": [], "hooks": [], "techniques": [], "world_docs": []}
    if (src_dir / "characters.json").exists():
        report["characters"] = migrate_characters(src_dir / "characters.json", store)
    if (src_dir / "future_hooks.json").exists():
        report["hooks"] = migrate_hooks(src_dir / "future_hooks.json", store)
    if (src_dir / "techniques.json").exists():
        report["techniques"] = migrate_techniques(src_dir / "techniques.json", store)
    for fname in WORLD_DOC_FILES:
        if (src_dir / fname).exists():
            report["world_docs"].append(migrate_world_doc(src_dir / fname, store))
    # preserve episode counter
    counter = src_dir / ".episode_counter"
    if counter.exists():
        (store.root / "_state.json").write_text(
            json.dumps({"next_episode": int(counter.read_text().strip() or "1")}, indent=2),
            encoding="utf-8",
        )
    return report
