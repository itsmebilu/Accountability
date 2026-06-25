#!/usr/bin/env python3
"""Send a structured weekly review summarising all goals and UPSC syllabus progress."""
import os
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from google import genai

ROOT = os.path.join(os.path.dirname(__file__), "..")

def load_all_logs():
    """Loads every log entry to track historical goal changes and syllabus tracking."""
    path = os.path.join(ROOT, "data", "log.json")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)

def get_active_goals(config, all_logs):
    """Scans history for goal updates via Telegram and overrides config defaults."""
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

def build_syllabus_tracker(all_logs):
    """Scans all logs to build a master list of subjects, time spent, allocations, and completion."""
    study_tracking = {}
    
    for e in all_logs:
        parsed = e.get("parsed", {})
        
        # Backwards compatibility for your older logs
        if isinstance(parsed.get("study"), dict):
            for subj, mins in parsed["study"].items():
                if subj not in study_tracking:
                    study_tracking[subj] = {"minutes": 0, "allocated_days": None, "completed": False}
                study_tracking[subj]["minutes"] += mins
                
        # Processing the new schema with deadlines and completion
        for session in parsed.get("study_sessions", []):
            subj = session.get("subject")
            if not subj: continue
            
            if subj not in study_tracking:
                study_tracking[subj] = {"minutes": 0, "allocated_days": None, "completed": False}
            
            if session.get("minutes"):
                study_tracking[subj]["minutes"] += session["minutes"]
            if session.get("allocated_days"):
                study_tracking[subj]["allocated_days"] = session["allocated_days"]
            if session.get("completed") is True:
                study_tracking[subj]["completed"] = True
                
    return study_tracking

def main():
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    config_path = os.path.join(ROOT, "config.json")
    config = json.load(open(config_path)) if os.path.exists(config_path) else {}
    
    all_logs = load_all_logs()
    run_goal, gym_goal, diet_goal = get_active_goals(config, all_logs)
    master_syllabus = build_syllabus_tracker(all_logs)
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    recent_entries = []
    
    for e in all_logs:
        try:
            ts = e.get("timestamp")
            if isinstance(ts, int) or (isinstance(ts, str) and ts.isdigit()):
                entry_time = datetime.fromtimestamp(int(ts), tz=timezone.utc)
            else:
                entry_time = datetime.fromisoformat(str(ts))
            if entry_time >= cutoff:
                recent_entries.append(e)
        except Exception:
            continue

    if not recent_entries:
        requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": "Weekly Review: Zero logs found. Unacceptable."})
        return

    # Aggregate weekly physical metrics
    total_km = sum(e.get("parsed", {}).get("run_km", 0) for e in recent_entries)
    runs = sum(1 for e in recent_entries if e.get("parsed", {}).get("run_km", 0) > 0)
    gym_sessions = [e["parsed"]["gym_session"] for e in recent_entries if e.get("parsed", {}).get("gym_session")]
    
    protein_entries = [e["parsed"].get("protein_g", 0) for e in recent_entries if e.get("parsed", {}).get("protein_g")]
    avg_protein = sum(protein_entries) / max(1, len(protein_entries)) if protein_entries else 0

    # Format the Syllabus Tracker for the AI Prompt
    study_text_lines = []
    for subj, data in master_syllabus.items():
        if data["minutes"] == 0 and not data["allocated_days"]:
            continue
        status = "COMPLETED ✅" if data["completed"] else "Ongoing"
        allocation = f"Deadline: {data['allocated_days']} days" if data["allocated_days"] else "No deadline set"
        hours = data["minutes"] // 60
        mins = data["minutes"] % 60
        study_text_lines.append(f"  - {subj}: {hours}h {mins}m total invested | {allocation} | Status: {status}")
        
    study_summary = "\n".join(study_text_lines)
    chat_history = "\n".join(f"- {e.get('user_input', '')}" for e in recent_entries)

    # Prompt the AI
    prompt = f"""
    You are a strict accountability coach assessing the user's weekly performance. Do not accept mediocrity.
    
    Active Targets for this week:
    - Running: {run_goal['weekly_km']}km over {run_goal['runs_per_week']} runs
    - Gym: {gym_goal['sessions_per_week']} sessions
    - Diet: {diet_goal['daily_protein_g']}g daily protein

    Actual physical performance:
    - Running: {total_km:.1f}km / {run_goal['weekly_km']}km goal, {runs}/{run_goal['runs_per_week']} runs
    - Gym: {len(gym_sessions)}/{gym_goal['sessions_per_week']} sessions
    - Protein: avg {avg_protein:.0f}g/day vs {diet_goal['daily_protein_g']}g target
    
    MASTER SYLLABUS TRACKER (All Time):
    {study_summary or '  No subjects logged.'}
    
    Raw Check-ins this week:
    {chat_history}

    INSTRUCTIONS:
    Write a 5-7 sentence weekly review for Telegram. 
    1. Analyze their physical numbers against their active targets.
    2. Review their UPSC CSE syllabus progress. Call out if they are dragging out a subject past its allocated deadline, or celebrate if they finally marked a subject as COMPLETED.
    3. Give a specific, gritty directive for next week.
    4. End with a short line of Urdu poetry or a quote about perseverance, sifar, and junoon.
    Plain text only.
    """
    
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        summary = response.text
    except Exception as e:
        summary = f"Weekly summary calculation failed: {e}"
        
    requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": summary})

if __name__ == "__main__":
    main()
