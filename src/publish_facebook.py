import os
import time
from pathlib import Path
import requests


GRAPH_API = "https://graph.facebook.com/v21.0"


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


def upload_to_facebook(video_path: Path, episode_data: dict) -> str:
    page_id = os.environ["FACEBOOK_PAGE_ID"]
    token = os.environ["FACEBOOK_ACCESS_TOKEN"]
    ep_num = episode_data["episode_number"]
    title = episode_data["title"]

    website_url = os.environ.get("ARION_WEBSITE_URL", "").strip()
    website_line = (
        f"\n🌐 Full story, character profiles & mysteries: {website_url}"
        if website_url else ""
    )

    description = (
        f"Episode {ep_num}: {title}\n\n"
        f"{episode_data['logline']}\n\n"
        f"Arion World — a new episode every Monday. "
        f"Follow the page so you don't miss the clues hidden in every episode. "
        f"What you see today will mean something very different in 100 episodes.\n\n"
        f"#ArionWorld #AnimeStory #EpicFantasy"
        f"{website_line}"
    )

    file_size = video_path.stat().st_size

    # Start resumable upload session
    def _start_session():
        resp = requests.post(
            f"{GRAPH_API}/{page_id}/videos",
            data={
                "upload_phase": "start",
                "file_size": file_size,
                "access_token": token,
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp

    start_resp = _retry(_start_session)
    session = start_resp.json()
    upload_session_id = session["upload_session_id"]

    # Upload chunks
    chunk_size = 10 * 1024 * 1024
    start_offset = int(session["start_offset"])
    end_offset = int(session["end_offset"])

    with open(video_path, "rb") as f:
        while True:
            f.seek(start_offset)
            chunk = f.read(end_offset - start_offset)
            if not chunk:
                break

            transfer_resp = requests.post(
                f"{GRAPH_API}/{page_id}/videos",
                data={
                    "upload_phase": "transfer",
                    "upload_session_id": upload_session_id,
                    "start_offset": start_offset,
                    "access_token": token,
                },
                files={"video_file_chunk": ("chunk", chunk, "application/octet-stream")},
                timeout=300
            )
            transfer_resp.raise_for_status()
            offsets = transfer_resp.json()
            start_offset = int(offsets["start_offset"])
            end_offset = int(offsets["end_offset"])

            if start_offset == end_offset:
                break

            print(f"Facebook upload progress: {start_offset / file_size * 100:.1f}%")

    # Finish upload
    finish_resp = requests.post(
        f"{GRAPH_API}/{page_id}/videos",
        data={
            "upload_phase": "finish",
            "upload_session_id": upload_session_id,
            "access_token": token,
            "title": f"Arion World — Episode {ep_num}: {title}",
            "description": description,
            "published": "true",
        },
        timeout=60
    )
    finish_resp.raise_for_status()
    video_id = finish_resp.json().get("video_id", "unknown")
    print(f"Facebook upload complete: video_id={video_id}")
    return video_id
