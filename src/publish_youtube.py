import os
import json
import time
from pathlib import Path
import requests


TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
API_URL = "https://www.googleapis.com/youtube/v3"


def _retry(fn, *args, max_attempts=3, **kwargs):
    import time
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            wait = 2 ** attempt
            print(f"  Attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)


def get_access_token() -> str:
    resp = requests.post(TOKEN_URL, data={
        "client_id": os.environ["YOUTUBE_CLIENT_ID"],
        "client_secret": os.environ["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": os.environ["YOUTUBE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]


def build_description(episode_data: dict) -> str:
    ep_num = episode_data["episode_number"]
    title = episode_data["title"]
    logline = episode_data["logline"]
    cliffhanger_hint = "Watch until the end — something changes everything."

    website_url = os.environ.get("ARION_WEBSITE_URL", "").strip()
    website_line = (
        f"\n🌐 Full story world, character profiles & mysteries: {website_url}\n"
        if website_url else ""
    )

    return f"""Episode {ep_num}: {title}

{logline}

{cliffhanger_hint}

━━━━━━━━━━━━━━━━━━━━━━━━━━━
ARION WORLD is an epic animated story series set in a universe where time is broken and every truth is a lie waiting to be remembered.

New episodes every Monday.

Subscribe and hit the bell — the clues are in the details.
{website_line}
#ArionWorld #AnimeStory #EpicFantasy #Storytime
━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""


LANGUAGE_NAMES = {
    "EN": "English", "ES": "Spanish", "PT": "Portuguese",
    "FR": "French", "DE": "German", "JA": "Japanese",
}


def upload_captions(video_id: str, subtitle_files: dict[str, Path], token: str):
    """Upload SRT subtitle tracks to a YouTube video."""
    headers = {"Authorization": f"Bearer {token}"}
    for lang, srt_path in subtitle_files.items():
        if not srt_path.exists():
            continue
        lang_lower = lang.lower()
        lang_name = LANGUAGE_NAMES.get(lang, lang)
        try:
            resp = requests.post(
                f"{API_URL}/captions?part=snippet",
                headers=headers,
                params={
                    "videoId": video_id,
                    "part": "snippet",
                },
                files={
                    "snippet": (None, json.dumps({
                        "snippet": {
                            "videoId": video_id,
                            "language": lang_lower,
                            "name": lang_name,
                            "isDraft": False,
                        }
                    }), "application/json"),
                    "media": (srt_path.name, srt_path.read_bytes(), "text/plain"),
                },
                timeout=60,
            )
            if resp.status_code in (200, 201):
                print(f"  Subtitles uploaded: {lang}")
            else:
                print(f"  Subtitle upload failed ({lang}): {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            print(f"  Subtitle upload error ({lang}): {e}")


def upload_to_youtube(video_path: Path, episode_data: dict, subtitle_files: dict[str, Path] | None = None) -> str:
    token = get_access_token()
    ep_num = episode_data["episode_number"]
    title = episode_data["title"]

    metadata = {
        "snippet": {
            "title": f"Arion World — Episode {ep_num}: {title}",
            "description": build_description(episode_data),
            "tags": ["ArionWorld", "anime", "fantasy", "story", "epic", "animated story"],
            "categoryId": "24",  # Entertainment
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        }
    }

    headers = {"Authorization": f"Bearer {token}"}
    file_size = video_path.stat().st_size

    # Initiate resumable upload
    def _init_upload():
        resp = requests.post(
            f"{UPLOAD_URL}?uploadType=resumable&part=snippet,status",
            headers={**headers, "Content-Type": "application/json", "X-Upload-Content-Type": "video/mp4",
                     "X-Upload-Content-Length": str(file_size)},
            json=metadata,
            timeout=30
        )
        resp.raise_for_status()
        return resp

    init_resp = _retry(_init_upload)
    upload_uri = init_resp.headers["Location"]

    # Upload in chunks
    chunk_size = 10 * 1024 * 1024  # 10MB
    uploaded = 0

    with open(video_path, "rb") as f:
        while uploaded < file_size:
            chunk = f.read(chunk_size)
            end = uploaded + len(chunk) - 1
            upload_resp = requests.put(
                upload_uri,
                headers={
                    **headers,
                    "Content-Range": f"bytes {uploaded}-{end}/{file_size}",
                    "Content-Type": "video/mp4",
                },
                data=chunk,
                timeout=300
            )

            if upload_resp.status_code in (200, 201):
                video_id = upload_resp.json()["id"]
                print(f"YouTube upload complete: https://youtube.com/watch?v={video_id}")
                if subtitle_files:
                    print("  Uploading subtitle tracks...")
                    upload_captions(video_id, subtitle_files, token)
                return video_id

            if upload_resp.status_code == 308:
                uploaded = int(upload_resp.headers["Range"].split("-")[1]) + 1
                print(f"YouTube upload progress: {uploaded / file_size * 100:.1f}%")
            else:
                upload_resp.raise_for_status()

    raise RuntimeError("YouTube upload ended without completion")
