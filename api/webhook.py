import os
import base64
import json
import requests
from flask import Flask, request
from google import genai

app = Flask(__name__)

# Initialize Gemini safely with the modern SDK
# The Client automatically picks up the GEMINI_API_KEY environment variable
try:
    client = genai.Client()
except Exception as e:
    client = None
    print(f"Failed to initialize Gemini Client: {e}")

def commit_to_github(new_entry):
    """Safely handles GitHub logging without blocking the chat response."""
    try:
        repo = os.environ.get("GITHUB_REPOSITORY")
        token = os.environ.get("GH_TOKEN")
        if not repo or not token:
            print("Skipping GitHub commit: GITHUB_REPOSITORY or GH_TOKEN missing.")
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
        elif r.status_code != 404:
            print(f"GitHub API fetch failed with status: {r.status_code}")
            return False
            
        log_data.append(new_entry)
        updated_content = json.dumps(log_data, indent=2)
        encoded_content = base64.b64encode(updated_content.encode('utf-8')).decode('utf-8')
        
        payload = {
            "message": "bot: log new accountability entry [skip ci]",
            "content": encoded_content,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
            
        res = requests.put(url, headers=headers, json=payload)
        print(f"GitHub commit response: {res.status_code}")
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

        # Ensure Gemini is initialized
        if not client:
            tg_url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_BOT_TOKEN')}/sendMessage"
            requests.post(tg_url, json={"chat_id": chat_id, "text": "Error: GEMINI_API_KEY is not configured on the server."})
            return "OK", 200

        # Hardened System Prompt
        prompt = f"""
        You are a strict, focused, old-school accountability coach. You have zero tolerance for excuses, but you are deeply invested in the user's success.
        - The user is preparing for highly demanding competitive civil services exams, runs long distances/half-marathons, and cycles mountain trails. Keep them to that absolute elite standard.
        - If they slip up (e.g., ate pizza/junk food, skipped a run, missed a study session), correct them instantly. Demand a recovery action (e.g., a massive caloric deficit tomorrow, an evening makeup run, double study hours).
        - Keep responses concise, impactful, and gritty. Occasionally weave in a brief, poignant line of Urdu poetry or a classic ghazal quote about struggle, resolve, or endurance to match an old-school aesthetic.
        
        User message: "{user_text}"
        """
        
        # Generate AI reply using the new SDK
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        bot_reply = response.text

        # Send Telegram message immediately
        bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        tg_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        requests.post(tg_url, json={"chat_id": chat_id, "text": bot_reply})

        # Async-style background commit to GitHub log
        new_entry = {
            "timestamp": timestamp,
            "user_input": user_text,
            "bot_response": bot_reply
        }
        commit_to_github(new_entry)

    except Exception as e:
        print(f"Critical Webhook Crash: {str(e)}")
        
    return "OK", 200
