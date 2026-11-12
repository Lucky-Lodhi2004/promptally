#!/usr/bin/env python3
"""
Dedicated Creative Writing & Narrative Prompts Ingestion Pipeline:
Ingests Gryphe/ChatGPT-4o-Writing-Prompts:
- 3,741 creative writing prompts categorized by genre (Sci-Fi, Fantasy, Horror, Comedy, Drama, Romance)
- Paired with story titles, genre tags, and narrative variables

Outputs validated JSON into: data/extracted/writing_prompts.json
"""

import os
import sys
import json
import re

OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/writing_prompts.json'

def extract_variables(text):
    bracket_vars = re.findall(r'\[([A-Z0-9_\-\s/]+)\]', text)
    curly_vars = re.findall(r'\{\{([A-Za-z0-9_\-\s/]+)\}\}', text)
    combined = set()
    for v in bracket_vars + curly_vars:
        clean = v.strip().lower().replace(' ', '_').replace('-', '_')
        if len(clean) > 1 and len(clean) < 30 and not clean.startswith('http'):
            combined.add(clean)
    return sorted(list(combined))

def run():
    prompts = []
    seen = set()
    input_file = '/tmp/hf_prompts/gryphe_writing.jsonl'

    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        return

    print("Ingesting Gryphe/ChatGPT-4o-Writing-Prompts...")
    with open(input_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                item = json.loads(line)
                p_text = item.get('prompt', '').strip()
                if not p_text or p_text in seen:
                    continue
                seen.add(p_text)

                title = item.get('title', 'Creative Writing Prompt').strip()
                genre_str = item.get('genre', 'Fiction')
                genres = [g.strip() for g in genre_str.split(',') if g.strip()]

                prompts.append({
                    "id": f"writing-prompt-{len(prompts)+1}",
                    "prompt_title": f"Story Concept: {title}",
                    "exact_prompt": p_text,
                    "category": f"Creative Writing ({genres[0] if genres else 'Fiction'})",
                    "prompt_type": "creative_writing_prompt",
                    "genres": genres,
                    "target_models": ["OpenAI GPT-4o", "Anthropic Claude 3.5 Sonnet", "Google Gemini 1.5 Pro"],
                    "variable_keys": extract_variables(p_text),
                    "source_repo": "Gryphe/ChatGPT-4o-Writing-Prompts",
                    "source_license": "Apache-2.0",
                    "tags": ["creative-writing", "storytelling", "fiction"] + [g.lower().replace(' ', '-') for g in genres]
                })
            except Exception:
                pass

    print(f"\nTotal writing prompts extracted: {len(prompts)}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)

    print(f"Saved successfully to: {OUTPUT_FILE}")

if __name__ == '__main__':
    run()

