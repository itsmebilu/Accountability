#!/usr/bin/env python3
"""
Send a single goal-aware, context-smart reminder to Telegram (or ntfy).
Usage: python send_reminder.py <goal>
Goals: running, gym, study, diet, evening_checkin
"""
import os
import sys
import json
import time
import random
import requests
from datetime import datetime, timezone
from google import genai

ROOT = os.path.join(os.path.dirname(__file__), "..")

def load_config():
    path = os.path.join(ROOT, "config.json")
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return json.load(f)

def load_all_logs():
    path = os.path.join(ROOT, "data", "log.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)

def get_active_goals(config, all_logs):
    """Scans history for goal updates via Telegram."""
    g = config.get("goals", {})
    run_goal = {"weekly_km": g.get("running", {}).get("weekly_km", 30), "runs_per_week": g.get("running", {}).get("runs_per_week", 4)}
    gym_goal = {"sessions_per_week": g.get("gym", {}).get("sessions_per_week", 4)}
    diet_goal = {"daily_protein_g": g.get("diet", {}).get("daily_protein_g", 150)}
    
    for e in all_logs:
        ug = e.get("updated_goals", {})
        if ug:
            if ug.get("weekly_km"): run_goal["weekly_km"] = ug["weekly_km"]
            if ug.get("runs_per_week"): run_goal["runs_per_week"] = ug["runs_per_week"]
            if ug.get("sessions_per_week"): gym_goal["sessions_per_week"] = ug["sessions_per_week"]
            if ug.get("daily_protein_g"): diet_goal["daily_protein_g"] = ug["daily_protein_g"]
            
    return run_goal, gym_goal, diet_goal

def should_skip_reminder(all_logs, task):
    """If the user checked in within the last 2.5 hours, do not bother them."""
    if not all_logs:
        return False
        
    last_log = all_logs[-1]
    ts = last_log.get("timestamp")
    
    try:
        if isinstance(ts, int) or (isinstance(ts, str) and ts.isdigit()):
            last_time = int(ts)
        else:
            last_time = int(datetime.fromisoformat(str(ts)).timestamp())
            
        current_time = int(datetime.now(timezone.utc).timestamp())
        hours_since_last_chat = (current_time - last_time) / 3600
        
        if hours_since_last_chat < 2.5 and task != "evening_checkin":
            print(f"User active {hours_since_last_chat:.1f} hours ago. Skipping redundant {task} reminder.")
            return True
    except Exception as e:
        print(f"Time parse error in skip logic: {e}")
        
    return False

def build_prompt(goal, config, all_logs):
    run_goal, gym_goal, diet_goal = get_active_goals(config, all_logs)
    
    # Extract just the last 5 logs for immediate conversational context
    recent = all_logs[-5:] if len(all_logs) >= 5 else all_logs
    history = "\n".join(f"- User: {e.get('user_input', '')}" for e in recent) or "No recent entries."

    base_persona = (
        "You are a strict, disciplined, old-school Pahadi accountability coach. "
        "You are texting Ahan, a rugged intellectual based in Dehradun preparing for the UPSC CSE Prelims (May 24, 2026). "
        "He is also training for half-marathons, skiing, and adventure sports. Demand excellence and zero excuses. "
    )

    prompts = {
        "running": (
            f"{base_persona}\n"
            f"His active goal is {run_goal['weekly_km']}km/week across {run_goal['runs_per_week']} runs.\n"
            f"Write ONE gritty, motivating push (max 2 sentences, 1 emoji max) for his morning run on the trails or road.\n"
            f"Recent log context:\n{history}\n\nReply ONLY with the text message."
        ),
        "gym": (
            f"{base_persona}\n"
            f"His active goal is {gym_goal['sessions_per_week']} strength sessions/week.\n"
            f"Write ONE short, commanding message to get him to the gym and lift heavy (max 2 sentences, 1 emoji).\n"
            f"Recent log context:\n{history}\n\nReply ONLY with the text message."
        ),
        "study": (
            f"{base_persona}\n"
            f"Write ONE focused, intense prompt demanding he lock in for his UPSC syllabus prep (max 2 sentences, 1 emoji).\n"
            f"Remind him the clock is ticking. Ask what subject he is clearing today.\n"
            f"Recent log context:\n{history}\n\nReply ONLY with the text message."
        ),
        "diet": (
            f"{base_persona}\n"
            f"His daily target is {diet_goal['daily_protein_g']}g of protein.\n"
            f"Write ONE short nudge asking for a diet check-in. No junk food allowed (max 2 sentences, 1 emoji).\n"
            f"Recent log context:\n{history}\n\nReply ONLY with the text message."
        ),
        "evening_checkin": (
            f"{base_persona}\n"
            f"Write a 2-3 sentence evening check-in message demanding his daily metrics: km run, gym session, "
            f"hours studied for UPSC subjects, and total protein intake. Include a short quote about "
            f"discipline. Make it feel like an intense mentor texting. 1 emoji max.\n"
            f"Recent log context:\n{history}\n\nReply ONLY with the text message."
        ),
    }
    return prompts.get(goal)

FALLBACKS = {
    "running": "🏃 Morning run time, Ahan. The mountain trails are waiting. Get your mileage in.",
    "gym": "💪 Gym session today. No excuses, go move some heavy iron.",
    "study": "📖 UPSC CSE Prelims is ticking closer. Lock in and clear your syllabus block now.",
    "diet": "🥗 Midday check. Where is your protein intake at? Hit your daily target.",
    "evening_checkin": "👋 Day is done. Give me your numbers: km run, gym split, study hours, and protein intake. Sabr aur junoon.",
}

def send_telegram(text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"Telegram failed: {e}")

def send_ntfy(text, title="Accountability"):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=text.encode('utf-8'),
            headers={"Title": title, "Priority": "high"},
            timeout=10
        )
    except Exception as e:
        print(f"Ntfy failed: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: send_reminder.py <goal>", file=sys.stderr)
        sys.exit(1)

    goal = sys.argv[1]
    config = load_config()
    all_logs = load_all_logs()

    # Pre-empt the alarm if you've already been chatting with the bot recently
    if should_skip_reminder(all_logs, goal):
        sys.exit(0)

    prompt = build_prompt(goal, config, all_logs)
    message = None
    
    if prompt:
        for attempt in range(3):
            try:
                client = genai.Client()
                response = client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt
                )
                message = response.text
                break
            except Exception as e:
                print(f"API Attempt {attempt + 1} failed: {str(e)}")
                if "503" in str(e) and attempt < 2:
                    time.sleep(10)
                else:
                    break

    # If the AI failed completely, use the hardcoded fallback
    if not message:
        message = FALLBACKS.get(goal, "Time to check in!")

    send_telegram(message)
    
    goal_titles = {"running":"🏃 Run time","gym":"💪 Gym time","study":"📖 Study time","diet":"🥗 Diet check","evening_checkin":"📋 Daily check-in"}
    send_ntfy(message, goal_titles.get(goal, "Reminder"))
    print(f"Sent [{goal}]: {message}")

if __name__ == "__main__":
    main()
