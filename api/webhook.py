import os
import requests
from flask import Flask, request
import google.generativeai as genai

app = Flask(__name__)

# Initialize Gemini
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-1.5-flash')

@app.route('/api/webhook', methods=['POST'])
def webhook():
    update = request.json
    if "message" not in update or "text" not in update["message"]:
        return "OK", 200
        
    chat_id = update["message"]["chat"]["id"]
    user_text = update["message"]["text"]

    # 1. The Dynamic System Prompt
    prompt = f"""
    You are a tough, 'old-school' accountability coach. You don't take excuses, but you are deeply motivational.
    - The user is an active Pahadi who trains for half-marathons and hits the mountain trails. Keep them up to that standard.
    - If they say they failed a goal (like eating pizza or skipping a run), instantly correct them, suggest a makeup session (like an evening run or a strict caloric deficit tomorrow), and tell them to log it.
    - If they succeeded, praise them briefly.
    - Keep the tone grounded, classic, and occasionally drop a short, relevant piece of Urdu poetry or a ghazal quote about perseverance to inspire them.
    
    User's message: "{user_text}"
    """
    
    # Generate AI response
    response = model.generate_content(prompt)
    bot_reply = response.text

    # 2. Send the instant reply back to Telegram
    tg_url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    requests.post(tg_url, json={"chat_id": chat_id, "text": bot_reply})

    # 3. Data logging logic will go here

    return "OK", 200
