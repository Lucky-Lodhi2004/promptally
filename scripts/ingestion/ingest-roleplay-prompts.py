#!/usr/bin/env python3
"""
Dedicated Roleplay & Interview Prompts Ingestion Pipeline:
- Extracts strict conversational roleplay, character acting, mock interviews,
  tutors, debaters, and coaching prompts from prompts.chat
- Sub-classifies into: Mock Interview, Academic Tutor, Character Acting, Debate & Philosophy, Coaching & Counseling
- Normalizes variable placeholders into {{VARIABLE}} format
- Saves into: /home/lucky/repos/Promptally/data/extracted/roleplay_prompts.json
"""

import os
import sys
import csv
import json
import re

csv.field_size_limit(sys.maxsize)

CSV_PATH = '/tmp/awesome_prompts.csv'
OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/roleplay_prompts.json'

ROLEPLAY_KEYWORDS = [
    'interviewer', 'interview', 'tutor', 'teacher', 'socratic',
    'debater', 'debate', 'character', 'roleplay', 'acting',
    'dialogue', 'dialog', 'counselor', 'therapist', 'coach',
    'mentor', 'philosopher', 'examiner', 'interrogator', 'patient',
    'doctor', 'guide', 'friend', 'companion'
]

KEYWORD_PATTERN = re.compile(r'\b(' + '|'.join(ROLEPLAY_KEYWORDS) + r')\b', re.IGNORECASE)

def classify_roleplay_subgroup(act, prompt):
    combined = (act + ' ' + prompt[:200]).lower()
    if 'interview' in combined or 'examiner' in combined or 'interrogator' in combined:
        return 'Mock Interview & Assessment'
    if 'tutor' in combined or 'teacher' in combined or 'socratic' in combined or 'instructor' in combined:
        return 'Academic Tutor & Teaching'
    if 'character' in combined or 'acting' in combined or 'roleplay' in combined or 'companion' in combined:
        return 'Character Acting & Simulation'
    if 'debate' in combined or 'debater' in combined or 'philosopher' in combined or 'socrates' in combined:
        return 'Debate & Philosophy'
    if 'coach' in combined or 'counselor' in combined or 'therapist' in combined or 'mentor' in combined:
        return 'Coaching & Mentorship'
    return 'Interactive Roleplay'

def normalize_placeholders(prompt_text):
    # Convert ${Variable:Default} or ${Variable} to {{VARIABLE}}
    normalized = re.sub(r'\$\{([^:}]+)(?::[^}]*)?\}', lambda m: '{{' + m.group(1).strip().upper().replace(' ', '_') + '}}', prompt_text)
    # Convert {placeholder} to {{PLACEHOLDER}}
    normalized = re.sub(r'\{([a-zA-Z0-9_\-\s]+)\}', lambda m: '{{' + m.group(1).strip().upper().replace(' ', '_') + '}}', normalized)
    return normalized

def generate_title(act):
    clean = act.strip()
    if clean.lower().startswith('act as') or clean.lower().startswith('act like'):
        return f"Prompt to {clean}"
    return f"Prompt to Turn ChatGPT into a {clean}"

def run():
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        sys.exit(1)

    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    results = []
    seen = set()

    for r in rows:
        act = (r.get('act') or '').strip()
        prompt = (r.get('prompt') or '').strip()

        if not act or not prompt or len(prompt) < 15:
            continue

        if not KEYWORD_PATTERN.search(act) and not KEYWORD_PATTERN.search(prompt[:160]):
            continue

        if prompt in seen:
            continue
        seen.add(prompt)

        subgroup = classify_roleplay_subgroup(act, prompt)
        normalized_prompt = normalize_placeholders(prompt)
        title = generate_title(act)
        slug = re.sub(r'[^a-z0-9]+', '-', act.lower()).strip('-')

        tags = ['roleplay', 'persona', 'chatgpt-persona', subgroup.lower().replace(' & ', '-').replace(' ', '-')]

        results.append({
            "prompt_title": title,
            "exact_prompt": normalized_prompt,
            "prompt_type": "roleplay_prompt",
            "roleplay_category": subgroup,
            "source_slug": slug,
            "tags": tags,
            "source_repo": "https://github.com/f/awesome-chatgpt-prompts",
            "license": "CC0-1.0"
        })

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        json.dump(results, out, indent=2)

    print(f"\nSuccessfully extracted {len(results)} Strict Roleplay & Interview Prompts into {OUTPUT_FILE}!")

    # Breakdown by subgroup
    subgroup_counts = {}
    for p in results:
        sg = p['roleplay_category']
        subgroup_counts[sg] = subgroup_counts.get(sg, 0) + 1

    print("\nBreakdown by Roleplay Category:")
    print(json.dumps(subgroup_counts, indent=2))

if __name__ == '__main__':
    run()

