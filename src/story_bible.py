import json
import os
from pathlib import Path

BIBLE_DIR = Path(__file__).parent.parent / "story_bible"
EPISODES_DIR = BIBLE_DIR / "episodes"
COUNTER_FILE = BIBLE_DIR / ".episode_counter"


def get_episode_number() -> int:
    return int(COUNTER_FILE.read_text().strip())


def increment_episode_number() -> int:
    n = get_episode_number() + 1
    COUNTER_FILE.write_text(str(n))
    return n


def load_universe() -> dict:
    return json.loads((BIBLE_DIR / "universe.json").read_text())


def load_characters() -> dict:
    return json.loads((BIBLE_DIR / "characters.json").read_text())


def load_races() -> dict:
    path = BIBLE_DIR / "races.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_continents() -> dict:
    path = BIBLE_DIR / "continents.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_techniques() -> dict:
    path = BIBLE_DIR / "techniques.json"
    return json.loads(path.read_text()) if path.exists() else {"techniques": []}


def load_character_visual_state() -> dict:
    path = BIBLE_DIR / "character_visual_state.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_visual_style() -> dict:
    path = BIBLE_DIR / "visual_style.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_caelum_city() -> dict:
    path = BIBLE_DIR / "caelum_city.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_chroniclers() -> dict:
    path = BIBLE_DIR / "chroniclers.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_curses() -> dict:
    path = BIBLE_DIR / "curses.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_crafting_arts() -> dict:
    path = BIBLE_DIR / "crafting_arts.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_season1_soil() -> dict:
    path = BIBLE_DIR / "season1_soil.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_story_philosophy() -> dict:
    path = BIBLE_DIR / "story_philosophy.json"
    return json.loads(path.read_text()) if path.exists() else {}


def load_future_hooks() -> dict:
    return json.loads((BIBLE_DIR / "future_hooks.json").read_text())


def load_recent_episodes(count: int = 3) -> list[dict]:
    episodes = sorted(EPISODES_DIR.glob("ep*.json"))
    recent = episodes[-count:] if len(episodes) >= count else episodes
    return [json.loads(p.read_text()) for p in recent]


def save_episode(episode_number: int, data: dict):
    EPISODES_DIR.mkdir(exist_ok=True)
    path = EPISODES_DIR / f"ep{episode_number:03d}.json"
    path.write_text(json.dumps(data, indent=2))


def update_future_hooks(updated_hooks: dict):
    path = BIBLE_DIR / "future_hooks.json"
    path.write_text(json.dumps(updated_hooks, indent=2))


def append_new_techniques(new_techniques: list[dict]):
    """Add newly demonstrated techniques from an episode into techniques.json."""
    if not new_techniques:
        return
    path = BIBLE_DIR / "techniques.json"
    data = json.loads(path.read_text()) if path.exists() else {"techniques": []}
    existing = data.setdefault("techniques", [])
    existing_names = {t["name"].lower() for t in existing}
    # Determine next available ID
    existing_ids = {t.get("id", "") for t in existing}
    next_id = len(existing) + 1
    added = 0
    for tech in new_techniques:
        if not isinstance(tech, dict) or not tech.get("name"):
            continue
        if tech["name"].lower() in existing_names:
            continue
        # Assign a non-conflicting ID
        while f"tech_{next_id:03d}" in existing_ids:
            next_id += 1
        tech["id"] = f"tech_{next_id:03d}"
        existing.append(tech)
        existing_names.add(tech["name"].lower())
        existing_ids.add(tech["id"])
        next_id += 1
        added += 1
    if added:
        path.write_text(json.dumps(data, indent=2))


def build_context_prompt(episode_number: int) -> str:
    universe = load_universe()
    characters = load_characters()
    races = load_races()
    continents = load_continents()
    techniques = load_techniques()
    hooks = load_future_hooks()
    recent_episodes = load_recent_episodes(3)
    visual_state = load_character_visual_state()
    visual_style = load_visual_style()
    caelum_city = load_caelum_city()
    chroniclers = load_chroniclers()
    curses = load_curses()
    crafting_arts = load_crafting_arts()
    story_philosophy = load_story_philosophy()
    season1_soil = load_season1_soil()

    relevant_hooks = [
        h for h in hooks["hooks"]
        if not h["revealed"] and (
            h["planted_episode"] >= episode_number - 50
            or h["payoff_episode"] <= episode_number + 5
        )
    ]

    # Only include races/continents relevant to current story scope
    # Early episodes: only Known Continent + races present there
    # Expand as episode count grows
    if episode_number < 20:
        relevant_races = {k: v for k, v in races.get("races", {}).items()
                         if k in ("Humans", "Keth", "Valdri", "Seren", "Fael", "Resonborn")}
        relevant_continents = {k: v for k, v in continents.get("continents", {}).items()
                               if v.get("status") in ("primary_season_1_location",)}
    else:
        relevant_races = races.get("races", {})
        relevant_continents = continents.get("continents", {})

    context = f"""
ARION WORLD — STORY BIBLE CONTEXT FOR EPISODE {episode_number}

=== WORLD OVERVIEW ===
{universe['overview']}

=== WORLD SETTING ===
{json.dumps(universe.get('world_setting', {}), indent=2)}

=== SKILL SYSTEM (THE OPEN PATH) ===
{json.dumps(universe.get('skill_system', {}), indent=2)}

=== ACTIVE TIMELINES ===
{json.dumps(universe['timelines'], indent=2)}

=== POWER SYSTEM ===
{json.dumps(universe['power_system'], indent=2)}

=== RACES (in story scope for this episode) ===
{json.dumps(relevant_races, indent=2)}

=== KNOWN GEOGRAPHY ===
{json.dumps(relevant_continents, indent=2)}

=== KNOWN TECHNIQUES (game-compatible skill log) ===
{json.dumps(techniques.get('techniques', []), indent=2)}

=== FACTIONS ===
{json.dumps(universe.get('factions', {}), indent=2)}

=== ACTIVE MYSTERIES ===
{json.dumps(universe['active_mysteries'], indent=2)}

=== MAIN CHARACTERS ===
{json.dumps(characters['main_cast'], indent=2)}

=== VISUAL STYLE (anime art direction — apply to all image_prompts) ===
{json.dumps(visual_style, indent=2)}

=== CURRENT CHARACTER PHYSICAL STATE ===
(Injuries, healing wounds, equipment changes — reflect these in scene descriptions)
{json.dumps(visual_state.get('characters', {}), indent=2)}
{"" if not caelum_city else f"""
=== CAELUM CITY — STREET LEVEL DETAIL ===
{json.dumps(caelum_city, indent=2)}
"""}{"" if not chroniclers else f"""
=== THE CHRONICLERS — INTERNAL STRUCTURE ===
{json.dumps(chroniclers, indent=2)}
"""}{"" if not curses else f"""
=== CURSE SYSTEM — EQUIVALENT EXCHANGE ===
{json.dumps(curses, indent=2)}
"""}{"" if not crafting_arts else f"""
=== CRAFTING ARTS — ALCHEMY & BLACKSMITHING ===
{json.dumps(crafting_arts, indent=2)}
"""}
=== RELEVANT FUTURE HOOKS ===
{json.dumps(relevant_hooks, indent=2)}
{"" if not story_philosophy else f"""
=== STORY STRUCTURE RULES (permanent laws of this world) ===
{json.dumps(story_philosophy, indent=2)}
"""}{"" if not season1_soil else f"""
=== SEASON 1 BOARD STATE (character positions and knowledge gaps at story start) ===
{json.dumps(season1_soil, indent=2) if episode_number <= 52 else "Reference season1_soil.json for original starting positions."}
"""}
=== RECENT EPISODE SUMMARIES ===
{json.dumps(recent_episodes, indent=2) if recent_episodes else "This is Episode 1 — no prior episodes."}
""".strip()

    return context
