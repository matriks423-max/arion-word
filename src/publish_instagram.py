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


def upload_reel_to_instagram(trailer_path: Path, episode_data: dict) -> str:
    """Upload a portrait-format video as an Instagram Reel."""
    account_id = os.environ["INSTAGRAM_ACCOUNT_ID"]
    token = os.environ["FACEBOOK_ACCESS_TOKEN"]
    ep_num = episode_data["episode_number"]

    website_url = os.environ.get("ARION_WEBSITE_URL", "").strip()
    website_line = (
        f"\n🌐 Full story at link in bio | {website_url}"
        if website_url else ""
    )

    caption = (
        f"⚔️ Arion World — Episode {ep_num}: {episode_data['title']}\n\n"
        f"{episode_data['logline']}\n\n"
        f"Full 30-minute episode on YouTube — link in bio.\n\n"
        f"New episode every Monday. The clues are hidden in plain sight. 👁️\n\n"
        f"#ArionWorld #AnimeStory #EpicFantasy #NewEpisode #Anime #Fantasy"
        f"{website_line}"
    )

    # Step 1: Create media container
    def _create_container():
        resp = requests.post(
            f"{GRAPH_API}/{account_id}/media",
            data={
                "media_type": "REELS",
                "video_url": _get_public_video_url(trailer_path),
                "caption": caption,
                "share_to_feed": "true",
                "access_token": token,
            },
            timeout=60
        )
        resp.raise_for_status()
        return resp

    container_resp = _retry(_create_container)
    container_id = container_resp.json()["id"]

    # Step 2: Wait for processing
    for attempt in range(20):
        time.sleep(15)
        status_resp = requests.get(
            f"{GRAPH_API}/{container_id}",
            params={"fields": "status_code,status", "access_token": token},
            timeout=30
        )
        status_resp.raise_for_status()
        status = status_resp.json().get("status_code")
        print(f"Instagram container status: {status}")

        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram media processing failed: {status_resp.json()}")

    # Step 3: Publish
    publish_resp = requests.post(
        f"{GRAPH_API}/{account_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=60
    )
    publish_resp.raise_for_status()
    media_id = publish_resp.json()["id"]
    print(f"Instagram Reel published: {media_id}")
    return media_id


def _get_public_video_url(video_path: Path) -> str:
    # Instagram requires a publicly accessible URL to pull the video from.
    # In the GitHub Actions pipeline, the video is uploaded to a temporary
    # public URL. For now this reads from the TRAILER_PUBLIC_URL env var
    # set by the pipeline after uploading to a CDN or GitHub Releases asset.
    url = os.environ.get("TRAILER_PUBLIC_URL", "").strip()
    if not url:
        raise RuntimeError(
            "TRAILER_PUBLIC_URL not set. Add an upload step to your CI workflow that "
            "uploads the trailer to a public URL and sets this env var. "
            "See MANUAL_ACTIONS_REQUIRED.md for setup instructions."
        )
    return url
