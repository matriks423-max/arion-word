"""
Autonomous lore builder — runs every 5 hours via GitHub Actions.

Reads the current state of the story bible, identifies what needs
expanding, calls Claude, and commits the enriched content back to the repo.

Each run focuses on one task so commits are small and reviewable.
Tasks rotate automatically based on what's least developed.
"""

import json
import os
import sys
from pathlib import Path
import anthropic

BIBLE_DIR = Path(__file__).parent.parent / "story_bible"

TASKS = [
    ("races",        "Expand one underdeveloped race entry in races.json with more cultural depth, internal politics, specific named locations in their homeland, and at least one named individual who will eventually appear in the story."),
    ("continents",   "Expand one continent in continents.json — add named cities, landmarks, political tensions, and one secret about that continent nobody in the story knows yet."),
    ("techniques",   "Add 2-3 new named techniques to techniques.json. Each must be concrete enough to implement as a game ability, belong to a specific branch, and fit naturally into the world as it exists."),
    ("factions",     "Deepen one faction in universe.json — add named members, internal power structure, a specific thing they did in the last 50 years that shaped the present, and one member who privately disagrees with the faction's direction."),
    ("hooks",        "Add 3 new long-range future hooks to future_hooks.json. Each should be subtle enough to plant in Episode 1-10 without being noticed, with a payoff planned for Episode 50-200."),
    ("world_detail", "Add to universe.json: 3 new named locations on the Known Continent with hidden truths, 2 new active mysteries, and expand the founding age key events with one specific detail that changes how the Great Betrayal is understood."),
    ("characters",   "Add one new supporting character to characters.json — someone who exists in Kairo's world from Episode 1 but whose significance only becomes clear later. Define their fatal flaw, what they want, what they fear, and one secret."),
    ("curses",      "Expand curses.json — add 3 new named curses following the equivalent exchange principle. Each must have: name, description, the_cost (what the bearer loses), the_hidden_gift (what a clever person exploits from it), origin (how it's contracted), rarity, known_bearers. They must fit the world's tone — specific, not generic."),
    ("crafting",    "Expand crafting_arts.json — add 1 new alchemy technique OR 1 new smithing technique (game-ready mechanics), AND add one new named practitioner with a specific secret connected to the main story. Follow the existing JSON structure exactly."),
    ("city_detail", "Expand caelum_city.json — add 2-3 new named locations in the outer or inner districts of Caelum City. Each location needs: address/location, description, what makes it significant, a hidden truth, and a connection to at least one named character from characters.json."),
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save_json(path: Path, data: dict):
    path.write_text(json.dumps(data, indent=2))


def get_current_task(run_number: int) -> tuple[str, str]:
    return TASKS[run_number % len(TASKS)]


def build_full_context() -> str:
    universe = load_json(BIBLE_DIR / "universe.json")
    characters = load_json(BIBLE_DIR / "characters.json")
    races = load_json(BIBLE_DIR / "races.json")
    continents = load_json(BIBLE_DIR / "continents.json")
    techniques = load_json(BIBLE_DIR / "techniques.json")
    hooks = load_json(BIBLE_DIR / "future_hooks.json")
    caelum = load_json(BIBLE_DIR / "caelum_city.json")
    chroniclers = load_json(BIBLE_DIR / "chroniclers.json")
    curses = load_json(BIBLE_DIR / "curses.json")
    crafting = load_json(BIBLE_DIR / "crafting_arts.json")
    season1 = load_json(BIBLE_DIR / "season1_soil.json")
    philosophy = load_json(BIBLE_DIR / "story_philosophy.json")

    context = f"""
ARION WORLD — CURRENT STORY BIBLE STATE

UNIVERSE:
{json.dumps(universe, indent=2)}

CHARACTERS:
{json.dumps(characters, indent=2)}

RACES:
{json.dumps(races, indent=2)}

CONTINENTS:
{json.dumps(continents, indent=2)}

TECHNIQUES:
{json.dumps(techniques, indent=2)}

FUTURE HOOKS:
{json.dumps(hooks, indent=2)}
"""

    if caelum:
        context += f"""
CAELUM CITY DETAIL:
{json.dumps(caelum, indent=2)}
"""

    if chroniclers:
        context += f"""
CHRONICLERS FACTION:
{json.dumps(chroniclers, indent=2)}
"""

    if curses:
        context += f"""
CURSE SYSTEM:
{json.dumps(curses, indent=2)}
"""

    if crafting:
        context += f"""
CRAFTING ARTS:
{json.dumps(crafting, indent=2)}
"""

    if season1:
        context += f"""
SEASON 1 SOIL:
{json.dumps(season1, indent=2)}
"""

    if philosophy:
        context += f"""
STORY PHILOSOPHY:
{json.dumps(philosophy, indent=2)}
"""

    return context.strip()


def run_lore_expansion(task_name: str, task_instruction: str) -> dict:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    context = build_full_context()

    system = """You are the world-builder for Arion World — a 16+ epic anime-style fantasy with WoW-scale races,
multiple continents, a pre-electricity magic system (The Open Path), and Game of Thrones/Dragon Age depth.

Core rules:
- No race is good or evil. Every faction believes it is right.
- Knowledge is the rarest resource, not power.
- The world is vastly larger than it appears. Reveal gradually.
- No character or outcome is protected.
- Everything you add must be consistent with what already exists.
- Be specific. Named people, named places, named events. Vague lore is weak lore.
- Game compatibility: any technique or ability must be concrete enough to implement as a game mechanic."""

    user_prompt = f"""CURRENT STORY BIBLE:
{context}

YOUR TASK: {task_instruction}

Return ONLY valid JSON matching the structure of the file you are updating.
Do not include explanation outside the JSON.
The JSON must be complete — include both existing content and your additions.
Target file: {task_name}"""

    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=32000,
        system=system,
        messages=[{"role": "user", "content": user_prompt}]
    )

    raw = message.content[0].text
    start = raw.find("{")
    end = raw.rfind("}") + 1
    return json.loads(raw[start:end])


def apply_update(task_name: str, updated_data: dict):
    file_map = {
        "races":        BIBLE_DIR / "races.json",
        "continents":   BIBLE_DIR / "continents.json",
        "techniques":   BIBLE_DIR / "techniques.json",
        "hooks":        BIBLE_DIR / "future_hooks.json",
        "world_detail": BIBLE_DIR / "universe.json",
        "factions":     BIBLE_DIR / "universe.json",
        "characters":   BIBLE_DIR / "characters.json",
        "curses":      BIBLE_DIR / "curses.json",
        "crafting":    BIBLE_DIR / "crafting_arts.json",
        "city_detail": BIBLE_DIR / "caelum_city.json",
    }
    path = file_map[task_name]

    # Validate that updated_data serialises cleanly before touching the file
    try:
        json_str = json.dumps(updated_data, indent=2)
        json.loads(json_str)  # round-trip check
    except (TypeError, ValueError) as e:
        raise RuntimeError(f"Updated data for '{task_name}' failed JSON validation: {e}")

    # Write a backup of the current file alongside it (if it exists)
    backup_path = path.with_suffix(".json.bak")
    if path.exists():
        backup_path.write_text(path.read_text())

    try:
        path.write_text(json_str)
        print(f"Updated: {path.name}")
    except Exception as e:
        # Restore from backup on failure
        if backup_path.exists():
            path.write_text(backup_path.read_text())
            print(f"Save failed — restored {path.name} from backup.")
        raise RuntimeError(f"Failed to save {path.name}: {e}") from e


def main():
    run_number = int(os.environ.get("RUN_NUMBER", "0"))
    task_name, task_instruction = get_current_task(run_number)

    print(f"\n=== Arion World — Auto Lore Builder ===")
    print(f"Run #{run_number} — Task: {task_name}")
    print(f"Instruction: {task_instruction[:80]}...\n")

    updated = run_lore_expansion(task_name, task_instruction)
    apply_update(task_name, updated)

    print(f"\nLore expansion complete. Task: {task_name}")


if __name__ == "__main__":
    main()
