import os
import base64
import json
import requests
from flask import Flask, request
from google import genai
from google.genai import types

app = Flask(__name__)

try:
    client = genai.Client()
except Exception as e:
    client = None
    print(f"Failed to initialize Gemini Client: {e}")

def commit_to_github(new_entry):
    """Commits the structured log entry to GitHub."""
    try:
        repo = os.environ.get("GITHUB_REPOSITORY")
        token = os.environ.get("GH_TOKEN")
        if not repo or not token:
            return False
            
        url = f"https://api.github.com/repos/{repo}/contents/data/log.json"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        r = requests.get(url, headers=headers)
        sha = None
        log_data = []
        
        if r.status_code == 200:
            file_json = r.json()
            sha = file_json["sha"]
            content_decoded = base64.b64decode(file_json["content"]).decode('utf-8')
            log_data = json.loads(content_decoded)
            
        log_data.append(new_entry)
        updated_content = json.dumps(log_data, indent=2)
        encoded_content = base64.b64encode(updated_content.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": "bot: log structured metrics [skip ci]",
            "content": encoded_content,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
            
        res = requests.put(url, headers=headers, json=payload)
        return res.status_code in [200, 201]
    except Exception as e:
        print(f"Error during GitHub commit: {str(e)}")
        return False

@app.route('/api/webhook', methods=['POST'])
def webhook():
    try:
        update = request.json
        if not update or "message" not in update or "text" not in update["message"]:
            return "OK", 200
            
        chat_id = update["message"]["chat"]["id"]
        user_text = update["message"]["text"]
        timestamp = update["message"]["date"]

        if not client:
            return "OK", 200

      # The JSON Extraction Prompt
        prompt = f"""
        Analyze the user's message and extract two things:
        1. Logged activities (running, gym, protein, studying).
        2. Any requests to change their long-term goals.
        
        Then, act as an understanding but realistic accountability coach. Write a disciplined response checking them on their progress.
        
        You MUST return ONLY a valid JSON object matching this structure. Put null or 0 if a metric is not mentioned.
        {{
            "bot_reply": "Your tough-love coach response here. Include motivational quote if fitting.",
            "parsed": {{
                "run_km": float,
                "gym_session": string or null,
                "protein_g": integer,
                "study_sessions": [
                    {{
                        "subject": "string (e.g., Polity, Modern History)",
                        "minutes": integer or null,
                        "allocated_days": integer or null (ONLY if they explicitly set a new deadline/allocation),
                        "completed": boolean or null (true ONLY if they state they finished the subject entirely)
                    }}
                ]
            }},
            "updated_goals": {{
                "weekly_km": float or null,
                "runs_per_week": integer or null,
                "sessions_per_week": integer or null,
                "daily_protein_g": integer or null
            }}
        }}
        
        User message: "{user_text}"
        """
        
        # Force JSON output via the config
        response = client.models.generate_content(
            model='gemini-1.5-flash-8b',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        # Parse the AI's JSON output
        ai_data = json.loads(response.text)
        bot_reply = ai_data.get("bot_reply", "Data logged.")
        parsed_metrics = ai_data.get("parsed", {})
        updated_goals = ai_data.get("updated_goals", {})

        # Send Telegram message
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(tg_url, json={"chat_id": chat_id, "text": bot_reply})

        # Commit the structured data to GitHub
        new_entry = {
            "timestamp": timestamp,
            "user_input": user_text,
            "bot_response": bot_reply,
            "parsed": parsed_metrics,
            "updated_goals": updated_goals
        }
        commit_to_github(new_entry)

    except Exception as e:
        print(f"Critical Webhook Crash: {str(e)}")
        
    return "OK", 200
