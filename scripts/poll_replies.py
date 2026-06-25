#!/usr/bin/env python3
"""
Poll Telegram for new messages and log them with structured parsed data.
Run on a schedule (every 15 min via GitHub Actions).

Log entry format:
  {
    "timestamp": "<ISO-8601 UTC>",
    "raw": "<original reply text>",
    "parsed": {
      "run_km": 5.2,          // optional
      "gym_session": "upper", // optional
      "protein_g": 148,       // optional
      "study": {"Physics": 90, "Maths": 60}  // optional, values in minutes
    }
  }
"""
import json
import os
import urllib.request
from datetime import datetime, timezone

import parse_entry

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA_DIR = os.path.join(ROOT, "data")
LOG_PATH = os.path.join(DATA_DIR, "log.json")
OFFSET_PATH = os.path.join(DATA_DIR, "offset.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def main():
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = str(os.environ["TELEGRAM_CHAT_ID"])
    offset = load_json(OFFSET_PATH, {"update_id": 0}).get("update_id", 0)
    log = load_json(LOG_PATH, [])

    # migrate old-format entries (text -> raw, no parsed)
    for e in log:
        if "text" in e and "raw" not in e:
            e["raw"] = e.pop("text")
        if "parsed" not in e:
            e["parsed"] = parse_entry.parse(e.get("raw", ""))

    url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=0"
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read())

    new_max = offset
    new_entries = 0
    for update in data.get("result", []):
        new_max = max(new_max, update["update_id"] + 1)
        msg = update.get("message")
        if not msg or str(msg.get("chat", {}).get("id")) != chat_id:
            continue
        text = msg.get("text", "")
        if not text:
            continue
        parsed = parse_entry.parse(text)
        log.append({
            "timestamp": datetime.fromtimestamp(msg["date"], tz=timezone.utc).isoformat(),
            "raw": text,
            "parsed": parsed,
        })
        new_entries += 1

    save_json(OFFSET_PATH, {"update_id": new_max})
    save_json(LOG_PATH, log)
    print(f"Logged {new_entries} new message(s). Offset now {new_max}.")


if __name__ == "__main__":
    main()
