from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from engine.canon.store import CanonStore, ValidationFailed


class PatchError(Exception):
    pass


@dataclass
class CanonPatch:
    source_run: str
    ops: list[dict] = field(default_factory=list)

    # ---- builders (chainable) --------------------------------------
    def create_entity(self, entity: dict) -> "CanonPatch":
        self.ops.append({"op": "create_entity", "entity": entity})
        return self

    def set_field(self, entity_id: str, path: str, value) -> "CanonPatch":
        self.ops.append({"op": "set_field", "id": entity_id, "path": path, "value": value})
        return self

    def append_to_list(self, entity_id: str, path: str, item) -> "CanonPatch":
        self.ops.append({"op": "append_to_list", "id": entity_id, "path": path, "item": item})
        return self

    def add_relationship(self, from_id: str, rel: str, to_id: str) -> "CanonPatch":
        self.ops.append({"op": "add_relationship", "id": from_id, "rel": rel, "to": to_id})
        return self

    def mark_hook_revealed(self, hook_id: str, episode) -> "CanonPatch":
        self.ops.append({"op": "mark_hook_revealed", "id": hook_id, "episode": episode})
        return self

    def record_death(self, character_id: str, episode) -> "CanonPatch":
        self.ops.append({"op": "record_death", "id": character_id, "episode": episode})
        return self

    # ---- apply (transactional) -------------------------------------
    def apply(self, store: CanonStore) -> None:
        touched = self._touched_ids()
        backup = Path(tempfile.mkdtemp(prefix="canon-bak-"))
        saved: dict[str, Path] = {}
        for eid in touched:
            try:
                src = store.path_for(eid)
                dst = backup / src.name
                shutil.copy2(src, dst)
                saved[eid] = dst
            except KeyError:
                pass  # entity does not exist yet (create op)
        try:
            for op in self.ops:
                self._apply_one(store, op)
        except (PatchError, ValidationFailed, KeyError) as exc:
            self._rollback(store, touched, saved)
            shutil.rmtree(backup, ignore_errors=True)
            raise PatchError(str(exc)) from exc
        shutil.rmtree(backup, ignore_errors=True)

    # ---- internals -------------------------------------------------
    def _touched_ids(self) -> list[str]:
        ids: list[str] = []
        for op in self.ops:
            eid = op.get("id") or op.get("entity", {}).get("id")
            if eid and eid not in ids:
                ids.append(eid)
        return ids

    def _rollback(self, store: CanonStore, touched, saved) -> None:
        for eid in touched:
            if eid in saved:
                store.path_for(eid).write_bytes(saved[eid].read_bytes())
            else:
                # was newly created this patch -> remove if present
                try:
                    store.path_for(eid).unlink()
                except KeyError:
                    pass

    def _bump(self, entity: dict, episode) -> None:
        entity.setdefault("provenance", {})["last_changed_episode"] = episode

    def _set_path(self, entity: dict, path: str, value) -> None:
        keys = path.split(".")
        node = entity
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        node[keys[-1]] = value

    def _get_or_create_list(self, entity: dict, path: str) -> list:
        keys = path.split(".")
        node = entity
        for k in keys[:-1]:
            node = node.setdefault(k, {})
        return node.setdefault(keys[-1], [])

    def _apply_one(self, store: CanonStore, op: dict) -> None:
        kind = op["op"]
        if kind == "create_entity":
            ent = op["entity"]
            if store.exists(ent["id"]):
                raise PatchError(f"create_entity: id already exists: {ent['id']}")
            store.save(ent)
            return

        if kind == "add_relationship" and not store.exists(op["to"]):
            raise PatchError(f"add_relationship: target does not exist: {op['to']}")

        ent = store.load(op["id"])  # raises KeyError if missing -> caught -> rollback

        if kind == "set_field":
            self._set_path(ent, op["path"], op["value"])
            self._bump(ent, self.source_run)
        elif kind == "append_to_list":
            self._get_or_create_list(ent, op["path"]).append(op["item"])
            self._bump(ent, self.source_run)
        elif kind == "add_relationship":
            rels = ent.setdefault("relationships", {}).setdefault(op["rel"], [])
            if op["to"] not in rels:
                rels.append(op["to"])
            self._bump(ent, self.source_run)
        elif kind == "mark_hook_revealed":
            ent["revealed"] = True
            self._bump(ent, op["episode"])
        elif kind == "record_death":
            ent.setdefault("public", {})["status"] = "dead"
            ent["public"]["died_episode"] = op["episode"]
            self._bump(ent, op["episode"])
        else:
            raise PatchError(f"unknown op: {kind}")

        store.save(ent)  # re-validates against schema
