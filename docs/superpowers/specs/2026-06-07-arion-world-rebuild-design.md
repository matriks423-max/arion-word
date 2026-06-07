# Arion World v2 — Design Spec

**Date:** 2026-06-07
**Status:** Approved (brainstorming complete) → ready for implementation planning
**Repo:** `matriks423-max/arion-world`, branch `v2-canon-rebuild` (rebuild in place; swap `main` when Phase 0 lands)

---

## 0. Why a rebuild

v1 was built before a disciplined AI-engineering workflow existed. It tried to ship a full
publishing firehose (1-hour weekly video → 4 social platforms → merch → Discord → website,
plus 5-hourly lore expansion) in a single commit — and the commit message literally says
`(no workflows yet)`. The automation engine (GitHub Actions) was never written, so nothing
could run. Underneath that, three structural flaws would have corrupted the universe even if
it had run:

1. **Lossy full-file canon rewrites.** Lore expansion asked the model to return the *entire*
   bible file (existing + additions) and overwrote it. As files grow this truncates or
   silently drops entries — the universe degrades every run.
2. **Brittle JSON parsing.** `find("{") … rfind("}")` + bare `json.loads` with no retry/repair
   — any prose, truncation, or stray comma kills the run.
3. **No continuity enforcement.** Nothing checked a new episode/lore change against existing
   canon, so contradictions, retcons, and drift accumulate invisibly.

This spec rebuilds around the thing v1 got wrong: **maintaining a large, self-consistent
fictional canon that grows autonomously without drifting or contradicting itself.**

## 1. Decisions captured (from brainstorming)

| Decision | Choice |
|---|---|
| Primary goal | **The universe itself** — quality of writing + canon consistency is the success metric |
| Artifacts | **All four**: readable serialized fiction · living world encyclopedia · game bible · video — built as *renderers over one canon*; video is the last skin |
| Autonomy | **Self-policing autonomous** — writer → continuity-critic → editor gate must pass before commit; no human gate (quarantine on failure instead) |
| Existing canon | **Migrate + clean** the v1 story bible as the seed |
| Model/budget | **Quality-first hybrid** — Opus writes + final-edits; free NVIDIA/Gemini panel does continuity-critique + bulk lore; bge-m3 embeddings |
| Architecture | **Canon-as-Code (A)** — file-per-entity, git-versioned, patch-mutated, targeted retrieval; server-free; LightRAG can enrich critique later without re-architecting |
| Repo | Rebuild in place on branch `v2-canon-rebuild` |

**Non-goals (now):** social publishing, merch, Discord, fully-automated video. Deferred to
Phases 2–3, behind a quality gate.

## 2. Architecture — three layers, one-way data flow

```
            (validated patches only)            (read only)
  Engine  ───────────────────────────►  Canon store  ◄───────────────────  Renderers
 (Python)                                (canon/, git)                      (Astro, exports)
```

- **Canon store** (`canon/`) — file-per-entity, schema-validated, git-versioned, patch-mutated.
  Single source of truth.
- **Engine** (`engine/`, Python 3.11) — retrieval + self-policing generation + canon mutation.
  Stateless except the store.
- **Renderers** (`render/`) — pure transforms canon → artifacts.

Invariant: **the Engine is the only writer of canon, and only via validated CanonPatches.**
Renderers never write. This boundary is what makes growth auditable and safe.

## 3. Canon store

Layout:

```
canon/
  _schema/            JSON Schema per entity type
  _index.json         generated manifest (id, type, name, aliases, tags, relationships)
  _index/embeddings.jsonl   bge-m3 vectors for relevance retrieval
  characters/  locations/  factions/  races/  continents/
  techniques/  curses/  crafting/  hooks/  timeline/  world/
  episodes/           one file per published episode
pending/              quarantined drafts that failed the gate (never canon)
```

- **One entity = one YAML file** (`canon/characters/kairo-voss.yaml`) — human-readable,
  comment-able, diffable. YAML over JSON for authoring ergonomics; schemas still enforced.
- **Every entity carries:** stable `id`, `type`, `name`, a **`public` vs `canon` layer split**
  (audience-safe vs full truth including secrets), `provenance`
  (`introduced_episode`, `last_changed_episode`, `source_run`), and type-specific fields.
- **`public` / `canon` layering** replaces v1's ad-hoc "public description / hidden secret"
  scattering. Renderers pick the layer: the fiction site and encyclopedia render `public`; the
  game bible renders the full `canon` layer.
- **Validation:** `canon/_schema/*.json` defines each type. Every write is validated; CI
  validates the entire canon on every commit (a single invalid file fails the build).
- **Index + embeddings** let the engine retrieve *relevant* entities without loading the whole
  bible — directly fixing v1's "dump everything into the prompt" cost and truncation.

## 4. Canon mutation = patches (root-cause fix for v1's data loss)

The engine **never** rewrites a file from a raw model dump. Generation produces a **CanonPatch**:
an ordered list of typed operations, each targeting an entity + field path:

- `create_entity(type, id, fields)`
- `set_field(id, path, value)`
- `append_to_list(id, path, item)`
- `add_relationship(from_id, rel, to_id)`
- `mark_hook_revealed(hook_id, episode)`
- `record_death(character_id, episode)`

Apply sequence:
1. **Validate** — schema check + **referential integrity** (no dangling ids, no relationship to
   a nonexistent entity, no reviving a dead character without an explicit op).
2. **Apply transactionally** — backup touched files → apply → on any error, restore from backup.
3. **Commit** — git commit carrying provenance (episode/run id) → full audit trail of how the
   universe evolved.

Because operations are additive/targeted, **silent whole-entry loss is structurally impossible.**

## 5. Self-policing generation pipeline

Two pipelines share one gate framework (`engine/gate.py`).

### 5.1 Episode pipeline (`engine/pipelines/episode.py`)

1. **Retrieve** — given episode N and any payoff-hooks due, pull only relevant canon (recurring
   characters, active locations, open hooks, recent episode summaries) via `_index.json` +
   embeddings. Bounded context, not the whole bible.
2. **Plan** — Opus drafts a beat outline (three movements: establishment → escalation →
   consequence) and declares which canon entities it will touch.
3. **Write** — Opus produces the episode (prose/script + structured metadata) using
   **structured / tool-use output** (forced JSON via the SDK, never brace-scraping). Long
   episodes are written in **scene batches** to stay under output-token limits, then stitched.
4. **Continuity critic** — a **NVIDIA multi-model panel** (the existing `council` pattern). Each
   voter receives the draft + retrieved canon and must flag: contradictions, retcons,
   dead-character reuse, equivalent-exchange / power-creep violations, tone breaks, and
   hook-logic errors. Returns a structured verdict with per-issue severity.
5. **Gate** —
   - **clean** → proceed.
   - **issues** → **bounded revise loop**: feed issues back to Opus, regenerate only the
     affected parts, re-critique. Cap at ~3 iterations.
   - **still failing** → **quarantine** the draft to `pending/episodes/`, log the reason, and
     **do not commit**. Autonomous but never corrupts canon.
6. **Edit** — Opus final pass: prose polish + emit the validated **CanonPatch** (new hooks,
   character/visual-state updates, deaths, techniques, world reveals).
7. **Commit** — apply patch, write the episode file, update index + embeddings, git commit.

### 5.2 Lore pipeline (`engine/pipelines/lore.py`)

Same gate, task-rotated like v1 (races / continents / techniques / curses / crafting / city
detail / hooks / factions / characters), but:
- retrieves only the **target entity + its neighbors**, not the whole bible;
- produces a **CanonPatch**, never a full-file dump;
- bulk drafting may run on **NVIDIA**; **Opus** handles only the final merge/edit for
  quality-sensitive entries;
- same critic + bounded-retry + quarantine behavior.

### 5.3 Model routing

One `models.yaml` maps each stage to a model (quality-first hybrid):
`plan/write/edit → Opus` · `critic panel + bulk lore → NVIDIA/Gemini` · `embeddings → bge-m3`.
Changing routing is config, not code. Episode model id is pinned via config (not a hard-coded
literal) so a deprecated id can't silently 404 the pipeline.

## 6. Orchestration

- **Local CLI first.** `python -m engine {episode|lore|validate|render|migrate}`. Every command
  supports `--no-commit` (dry-run). Everything hand-runnable and testable before any automation.
- **Autonomous (GitHub Actions cron).**
  - `episode.yml` — weekly.
  - `lore.yml` — every 12–24h (not v1's 5h — cost control).
  - On success: commit canon + push. On quarantine: open a GitHub Issue containing the failed
    draft + critic reasons (an optional glance, not a required human gate).
- **Video is explicitly NOT on GitHub Actions** (runner disk/time can't assemble hour-long
  1080p video). It is a separate local/opt-in module (Phase 2).

## 7. Renderers — four artifacts from one source

- **Astro site** (`render/site/`, reused/hardened from v1): `/read` (fiction, public layer,
  episode by episode), `/world` (encyclopedia, cross-linked entities, public layer),
  `/timeline`. Static build → GitHub Pages / Vercel. Styled via the `design-taste-frontend`
  skill (anti-slop, mandatory).
- **Game-bible export** (`render/gamebible/`): canon → structured mechanics doc/JSON —
  techniques → abilities (cost + effect), crafting → systems, regions → zones. Renders the
  **full `canon` layer** (it is the internal design doc, secrets included).
- **Video** (Phase 2): episode → narration → images → assembly. v1's modules hardened
  (structured errors, retries) and decoupled; opt-in.

## 8. Error handling (prime directive: fix, don't skip)

- No silent skips, no swallow-and-continue. Every model/embedding call uses typed errors,
  retry-with-backoff on 5xx/429, distinct handling for 401 (auth) and 404 (wrong id), and a
  loud hard-fail when unrecoverable.
- Structured output + schema validation on every model result; invalid → repair-retry →
  quarantine.
- Canon writes are transactional with backup/restore and a pre-commit referential-integrity
  check.
- A failing run parks a draft in `pending/` and logs why — it never writes bad canon.

## 9. Testing (v1 had none)

- **Schema tests** — every canon file validates; the migrated v1 bible must pass.
- **Patch-engine unit tests** — apply/rollback, referential integrity, no-data-loss on growth.
- **Continuity-critic golden fixtures** — known-contradictory drafts the critic MUST catch, and
  known-clean drafts it must NOT false-flag (false positives stall the autonomous loop).
- **Retrieval tests** — seeded episodes return the expected relevant entities.
- **Pipeline dry-run integration test** on a tiny fixture canon.
- CI runs all of the above on every push.

## 10. Migration (Phase 0, step 1)

Import v1 `story_bible/*.json` → file-per-entity canon mapped to the new schemas. Run the
continuity critic once over the whole imported canon to surface pre-existing contradictions →
fix → clean seed. Preserve `.episode_counter`.

## 11. Build order (each phase = its own plan → build → verify)

- **Phase 0 — Working slice (the proof).** Canon store + schemas + validation · migrate+clean
  v1 bible · patch engine · retrieval · episode pipeline with the self-policing gate · minimal
  Astro `/read` showing **one** genuinely good, continuity-checked episode. No video, no social.
  *Exit criterion: one episode generated end-to-end, passes the critic, renders readably, and
  the canon it touched is valid + diffable.*
- **Phase 1 — World + autonomy.** Encyclopedia renderer · game-bible export · lore pipeline ·
  GitHub Actions cron + quarantine-to-Issue.
- **Phase 2 — Video skin** (opt-in, gated on the writing being genuinely good).
- **Phase 3 — Reach** (social publish / merch / Discord, optional).

## 12. Stack

Python 3.11 (engine) · Astro + Tailwind (site, reused from v1) · JSON Schema (canon validation) ·
NVIDIA NIM + Anthropic SDK · GitHub Actions (orchestration). Branch `v2-canon-rebuild`, swap to
`main` when Phase 0 meets its exit criterion; v1 history preserved.
