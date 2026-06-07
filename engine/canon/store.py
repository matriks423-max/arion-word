from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

_TYPE_DIR = {
    "character": "characters",
    "hook": "hooks",
    "technique": "techniques",
    "world_doc": "world",
    "episode": "episodes",
}


class ValidationFailed(Exception):
    pass


class CanonStore:
    """File-per-entity canon store rooted at a canon/ directory."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.schema_dir = self.root / "_schema"
        self._validators: dict[str, Draft202012Validator] = {}
        self._registry: Registry | None = None

    # ---- validation -------------------------------------------------
    def _registry_(self) -> Registry:
        if self._registry is None:
            resources = []
            for f in sorted(self.schema_dir.glob("*.json")):
                contents = json.loads(f.read_text(encoding="utf-8"))
                res = Resource.from_contents(contents, default_specification=DRAFT202012)
                resources.append((f.name, res))
            self._registry = Registry().with_resources(resources)
        return self._registry

    def _validator(self, entity_type: str) -> Draft202012Validator:
        if entity_type not in self._validators:
            schema_path = self.schema_dir / f"{entity_type}.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            self._validators[entity_type] = Draft202012Validator(
                schema, registry=self._registry_()
            )
        return self._validators[entity_type]

    def validate(self, entity: dict) -> None:
        etype = entity.get("type")
        if etype not in _TYPE_DIR:
            raise ValidationFailed(f"unknown entity type: {etype!r}")
        errors = sorted(self._validator(etype).iter_errors(entity), key=lambda e: str(list(e.path)))
        if errors:
            msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors)
            raise ValidationFailed(f"{entity.get('id')}: {msgs}")

    # ---- paths ------------------------------------------------------
    def _dir_for(self, entity_type: str) -> Path:
        return self.root / _TYPE_DIR[entity_type]

    def path_for(self, entity_id: str) -> Path:
        for etype, sub in _TYPE_DIR.items():
            p = self.root / sub / f"{entity_id}.yaml"
            if p.exists():
                return p
        raise KeyError(entity_id)

    # ---- CRUD -------------------------------------------------------
    def save(self, entity: dict) -> Path:
        self.validate(entity)
        d = self._dir_for(entity["type"])
        d.mkdir(parents=True, exist_ok=True)
        path = d / f"{entity['id']}.yaml"
        path.write_text(
            yaml.safe_dump(entity, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return path

    def load(self, entity_id: str) -> dict:
        return yaml.safe_load(self.path_for(entity_id).read_text(encoding="utf-8"))

    def exists(self, entity_id: str) -> bool:
        try:
            self.path_for(entity_id)
            return True
        except KeyError:
            return False

    def list_ids(self, entity_type: str | None = None) -> list[str]:
        subs = [_TYPE_DIR[entity_type]] if entity_type else list(_TYPE_DIR.values())
        ids: list[str] = []
        for sub in subs:
            d = self.root / sub
            if d.exists():
                ids.extend(sorted(p.stem for p in d.glob("*.yaml")))
        return sorted(ids)

    def all_entities(self):
        for eid in self.list_ids():
            yield self.load(eid)
