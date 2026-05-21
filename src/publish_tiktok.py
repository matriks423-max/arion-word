import os
import time
from pathlib import Path
import requests


TIKTOK_API = "https://open.tiktokapis.com/v2"


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


def upload_to_tiktok(trailer_path: Path, episode_data: dict) -> str:
    token = os.environ["TIKTOK_ACCESS_TOKEN"]
    ep_num = episode_data["episode_number"]

    title = (
        f"Arion World Ep {ep_num}: {episode_data['title']} "
        f"#ArionWorld #AnimeStory #EpicFantasy #Anime #Fantasy #NewEpisode"
    )[:150]  # TikTok title limit

    website_url = os.environ.get("ARION_WEBSITE_URL", "").strip()
    description = (
        f"Arion World — Episode {ep_num}: {episode_data['title']}. "
        f"{episode_data.get('logline', '')} "
        f"New episode every Monday. #ArionWorld #AnimeStory #EpicFantasy"
    )
    if website_url:
        description += f" | Full story: {website_url}"
    description = description[:2200]  # TikTok description limit

    file_size = trailer_path.stat().st_size

    # Query creator info to get upload constraints
    info_resp = requests.post(
        f"{TIKTOK_API}/post/publish/creator_info/query/",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
        json={},
        timeout=30
    )
    info_resp.raise_for_status()
    creator_info = info_resp.json().get("data", {})
    max_video_post_duration = creator_info.get("max_video_post_duration_sec", 60)

    # Initialise upload
    def _init_upload():
        resp = requests.post(
            f"{TIKTOK_API}/post/publish/video/init/",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
            json={
                "post_info": {
                    "title": title,
                    "description": description,
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                    "video_cover_timestamp_ms": 1000,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": file_size,
                    "total_chunk_count": 1,
                }
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp

    init_resp = _retry(_init_upload)
    init_data = init_resp.json()["data"]
    publish_id = init_data["publish_id"]
    upload_url = init_data["upload_url"]

    # Upload video
    with open(trailer_path, "rb") as f:
        video_data = f.read()

    upload_resp = requests.put(
        upload_url,
        headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
            "Content-Length": str(file_size),
        },
        data=video_data,
        timeout=300
    )
    upload_resp.raise_for_status()

    # Poll for status
    for _ in range(20):
        time.sleep(10)
        status_resp = requests.post(
            f"{TIKTOK_API}/post/publish/status/fetch/",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"},
            json={"publish_id": publish_id},
            timeout=30
        )
        status_resp.raise_for_status()
        status = status_resp.json().get("data", {}).get("status")
        print(f"TikTok publish status: {status}")

        if status == "PUBLISH_COMPLETE":
            print(f"TikTok published successfully: publish_id={publish_id}")
            return publish_id
        if status in ("FAILED", "PUBLISH_FAILED"):
            raise RuntimeError(f"TikTok publish failed: {status_resp.json()}")

    raise TimeoutError("TikTok publish polling timed out")
