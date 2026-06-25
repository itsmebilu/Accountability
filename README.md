# Accountability Bot

A free, self-hosted alternative to tomorrow.ai: a Telegram bot that pings you
on a schedule (morning run alarm, study reminders, diet check-ins), logs your
replies, and uses Claude to write personalized messages and weekly reviews.

**Cost:** $0 baseline (Telegram is free, GitHub Actions free tier is far more
than this needs). Claude personalization is optional — add a few dollars of
API credit if you want it, or skip it and the bot uses plain template
messages instead.

**How it runs 24/7 without you hosting a server:** GitHub Actions has a free
scheduled-job (cron) feature. It wakes up at the times you set, runs a small
Python script, and goes back to sleep. No server to maintain.

---

## 1. Create your Telegram bot (2 minutes)

1. In Telegram, search for **@BotFather** and start a chat.
2. Send `/newbot`, give it a name and a username (must end in `bot`, e.g. `mystudybot`).
3. BotFather replies with a **token** like `123456789:AAH...` — save it.
4. Search for your new bot by its username and send it any message (e.g. "hi"), so it has a chat to talk to you in.

## 2. Find your chat_id

On your own computer (needs Python installed):

```bash
export TELEGRAM_BOT_TOKEN=paste-your-token-here
python scripts/get_chat_id.py
```

It will print your `chat_id`. Save it.

## 3. Get a free AI API key (for personalized messages)

The bot works with $0 template messages with no key at all. To get
AI-personalized reminders and weekly reviews, set up **one** of these
(it tries Gemini first, then Claude, automatically):

**Option A — Gemini (recommended, genuinely free):**
1. Go to [aistudio.google.com](https://aistudio.google.com) and sign in.
2. Click "Get API key" → "Create API key". No credit card needed.
3. This is separate from any Google AI Pro / Gemini Advanced subscription —
   you don't need one, and having one doesn't give you this key automatically.
4. Free tier covers ~250 requests/day on the model this bot uses — this bot
   needs about 5/day, so you won't get close to the limit.

**Option B — Claude:**
1. Go to [console.anthropic.com](https://console.anthropic.com), create an
   API key. This is a separate, pay-as-you-go product from Claude.ai (the
   chat app) — your Claude.ai plan and its daily message limit don't apply
   here, but a card is required and each call costs a small fraction of a cent.

You can set both if you want Claude as a backup if Gemini's free quota is
ever hit, but one is enough.

## 4. Push this folder to a GitHub repo

1. Create a new repo on GitHub (private is fine, free).
2. Push this whole `accountability-bot` folder to it.

## 5. Add your secrets

In the repo: **Settings → Secrets and variables → Actions → New repository secret**

Add:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `GEMINI_API_KEY` (recommended — free, from step 3 option A)
- `ANTHROPIC_API_KEY` (optional — only if you did step 3 option B)

## 6. Customize your schedule

Edit `config.json` — change the `message_hint` text, add/remove tasks, or
adjust `time_ist`. Then **also update the cron times** in
`.github/workflows/scheduler.yml` to match (GitHub Actions cron is in UTC;
IST is UTC+5:30, so subtract 5:30 from your IST time). The file has comments
showing the conversion for the default schedule.

Commit and push your changes — they take effect on the next scheduled run.

## 7. Test it

Go to the **Actions** tab in your repo → "Accountability Bot" → **Run workflow**
(the `workflow_dispatch` button). Leave the input as `poll`, or type a task
id like `morning_run` to test a specific reminder immediately.

## How it works day-to-day

- At each scheduled time, the bot sends you a Telegram message (an alarm/reminder).
- Just **reply directly in the chat** — "ran 4km, studied 1.5hrs, ate clean" or
  whatever. No special format needed.
- Every 15 minutes, the bot reads new replies and saves them to `data/log.json`
  (committed back into your repo, so it's your permanent record).
- Every Sunday night, it sends a Claude-written weekly review based on that log.

## Known limitations / things to know

- GitHub Actions scheduled workflows can run a few minutes late during high
  platform load — fine for a personal alarm, not millisecond-precise.
- GitHub **disables scheduled workflows automatically if a repo gets zero
  activity for 60 days.** Since this bot commits to the repo regularly, that
  won't happen as long as it's running — just don't disable Actions manually.
- This sends to one chat_id (you). It's not built for multiple users.
- If you'd rather not write/maintain code at all, the no-code equivalent of
  this exact pipeline is **n8n** (self-hostable, free) or **Make.com** (free
  tier, ~1000 ops/month): same idea — a scheduled trigger → an HTTP call to
  Claude's API → a Telegram/WhatsApp send node → a webhook to catch replies.

## Extending it

Ideas if you want to go further:
- Add more tasks to `config.json` (water intake, sleep time, gym, etc).
- Parse replies with Claude into structured fields (km run, hours studied) and
  build a small dashboard or weekly chart from `data/log.json`.
- Add a "streak" counter and have the weekly summary mention it.
- Swap Telegram for WhatsApp using the Twilio WhatsApp API if you'd prefer
  that app (more setup, has a small per-message cost).
