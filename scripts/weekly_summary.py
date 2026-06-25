#!/usr/bin/env python3
"""Send a structured weekly review summarising all four goals."""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import ai_provider

ROOT = os.path.join(os.path.dirname(__file__), "..")


def load_config():
    with open(os.path.join(ROOT, "config.json")) as f:
        return json.load(f)


def recent_entries(days=7):
    path = os.path.join(ROOT, "data", "log.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        log = json.load(f)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [e for e in log if datetime.fromisoformat(e["timestamp"]) >= cutoff]


def build_summary_prompt(config, entries):
    g = config.get("goals", {})
    run_goal = g.get("running", {})
    gym_goal = g.get("gym", {})
    study_goal = g.get("study", {})
    diet_goal = g.get("diet", {})

    # Aggregate parsed data
    total_km = sum(e.get("parsed", {}).get("run_km", 0) for e in entries)
    runs = sum(1 for e in entries if e.get("parsed", {}).get("run_km", 0) > 0)
    gym_sessions = [e["parsed"]["gym_session"] for e in entries if e.get("parsed", {}).get("gym_session")]
    avg_protein = (
        sum(e["parsed"].get("protein_g", 0) for e in entries if e.get("parsed", {}).get("protein_g"))
        / max(1, sum(1 for e in entries if e.get("parsed", {}).get("protein_g")))
    )
    study_totals = {}
    for e in entries:
        for subj, mins in (e.get("parsed", {}).get("study") or {}).items():
            study_totals[subj] = study_totals.get(subj, 0) + mins

    subjects = study_goal.get("subjects", [])
    study_summary = "\n".join(
        f"  {s['name']}: {study_totals.get(s['name'],0)//60}h {study_totals.get(s['name'],0)%60}m of {s['weekly_hours']}h target"
        for s in subjects
    )

    context = f"""
Weekly results:
- Running: {total_km:.1f}km / {run_goal.get('weekly_km',30)}km goal, {runs}/{run_goal.get('runs_per_week',4)} runs
- Gym: {len(gym_sessions)}/{gym_goal.get('sessions_per_week',4)} sessions ({', '.join(gym_sessions) or 'none logged'})
- Study:\n{study_summary or '  nothing logged'}
- Protein: avg {avg_protein:.0f}g/day vs {diet_goal.get('daily_protein_g',150)}g target
- Check-ins logged: {len(entries)}

Write a 4-6 sentence weekly review for Telegram. Be warm and direct: celebrate wins, name one gap honestly, give one specific actionable tip for next week. Plain text only.
"""
    return context


def send_telegram(text):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=20)


def send_ntfy(text):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=text.encode(),
        headers={"Title": "📊 Weekly Review", "Priority": "default"},
    )
    urllib.request.urlopen(req, timeout=10)


def main():
    config = load_config()
    entries = recent_entries()
    prompt = build_summary_prompt(config, entries)
    summary = ai_provider.generate(prompt, max_tokens=400) or (
        f"Weekly summary: {len(entries)} check-ins logged. Keep going!"
    )
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        send_telegram(summary)
    if os.environ.get("NTFY_TOPIC"):
        send_ntfy(summary)
    print(f"Sent: {summary}")


if __name__ == "__main__":
    main()
