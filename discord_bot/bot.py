"""
Arion World Discord Bot

Features:
  !episode   — latest episode info
  !characters — main character list
  !mystery   — random open mystery
  !lore      — random world lore fact
  !contact   — business contact email
  /ask       — FAQ slash command

Auto-posts episode announcements to DISCORD_ANNOUNCEMENT_CHANNEL_ID
when a new episode JSON is detected.

Env vars required:
  DISCORD_BOT_TOKEN                 — bot token from Discord Developer Portal
  DISCORD_ANNOUNCEMENT_CHANNEL_ID   — channel ID for episode announcements

Optional:
  ARION_CONTENT_DIR   — path to website/public/content/ (default: auto-detected)
  CONTACT_EMAIL       — business contact email address
"""

import os
import json
import random
import asyncio
import logging
from pathlib import Path

import disnake
from disnake.ext import commands, tasks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("arion-bot")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
ANNOUNCEMENT_CHANNEL_ID = int(os.environ.get("DISCORD_ANNOUNCEMENT_CHANNEL_ID", "0"))
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "contact@arionworld.com")

# Resolve content directory: try env override, then walk up from __file__
_env_content_dir = os.environ.get("ARION_CONTENT_DIR", "").strip()
if _env_content_dir and Path(_env_content_dir).is_dir():
    CONTENT_DIR = Path(_env_content_dir)
else:
    # Assume bot.py lives in discord_bot/ next to website/
    _bot_dir = Path(__file__).parent
    CONTENT_DIR = _bot_dir.parent / "website" / "public" / "content"

logger.info("Content directory: %s", CONTENT_DIR)

EPISODE_COUNTER_PATH = (
    Path(__file__).parent.parent / "story_bible" / ".episode_counter"
)

# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

_WEBSITE_URL = os.environ.get("ARION_WEBSITE_URL", "").rstrip("/")


def _load_json(filename: str, fallback=None):
    # 1. Try local filesystem (works when running in the same repo)
    path = CONTENT_DIR / filename
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("Failed to read local %s: %s", path, e)

    # 2. Fallback: fetch from public website URL (works on Railway/Fly.io)
    if _WEBSITE_URL:
        import urllib.request
        try:
            url = f"{_WEBSITE_URL}/content/{filename}"
            with urllib.request.urlopen(url, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            logger.warning("Failed to fetch %s from website: %s", filename, e)

    logger.warning("Content unavailable: %s", filename)
    return fallback


def _latest_episode_number() -> int:
    """Read episode counter from file, fallback to episodes.json."""
    if EPISODE_COUNTER_PATH.exists():
        try:
            return int(EPISODE_COUNTER_PATH.read_text().strip())
        except Exception:
            pass
    data = _load_json("episodes.json", {"episodes": []})
    episodes = data.get("episodes", [])
    if episodes:
        return max(ep.get("episode_number", 0) for ep in episodes)
    return 0


# ---------------------------------------------------------------------------
# Bot setup
# ---------------------------------------------------------------------------

intents = disnake.Intents.default()
intents.message_content = True

# disnake's commands.Bot supports both prefix (!commands) and slash (/commands)
bot = commands.Bot(command_prefix="!", intents=intents)

# Track last seen episode to detect new ones for auto-announcement
_last_announced_episode: int = 0


# ---------------------------------------------------------------------------
# Prefix commands
# ---------------------------------------------------------------------------

@bot.command(name="episode")
async def cmd_episode(ctx: commands.Context):
    """Post latest episode info."""
    data = _load_json("episodes.json", {"episodes": []})
    episodes = data.get("episodes", [])
    if not episodes:
        await ctx.send("No episodes published yet — check back soon!")
        return

    ep = max(episodes, key=lambda e: e.get("episode_number", 0))
    ep_num = ep.get("episode_number", "?")
    title = ep.get("title", "Unknown")
    logline = ep.get("logline", "")
    youtube_url = ep.get("youtube_url", "")

    embed = disnake.Embed(
        title=f"Episode {ep_num}: {title}",
        description=logline,
        color=0xD4AF37,  # gold
    )
    embed.set_author(name="Arion World")
    if youtube_url:
        embed.add_field(name="Watch", value=youtube_url, inline=False)
    embed.set_footer(text="New episode every Monday")
    await ctx.send(embed=embed)


@bot.command(name="characters")
async def cmd_characters(ctx: commands.Context):
    """List main characters with brief descriptions."""
    data = _load_json("characters_public.json", {"characters": []})
    characters = data.get("characters", [])
    if not characters:
        await ctx.send("Character profiles are still being uncovered...")
        return

    embed = disnake.Embed(
        title="Arion World — Characters",
        description="Profiles update as the story reveals them.",
        color=0xD4AF37,
    )
    embed.set_author(name="Arion World")

    for char in characters[:10]:  # cap at 10 to avoid embed overflow
        name = char.get("name", "Unknown")
        role = char.get("role", "")
        desc = char.get("public_description", "Unknown")
        status = char.get("status", "unknown")
        field_name = f"{name}  [{status}]" if role == "" else f"{name} — {role}  [{status}]"
        field_value = desc[:200] + ("…" if len(desc) > 200 else "")
        embed.add_field(name=field_name, value=field_value, inline=False)

    if len(characters) > 10:
        embed.set_footer(text=f"Showing 10 of {len(characters)} characters. Visit the website for full profiles.")

    await ctx.send(embed=embed)


@bot.command(name="mystery")
async def cmd_mystery(ctx: commands.Context):
    """Post a random open mystery."""
    data = _load_json("mysteries.json", {"open": []})
    # mysteries.json uses {"open": [...], "solved": [...]}
    open_mysteries = data.get("open", data.get("mysteries", []))

    if not open_mysteries:
        await ctx.send("All mysteries are being kept in the shadows for now...")
        return

    mystery = random.choice(open_mysteries)
    question = mystery.get("question", mystery.get("title", "Unknown mystery"))
    first_appeared = mystery.get("first_raised_episode", mystery.get("first_appeared_episode"))
    hint = mystery.get("hint", "")

    embed = disnake.Embed(
        title="Open Mystery",
        description=f"**{question}**",
        color=0x6B46C1,  # purple
    )
    embed.set_author(name="Arion World")
    if first_appeared:
        embed.add_field(name="First appeared", value=f"Episode {first_appeared}", inline=True)
    if hint:
        embed.add_field(name="Clue", value=f"*{hint}*", inline=False)
    embed.set_footer(text="What do YOU think the answer is?")

    await ctx.send(embed=embed)


@bot.command(name="lore")
async def cmd_lore(ctx: commands.Context):
    """Post a random lore fact about the world."""
    # world_public.json uses factions_known / locations_known; overview is a lore string
    data = _load_json("world_public.json", {"factions_known": [], "locations_known": []})

    factions = data.get("factions_known", data.get("factions", []))
    locations = data.get("locations_known", data.get("locations", []))

    lore_pool = []
    overview = data.get("overview", "")
    if overview:
        lore_pool.append(overview)

    for f in factions:
        if isinstance(f, dict) and f.get("description"):
            lore_pool.append(f"**{f.get('name', 'Unknown faction')}**: {f['description']}")

    for loc in locations:
        if isinstance(loc, dict) and loc.get("description"):
            lore_pool.append(f"**{loc.get('name', 'Unknown location')}**: {loc['description']}")

    if not lore_pool:
        await ctx.send("The lore of Arion World is still being uncovered. Stay tuned.")
        return

    fact = random.choice(lore_pool)

    embed = disnake.Embed(
        title="Arion World Lore",
        description=fact[:2000],
        color=0x2D6A4F,  # deep green
    )
    embed.set_author(name="Arion World")
    embed.set_footer(text="Every truth is a lie waiting to be remembered.")
    await ctx.send(embed=embed)


@bot.command(name="contact")
async def cmd_contact(ctx: commands.Context):
    """Show business contact information."""
    embed = disnake.Embed(
        title="Arion World — Business Contact",
        description=(
            "For business inquiries, collaboration proposals, or licensing:\n\n"
            f"📧 **{CONTACT_EMAIL}**\n\n"
            "We welcome:\n"
            "• Brand partnerships & sponsorships\n"
            "• Merchandise collaboration\n"
            "• Fan art & creative collaborations\n"
            "• Press & media inquiries"
        ),
        color=0xD4AF37,
    )
    embed.set_author(name="Arion World")
    await ctx.send(embed=embed)


# ---------------------------------------------------------------------------
# Slash command: /ask
# ---------------------------------------------------------------------------

FAQ_ANSWERS = {
    "What is Arion World?": (
        "Arion World is an epic anime-style fantasy story series set in a universe where time is "
        "broken and every truth is a lie waiting to be remembered. New episodes every Monday."
    ),
    "When do episodes come out?": (
        "New episodes are released every Monday. Subscribe on YouTube and follow on social media "
        "so you never miss a clue hidden in each episode."
    ),
    "Where can I watch?": (
        "Full episodes are on YouTube at youtube.com/@ArionWorld\n"
        "Short clips and trailers on TikTok and Instagram @ArionWorld\n"
        "New episode every Monday!"
    ),
    "How do I buy merch?": (
        "Arion World merch is available on our website — t-shirts, posters, and mugs featuring "
        "artwork from key episodes. Print-on-demand, no stock issues. Check the website for the "
        "latest designs."
    ),
    "How do I contact for business?": (
        f"For business inquiries, collaborations, or licensing, email: **{CONTACT_EMAIL}**\n"
        "We respond within 48 hours."
    ),
}


@bot.slash_command(name="ask", description="Ask a question about Arion World")
async def slash_ask(
    inter: disnake.ApplicationCommandInteraction,
    question: str = commands.Param(
        description="Choose a frequently asked question",
        choices=list(FAQ_ANSWERS.keys()),
    ),
):
    answer = FAQ_ANSWERS.get(question, "That question is still shrouded in mystery...")
    embed = disnake.Embed(
        title=question,
        description=answer,
        color=0xD4AF37,
    )
    embed.set_author(name="Arion World")
    await inter.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# Auto-announcement: check for new episodes every 5 minutes
# ---------------------------------------------------------------------------

@tasks.loop(minutes=5)
async def check_new_episode():
    global _last_announced_episode
    if not ANNOUNCEMENT_CHANNEL_ID:
        return

    latest = _latest_episode_number()
    if latest <= _last_announced_episode:
        return

    # New episode detected
    data = _load_json("episodes.json", {"episodes": []})
    episodes = data.get("episodes", [])
    ep = next(
        (e for e in episodes if e.get("episode_number") == latest),
        None,
    )
    if ep is None:
        return

    channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if channel is None:
        logger.warning("Announcement channel %s not found.", ANNOUNCEMENT_CHANNEL_ID)
        return

    ep_num = ep.get("episode_number", latest)
    title = ep.get("title", "New Episode")
    logline = ep.get("logline", "")
    youtube_url = ep.get("youtube_url", "https://youtube.com/@ArionWorld")

    embed = disnake.Embed(
        title=f"New Episode — {ep_num}: {title}",
        description=logline,
        color=0xD4AF37,
        url=youtube_url,
    )
    embed.set_author(name="Arion World")
    embed.add_field(name="Watch Now", value=youtube_url, inline=False)
    embed.set_footer(text="New episode every Monday. The clues are in the details.")

    try:
        await channel.send(
            content="@everyone A new episode of Arion World is out! 🎬",
            embed=embed,
        )
        _last_announced_episode = latest
        logger.info("Announced episode %s in channel %s", latest, ANNOUNCEMENT_CHANNEL_ID)
    except Exception as e:
        logger.error("Failed to post announcement: %s", e)


@check_new_episode.before_loop
async def before_check():
    await bot.wait_until_ready()
    # Set baseline so we don't re-announce old episodes on startup
    global _last_announced_episode
    _last_announced_episode = _latest_episode_number()
    logger.info("Episode baseline set to %s", _last_announced_episode)


# ---------------------------------------------------------------------------
# Bot events
# ---------------------------------------------------------------------------

@bot.event
async def on_ready():
    logger.info("Arion World Bot ready as %s (ID: %s)", bot.user, bot.user.id)
    # disnake registers slash commands automatically — no manual sync needed
    check_new_episode.start()


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    logger.error("Command error in %s: %s", ctx.command, error)
    await ctx.send(f"Something went wrong: {error}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError(
            "DISCORD_BOT_TOKEN not set. "
            "See discord_bot/requirements.txt and MANUAL_ACTIONS_REQUIRED.md."
        )
    bot.run(TOKEN)
