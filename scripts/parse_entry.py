#!/usr/bin/env python3
"""
Parse a free-text check-in reply into structured data using AI.

The AI returns JSON with these optional keys:
  run_km        float  — distance run today (0 or omit if no run)
  gym_session   str    — "upper", "lower", or omit if no gym
  study         dict   — {SubjectName: minutes} e.g. {"Physics": 90}
  protein_g     int    — grams of protein consumed today

Falls back to lightweight regex if AI is unavailable.
"""
import json
import re
import ai_provider


PARSE_PROMPT = """Extract workout and study data from this check-in message and return ONLY valid JSON.

Message: {text}

Return a JSON object with these keys (omit any that aren't mentioned):
- "run_km": number (km run today, omit if no run)
- "gym_session": "upper" or "lower" (omit if no gym today)
- "study": object mapping subject name to minutes studied (e.g. {{"Physics": 90, "Maths": 60}})
- "protein_g": number (grams of protein, omit if not mentioned)

Return ONLY the JSON object. No explanation, no markdown.
"""


def parse_with_ai(text):
    result = ai_provider.generate(PARSE_PROMPT.format(text=text), max_tokens=200)
    if not result:
        return None
    try:
        clean = result.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(clean)
    except Exception:
        return None


def parse_with_regex(text):
    t = text.lower()
    result = {}

    # run distance
    m = re.search(r'(\d+\.?\d*)\s*km', t)
    if m and any(w in t for w in ['run', 'ran', 'jog', 'km']):
        result['run_km'] = float(m.group(1))

    # gym split
    if 'upper' in t:
        result['gym_session'] = 'upper'
    elif 'lower' in t:
        result['gym_session'] = 'lower'
    elif 'gym' in t or 'workout' in t or 'lift' in t:
        result['gym_session'] = 'gym'

    # protein
    pm = re.search(r'(\d+)\s*g?\s*protein|protein\s*[:\-]?\s*(\d+)', t)
    if pm:
        result['protein_g'] = int(pm.group(1) or pm.group(2))

    # study hours/minutes per subject
    # e.g. "studied physics 2hrs", "physics 1.5h", "2 hours of maths"
    study = {}
    for m in re.finditer(r'(\w+)\s+(\d+\.?\d*)\s*(h|hr|hrs|hour|hours|min|mins|minutes)', t):
        subj = m.group(1).capitalize()
        val  = float(m.group(2))
        unit = m.group(3)
        if subj in ('Studied', 'Study', 'Did', 'Spent', 'And', 'For'):
            continue
        mins = int(val * 60) if unit.startswith('h') else int(val)
        study[subj] = study.get(subj, 0) + mins
    if study:
        result['study'] = study

    return result if result else None


def parse(text):
    """Try AI first, fall back to regex."""
    result = parse_with_ai(text)
    if result and isinstance(result, dict):
        return result
    return parse_with_regex(text) or {}
