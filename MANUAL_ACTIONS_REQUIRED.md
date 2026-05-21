# Arion World — Manual Setup Required

These items cannot be automated and require your personal action.
Check them off as you complete them.

## Critical (do before first run)

- [ ] **Printful account**: Create free account at printful.com, get API key, add as GitHub Secret `PRINTFUL_API_KEY`
- [ ] **Discord server**: Create server at discord.com, create channels: #announcements, #episodes, #theories, #fan-art, #general. Enable Community mode.
- [ ] **Discord bot**: Go to discord.com/developers, create Application "Arion World Bot", add Bot, copy token → GitHub Secret `DISCORD_BOT_TOKEN`. Invite bot to your server with permissions: Send Messages, Embed Links, Read Message History.
- [ ] **Discord announcement channel**: Copy channel ID of #announcements → GitHub Secret `DISCORD_ANNOUNCEMENT_CHANNEL_ID`
- [ ] **Contact email**: Create contact@arionworld.com (or use Gmail: arionworld.contact@gmail.com). Set as GitHub Secret `CONTACT_EMAIL` and update ChatWidget.astro
- [ ] **Formspree**: Create free account at formspree.io, create form, copy Form ID → replace `FORMSPREE_FORM_ID` in website/src/components/ContactForm.astro
- [ ] **Website URL**: Once domain is set up, add GitHub Secret `ARION_WEBSITE_URL` (e.g. https://arionworld.com)
- [x] **Instagram TRAILER_PUBLIC_URL**: ✅ SOLVED — the pipeline now uploads the trailer to a GitHub Release before publishing. The public release asset URL is passed automatically as `TRAILER_PUBLIC_URL`. No cloud storage setup needed. Requires the repo to be public (which it is).

## Additional GitHub Secrets Needed

These are required by the monthly token refresh workflow:
- `FACEBOOK_APP_ID` — from Meta Developer Portal
- `FACEBOOK_APP_SECRET` — from Meta Developer Portal  
- `TIKTOK_CLIENT_KEY` — from TikTok Developer Portal
- `TIKTOK_CLIENT_SECRET` — from TikTok Developer Portal
- `TIKTOK_REFRESH_TOKEN` — from TikTok OAuth flow
- `DISCORD_WEBHOOK_URL` — (optional) from Discord channel → Edit → Integrations → Webhooks. Enables episode announcements via the weekly-publish workflow without hosting the bot.

## Nice to Have (after launch)

- [ ] **Custom domain**: Point arionworld.com to your GitHub Pages or Vercel deployment
- [ ] **Printful store**: Connect Printful to your website URL in Printful dashboard
- [ ] **YouTube channel art**: Upload banner and profile picture that match the Arion World visual style
- [ ] **Link in bio**: Set Instagram bio link to your website URL
- [ ] **Discord roles**: Set up Watcher, Theorist, Supporter roles with channel access tiers

## Discord Bot Deployment (free options)

The bot needs to run 24/7. Three free options:

### Option A — Railway.app (Recommended, easiest)
1. Go to railway.app, sign in with GitHub
2. New Project → Deploy from GitHub Repo → select matriks423-max/jobsy-lv
3. Set Root Directory to `discord_bot`
4. Add environment variables: DISCORD_BOT_TOKEN, DISCORD_ANNOUNCEMENT_CHANNEL_ID, CONTACT_EMAIL
5. Set ARION_CONTENT_DIR to `/app/content` and mount a volume OR just remove the volume and have the bot fetch from GitHub raw content URLs instead
6. Deploy — Railway free tier gives $5/month credit (enough for a lightweight bot)

### Option B — Fly.io (Free tier, more control)
1. Install flyctl: `curl -L https://fly.io/install.sh | sh`
2. `cd discord_bot && fly launch`
3. Set secrets: `fly secrets set DISCORD_BOT_TOKEN=xxx DISCORD_ANNOUNCEMENT_CHANNEL_ID=xxx`
4. Deploy: `fly deploy`
5. Free tier: 3 shared-CPU VMs, 256MB RAM each

### Option C — Self-hosted (VPS or home server)
```bash
cd discord_bot
cp .env.example .env
# Fill in .env with your values
docker-compose up -d
```

### GitHub Actions Webhook (alternative to always-on bot)
Instead of 24/7 hosting, use a Discord webhook for episode announcements only.
Add `DISCORD_WEBHOOK_URL` secret (from Discord channel → Edit → Integrations → Webhooks).
The weekly-publish workflow can POST to this URL directly — no bot hosting needed for announcements.
