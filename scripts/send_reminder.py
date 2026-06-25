#!/usr/bin/env python3
"""
Send a single goal-aware reminder to Telegram (or ntfy if configured).

Usage:
    python send_reminder.py <goal>

<goal> can be: running, gym, study, diet, evening_checkin

The message is personalized using AI + recent log data and asks for
the specific structured info needed to track that goal.
"""
import json
import os
import sys
import urllib.parse
import urllib.request

import ai_provider

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_config():
    with open(os.path.join(ROOT, "config.json")) as f:
        return json.load(f)


def load_recent_log(n=7):
    path = os.path.join(ROOT, "data", "log.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        entries = json.load(f)
    return entries[-n:]


def build_prompt(goal, config, recent):
    g = config.get("goals", {})
    history = "\n".join(
        f"- {e['timestamp']}: {e.get('raw', e.get('text',''))} | parsed: {json.dumps(e.get('parsed',{}))}"
        for e in recent
    ) or "No recent entries."

    prompts = {
        "running": (
            f"You are a running coach texting someone. Their goal is {g.get('running',{}).get('weekly_km',30)}km/week "
            f"across {g.get('running',{}).get('runs_per_week',4)} runs. "
            f"Write ONE motivating push (max 2 sentences, 1 emoji max) for their morning run. "
            f"Recent log:\n{history}\n\nReply ONLY with the message."
        ),
        "gym": (
            f"You are a gym coach texting someone. They do upper/lower splits, "
            f"{g.get('gym',{}).get('sessions_per_week',4)} sessions/week. "
            f"Look at their recent log to figure out if today should be upper or lower, and write "
            f"ONE short motivating message (max 2 sentences, 1 emoji). "
            f"Recent log:\n{history}\n\nReply ONLY with the message."
        ),
        "study": (
            f"You are a study coach. Their weekly study goals: "
            + ", ".join(f"{s['name']} {s['weekly_hours']}h" for s in g.get('study',{}).get('subjects',[]))
            + f". Write ONE focused study prompt (max 2 sentences, 1 emoji). "
            f"Recent log:\n{history}\n\nReply ONLY with the message."
        ),
        "diet": (
            f"You are a nutrition coach. Their daily protein target is "
            f"{g.get('diet',{}).get('daily_protein_g',150)}g. "
            f"Write ONE short diet check-in nudge asking how protein intake is going (max 2 sentences, 1 emoji). "
            f"Recent log:\n{history}\n\nReply ONLY with the message."
        ),
        "evening_checkin": (
            f"You are an accountability coach. The user tracks: running (goal "
            f"{g.get('running',{}).get('weekly_km',30)}km/week), gym (upper/lower split), "
            f"study subjects ({', '.join(s['name'] for s in g.get('study',{}).get('subjects',[]))}), "
            f"and daily protein (target {g.get('diet',{}).get('daily_protein_g',150)}g).\n\n"
            f"Write a conversational evening check-in message (2-3 sentences) asking them to share "
            f"today's: run distance (or 0), gym session (upper/lower or rest), hours studied per subject, "
            f"and protein intake. Make it feel like a friend asking, not a form. 1 emoji max.\n\n"
            f"Recent log:\n{history}\n\nReply ONLY with the message."
        ),
    }
    return prompts.get(goal)


FALLBACKS = {
    "running":         "🏃 Morning run time! Lace up and get out — even an easy 4km counts toward your weekly goal.",
    "gym":             "💪 Gym session today — check your split and make it count.",
    "study":           "📖 Study block starting now — pick your subject and dive in.",
    "diet":            "🥗 Midday check — how's your protein looking? Don't let it slip.",
    "evening_checkin": "👋 Day's almost done! Drop a quick note: km run, gym session, study hours per subject, and protein intake.",
}


def send_telegram(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20)


def send_ntfy(text, title="Accountability"):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=text.encode(),
        headers={"Title": title, "Priority": "high"},
    )
    urllib.request.urlopen(req, timeout=10)


def main():
    if len(sys.argv) < 2:
        print("Usage: send_reminder.py <goal>", file=sys.stderr)
        sys.exit(1)

    goal = sys.argv[1]
    config = load_config()
    recent = load_recent_log()
    prompt = build_prompt(goal, config, recent)
    message = (ai_provider.generate(prompt) if prompt else None) or FALLBACKS.get(goal, "Time to check in!")

    # Send to whichever channel(s) are configured
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        send_telegram(message)
    if os.environ.get("NTFY_TOPIC"):
        goal_titles = {"running":"🏃 Run time","gym":"💪 Gym time","study":"📖 Study time","diet":"🥗 Diet check","evening_checkin":"📋 Daily check-in"}
        send_ntfy(message, goal_titles.get(goal, "Reminder"))

    print(f"Sent [{goal}]: {message}")


if __name__ == "__main__":
    main()
