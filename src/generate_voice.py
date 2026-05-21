import os
import subprocess
import time
from pathlib import Path
import requests


ELEVENLABS_API = "https://api.elevenlabs.io/v1"


def generate_narration(episode_data: dict, output_dir: Path) -> list[Path]:
    api_key = os.environ["ELEVENLABS_API_KEY"]
    voice_id = os.environ["ELEVENLABS_VOICE_ID"]

    output_dir.mkdir(parents=True, exist_ok=True)
    audio_files = []

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }

    for scene in episode_data["scenes"]:
        scene_num = scene["scene_number"]
        narration_text = scene["narration"]

        # Add dialogue lines inline with narration pauses
        dialogue_lines = scene.get("dialogue", [])
        if dialogue_lines:
            for line in dialogue_lines:
                tone = line.get('tone', '')
                tone_prefix = {
                    'whispered': 'In a low voice, ', 'angry': 'With barely contained fury, ',
                    'desperate': 'Desperately, ', 'cold': 'Coldly, ', 'quiet': 'Quietly, '
                }.get(tone, '')
                character = line.get('character', 'Unknown')
                spoken = line.get('line', '')
                if spoken:
                    narration_text += f"\n\n{tone_prefix}{character}: — {spoken}"

        payload = {
            "text": narration_text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.75,
                "similarity_boost": 0.85,
                "style": 0.3,
                "use_speaker_boost": True
            }
        }

        url = f"{ELEVENLABS_API}/text-to-speech/{voice_id}"
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()

        audio_path = output_dir / f"scene_{scene_num:02d}.mp3"
        audio_path.write_bytes(resp.content)
        audio_files.append(audio_path)

        print(f"Generated audio for scene {scene_num}")
        time.sleep(0.5)  # Respect rate limits

    return audio_files


def get_voice_duration_seconds(audio_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())
