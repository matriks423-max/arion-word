"""
Token refresh + health check for all platform API tokens.

Run manually:   python src/refresh_tokens.py
Run via CI:     triggered monthly by GitHub Actions

What it does:
- Facebook: exchanges current token for a new 60-day long-lived token
- TikTok: uses refresh token to get a new access token (24h lifetime)
- YouTube: refresh token never expires — no action needed
- Prints a warning and creates a GitHub issue if any token needs manual renewal
"""

import os
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import requests


TOKEN_STATE_FILE = Path(__file__).parent.parent / "story_bible" / ".token_state.json"
GRAPH_API = "https://graph.facebook.com/v21.0"
TIKTOK_API = "https://open.tiktokapis.com/v2"


def load_token_state() -> dict:
    if TOKEN_STATE_FILE.exists():
        return json.loads(TOKEN_STATE_FILE.read_text())
    return {}


def save_token_state(state: dict):
    TOKEN_STATE_FILE.write_text(json.dumps(state, indent=2))


def refresh_facebook_token() -> dict:
    """Exchange current Facebook token for a new long-lived token (~60 days)."""
    token = os.environ["FACEBOOK_ACCESS_TOKEN"]
    app_id = os.environ["FACEBOOK_APP_ID"]
    app_secret = os.environ["FACEBOOK_APP_SECRET"]

    resp = requests.get(
        f"{GRAPH_API}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    new_token = data["access_token"]
    expires_in = data.get("expires_in", 5183944)  # ~60 days default

    print(f"Facebook token refreshed. Expires in {expires_in // 86400} days.")
    return {"token": new_token, "expires_in_seconds": expires_in}


def refresh_tiktok_token() -> dict:
    """Use TikTok refresh token to get a new access token."""
    refresh_token = os.environ["TIKTOK_REFRESH_TOKEN"]
    client_key = os.environ["TIKTOK_CLIENT_KEY"]
    client_secret = os.environ["TIKTOK_CLIENT_SECRET"]

    resp = requests.post(
        f"{TIKTOK_API}/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json().get("data", {})
    new_access_token = data["access_token"]
    new_refresh_token = data.get("refresh_token", refresh_token)
    expires_in = data.get("expires_in", 86400)

    print(f"TikTok token refreshed. Access token expires in {expires_in // 3600}h.")
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "expires_in_seconds": expires_in,
    }


def check_facebook_token_validity() -> bool:
    token = os.environ.get("FACEBOOK_ACCESS_TOKEN", "")
    if not token:
        return False
    resp = requests.get(
        f"{GRAPH_API}/me",
        params={"access_token": token, "fields": "id"},
        timeout=15,
    )
    return resp.status_code == 200


def update_github_secret(secret_name: str, value: str):
    """Print instructions for updating a GitHub Secret (requires manual action or gh CLI)."""
    print(f"\n⚠️  ACTION REQUIRED: Update GitHub Secret '{secret_name}'")
    print(f"   Go to: Settings → Secrets → Actions → {secret_name}")
    print(f"   New value: {value[:8]}...{value[-4:]}\n")


def create_github_issue_if_needed(failures: list[str]):
    """Create a GitHub issue if tokens need manual renewal."""
    if not failures:
        return

    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "matriks423-max/arion-world")

    if not token:
        print(f"\n🚨 MANUAL ACTION NEEDED for: {', '.join(failures)}")
        return

    body = (
        "## Token Renewal Required\n\n"
        "The following platform tokens need manual renewal:\n\n"
        + "\n".join(f"- **{f}**" for f in failures)
        + "\n\nPlease renew them and update the GitHub Secrets before the next Monday episode run.\n\n"
        "See `.env.example` for instructions on obtaining each token."
    )

    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"title": "⚠️ Platform tokens need renewal", "body": body, "labels": ["maintenance"]},
        timeout=30,
    )
    if resp.status_code == 201:
        print(f"GitHub issue created: {resp.json()['html_url']}")
    else:
        print(f"Could not create GitHub issue: {resp.status_code}")


def run():
    print("\n=== Arion World — Token Refresh ===\n")
    state = load_token_state()
    failures = []
    new_env_values = {}

    # ── Facebook ──────────────────────────────────────────────
    print("Checking Facebook token...")
    if not check_facebook_token_validity():
        print("Facebook token invalid or missing — cannot auto-refresh without app credentials.")
        failures.append("FACEBOOK_ACCESS_TOKEN")
    else:
        try:
            result = refresh_facebook_token()
            new_env_values["FACEBOOK_ACCESS_TOKEN"] = result["token"]
            state["facebook_refreshed_at"] = datetime.now(timezone.utc).isoformat()
            update_github_secret("FACEBOOK_ACCESS_TOKEN", result["token"])
        except Exception as e:
            print(f"Facebook refresh failed: {e}")
            failures.append("FACEBOOK_ACCESS_TOKEN")

    # ── TikTok ────────────────────────────────────────────────
    print("Checking TikTok token...")
    tiktok_refresh = os.environ.get("TIKTOK_REFRESH_TOKEN")
    if tiktok_refresh:
        try:
            result = refresh_tiktok_token()
            new_env_values["TIKTOK_ACCESS_TOKEN"] = result["access_token"]
            if result["refresh_token"] != tiktok_refresh:
                new_env_values["TIKTOK_REFRESH_TOKEN"] = result["refresh_token"]
            state["tiktok_refreshed_at"] = datetime.now(timezone.utc).isoformat()
            update_github_secret("TIKTOK_ACCESS_TOKEN", result["access_token"])
        except Exception as e:
            print(f"TikTok refresh failed: {e}")
            failures.append("TIKTOK_ACCESS_TOKEN")
    else:
        print("TIKTOK_REFRESH_TOKEN not set — skipping TikTok refresh.")
        failures.append("TIKTOK_ACCESS_TOKEN (no refresh token configured)")

    # ── YouTube ───────────────────────────────────────────────
    print("YouTube: refresh token never expires — no action needed. ✓")

    # ── Summary ───────────────────────────────────────────────
    save_token_state(state)
    create_github_issue_if_needed(failures)

    print("\n=== Token Refresh Complete ===")
    if failures:
        print(f"⚠️  {len(failures)} token(s) need manual attention: {', '.join(failures)}")
        sys.exit(1)
    else:
        print("✓ All tokens refreshed successfully.")


if __name__ == "__main__":
    run()
