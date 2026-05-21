"""
Arion World — Scene Image Generator

Enforces visual consistency across every episode:
  - Each character always looks the same (same hair, face, build, clothing)
  - Injuries and wounds persist until healed
  - Aging is reflected as the story progresses
  - Technique visual effects are always identical for the same technique
  - Art style stays consistent — one show, not a gallery of random anime

This is achieved by building every prompt from:
  1. visual_style.json       — global art direction (style, tone, negatives)
  2. characters.json         — base visual profile per character (prompt_tags)
  3. character_visual_state.json — current injuries, aging, equipment changes
  4. techniques.json         — visual_effect_tags per named technique
  5. scene["image_prompt"]   — environment, composition, lighting, mood ONLY
"""

import json
import os
import time
import requests
from pathlib import Path


REPLICATE_API = "https://api.replicate.com/v1"
BIBLE_DIR = Path(__file__).parent.parent / "story_bible"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def _build_character_lookup() -> dict[str, str]:
    """Map character name → base prompt_tags from characters.json."""
    chars = _load_json(BIBLE_DIR / "characters.json")
    lookup = {}
    for char_name, char_data in chars.get("main_cast", {}).items():
        vp = char_data.get("visual_profile", {})
        if tags := vp.get("prompt_tags"):
            lookup[char_name] = tags
    return lookup


def _build_state_lookup() -> dict[str, dict]:
    """Map character name → current visual state from character_visual_state.json."""
    state = _load_json(BIBLE_DIR / "character_visual_state.json")
    return state.get("characters", {})


def _build_technique_lookup() -> dict[str, str]:
    """Map technique name → visual_effect_tags from techniques.json."""
    techs = _load_json(BIBLE_DIR / "techniques.json")
    lookup = {}
    for tech in techs.get("techniques", []):
        if tags := tech.get("visual_effect_tags"):
            lookup[tech["name"].lower()] = tags
    return lookup


def _get_character_prompt(
    char_name: str,
    char_lookup: dict[str, str],
    state_lookup: dict[str, dict],
) -> str:
    """Build the full prompt fragment for one character in their current state."""
    base = char_lookup.get(char_name, "")
    if not base:
        return ""

    state = state_lookup.get(char_name, {})
    parts = [base]

    # Add active injuries
    for injury in state.get("active_injuries", []):
        if tag := injury.get("prompt_tag"):
            parts.append(tag)

    # Add healing injuries (visible but less severe)
    for injury in state.get("healing_injuries", []):
        if tag := injury.get("prompt_tag"):
            parts.append(f"partially healed {tag}")

    # Add equipment changes
    for equip in state.get("equipment_changes", []):
        if tag := equip.get("prompt_tag"):
            parts.append(tag)

    # Override age appearance if it has changed (aging arc)
    if age_override := state.get("age_appearance"):
        current_age_tag = base.split(",")[1].strip() if "," in base else ""
        if current_age_tag and age_override not in base:
            parts[0] = base.replace(current_age_tag, age_override)

    # Any freeform additions
    if extra := state.get("prompt_additions", "").strip():
        parts.append(extra)

    return ", ".join(p for p in parts if p)


def build_scene_prompt(
    scene: dict,
    char_lookup: dict[str, str],
    state_lookup: dict[str, dict],
    tech_lookup: dict[str, str],
    style: dict,
) -> str:
    """
    Build the full SDXL prompt for one scene.

    Order: style → character descriptions → technique effects → scene environment/composition
    This order matters — SDXL weights earlier tokens more heavily.
    """
    parts = []

    # 1. Global style (always first — highest weight)
    parts.append(style.get("style_tokens", "dark fantasy anime illustration, masterpiece, best quality"))
    parts.append(style.get("tone_tokens", "dramatic lighting, deep shadow contrast"))

    # 2. Characters present in the scene
    for char_name in scene.get("characters_in_scene", []):
        char_prompt = _get_character_prompt(char_name, char_lookup, state_lookup)
        if char_prompt:
            parts.append(char_prompt)

    # 3. Technique visual effects
    for tech_name in scene.get("techniques_used", []):
        effect = tech_lookup.get(tech_name.lower(), "")
        if not effect:
            # Try partial match
            for key, val in tech_lookup.items():
                if key in tech_name.lower() or tech_name.lower() in key:
                    effect = val
                    break
        if effect:
            parts.append(effect)

    # 4. Scene description (environment, lighting, composition — NOT character descriptions)
    scene_prompt = scene.get("image_prompt", "").strip()
    if scene_prompt:
        parts.append(scene_prompt)

    return ", ".join(p for p in parts if p)


def generate_scene_image(prompt: str, negative_prompt: str, scene_num: int, output_dir: Path) -> Path:
    api_token = os.environ["REPLICATE_API_TOKEN"]

    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "version": "7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc",
        "input": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": 1920,
            "height": 1080,
            "num_inference_steps": 35,
            "guidance_scale": 8.0,
            "scheduler": "DPMSolverMultistep",
        }
    }

    resp = requests.post(f"{REPLICATE_API}/predictions", json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    prediction_id = resp.json()["id"]

    for _ in range(60):
        time.sleep(3)
        status_resp = requests.get(
            f"{REPLICATE_API}/predictions/{prediction_id}",
            headers=headers,
            timeout=30,
        )
        status_resp.raise_for_status()
        result = status_resp.json()

        if result["status"] == "succeeded":
            image_url = result["output"][0]
            img_resp = requests.get(image_url, timeout=60)
            img_resp.raise_for_status()
            output_path = output_dir / f"scene_{scene_num:02d}.png"
            output_path.write_bytes(img_resp.content)
            return output_path

        if result["status"] == "failed":
            raise RuntimeError(f"Image generation failed for scene {scene_num}: {result.get('error')}")

    raise TimeoutError(f"Image generation timed out for scene {scene_num}")


def generate_all_images(episode_data: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load all visual consistency data once at the start
    style = _load_json(BIBLE_DIR / "visual_style.json")
    char_lookup = _build_character_lookup()
    state_lookup = _build_state_lookup()
    tech_lookup = _build_technique_lookup()
    negative_prompt = style.get("negative_prompt", "blurry, low quality, watermark, deformed, bad anatomy")

    image_files = []
    scenes = episode_data["scenes"]

    for scene in scenes:
        scene_num = scene["scene_number"]
        prompt = build_scene_prompt(scene, char_lookup, state_lookup, tech_lookup, style)

        # Log character count for debugging
        chars = scene.get("characters_in_scene", [])
        techs = scene.get("techniques_used", [])
        print(f"Scene {scene_num}: {len(chars)} character(s){', ' + str(len(techs)) + ' technique(s)' if techs else ''}")

        img_path = generate_scene_image(prompt, negative_prompt, scene_num, output_dir)
        image_files.append(img_path)
        time.sleep(1)

    return image_files
