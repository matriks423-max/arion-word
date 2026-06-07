# Arion World — Phase 0c: Reading Site — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Render the canon into two reader-facing surfaces — `/read` (serialized fiction) and `/world` (living encyclopedia) — from a spoiler-safe data export, reusing and restyling the v1 Astro site.

**Architecture:** A Python `render/export.py` reads the canon store and emits **public-layer-only** JSON into `website/src/data/`. The Astro site consumes that JSON at build time. The export is the single chokepoint that enforces spoiler safety: it copies the `public` layer and episode public fields, and NEVER the `canon` (secret) layer or `hook` entities. `engine render` runs the export; `npm run build` produces the static site.

**Design Read (taste skill):** editorial serialized-fiction + encyclopedia, literary language, **VARIANCE 6 / MOTION 3 / DENSITY 3**, dark-mode default (off-black, not pure black), one locked cool accent, serif body justified (genuine long-form fiction), zero em-dashes.

**Tech Stack:** Python 3.11 (export) · Astro 4 + Tailwind (reused from v1 `website/`) · pytest.

**Spec:** `docs/superpowers/specs/2026-06-07-arion-world-rebuild-design.md` (§7 renderers, §3 public/canon layers).

**Depends on:** Plan 0a (canon store) and the episode entity type from Plan 0b. Does NOT need live LLM keys — it renders the 47 already-migrated entities today; episodes appear once generated.

---

## File Structure

```
render/
  __init__.py
  export.py                  # canon -> website/src/data/*.json (public layer only)
website/
  src/data/                  # generated: characters.json, techniques.json, world.json, episodes.json
  src/layouts/Reader.astro   # dark editorial base layout
  src/pages/index.astro      # landing: enter /read or /world
  src/pages/read/index.astro
  src/pages/read/[id].astro  # episode reader
  src/pages/world/index.astro
  src/pages/world/[id].astro # entity page
  src/styles/reader.css       # tokens: dark, off-black, accent, serif body
engine/__main__.py           # add `render` subcommand
tests/test_export.py
```

---

## Task 1: Spoiler-safe content export

**Files:**
- Create: `render/__init__.py`, `render/export.py`
- Test: `tests/test_export.py`

- [ ] **Step 1: Write the failing test** (`tests/test_export.py`)

```python
import json
from engine.canon.store import CanonStore
from render.export import export_site


def _char(cid, name):
    return {
        "id": cid, "type": "character", "name": name,
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "t"},
        "public": {"role": "protagonist", "description": "a street resonant"},
        "canon": {"secret": "is actually Shattered"},
    }


def _hook(hid):
    return {
        "id": hid, "type": "hook", "name": hid, "description": "secret clock detail",
        "provenance": {"introduced_episode": 1, "last_changed_episode": 1, "source_run": "t"},
        "planted_episode": 1, "payoff_episode": 88, "category": "character_secret", "revealed": False,
    }


def test_export_emits_public_only(tmp_canon, tmp_path):
    store = CanonStore(tmp_canon)
    store.save(_char("char-kairo", "Kairo"))
    store.save(_hook("hook-001"))
    out = tmp_path / "data"
    export_site(store, out)

    chars = json.loads((out / "characters.json").read_text(encoding="utf-8"))
    assert chars[0]["name"] == "Kairo"
    assert chars[0]["role"] == "protagonist"
    blob = (out / "characters.json").read_text(encoding="utf-8")
    assert "Shattered" not in blob          # canon-layer secret never leaks
    assert "secret" not in blob


def test_export_excludes_hooks_entirely(tmp_canon, tmp_path):
    store = CanonStore(tmp_canon)
    store.save(_hook("hook-001"))
    out = tmp_path / "data"
    export_site(store, out)
    assert not (out / "hooks.json").exists()     # hooks are internal, never shipped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_export.py -v`
Expected: FAIL — `ModuleNotFoundError: render.export`.

- [ ] **Step 3: Write `render/__init__.py` (empty) and `render/export.py`**

```python
from __future__ import annotations

import json
from pathlib import Path

from engine.canon.store import CanonStore

# entity types that are safe to ship to readers (hooks are internal-only)
_PUBLIC_TYPES = {"character", "technique", "world_doc", "episode"}


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
        base["data"] = entity.get("data", {})
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_export.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add render/__init__.py render/export.py tests/test_export.py
git commit -m "feat(render): spoiler-safe canon->site export (public layer only)"
```

---

## Task 2: `engine render` command + run export

**Files:**
- Modify: `engine/__main__.py`
- Generated: `website/src/data/*.json`

- [ ] **Step 1: Add the `render` command to `engine/__main__.py`**

Add the function:
```python
def cmd_render(args) -> int:
    from render.export import export_site
    store = CanonStore(Path(args.canon))
    counts = export_site(store, Path(args.out))
    for bucket, n in counts.items():
        print(f"{bucket}: {n}")
    return 0
```
Register it in `main()`:
```python
    r = sub.add_parser("render", parents=[parent])
    r.add_argument("--out", default="website/src/data")
```
and add `"render": cmd_render` to the dispatch dict.

- [ ] **Step 2: Run the export against the real canon**

Run: `python -m engine render --canon canon --out website/src/data`
Expected: `characters: 5`, `techniques: 13`, `world: 11`, `episodes: 0` (no episodes until a live run).

- [ ] **Step 3: Verify no secrets leaked**

Run: `grep -ri "canon\|secret" website/src/data/characters.json | head` (expect: no `canon`-layer content; only public fields).

- [ ] **Step 4: Commit the command + generated data**

```bash
git add engine/__main__.py website/src/data
git commit -m "feat(cli): engine render command + initial site data export"
```

---

## Task 3: Astro base layout + tokens (dark editorial)

**Files:**
- Modify/Create: `website/src/layouts/Reader.astro`, `website/src/styles/reader.css`
- Reuse: existing `website/` Astro+Tailwind scaffold from v1

- [ ] **Step 1: Confirm the v1 Astro app builds**

Run: `cd website && npm install && npm run build` — confirm a clean baseline before changes. If v1 pages reference old `public/content/*.json`, they will be replaced in Tasks 4-5.

- [ ] **Step 2: Write `website/src/styles/reader.css`** (locked tokens, dark, off-black, one accent, serif body)

```css
:root {
  --bg: #0f1115;          /* off-black, not pure */
  --bg-elev: #161922;
  --text: #e8e6e0;
  --text-dim: #9aa0ab;
  --accent: #6aa9ff;      /* single locked cool accent */
  --rule: #232733;
  --serif: "Iowan Old Style", "Georgia", "Times New Roman", serif;
  --sans: "Inter", system-ui, sans-serif;
}
html { background: var(--bg); color: var(--text); }
body { font-family: var(--serif); line-height: 1.7; }
.reading { max-width: 68ch; margin: 0 auto; padding: 4rem 1.25rem; }
.reading p { margin: 0 0 1.4rem; font-size: 1.18rem; }
a { color: var(--accent); text-decoration: none; }
.label { font-family: var(--sans); text-transform: uppercase; letter-spacing: .14em;
         font-size: .72rem; color: var(--text-dim); }
@media (prefers-reduced-motion: no-preference) {
  .fade-in { animation: fade .5s ease both; }
  @keyframes fade { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; } }
}
```

- [ ] **Step 3: Write `website/src/layouts/Reader.astro`**

```astro
---
const { title = "Arion World", label } = Astro.props;
import "../styles/reader.css";
---
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
  </head>
  <body>
    <nav class="reading" style="padding-top:1.5rem;padding-bottom:0;display:flex;gap:1.5rem;">
      <a href="/">Arion World</a>
      <a href="/read">Read</a>
      <a href="/world">World</a>
    </nav>
    <main class="reading fade-in">
      {label && <p class="label">{label}</p>}
      <slot />
    </main>
  </body>
</html>
```

- [ ] **Step 4: Build to confirm no errors**

Run: `cd website && npm run build`
Expected: build succeeds.

- [ ] **Step 5: Commit**

```bash
git add website/src/layouts/Reader.astro website/src/styles/reader.css
git commit -m "feat(site): dark editorial reader layout + locked tokens"
```

---

## Task 4: `/read` — fiction reader

**Files:**
- Create: `website/src/pages/read/index.astro`, `website/src/pages/read/[id].astro`

- [ ] **Step 1: Write `website/src/pages/read/index.astro`** (episode list + empty state)

```astro
---
import Reader from "../../layouts/Reader.astro";
import episodes from "../../data/episodes.json";
---
<Reader title="Arion World — Read" label="Episodes">
  {episodes.length === 0 ? (
    <p style="color:var(--text-dim)">No episodes yet. The first will appear once the engine publishes it.</p>
  ) : (
    <ul style="list-style:none;padding:0">
      {episodes.map((ep) => (
        <li style="margin:0 0 1.5rem;border-top:1px solid var(--rule);padding-top:1rem">
          <a href={`/read/${ep.id}`} style="font-size:1.4rem">{ep.number}. {ep.name}</a>
          <p style="color:var(--text-dim);margin:.3rem 0 0">{ep.logline}</p>
        </li>
      ))}
    </ul>
  )}
</Reader>
```

- [ ] **Step 2: Write `website/src/pages/read/[id].astro`** (one episode, scenes as prose)

```astro
---
import Reader from "../../layouts/Reader.astro";
import episodes from "../../data/episodes.json";
export function getStaticPaths() {
  return episodes.map((ep) => ({ params: { id: ep.id }, props: { ep } }));
}
const { ep } = Astro.props;
---
<Reader title={`Arion World — ${ep.name}`} label={`Episode ${ep.number}`}>
  <h1 style="font-size:2.4rem;line-height:1.15;margin:0 0 .5rem">{ep.name}</h1>
  <p style="color:var(--text-dim);margin:0 0 2.5rem">{ep.logline}</p>
  {ep.scenes.map((s) => (
    <section style="margin:0 0 2.5rem">
      {s.location && <p class="label">{s.location}</p>}
      <p>{s.prose}</p>
    </section>
  ))}
  {ep.cliffhanger && <p style="font-style:italic;color:var(--text-dim)">{ep.cliffhanger}</p>}
</Reader>
```

- [ ] **Step 3: Build (empty episodes still builds — no static paths)**

Run: `cd website && npm run build`
Expected: build succeeds; `/read` renders the empty state.

- [ ] **Step 4: Commit**

```bash
git add website/src/pages/read
git commit -m "feat(site): /read fiction reader with empty state"
```

---

## Task 5: `/world` encyclopedia + landing + verify

**Files:**
- Create: `website/src/pages/world/index.astro`, `website/src/pages/world/[id].astro`, `website/src/pages/index.astro`

- [ ] **Step 1: Write `website/src/pages/world/index.astro`** (characters + techniques + world docs)

```astro
---
import Reader from "../../layouts/Reader.astro";
import characters from "../../data/characters.json";
import techniques from "../../data/techniques.json";
import world from "../../data/world.json";
const groups = [
  { label: "Characters", items: characters },
  { label: "Techniques", items: techniques },
  { label: "The World", items: world },
];
---
<Reader title="Arion World — Encyclopedia" label="The World">
  {groups.map((g) => (
    <section style="margin:0 0 2.5rem">
      <h2 style="font-size:1.6rem;border-bottom:1px solid var(--rule);padding-bottom:.4rem">{g.label}</h2>
      <ul style="list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:.75rem">
        {g.items.map((it) => (
          <li><a href={`/world/${it.id}`}>{it.name}</a></li>
        ))}
      </ul>
    </section>
  ))}
</Reader>
```

- [ ] **Step 2: Write `website/src/pages/world/[id].astro`**

```astro
---
import Reader from "../../layouts/Reader.astro";
import characters from "../../data/characters.json";
import techniques from "../../data/techniques.json";
import world from "../../data/world.json";
const all = [...characters, ...techniques, ...world];
export function getStaticPaths() {
  const items = [...characters, ...techniques, ...world];
  return items.map((it) => ({ params: { id: it.id }, props: { it } }));
}
const { it } = Astro.props;
---
<Reader title={`Arion World — ${it.name}`} label={it.type.replace("_", " ")}>
  <h1 style="font-size:2.2rem;margin:0 0 1rem">{it.name}</h1>
  {it.description && <p>{it.description}</p>}
  {it.role && <p class="label">Role: {it.role}</p>}
  {it.branch && <p class="label">Branch: {it.branch}</p>}
</Reader>
```

- [ ] **Step 3: Write `website/src/pages/index.astro`** (landing)

```astro
---
import Reader from "../layouts/Reader.astro";
---
<Reader title="Arion World">
  <h1 style="font-size:3rem;line-height:1.1;margin:0 0 1rem">Arion World</h1>
  <p style="font-size:1.3rem;color:var(--text-dim)">
    An epic fantasy universe where equivalent exchange governs all power and no outcome is protected.
  </p>
  <p style="margin-top:2rem"><a href="/read">Start reading</a> &nbsp;·&nbsp; <a href="/world">Explore the world</a></p>
</Reader>
```

- [ ] **Step 4: Build, then verify in the browser preview**

Run: `cd website && npm run build && npm run preview` (or use the preview_* workflow).
Verify with the preview tools: `/` landing renders, `/world` lists the 5 characters + 13 techniques + 11 world docs, an entity page renders, `/read` shows the empty state. Take a screenshot. Confirm: dark theme, serif body, single accent, **no secrets** visible (search the rendered `/world` pages for any `canon`-layer text).

- [ ] **Step 5: Commit**

```bash
git add website/src/pages
git commit -m "feat(site): /world encyclopedia + landing; reader site complete"
```

---

## Self-Review (completed by plan author)

**Spec coverage:** §7 `/read` fiction → Task 4. §7 `/world` encyclopedia → Task 5. §3 public/canon layer enforcement → Task 1 (the export is the single spoiler chokepoint; a test asserts secrets and hooks never ship). `engine render` → Task 2.

**Placeholder scan:** none — full code for the export module + every Astro page. Entity counts in Task 2 step 2 reflect the real migrated canon (5/13/11/0).

**Type consistency:** `export_site(store, out_dir) -> counts` matches the CLI and tests. Bucket filenames (`characters/techniques/world/episodes.json`) match the Astro imports exactly. Episode fields emitted by `_public_view` (number, logline, summary, cliffhanger, scenes) match `read/[id].astro` usage and the Plan 0b episode schema.

**Exit criterion (Phase 0c):** `engine render` writes spoiler-safe data; `npm run build` succeeds; the browser preview shows `/`, `/world` (47-entity encyclopedia), an entity page, and `/read` empty state, dark editorial, no secrets leaked. Phase 0 (a+b+c) then renders a readable universe from validated canon, with the self-policing episode pipeline ready to populate `/read` the moment LLM keys are set.
```
