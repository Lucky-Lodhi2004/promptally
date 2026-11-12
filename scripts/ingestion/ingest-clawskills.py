#!/usr/bin/env python3
"""
Ingestion script for OpenClaw & Sovereign Intelligence Agent Skills
Source: amoghacloud/clawskills-intelligence-corpus (5,147+ Agent Skills)
"""

import os
import re
import glob
import json
import yaml

CLAW_DIR = "/tmp/clawskills"
OUTPUT_CLAW_PATH = "/home/lucky/repos/Promptally/data/extracted/clawskills.json"
OUTPUT_ALL_SKILLS_PATH = "/home/lucky/repos/Promptally/data/extracted/agentic_skills.json"

def parse_frontmatter(content):
    meta = {}
    body = content
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    if match:
        fm_text = match.group(1)
        body = match.group(2)
        try:
            meta = yaml.safe_load(fm_text) or {}
        except Exception:
            for line in fm_text.splitlines():
                if ':' in line:
                    k, v = line.split(':', 1)
                    meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta, body

def main():
    print("Ingesting Clawskills Intelligence Corpus...")

    # 1. Map skill to category from categories/*.md
    category_map = {}
    cat_files = glob.glob(os.path.join(CLAW_DIR, "categories", "*.md"))
    for cf in cat_files:
        cat_slug = os.path.basename(cf).replace('.md', '')
        with open(cf, "r", encoding="utf-8", errors="replace") as f:
            ccontent = f.read()
        
        # Heading 1 is category name
        h1_match = re.search(r'^#\s+([^\n]+)', ccontent)
        cat_name = h1_match.group(1).strip() if h1_match else cat_slug.replace('-', ' ').title()
        
        # Matches: - [skill-name](../skills/skill-name/SKILL.md)
        skill_links = re.findall(r'\[([^\]]+)\]\(\.\./skills/([^/]+)/SKILL\.md\)', ccontent)
        for s_title, s_name in skill_links:
            category_map[s_name.strip()] = cat_name

    print(f"Loaded category mappings for {len(category_map)} skills across {len(cat_files)} categories.")

    # 2. Parse all SKILL.md files
    skill_files = sorted(glob.glob(os.path.join(CLAW_DIR, "skills", "*", "SKILL.md")))
    print(f"Found {len(skill_files)} SKILL.md files to process.")

    claw_skills = []
    seen_names = set()

    for sf in skill_files:
        skill_folder = os.path.basename(os.path.dirname(sf))
        try:
            with open(sf, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {sf}: {e}")
            continue

        fm, body = parse_frontmatter(content)
        name = fm.get("name") or skill_folder
        name = str(name).strip().lower()
        
        if name in seen_names:
            continue
        seen_names.add(name)

        description = fm.get("description") or ""
        if not description:
            # Fallback to first non-heading line
            lines = [l.strip() for l in body.splitlines() if l.strip() and not l.startswith("#")]
            description = lines[0] if lines else f"Autonomous agent skill for {name}"

        category = category_map.get(name) or category_map.get(skill_folder) or "General Utilities"
        version = str(fm.get("version", "1.0.0"))
        source_tag = str(fm.get("source", "SISR-Registry"))
        fidelity = str(fm.get("fidelity", "High"))

        skill_title = name.replace('-', ' ').replace('_', ' ').title()

        tags = [
            "agentic-skill",
            "skill-md",
            "openclaw",
            "sovereign-intelligence",
            category.lower().replace('&', 'and').replace(' ', '-')
        ]

        skill_obj = {
            "skill_name": name,
            "skill_title": f"Agentic Skill: {skill_title}",
            "source_slug": name,
            "skill_type": "agentic_skill",
            "file_name": "SKILL.md",
            "file_extension": ".md",
            "metadata": {
                "description": description,
                "category": category,
                "version": version,
                "fidelity": fidelity,
                "source_tag": source_tag,
                "target_agents": [
                    "OpenClaw",
                    "Claude Code",
                    "Cursor",
                    "Windsurf",
                    "Codex",
                    "Antigravity"
                ],
                "framework": "OpenClaw / SISR",
                "bundled_files_count": 0
            },
            "skill_content": content,
            "bundle_files": [],
            "install_command": f"clawhub install {name}",
            "tags": tags,
            "source_repo": "https://huggingface.co/datasets/amoghacloud/clawskills-intelligence-corpus",
            "license": "MIT"
        }
        claw_skills.append(skill_obj)

    print(f"Total parsed unique skills from corpus: {len(claw_skills)}")

    # 3. Save to clawskills.json
    os.makedirs(os.path.dirname(OUTPUT_CLAW_PATH), exist_ok=True)
    with open(OUTPUT_CLAW_PATH, "w", encoding="utf-8") as f:
        json.dump(claw_skills, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(claw_skills)} skills to {OUTPUT_CLAW_PATH}")

    # 4. Also update agentic_skills.json with non-duplicate skills
    existing_skills = []
    if os.path.exists(OUTPUT_ALL_SKILLS_PATH):
        with open(OUTPUT_ALL_SKILLS_PATH, "r", encoding="utf-8") as f:
            existing_skills = json.load(f)
    
    existing_names = set(s.get("skill_name") for s in existing_skills)
    added_count = 0
    for cs in claw_skills:
        if cs["skill_name"] not in existing_names:
            existing_skills.append(cs)
            existing_names.add(cs["skill_name"])
            added_count += 1

    with open(OUTPUT_ALL_SKILLS_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_skills, f, indent=2, ensure_ascii=False)
    print(f"Merged {added_count} new skills into {OUTPUT_ALL_SKILLS_PATH}. Total agentic skills: {len(existing_skills)}")

if __name__ == "__main__":
    main()

