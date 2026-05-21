"""
After each episode is generated, this script extracts the public-facing
content and writes it to website/public/content/.

Rules:
- Only reveals what the AUDIENCE now knows — never hidden secrets
- Characters marked deceased if they died in this episode
- World lore sections expand only as episodes reveal them
- Mysteries list updates with new questions raised and old ones answered
"""

import json
from pathlib import Path

BIBLE_DIR = Path(__file__).parent.parent / "story_bible"
WEBSITE_CONTENT = Path(__file__).parent.parent.parent / "website" / "public" / "content"


def slugify(name: str) -> str:
    return name.lower().replace(" ", "-").replace("'", "").replace(".", "")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def update_site_state(episode_data: dict, current_episode: int):
    """Update the home page state."""
    existing = load_json(WEBSITE_CONTENT / "site_state.json")

    # Determine world tone from episode content
    title = episode_data.get("title", "").lower()
    cliffhanger = episode_data.get("cliffhanger", "").lower()
    has_death = bool(episode_data.get("character_deaths"))

    if has_death or any(w in cliffhanger for w in ["dies", "dead", "destroyed", "gone"]):
        tone = "dark"
    elif any(w in title + cliffhanger for w in ["hope", "light", "dawn", "together"]):
        tone = "hopeful"
    elif any(w in title + cliffhanger for w in ["danger", "war", "threat", "enemy", "hunted"]):
        tone = "tense"
    else:
        tone = existing.get("world_tone", "mysterious")

    state = {
        "episode_number": current_episode,
        "latest_episode_title": episode_data.get("title", ""),
        "latest_episode_logline": episode_data.get("logline", ""),
        "latest_episode_cliffhanger": episode_data.get("cliffhanger", ""),
        "world_tone": tone,
        "active_characters": existing.get("active_characters", []),
    }
    save_json(WEBSITE_CONTENT / "site_state.json", state)


def update_characters(episode_data: dict, current_episode: int):
    """Update public character profiles — only revealed information."""
    existing_data = load_json(WEBSITE_CONTENT / "characters_public.json")
    existing_chars = {c["slug"]: c for c in existing_data.get("characters", [])}

    # Characters introduced this episode
    new_chars = episode_data.get("characters_introduced", [])
    for char in new_chars:
        slug = slugify(char["name"])
        existing_chars[slug] = {
            "slug": slug,
            "name": char["name"],
            "role": char.get("public_role", "Unknown"),
            "status": "alive",
            "public_description": char.get("public_description", ""),
            "first_appeared_episode": current_episode,
            "died_episode": None,
        }

    # Characters who died this episode
    deaths = episode_data.get("character_deaths", [])
    for name in deaths:
        slug = slugify(name)
        if slug in existing_chars:
            existing_chars[slug]["status"] = "deceased"
            existing_chars[slug]["died_episode"] = current_episode

    # Characters whose public description updates
    updates = episode_data.get("character_public_updates", {})
    for name, new_desc in updates.items():
        slug = slugify(name)
        if slug in existing_chars:
            existing_chars[slug]["public_description"] = new_desc

    save_json(WEBSITE_CONTENT / "characters_public.json", {
        "characters": list(existing_chars.values()),
        "last_updated_episode": current_episode,
    })


def update_episodes(episode_data: dict, current_episode: int, publish_results: dict | None = None):
    """Add this episode to the public episode list."""
    existing = load_json(WEBSITE_CONTENT / "episodes.json")
    episodes = existing.get("episodes", [])

    entry: dict = {
        "episode_number": current_episode,
        "title": episode_data.get("title", ""),
        "logline": episode_data.get("logline", ""),
        "summary": episode_data.get("episode_summary", ""),
        "cliffhanger": episode_data.get("cliffhanger", ""),
        "major_death": bool(episode_data.get("character_deaths")),
    }

    if publish_results:
        yt = publish_results.get("youtube", "")
        if yt and not str(yt).startswith("FAILED"):
            yt_str = str(yt).strip()
            # youtube publisher returns video_id — build full URL
            if not yt_str.startswith("http"):
                yt_str = f"https://youtube.com/watch?v={yt_str}"
            entry["youtube_url"] = yt_str

    episodes.append(entry)
    save_json(WEBSITE_CONTENT / "episodes.json", {"episodes": episodes})


def update_world(episode_data: dict, current_episode: int):
    """Expand world lore only with what this episode revealed."""
    existing = load_json(WEBSITE_CONTENT / "world_public.json")

    reveals = episode_data.get("world_reveals", {})

    # Build updated world data
    timelines = existing.get("timelines_known", [])
    for t in reveals.get("timelines", []):
        if not any(x["name"] == t["name"] for x in timelines):
            timelines.append(t)

    factions = existing.get("factions_known", [])
    for f in reveals.get("factions", []):
        existing_faction = next((x for x in factions if x["name"] == f["name"]), None)
        if existing_faction:
            if f.get("known_secret"):
                existing_faction["known_secret"] = f["known_secret"]
        else:
            factions.append(f)

    locations = existing.get("locations_known", [])
    for loc in reveals.get("locations", []):
        if not any(x["name"] == loc["name"] for x in locations):
            locations.append(loc)

    power_system = existing.get("power_system_known")
    if reveals.get("power_system") and not power_system:
        power_system = reveals["power_system"]

    world_data = {
        "overview": reveals.get("overview_update") or existing.get("overview",
            "Arion World spans broken timelines and centuries of buried truth."),
        "timelines_known": timelines,
        "factions_known": factions,
        "locations_known": locations,
        "power_system_known": power_system,
        "last_updated_episode": current_episode,
    }
    save_json(WEBSITE_CONTENT / "world_public.json", world_data)


def update_mysteries(episode_data: dict, current_episode: int):
    """Track open and resolved mysteries."""
    existing = load_json(WEBSITE_CONTENT / "mysteries.json")
    open_mysteries = existing.get("open", [])
    solved = existing.get("solved", [])

    # New mysteries raised this episode
    for q in episode_data.get("mysteries_raised", []):
        if not any(m["question"] == q for m in open_mysteries):
            open_mysteries.append({
                "question": q,
                "first_raised_episode": current_episode,
            })

    # Mysteries resolved this episode
    resolved_questions = episode_data.get("mysteries_resolved", [])
    still_open = []
    for m in open_mysteries:
        if m["question"] in resolved_questions:
            solved.append({**m, "resolved_episode": current_episode})
        else:
            still_open.append(m)

    save_json(WEBSITE_CONTENT / "mysteries.json", {
        "open": still_open,
        "solved": solved,
        "last_updated_episode": current_episode,
    })


def update_merch(merch_products: list, current_episode: int):
    """Add newly created merch products to the website merch page."""
    if not merch_products:
        return
    existing = load_json(WEBSITE_CONTENT / "merch.json")
    products = existing.get("products", [])
    existing_urls = {p.get("url") for p in products}
    for product in merch_products:
        if isinstance(product, dict) and product.get("url") not in existing_urls:
            products.append({"episode_number": current_episode, **product})
    save_json(WEBSITE_CONTENT / "merch.json", {
        "products": products,
        "store_url": existing.get("store_url", ""),
        "last_updated_episode": current_episode,
    })


def generate_all(
    episode_data: dict,
    current_episode: int,
    merch_products: list | None = None,
    publish_results: dict | None = None,
):
    """Run all website content updates for this episode."""
    print("Updating website content...")
    update_site_state(episode_data, current_episode)
    update_characters(episode_data, current_episode)
    update_episodes(episode_data, current_episode, publish_results)
    update_world(episode_data, current_episode)
    update_mysteries(episode_data, current_episode)
    if merch_products:
        update_merch(merch_products, current_episode)
    print(f"Website content updated through Episode {current_episode}.")
