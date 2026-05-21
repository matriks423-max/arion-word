"""
Arion World — Weekly Episode Publishing Pipeline

Run manually:   python src/pipeline.py
Run via CI:     triggered by GitHub Actions every Monday 9am UTC

Steps:
  1. Generate episode script (Claude)
  2. Generate narration audio (ElevenLabs)
  3. Generate scene images (Replicate SDXL)
  4. Generate SRT subtitles + translations (DeepL)
  5. Assemble 1-hour video (FFmpeg)
  6. Create 2-min portrait trailer with burned subtitles (FFmpeg)
  7. Publish to YouTube, Facebook, Instagram, TikTok
  8. Update story bible and commit
"""

import json
import os
import sys
import traceback
from pathlib import Path

# Ensure src/ is on path when running from repo root
sys.path.insert(0, str(Path(__file__).parent))

from generate_story import generate_episode
from generate_voice import generate_narration
from generate_images import generate_all_images
from generate_subtitles import generate_subtitles
from assemble_video import assemble_video
from create_trailer import create_portrait_trailer
from publish_youtube import upload_to_youtube
from publish_facebook import upload_to_facebook
from publish_instagram import upload_reel_to_instagram
from publish_tiktok import upload_to_tiktok
from story_bible import get_episode_number, increment_episode_number, save_episode
from generate_website_content import generate_all as update_website


BASE_DIR = Path(__file__).parent.parent
WORK_DIR = BASE_DIR / "output"
MUSIC_DIR = BASE_DIR / "assets" / "music"
BIBLE_DIR = BASE_DIR / "story_bible"


def _apply_visual_state_updates(episode_number: int, updates: dict):
    """Persist injury/aging/equipment changes to character_visual_state.json."""
    state_path = BIBLE_DIR / "character_visual_state.json"
    if not state_path.exists():
        return

    state = json.loads(state_path.read_text())
    chars = state.setdefault("characters", {})

    for char_name, changes in updates.items():
        if char_name not in chars:
            chars[char_name] = {
                "active_injuries": [], "healing_injuries": [],
                "permanent_changes": [], "equipment_changes": [],
                "prompt_additions": "", "prompt_removals": "",
            }
        c = chars[char_name]

        for inj in changes.get("new_injuries", []):
            inj["received_episode"] = episode_number
            c.setdefault("active_injuries", []).append(inj)

        for healed_tag in changes.get("injuries_healed", []):
            c["active_injuries"] = [
                i for i in c.get("active_injuries", []) if i.get("prompt_tag") != healed_tag
            ]

        for equip in changes.get("new_equipment", []):
            equip["acquired_episode"] = episode_number
            c.setdefault("equipment_changes", []).append(equip)

        for removed_tag in changes.get("equipment_removed", []):
            c["equipment_changes"] = [
                e for e in c.get("equipment_changes", []) if e.get("prompt_tag") != removed_tag
            ]

        for perm in changes.get("permanent_changes", []):
            c.setdefault("permanent_changes", []).append(perm)

        if override := changes.get("age_appearance_override"):
            c["age_appearance"] = override

    state["episode_last_updated"] = episode_number
    state_path.write_text(json.dumps(state, indent=2))


def find_background_music() -> Path | None:
    music_files = list(MUSIC_DIR.glob("*.mp3")) + list(MUSIC_DIR.glob("*.wav"))
    return music_files[0] if music_files else None


def run_pipeline():
    episode_number = get_episode_number()
    print(f"\n{'='*60}")
    print(f"  ARION WORLD — Episode {episode_number} Pipeline Starting")
    print(f"{'='*60}\n")

    episode_dir = WORK_DIR / f"ep{episode_number:03d}"
    audio_dir = episode_dir / "audio"
    images_dir = episode_dir / "images"
    subs_dir = episode_dir / "subtitles"
    video_path = episode_dir / f"arion_world_ep{episode_number:03d}.mp4"
    trailer_path = episode_dir / f"arion_world_ep{episode_number:03d}_trailer.mp4"

    # ── Step 1: Generate story ────────────────────────────────
    print("Step 1/6 — Generating episode script with Claude...")
    episode_data = generate_episode(episode_number)
    (episode_dir / "episode_data.json").parent.mkdir(parents=True, exist_ok=True)
    (episode_dir / "episode_data.json").write_text(json.dumps(episode_data, indent=2))
    print(f"Episode '{episode_data['title']}' generated. {len(episode_data['scenes'])} scenes.")

    # ── Step 2: Generate voice narration ─────────────────────
    print("\nStep 2/6 — Generating narration audio with ElevenLabs...")
    audio_files = generate_narration(episode_data, audio_dir)
    print(f"{len(audio_files)} audio files generated.")

    # ── Step 3: Generate images ───────────────────────────────
    print("\nStep 3/7 — Generating scene images with Replicate SDXL...")
    image_files = generate_all_images(episode_data, images_dir)
    print(f"{len(image_files)} images generated.")

    # ── Step 3b: Generate and publish merch ──────────────────────
    print("\nStep 3b — Generating merch from episode art...")
    merch_products = []
    try:
        from publish_merch import publish_merch_for_episode
        merch_products = publish_merch_for_episode(episode_data, image_files) or []
        if merch_products:
            print(f"  {len(merch_products)} merch product(s) created.")
        else:
            print("  Merch skipped (PRINTFUL_API_KEY not set or no suitable images).")
    except Exception as e:
        print(f"  Merch generation failed (non-fatal): {e}")

    # ── Step 4: Generate subtitles ────────────────────────────
    print("\nStep 4/7 — Generating subtitles + translations...")
    subtitle_files = generate_subtitles(episode_data, audio_files, subs_dir)
    en_srt = subtitle_files.get("EN")

    # ── Step 5: Assemble video ────────────────────────────────
    print("\nStep 5/7 — Assembling 1-hour video with FFmpeg...")
    music = find_background_music()
    if music:
        print(f"  Using background music: {music.name}")
    assemble_video(episode_data, image_files, audio_files, video_path, music)

    # ── Step 6: Create trailer ────────────────────────────────
    print("\nStep 6/7 — Creating 2-minute portrait trailer with subtitles...")
    create_portrait_trailer(video_path, trailer_path, subtitle_file=en_srt)

    # ── Step 7: Publish to all platforms ─────────────────────
    print("\nStep 7/7 — Publishing to platforms...")
    results = {}

    try:
        print("  → YouTube (full 1-hour video + subtitle tracks)...")
        results["youtube"] = upload_to_youtube(video_path, episode_data, subtitle_files)
    except Exception as e:
        print(f"  ✗ YouTube failed: {e}")
        results["youtube"] = f"FAILED: {e}"

    try:
        print("  → Facebook (full video)...")
        results["facebook"] = upload_to_facebook(video_path, episode_data)
    except Exception as e:
        print(f"  ✗ Facebook failed: {e}")
        results["facebook"] = f"FAILED: {e}"

    try:
        print("  → Instagram Reels (90-sec trailer)...")
        results["instagram"] = upload_reel_to_instagram(trailer_path, episode_data)
    except Exception as e:
        print(f"  ✗ Instagram failed: {e}")
        results["instagram"] = f"FAILED: {e}"

    try:
        print("  → TikTok (90-sec trailer)...")
        results["tiktok"] = upload_to_tiktok(trailer_path, episode_data)
    except Exception as e:
        print(f"  ✗ TikTok failed: {e}")
        results["tiktok"] = f"FAILED: {e}"

    # ── Update website content ────────────────────────────────
    try:
        update_website(episode_data, episode_number, merch_products, results)
    except Exception as e:
        print(f"Website content update failed (non-fatal): {e}")

    # ── Apply character visual state updates ──────────────────
    visual_updates = episode_data.get("character_visual_state_updates", {})
    if visual_updates:
        try:
            _apply_visual_state_updates(episode_number, visual_updates)
            print(f"Visual state updated for: {', '.join(visual_updates.keys())}")
        except Exception as e:
            print(f"Visual state update failed (non-fatal): {e}")

    # ── Save episode to bible ─────────────────────────────────
    save_episode(episode_number, {
        "episode_number": episode_number,
        "title": episode_data["title"],
        "logline": episode_data["logline"],
        "summary": episode_data["episode_summary"],
        "cliffhanger": episode_data["cliffhanger"],
        "character_updates": episode_data.get("character_state_updates", {}),
        "hooks_planted": [h["id"] for h in episode_data.get("new_hooks_planted", [])],
        "hooks_paid_off": episode_data.get("hooks_paid_off", []),
        "publish_results": results,
    })

    increment_episode_number()

    print(f"\n{'='*60}")
    print(f"  Episode {episode_number} Complete!")
    print(f"  Title: {episode_data['title']}")
    print(f"  Cliffhanger: {episode_data['cliffhanger']}")
    print(f"\n  Platform results:")
    for platform, result in results.items():
        status = "✓" if not str(result).startswith("FAILED") else "✗"
        print(f"    {status} {platform}: {result}")
    print(f"{'='*60}\n")

    failed = [p for p, r in results.items() if str(r).startswith("FAILED")]
    if failed:
        print(f"WARNING: {len(failed)} platform(s) failed: {', '.join(failed)}")
        sys.exit(1)


def run_generate_only():
    """
    Steps 1-6 only: generate story, voice, images, subtitles, video, trailer.
    Writes story data and media to disk — does NOT publish anywhere.
    Used by weekly-publish.yml --mode generate so the trailer can be uploaded
    to GitHub Releases before publishing starts.
    """
    episode_number = get_episode_number()
    print(f"\n{'='*60}")
    print(f"  ARION WORLD — Episode {episode_number} — GENERATE PHASE")
    print(f"{'='*60}\n")

    episode_dir = WORK_DIR / f"ep{episode_number:03d}"
    audio_dir = episode_dir / "audio"
    images_dir = episode_dir / "images"
    subs_dir = episode_dir / "subtitles"
    video_path = episode_dir / f"arion_world_ep{episode_number:03d}.mp4"
    trailer_path = episode_dir / f"arion_world_ep{episode_number:03d}_trailer.mp4"

    episode_data_path = episode_dir / "episode_data.json"

    print("Step 1/6 — Generating episode script with Claude...")
    episode_data = generate_episode(episode_number)
    episode_dir.mkdir(parents=True, exist_ok=True)
    episode_data_path.write_text(json.dumps(episode_data, indent=2))
    print(f"Episode '{episode_data['title']}' generated. {len(episode_data['scenes'])} scenes.")

    print("\nStep 2/6 — Generating narration audio with ElevenLabs...")
    audio_files = generate_narration(episode_data, audio_dir)

    print("\nStep 3/6 — Generating scene images with Replicate SDXL...")
    image_files = generate_all_images(episode_data, images_dir)

    print("\nStep 4/6 — Generating subtitles + translations...")
    subtitle_files = generate_subtitles(episode_data, audio_files, subs_dir)
    en_srt = subtitle_files.get("EN")

    print("\nStep 5/6 — Assembling 1-hour video with FFmpeg...")
    music = find_background_music()
    assemble_video(episode_data, image_files, audio_files, video_path, music)

    print("\nStep 6/6 — Creating 2-minute portrait trailer...")
    create_portrait_trailer(video_path, trailer_path, subtitle_file=en_srt)

    # Write trailer path to a well-known file for the publish phase to read
    (episode_dir / "trailer_path.txt").write_text(str(trailer_path))
    print(f"\nGenerate phase complete. Trailer: {trailer_path}")
    print("Upload the trailer to GitHub Releases, then run --mode publish")


def run_publish_only():
    """
    Steps 7+: publish to platforms, update website, save to bible.
    Reads episode_data.json and media from disk (written by run_generate_only).
    TRAILER_PUBLIC_URL must be set in the environment before calling this.
    """
    episode_number = get_episode_number()
    episode_dir = WORK_DIR / f"ep{episode_number:03d}"
    episode_data_path = episode_dir / "episode_data.json"

    if not episode_data_path.exists():
        print(f"ERROR: {episode_data_path} not found. Run --mode generate first.")
        sys.exit(1)

    episode_data = json.loads(episode_data_path.read_text())
    video_path = episode_dir / f"arion_world_ep{episode_number:03d}.mp4"
    trailer_path = episode_dir / f"arion_world_ep{episode_number:03d}_trailer.mp4"
    subs_dir = episode_dir / "subtitles"

    # Reconstruct subtitle_files dict from disk
    subtitle_files = {}
    if subs_dir.exists():
        for srt in subs_dir.glob("*.srt"):
            lang = srt.stem.split("_")[-1].upper()
            subtitle_files[lang] = srt

    images_dir = episode_dir / "images"
    image_files = sorted(images_dir.glob("*.png")) if images_dir.exists() else []
    merch_products = []

    print(f"\n{'='*60}")
    print(f"  ARION WORLD — Episode {episode_number} — PUBLISH PHASE")
    print(f"{'='*60}\n")

    # Merch (uses existing images from generate phase)
    try:
        from publish_merch import publish_merch_for_episode
        merch_products = publish_merch_for_episode(episode_data, image_files) or []
        if merch_products:
            print(f"Merch: {len(merch_products)} product(s) created.")
    except Exception as e:
        print(f"Merch generation failed (non-fatal): {e}")

    results = {}

    try:
        print("→ YouTube (full video + subtitles)...")
        results["youtube"] = upload_to_youtube(video_path, episode_data, subtitle_files)
    except Exception as e:
        print(f"✗ YouTube failed: {e}")
        results["youtube"] = f"FAILED: {e}"

    try:
        print("→ Facebook (full video)...")
        results["facebook"] = upload_to_facebook(video_path, episode_data)
    except Exception as e:
        print(f"✗ Facebook failed: {e}")
        results["facebook"] = f"FAILED: {e}"

    try:
        print("→ Instagram Reels (trailer)...")
        results["instagram"] = upload_reel_to_instagram(trailer_path, episode_data)
    except Exception as e:
        print(f"✗ Instagram failed: {e}")
        results["instagram"] = f"FAILED: {e}"

    try:
        print("→ TikTok (trailer)...")
        results["tiktok"] = upload_to_tiktok(trailer_path, episode_data)
    except Exception as e:
        print(f"✗ TikTok failed: {e}")
        results["tiktok"] = f"FAILED: {e}"

    try:
        update_website(episode_data, episode_number, merch_products, results)
    except Exception as e:
        print(f"Website content update failed (non-fatal): {e}")

    visual_updates = episode_data.get("character_visual_state_updates", {})
    if visual_updates:
        try:
            _apply_visual_state_updates(episode_number, visual_updates)
        except Exception as e:
            print(f"Visual state update failed (non-fatal): {e}")

    save_episode(episode_number, {
        "episode_number": episode_number,
        "title": episode_data["title"],
        "logline": episode_data["logline"],
        "summary": episode_data["episode_summary"],
        "cliffhanger": episode_data["cliffhanger"],
        "character_updates": episode_data.get("character_state_updates", {}),
        "hooks_planted": [h["id"] for h in episode_data.get("new_hooks_planted", [])],
        "hooks_paid_off": episode_data.get("hooks_paid_off", []),
        "publish_results": results,
    })
    increment_episode_number()

    failed = [p for p, r in results.items() if str(r).startswith("FAILED")]
    print(f"\nEpisode {episode_number} publish complete.")
    if failed:
        print(f"WARNING: {len(failed)} platform(s) failed: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "generate", "publish"], default="full")
    args = parser.parse_args()

    if args.mode == "generate":
        run_generate_only()
    elif args.mode == "publish":
        run_publish_only()
    else:
        run_pipeline()
