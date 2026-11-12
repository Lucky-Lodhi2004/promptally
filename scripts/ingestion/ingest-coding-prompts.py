#!/usr/bin/env python3
"""
Dedicated Coding Prompts Ingestion Pipeline:
- Extracts coding, developer, and technical prompts from prompts.chat (f/awesome-chatgpt-prompts)
- Handles huge multiline CSV fields using sys.maxsize
- Normalizes variable placeholders into {{VARIABLE}} format
- Detects programming languages / stacks (e.g., Python, JavaScript, Solidity, SQL, Linux, Rust, Docker)
- Saves into: /home/lucky/repos/Promptally/data/extracted/coding_prompts.json
"""

import os
import sys
import csv
import json
import re

csv.field_size_limit(sys.maxsize)

CSV_PATH = '/tmp/awesome_prompts.csv'
OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/coding_prompts.json'

CODING_KEYWORDS = [
    'developer', 'terminal', 'console', 'coder', 'programming', 'code',
    'sql', 'regex', 'python', 'javascript', 'typescript', 'solidity', 'git',
    'bash', 'linux', 'html', 'css', 'react', 'api', 'docker', 'kubernetes',
    'c\\+\\+', 'rust', 'golang', 'java', 'php', 'swift', 'compiler', 'debugger',
    'refactor', 'algorithm', 'vulnerability', 'penetration', 'cybersecurity',
    'database', 'shell', 'backend', 'frontend', 'devops', 'web3', 'smart contract'
]

KEYWORD_PATTERN = re.compile(r'\b(' + '|'.join(CODING_KEYWORDS) + r')\b', re.IGNORECASE)

STACK_MAP = {
    'python': 'Python',
    'javascript': 'JavaScript',
    'typescript': 'TypeScript',
    'solidity': 'Solidity / Web3',
    'sql': 'SQL / Databases',
    'linux': 'Linux / Bash',
    'terminal': 'Terminal / CLI',
    'bash': 'Linux / Bash',
    'docker': 'Docker / DevOps',
    'git': 'Git / Version Control',
    'regex': 'Regular Expressions',
    'rust': 'Rust',
    'c++': 'C++',
    'golang': 'Go',
    'html': 'Frontend / Web',
    'css': 'Frontend / CSS',
    'react': 'React / Frontend',
    'cybersecurity': 'Cybersecurity / SecOps'
}

def detect_stack(act, prompt):
    combined = (act + ' ' + prompt[:200]).lower()
    for key, label in STACK_MAP.items():
        if re.search(r'\b' + re.escape(key) + r'\b', combined):
            return label
    return 'General Coding'

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
        for_devs = (r.get('for_devs') or '').strip().upper()

        if not act or not prompt or len(prompt) < 15:
            continue

        is_dev_flagged = (for_devs == 'TRUE')
        is_keyword_match = bool(KEYWORD_PATTERN.search(act) or KEYWORD_PATTERN.search(prompt[:160]))

        if not (is_dev_flagged or is_keyword_match):
            continue

        if prompt in seen:
            continue
        seen.add(prompt)

        stack = detect_stack(act, prompt)
        normalized_prompt = normalize_placeholders(prompt)
        title = generate_title(act)
        slug = re.sub(r'[^a-z0-9]+', '-', act.lower()).strip('-')

        tags = ['coding', 'developer-tool', 'chatgpt-coding']
        if stack != 'General Coding':
            tags.append(stack.lower().replace(' / ', '-').replace(' ', '-'))

        results.append({
            "prompt_title": title,
            "exact_prompt": normalized_prompt,
            "prompt_type": "coding_prompt",
            "language_or_stack": stack,
            "source_slug": slug,
            "tags": tags,
            "source_repo": "https://github.com/f/awesome-chatgpt-prompts",
            "license": "CC0-1.0"
        })

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        json.dump(results, out, indent=2)

    print(f"\nSuccessfully extracted {len(results)} Coding Prompts into {OUTPUT_FILE}!")

    # Breakdown by detected stack
    stack_counts = {}
    for p in results:
        s = p['language_or_stack']
        stack_counts[s] = stack_counts.get(s, 0) + 1

    print("\nBreakdown by Language / Stack:")
    print(json.dumps(stack_counts, indent=2))

if __name__ == '__main__':
    run()

