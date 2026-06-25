#!/usr/bin/env python3
"""
Shared helper to generate a short AI message, trying providers in order:

  1. Gemini API (GEMINI_API_KEY)   - free tier, no credit card needed. Get a
                                      key at https://aistudio.google.com
  2. Claude API (ANTHROPIC_API_KEY) - paid, fractions of a cent per call on
                                      Haiku. Get a key at https://console.anthropic.com

You only need ONE of these set. If neither is set (or both calls fail),
generate() returns None and the caller falls back to a plain template
message — the bot still works for $0 either way.
"""
import json
import os
import urllib.request


def _gemini(prompt, max_tokens):
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash:generateContent?key={api_key}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"Gemini call failed, will try next provider: {e}")
        return None


def _claude(prompt, max_tokens):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    body = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
        return "".join(block.get("text", "") for block in data.get("content", [])).strip()
    except Exception as e:
        print(f"Claude call failed: {e}")
        return None


def generate(prompt, max_tokens=200):
    """Try Gemini first (free), then Claude. Returns None if both unavailable/fail."""
    return _gemini(prompt, max_tokens) or _claude(prompt, max_tokens)
