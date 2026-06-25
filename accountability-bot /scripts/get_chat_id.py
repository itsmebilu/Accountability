#!/usr/bin/env python3
"""
Run this ONCE on your own laptop to find your Telegram chat_id.

Steps:
1. Open Telegram, find your bot (search the username you gave it in BotFather),
   and send it any message, e.g. "hi".
2. In a terminal, set your bot token:
       export TELEGRAM_BOT_TOKEN=123456:ABC-your-token-here
3. Run:
       python get_chat_id.py
4. Copy the chat_id it prints — you'll add it as a GitHub secret.
"""
import json
import os
import urllib.request

token = os.environ["TELEGRAM_BOT_TOKEN"]
url = f"https://api.telegram.org/bot{token}/getUpdates"
with urllib.request.urlopen(url, timeout=20) as resp:
    data = json.loads(resp.read())

seen = set()
for update in data.get("result", []):
    msg = update.get("message", {})
    chat = msg.get("chat", {})
    cid = chat.get("id")
    if cid and cid not in seen:
        seen.add(cid)
        name = chat.get("first_name") or chat.get("username") or "unknown"
        print(f"chat_id: {cid}  (from {name})")

if not seen:
    print("No messages found yet. Send your bot a message on Telegram first, then re-run this.")
