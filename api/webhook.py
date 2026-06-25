import os
import base64
import json
import requests
from flask import Flask, request
import google.generativeai as genai

app = Flask(__name__)

# Initialize Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

GITHUB_REPO = os.environ["GITHUB_REPOSITORY"]  # Automatically provided by Vercel if linked, or set manually
GITHUB_TOKEN = os.environ["GH_TOKEN"]          # Your GitHub Personal Access Token
LOG_FILE_PATH = "data/log.json"

def commit_to_github(new_entry):
    """Fetches log.json from GitHub, appends the new entry, and commits it back."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{LOG_FILE_PATH}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    # Step 1: Get the current file content and its SHA hash
    r = requests.get(url, headers=headers)
    sha = None
    log_data = []
    
    if r.status_code == 200:
        file_json = r.json()
        sha = file_json["sha"]
        content_decoded = base64.b64decode(file_json["content"]).decode('utf-8')
        log_data = json.loads(content_decoded)
    elif r.status_code != 404:
        return False  # API error
        
    # Step 2: Append the new entry
    log_data.append(new_entry)
    updated_content = json.dumps(log_data, indent=2)
    encoded_content = base64.b64encode(updated_content.encode('utf-8')).decode('utf-8')
    
    # Step 3: Push the commit back to GitHub
    payload = {
        "message": "bot: log new accountability entry [skip ci]",
        "content": encoded_content,
        "branch": "main"
    }
    if sha:
        payload["sha"] = sha
        
    requests.put(url, headers=headers, json=payload)
    return True

@app.route('/api/webhook', methods=['POST'])
def webhook():
    update = request.json
    if "message" not in update or "text" not in update["message"]:
        return "OK", 200
        
    chat_id = update["message"]["chat"]["id"]
    user_text = update["message"]["text"]
    timestamp = update["message"]["date"]

    # System prompt for an intense, classic, disciplined coach persona
    prompt = f"""
    You are a strict, focused, old-school accountability coach. You have zero tolerance for excuses, but you are deeply invested in the user's success.
    - The user is preparing for highly demanding competitive civil services exams, runs long distances/half-marathons, and cycles mountain trails. Keep them to that absolute elite standard.
    - If they slip up (e.g., ate pizza/junk food, skipped a run, missed a study session), correct them instantly. Demand a recovery action (e.g., a massive caloric deficit tomorrow, an evening makeup run, double study hours).
    - Keep responses concise, impactful, and gritty. Occasionally weave in a brief, poignant line of Urdu poetry or a classic ghazal quote about struggle, resolve, or endurance (*sabr* and *junoon*) to match an old-school aesthetic.
    
    User message: "{user_text}"
    """
    
    # Generate and send the response
    response = model.generate_content(prompt)
    bot_reply = response.text

    tg_url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    requests.post(tg_url, json={"chat_id": chat_id, "text": bot_reply})

    # Log the entry into the GitHub repository asynchronously
    new_entry = {
        "timestamp": timestamp,
        "user_input": user_text,
        "bot_response": bot_reply
    }
    commit_to_github(new_entry)

    return "OK", 200
