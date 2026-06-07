# Arion World — Phase 0a: Canon Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the offline, LLM-free canon data layer — schema-validated file-per-entity store, transactional patch engine, retrieval index, and a lossless migration of the v1 story bible into it.

**Architecture:** Canon-as-Code. Every world entity is one YAML file under `canon/<type>/<id>.yaml` with a strict envelope (`id`, `type`, `name`, `provenance`) and a permissive type-specific payload. All writes go through validated `CanonPatch` operations (never full-file rewrites). A generated `canon/_index.json` enables retrieval without loading every file. This plan adds NO model calls — it is fully testable with `pytest` offline.

**Tech Stack:** Python 3.11 · `pyyaml` · `jsonschema` · `pytest` · GitHub Actions. Work on branch `v2-canon-rebuild` in `~/Projects/arion-world`.

**Spec:** `docs/superpowers/specs/2026-06-07-arion-world-rebuild-design.md` (§3 canon store, §4 patches, §9 testing, §10 migration).

**Scope note:** This is Plan 0a of Phase 0. Plan 0b (generation pipeline: LLM clients, embeddings retrieval, continuity critic, episode pipeline) and Plan 0c (Astro `/read` renderer) depend on this and get their own plans.

---

## File Structure

```
pyproject.toml                         # package + deps + pytest config
engine/
  __init__.py
  __main__.py                          # CLI: migrate | validate | index
  canon/
    __init__.py
    ids.py                             # slugify + id helpers
    store.py                           # load/save/list/validate entities
    patch.py                           # CanonPatch + ops + transactional apply
    index.py                           # build canon/_index.json
    retrieval.py                       # query the index (offline)
  migrate.py                           # v1 story_bible/*.json -> canon/*.yaml
canon/
  _schema/
    base.schema.json
    character.schema.json
    hook.schema.json
    technique.schema.json
    world_doc.schema.json
tests/
  conftest.py
  test_ids.py
  test_store.py
  test_patch.py
  test_index.py
  test_retrieval.py
  test_migrate.py
.github/workflows/ci.yml               # pytest + canon validate on push
```

Entity envelope (every canon file):

```yaml
id: char-kairo-voss
type: character
name: Kairo Voss
provenance:
  introduced_episode: 1
  last_changed_episode: 1
  source_run: migration-v1
# ...type-specific payload below (public/canon for characters, domain fields for hooks/techniques)
```

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `engine/__init__.py`, `engine/canon/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "arion-engine"
version = "0.0.1"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0", "jsonschema>=4.21"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 2: Create empty package files**

```bash
mkdir -p engine/canon tests canon/_schema
printf '' > engine/__init__.py
printf '' > engine/canon/__init__.py
```

- [ ] **Step 3: Write `tests/conftest.py`** (shared fixtures)

```python
import json
from pathlib import Path
import pytest


@pytest.fixture
def tmp_canon(tmp_path: Path) -> Path:
    """A throwaway canon root with the real schemas copied in."""
    root = tmp_path / "canon"
    (root / "_schema").mkdir(parents=True)
    repo_schema = Path(__file__).parent.parent / "canon" / "_schema"
    for f in repo_schema.glob("*.json"):
        (root / "_schema" / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    return root
```

- [ ] **Step 4: Write `tests/test_smoke.py`**

```python
def test_python_and_imports():
    import engine
    import engine.canon
    assert True
```

- [ ] **Step 5: Install deps and run the smoke test**

Run:
```bash
cd /c/Users/Toms/Projects/arion-world
python -m pip install -e ".[dev]"
python -m pytest tests/test_smoke.py -v
```
Expected: PASS (1 passed).

- [ ] **Step 6: Add a `.gitignore` entry for build/output**

Append to `.gitignore` (create if missing):
```
__pycache__/
*.egg-info/
.pytest_cache/
output/
pending/
```

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml engine tests .gitignore
git commit -m "chore: scaffold arion-engine package + pytest"
```

---

## Task 2: Canon JSON schemas

**Files:**
- Create: `canon/_schema/base.schema.json`
- Create: `canon/_schema/character.schema.json`
- Create: `canon/_schema/hook.schema.json`
- Create: `canon/_schema/technique.schema.json`
- Create: `canon/_schema/world_doc.schema.json`

- [ ] **Step 1: Write `base.schema.json`** (the strict envelope every entity shares)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "base.schema.json",
  "type": "object",
  "required": ["id", "type", "name", "provenance"],
  "properties": {
    "id": { "type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$" },
    "type": { "type": "string", "enum": ["character", "hook", "technique", "world_doc"] },
    "name": { "type": "string", "minLength": 1 },
    "provenance": {
      "type": "object",
      "required": ["introduced_episode", "last_changed_episode", "source_run"],
      "properties": {
        "introduced_episode": { "type": ["integer", "string"] },
        "last_changed_episode": { "type": ["integer", "string"] },
        "source_run": { "type": "string" }
      }
    },
    "relationships": { "type": "object" }
  }
}
```

- [ ] **Step 2: Write `character.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "character.schema.json",
  "allOf": [{ "$ref": "base.schema.json" }],
  "properties": {
    "type": { "const": "character" },
    "public": { "type": "object" },
    "canon": { "type": "object" }
  },
  "required": ["public"]
}
```

- [ ] **Step 3: Write `hook.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "hook.schema.json",
  "allOf": [{ "$ref": "base.schema.json" }],
  "properties": {
    "type": { "const": "hook" },
    "description": { "type": "string" },
    "planted_episode": { "type": ["integer", "string"] },
    "payoff_episode": { "type": ["integer", "string"] },
    "payoff_description": { "type": "string" },
    "category": { "type": "string" },
    "revealed": { "type": "boolean" }
  },
  "required": ["planted_episode", "payoff_episode", "category", "revealed"]
}
```

- [ ] **Step 4: Write `technique.schema.json`**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "technique.schema.json",
  "allOf": [{ "$ref": "base.schema.json" }],
  "properties": {
    "type": { "const": "technique" },
    "branch": { "type": "string" },
    "tier": { "type": ["integer", "string"] },
    "description": { "type": "string" },
    "cost": { "type": "string" },
    "game_mechanic_concept": { "type": "string" }
  },
  "required": ["branch", "description"]
}
```

- [ ] **Step 5: Write `world_doc.schema.json`** (lossless catch-all for bulk lore)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "world_doc.schema.json",
  "allOf": [{ "$ref": "base.schema.json" }],
  "properties": {
    "type": { "const": "world_doc" },
    "data": { "type": "object" }
  },
  "required": ["data"]
}
```

- [ ] **Step 6: Commit**

```bash
git add canon/_schema
git commit -m "feat(canon): entity JSON schemas (envelope + 4 types)"
```

---

## Task 3: ID helpers

**Files:**
- Create: `engine/canon/ids.py`
- Test: `tests/test_ids.py`

- [ ] **Step 1: Write the failing test** (`tests/test_ids.py`)

```python
from engine.canon.ids import slugify, entity_id


def test_slugify_basic():
    assert slugify("Kairo Voss") == "kairo-voss"


def test_slugify_strips_punctuation_and_accents():
    assert slugify("Caelum City — Inner District!") == "caelum-city-inner-district"


def test_entity_id_prefixes_type():
    assert entity_id("character", "Kairo Voss") == "char-kairo-voss"
    assert entity_id("world_doc", "Curses") == "world-curses"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ids.py -v`
Expected: FAIL with `ModuleNotFoundError: engine.canon.ids`.

- [ ] **Step 3: Write `engine/canon/ids.py`**

```python
import re
import unicodedata

_TYPE_PREFIX = {
    "character": "char",
    "hook": "hook",
    "technique": "tech",
    "world_doc": "world",
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def entity_id(entity_type: str, name: str) -> str:
    prefix = _TYPE_PREFIX[entity_type]
    return f"{prefix}-{slugify(name)}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ids.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/canon/ids.py tests/test_ids.py
git commit -m "feat(canon): slugify + typed entity ids"
```

---

## Task 4: Entity store (load / save / validate / list)

**Files:**
- Create: `engine/canon/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test** (`tests/test_store.py`)

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_store.py -v`
Expected: FAIL with `ModuleNotFoundError: engine.canon.store`.

- [ ] **Step 3: Write `engine/canon/store.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, RefResolver

_TYPE_DIR = {
    "character": "characters",
    "hook": "hooks",
    "technique": "techniques",
    "world_doc": "world",
}


class ValidationFailed(Exception):
    pass


class CanonStore:
    """File-per-entity canon store rooted at a canon/ directory."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.schema_dir = self.root / "_schema"
        self._validators: dict[str, Draft202012Validator] = {}

    # ---- validation -------------------------------------------------
    def _validator(self, entity_type: str) -> Draft202012Validator:
        if entity_type not in self._validators:
            schema_path = self.schema_dir / f"{entity_type}.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            resolver = RefResolver(base_uri=schema_path.resolve().as_uri(), referrer=schema)
            self._validators[entity_type] = Draft202012Validator(schema, resolver=resolver)
        return self._validators[entity_type]

    def validate(self, entity: dict) -> None:
        etype = entity.get("type")
        if etype not in _TYPE_DIR:
            raise ValidationFailed(f"unknown entity type: {etype!r}")
        errors = sorted(self._validator(etype).iter_errors(entity), key=lambda e: e.path)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_store.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/canon/store.py tests/test_store.py
git commit -m "feat(canon): schema-validated entity store"
```

---

## Task 5: Patch engine (transactional, referential-integrity-checked)

**Files:**
- Create: `engine/canon/patch.py`
- Test: `tests/test_patch.py`

- [ ] **Step 1: Write the failing test** (`tests/test_patch.py`)

```python
import pytest
from engine.canon.store import CanonStore
from engine.canon.patch import CanonPatch, PatchError


def _char(cid, name, ep=1):
    return {
        "id": cid, "type": "character", "name": name,
        "provenance": {"introduced_episode": ep, "last_changed_episode": ep, "source_run": "test"},
        "public": {"role": "supporting"},
    }


def _hook(hid):
    return {
        "id": hid, "type": "hook", "name": hid, "description": "x",
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "test"},
        "planted_episode": 1, "payoff_episode": 88, "category": "world_lore", "revealed": False,
    }


def test_create_entity(tmp_canon):
    store = CanonStore(tmp_canon)
    CanonPatch(source_run="ep002").create_entity(_char("char-ren", "Ren")).apply(store)
    assert store.load("char-ren")["name"] == "Ren"


def test_set_field_and_append(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren"))
    (CanonPatch(source_run="ep002")
        .set_field("char-ren", "public.role", "mentor")
        .append_to_list("char-ren", "public.titles", "Clockkeeper")
        .apply(store))
    ren = store.load("char-ren")
    assert ren["public"]["role"] == "mentor"
    assert ren["public"]["titles"] == ["Clockkeeper"]
    assert ren["provenance"]["last_changed_episode"] == "ep002"


def test_add_relationship_requires_target(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren"))
    with pytest.raises(PatchError):
        CanonPatch(source_run="ep002").add_relationship("char-ren", "mentor_of", "char-ghost").apply(store)


def test_mark_hook_revealed(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_hook("hook-001"))
    CanonPatch(source_run="ep088").mark_hook_revealed("hook-001", 88).apply(store)
    assert store.load("hook-001")["revealed"] is True


def test_apply_is_atomic_on_failure(tmp_canon):
    """A patch that fails partway must leave the store untouched."""
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren"))
    patch = (CanonPatch(source_run="ep002")
             .set_field("char-ren", "public.role", "traitor")
             .create_entity(_char("char-ren", "Ren")))   # duplicate id -> fails
    with pytest.raises(PatchError):
        patch.apply(store)
    assert store.load("char-ren")["public"]["role"] == "supporting"   # rolled back
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_patch.py -v`
Expected: FAIL with `ModuleNotFoundError: engine.canon.patch`.

- [ ] **Step 3: Write `engine/canon/patch.py`**

```python
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
        touched = self._touched_ids(store)
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
    def _touched_ids(self, store: CanonStore) -> list[str]:
        ids: list[str] = []
        for op in self.ops:
            eid = op.get("id") or op.get("entity", {}).get("id")
            if eid and eid not in ids:
                ids.append(eid)
        return ids

    def _rollback(self, store, touched, saved):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_patch.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/canon/patch.py tests/test_patch.py
git commit -m "feat(canon): transactional patch engine with rollback + referential checks"
```

---

## Task 6: Index builder

**Files:**
- Create: `engine/canon/index.py`
- Test: `tests/test_index.py`

- [ ] **Step 1: Write the failing test** (`tests/test_index.py`)

```python
import json
from engine.canon.store import CanonStore
from engine.canon.index import build_index


def _char(cid, name):
    return {
        "id": cid, "type": "character", "name": name,
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "t"},
        "public": {"role": "supporting", "tags": ["caelum"]},
    }


def test_build_index_writes_manifest(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren"))
    store.save(_char("char-lyra", "Lyra"))
    index = build_index(store)
    assert {e["id"] for e in index["entities"]} == {"char-ren", "char-lyra"}
    assert index["by_type"]["character"] == ["char-lyra", "char-ren"]
    # persisted to disk
    written = json.loads((tmp_canon / "_index.json").read_text(encoding="utf-8"))
    assert written["count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_index.py -v`
Expected: FAIL with `ModuleNotFoundError: engine.canon.index`.

- [ ] **Step 3: Write `engine/canon/index.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_index.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/canon/index.py tests/test_index.py
git commit -m "feat(canon): index builder (_index.json manifest)"
```

---

## Task 7: Offline retrieval

**Files:**
- Create: `engine/canon/retrieval.py`
- Test: `tests/test_retrieval.py`

- [ ] **Step 1: Write the failing test** (`tests/test_retrieval.py`)

```python
from engine.canon.store import CanonStore
from engine.canon.index import build_index
from engine.canon.retrieval import Retriever


def _char(cid, name, tags=None, rels=None):
    e = {
        "id": cid, "type": "character", "name": name,
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "t"},
        "public": {"role": "supporting", "tags": tags or []},
    }
    if rels:
        e["relationships"] = rels
    return e


def test_by_type_and_by_tag(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-ren", "Ren", tags=["caelum"]))
    store.save(_char("char-lyra", "Lyra", tags=["echo"]))
    build_index(store)
    r = Retriever(store)
    assert r.by_type("character") == ["char-lyra", "char-ren"]
    assert r.by_tag("caelum") == ["char-ren"]


def test_related(tmp_canon):
    store = CanonStore(tmp_canon)
    store.save(_char("char-lyra", "Lyra"))
    store.save(_char("char-ren", "Ren", rels={"knows": ["char-lyra"]}))
    build_index(store)
    r = Retriever(store)
    assert r.related("char-ren") == ["char-lyra"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_retrieval.py -v`
Expected: FAIL with `ModuleNotFoundError: engine.canon.retrieval`.

- [ ] **Step 3: Write `engine/canon/retrieval.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_retrieval.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/canon/retrieval.py tests/test_retrieval.py
git commit -m "feat(canon): offline index retrieval (type/tag/related)"
```

---

## Task 8: v1 bible migration

**Files:**
- Create: `engine/migrate.py`
- Test: `tests/test_migrate.py`

The v1 files live in `story_bible/`. Shapes observed: `characters.json` has name-keyed groups (`main_cast`, etc.) of dicts; `future_hooks.json` has a `hooks` array; `techniques.json` has a `techniques` array; everything else (`universe.json`, `curses.json`, `continents.json`, `races.json`, `crafting_arts.json`, `caelum_city.json`, `chroniclers.json`, `season1_soil.json`, `story_philosophy.json`, `visual_style.json`) is a deep nested doc → one `world_doc` each (lossless). Keys beginning with `_` (e.g. `_copyright`) are dropped from `name`/payload roots but preserved inside `data` for world_docs.

- [ ] **Step 1: Write the failing test** (`tests/test_migrate.py`)

```python
import json
from pathlib import Path
from engine.canon.store import CanonStore
from engine.migrate import migrate_characters, migrate_hooks, migrate_techniques, migrate_world_doc


def test_migrate_characters(tmp_canon, tmp_path):
    src = tmp_path / "characters.json"
    src.write_text(json.dumps({
        "_philosophy": "ignore me",
        "main_cast": {
            "Kairo Voss": {"role": "protagonist", "age": 19, "description": "street Resonant",
                            "secret_flag": "is Shattered"}
        }
    }), encoding="utf-8")
    store = CanonStore(tmp_canon)
    ids = migrate_characters(src, store)
    assert ids == ["char-kairo-voss"]
    k = store.load("char-kairo-voss")
    assert k["name"] == "Kairo Voss"
    assert k["public"]["role"] == "protagonist"
    assert k["canon"]["secret_flag"] == "is Shattered"   # full original kept in canon layer


def test_migrate_hooks(tmp_canon, tmp_path):
    src = tmp_path / "future_hooks.json"
    src.write_text(json.dumps({"hooks": [
        {"id": "hook_001", "description": "clock 3:12", "planted_episode": 1,
         "payoff_episode": 88, "payoff_description": "Ren is Shattered",
         "revealed": False, "category": "character_secret"}
    ]}), encoding="utf-8")
    store = CanonStore(tmp_canon)
    ids = migrate_hooks(src, store)
    assert ids == ["hook-001"]
    assert store.load("hook-001")["payoff_episode"] == 88


def test_migrate_world_doc(tmp_canon, tmp_path):
    src = tmp_path / "curses.json"
    src.write_text(json.dumps({"_copyright": "x", "mechanics": {"what_a_curse_is": "..."}}), encoding="utf-8")
    store = CanonStore(tmp_canon)
    wid = migrate_world_doc(src, store)
    assert wid == "world-curses"
    doc = store.load("world-curses")
    assert doc["type"] == "world_doc"
    assert "mechanics" in doc["data"]
    assert doc["data"]["_copyright"] == "x"   # lossless: nothing dropped from data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migrate.py -v`
Expected: FAIL with `ModuleNotFoundError: engine.migrate`.

- [ ] **Step 3: Write `engine/migrate.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_migrate.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/migrate.py tests/test_migrate.py
git commit -m "feat: lossless v1 story-bible migration (characters/hooks/techniques/world_docs)"
```

---

## Task 9: CLI (`migrate` / `validate` / `index`)

**Files:**
- Create: `engine/__main__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test** (`tests/test_cli.py`)

```python
import subprocess
import sys
from pathlib import Path


def test_validate_cli_passes_on_clean_canon(tmp_canon, tmp_path):
    # seed one valid entity by hand
    (tmp_canon / "characters").mkdir()
    (tmp_canon / "characters" / "char-ren.yaml").write_text(
        "id: char-ren\ntype: character\nname: Ren\n"
        "provenance: {introduced_episode: 1, last_changed_episode: 1, source_run: t}\n"
        "public: {role: mentor}\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "engine", "validate", "--canon", str(tmp_canon)],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_validate_cli_fails_on_bad_entity(tmp_canon):
    (tmp_canon / "characters").mkdir()
    (tmp_canon / "characters" / "char-bad.yaml").write_text(
        "id: char-bad\ntype: character\nname: Bad\n"
        "provenance: {introduced_episode: 1, last_changed_episode: 1, source_run: t}\n",  # no public
        encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "engine", "validate", "--canon", str(tmp_canon)],
        capture_output=True, text=True, cwd=Path(__file__).parent.parent)
    assert result.returncode == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL (no `engine/__main__.py`, returncode != expected).

- [ ] **Step 3: Write `engine/__main__.py`**

```python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from engine.canon.store import CanonStore, ValidationFailed
from engine.canon.index import build_index
from engine.migrate import migrate_all

DEFAULT_CANON = Path(__file__).parent.parent / "canon"


def cmd_validate(args) -> int:
    store = CanonStore(Path(args.canon))
    failures = 0
    for eid in store.list_ids():
        try:
            store.validate(store.load(eid))
        except ValidationFailed as exc:
            print(f"INVALID {eid}: {exc}", file=sys.stderr)
            failures += 1
    if failures:
        print(f"{failures} invalid ent/ies", file=sys.stderr)
        return 1
    print(f"OK — {len(store.list_ids())} entities valid")
    return 0


def cmd_index(args) -> int:
    store = CanonStore(Path(args.canon))
    index = build_index(store)
    print(f"index built: {index['count']} entities -> {store.root / '_index.json'}")
    return 0


def cmd_migrate(args) -> int:
    store = CanonStore(Path(args.canon))
    report = migrate_all(Path(args.src), store)
    for k, v in report.items():
        print(f"{k}: {len(v)}")
    build_index(store)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="engine")
    parser.add_argument("--canon", default=str(DEFAULT_CANON))
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate")
    sub.add_parser("index")
    m = sub.add_parser("migrate")
    m.add_argument("--src", default="story_bible")

    args = parser.parse_args(argv)
    return {"validate": cmd_validate, "index": cmd_index, "migrate": cmd_migrate}[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add engine/__main__.py tests/test_cli.py
git commit -m "feat(cli): engine migrate/validate/index commands"
```

---

## Task 10: Run real migration + full validation (integration, the 0a exit criterion)

**Files:**
- Create: `canon/characters/*.yaml`, `canon/hooks/*.yaml`, `canon/techniques/*.yaml`, `canon/world/*.yaml`, `canon/_index.json`, `canon/_state.json` (all generated)

- [ ] **Step 1: Run the migration against the real v1 bible**

Run:
```bash
cd /c/Users/Toms/Projects/arion-world
python -m engine --canon canon migrate --src story_bible
```
Expected stdout (counts > 0):
```
characters: <N>
hooks: <N>
techniques: <N>
world_docs: <N>
index built ...
```

- [ ] **Step 2: Validate the entire generated canon**

Run:
```bash
python -m engine --canon canon validate
```
Expected: `OK — <N> entities valid`, returncode 0.

If any entity is INVALID: do NOT patch the schema to force a pass. Inspect the offending v1 record, fix the mapper in `engine/migrate.py` (root cause), re-run migrate + validate. (Prime directive: fix, don't work around.)

- [ ] **Step 3: Run the whole test suite**

Run: `python -m pytest -v`
Expected: ALL pass.

- [ ] **Step 4: Eyeball one migrated character for fidelity**

Run: `cat canon/characters/char-kairo-voss.yaml`
Expected: envelope + `public` (role/description) + `canon` (full original incl. visual_profile). Confirm nothing was lost vs `story_bible/characters.json`.

- [ ] **Step 5: Commit the generated canon**

```bash
git add canon/
git commit -m "feat(canon): migrate v1 story bible into validated canon-as-code"
```

---

## Task 11: CI — validate + test on every push

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: CI
on:
  push:
    branches: ["**"]
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: python -m pip install -e ".[dev]"
      - run: python -m pytest -v
      - run: python -m engine --canon canon validate
```

- [ ] **Step 2: Commit and push the branch**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: pytest + canon validation on push"
git push -u origin v2-canon-rebuild
```

- [ ] **Step 3: Confirm CI is green**

Run: `gh run watch` (or `gh run list --branch v2-canon-rebuild`)
Expected: the `CI` workflow completes successfully.

---

## Self-Review (completed by plan author)

**Spec coverage:** §3 canon store → Tasks 2,4. §4 patches → Task 5. Index/retrieval → Tasks 6,7. §9 testing → every task is TDD + Task 11 CI. §10 migration → Tasks 8,10. (Embeddings retrieval §3, continuity critic §5, episode pipeline §5, renderers §7 are explicitly Plan 0b/0c — out of scope here.)

**Placeholder scan:** none — every code step contains complete code; every run step has an exact command + expected result. Task 10 deliberately leaves entity counts as `<N>` because they depend on live v1 data, not on author choice.

**Type consistency:** `CanonStore` API (`save/load/exists/list_ids/all_entities/path_for/validate/root`) is consistent across store, patch, index, retrieval, migrate, CLI. `CanonPatch` builder names match their tests. `entity_id`/`slugify` signatures match across ids, migrate. `build_index` returns the same dict shape that `Retriever` reads.

**Exit criterion (Phase 0a):** `python -m engine migrate` then `python -m engine validate` → `OK`, full `pytest` green, CI green, v1 bible fully represented as validated canon-as-code with a working patch engine + index. Ready for Plan 0b (generation pipeline).
```
