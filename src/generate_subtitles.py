"""
Generate SRT subtitles from episode narration audio + translate via DeepL.

Flow:
  1. Read actual audio durations (ffprobe) to get precise scene timing
  2. Chunk narration text into ~5-second subtitle cards
  3. Translate EN SRT to up to 5 languages via DeepL free tier
     (500k chars/month free — one 1-hr episode ≈ 60k chars → ~8 langs free)

Returns a {lang_code: Path} dict for use by publish_youtube and create_trailer.
"""

import os
import re
import subprocess
from pathlib import Path

import requests

TARGET_LANGUAGES = ["ES", "PT", "FR", "DE", "JA"]
MAX_LINE_CHARS = 42
SUBTITLE_CHUNK_SECONDS = 5


def _audio_duration(path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    return float(result.stdout.strip())


def _ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _wrap(text: str) -> str:
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= MAX_LINE_CHARS:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines[:2])  # max 2 lines per card


def _build_srt(episode_data: dict, audio_files: list[Path]) -> str:
    entries = []
    index = 1
    cursor = 0.0

    for scene, audio in zip(episode_data["scenes"], audio_files):
        if not audio.exists():
            continue
        duration = _audio_duration(audio)
        text = scene.get("narration", "").strip()
        if not text:
            cursor += duration
            continue

        words = text.split()
        wps = len(words) / duration if duration > 0 else 3.0
        chunk_words = max(1, int(wps * SUBTITLE_CHUNK_SECONDS))
        chunks = [words[i:i + chunk_words] for i in range(0, len(words), chunk_words)]
        chunk_dur = duration / len(chunks)

        for chunk in chunks:
            start, end = cursor, cursor + chunk_dur
            body = _wrap(" ".join(chunk))
            entries.append(f"{index}\n{_ts(start)} --> {_ts(end)}\n{body}")
            index += 1
            cursor += chunk_dur

    return "\n\n".join(entries)


def _translate(srt: str, lang: str, api_key: str) -> str:
    lines = srt.split("\n")
    text_indices, texts = [], []

    for i, line in enumerate(lines):
        if re.match(r"^\d+$", line.strip()) or "-->" in line or not line.strip():
            continue
        text_indices.append(i)
        texts.append(line.strip())

    if not texts:
        return srt

    resp = requests.post(
        "https://api-free.deepl.com/v2/translate",
        data={"auth_key": api_key, "text": texts, "source_lang": "EN", "target_lang": lang},
        timeout=60,
    )
    resp.raise_for_status()
    translated = [t["text"] for t in resp.json()["translations"]]

    result = lines.copy()
    for pos, t in zip(text_indices, translated):
        result[pos] = t
    return "\n".join(result)


def generate_subtitles(
    episode_data: dict,
    audio_files: list[Path],
    output_dir: Path,
) -> dict[str, Path]:
    """
    Build EN SRT then translate to TARGET_LANGUAGES if DEEPL_API_KEY is set.
    Returns {lang_code: srt_path}, always includes "EN".
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    ep = episode_data["episode_number"]

    en_srt = _build_srt(episode_data, audio_files)
    en_path = output_dir / f"ep{ep:03d}_en.srt"
    en_path.write_text(en_srt, encoding="utf-8")
    print(f"Subtitles (EN): {en_path.name}")

    result: dict[str, Path] = {"EN": en_path}

    api_key = os.environ.get("DEEPL_API_KEY")
    if not api_key:
        print("DEEPL_API_KEY not set — skipping translations (set it for multilingual subs)")
        return result

    for lang in TARGET_LANGUAGES:
        try:
            translated = _translate(en_srt, lang, api_key)
            path = output_dir / f"ep{ep:03d}_{lang.lower()}.srt"
            path.write_text(translated, encoding="utf-8")
            result[lang] = path
            print(f"  Subtitles ({lang}): {path.name}")
        except Exception as e:
            print(f"  Subtitle translation failed ({lang}): {e}")

    return result
