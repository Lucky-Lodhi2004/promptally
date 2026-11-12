#!/usr/bin/env python3
"""
Dedicated Agentic Skills (SKILL.md) Ingestion Pipeline:
- Ingests production SKILL.md packages from:
  * affaan-m/ECC (314 cross-platform skills for Claude Code, Cursor, OpenClaw)
  * Jeffallan/claude-skills (68 DevOps, full-stack, and architecture skills)
  * addyosmani/agent-skills (27 software lifecycle and testing skills)
  * mattpocock/skills (36 TypeScript and architecture skills)
- Normalizes YAML frontmatter, tool requirements, descriptions, and markdown instructions
- Saves into: /home/lucky/repos/Promptally/data/extracted/agentic_skills.json
"""

import os
import sys
import json
import yaml
import re

OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/agentic_skills.json'

def parse_skill_md(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None, None

    if not content.startswith('---'):
        return {}, content

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
    if match:
        try:
            fm = yaml.safe_load(match.group(1)) or {}
            body = match.group(2)
            return fm, body
        except Exception:
            return {}, content
    return {}, content

def clean_title(name):
    words = [w.capitalize() for w in name.replace('-', ' ').replace('_', ' ').split()]
    title = ' '.join(words)
    if not title.lower().startswith('agentic skill'):
        return f"Agentic Skill: {title}"
    return title

def extract_tools(body, desc):
    combined = (desc + ' ' + body[:500]).lower()
    tools = set()
    if 'terminal' in combined or 'command' in combined or 'bash' in combined or 'shell' in combined or 'run' in combined:
        tools.add('run_command')
    if 'read' in combined or 'file' in combined or 'grep' in combined:
        tools.add('read_file')
    if 'write' in combined or 'edit' in combined or 'patch' in combined:
        tools.add('edit_file')
    if 'mcp' in combined:
        tools.add('call_mcp_tool')
    if 'search' in combined or 'web' in combined or 'browser' in combined:
        tools.add('search_web')
    return list(tools) if tools else ['read_file', 'edit_file']

def run():
    skills = []
    seen = set()

    sources = [
        ('/tmp/ecc/skills', 'https://github.com/affaan-m/ECC', 'Apache-2.0'),
        ('/tmp/jeffallan-skills/skills', 'https://github.com/Jeffallan/claude-skills', 'MIT'),
        ('/tmp/addy-skills/skills', 'https://github.com/addyosmani/agent-skills', 'MIT'),
        ('/tmp/matt-skills/skills', 'https://github.com/mattpocock/skills', 'MIT')
    ]

    for root_dir, repo_url, default_license in sources:
        if not os.path.exists(root_dir):
            continue
        print(f"Scanning {root_dir}...")
        for root, _, files in os.walk(root_dir):
            if 'SKILL.md' in files:
                skill_path = os.path.join(root, 'SKILL.md')
                folder_name = os.path.basename(root)
                
                fm, body = parse_skill_md(skill_path)
                skill_name = fm.get('name') or folder_name
                desc = fm.get('description') or ''
                if not desc and body:
                    # extract first paragraph
                    paragraphs = [p.strip() for p in body.split('\n\n') if p.strip() and not p.strip().startswith('#')]
                    if paragraphs:
                        desc = paragraphs[0][:200]

                slug = re.sub(r'[^a-z0-9]+', '-', skill_name.lower()).strip('-')
                if slug in seen:
                    continue
                seen.add(slug)

                with open(skill_path, 'r', encoding='utf-8') as f:
                    verbatim_content = f.read()

                tools = extract_tools(body, desc)
                title = clean_title(skill_name)

                # Check for bundled references or scripts
                bundle_files = []
                for sub_root, _, sub_files in os.walk(root):
                    for sf in sub_files:
                        if sf == 'SKILL.md' or sf.startswith('.'):
                            continue
                        sub_full = os.path.join(sub_root, sf)
                        rel_path = os.path.relpath(sub_full, root)
                        if os.path.getsize(sub_full) < 50000: # under 50KB
                            try:
                                with open(sub_full, 'r', encoding='utf-8') as sff:
                                    bundle_files.append({
                                        "path": rel_path,
                                        "content": sff.read()
                                    })
                            except Exception:
                                pass

                skills.append({
                    "skill_name": skill_name,
                    "skill_title": title,
                    "source_slug": slug,
                    "skill_type": "agentic_skill",
                    "file_name": "SKILL.md",
                    "file_extension": ".md",
                    "metadata": {
                        "description": desc.strip(),
                        "tools_required": tools,
                        "target_agents": ["Antigravity", "Claude Code", "Cursor", "Windsurf", "Codex"],
                        "framework": fm.get('metadata', {}).get('domain', 'Fullstack / Architecture') if isinstance(fm.get('metadata'), dict) else 'Developer Skill',
                        "bundled_files_count": len(bundle_files)
                    },
                    "skill_content": verbatim_content,
                    "bundle_files": bundle_files,
                    "install_command": f"curl -sL https://promptally.com/skills/{slug}/SKILL.md -o .agents/skills/{skill_name}/SKILL.md",
                    "tags": ["agentic-skill", "skill-md", "automation", skill_name.lower().replace('-', ' ')],
                    "source_repo": repo_url,
                    "license": fm.get('license', default_license)
                })

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        json.dump(skills, out, indent=2)

    print(f"\nSuccessfully extracted {len(skills)} Agentic Skills into {OUTPUT_FILE}!")

if __name__ == '__main__':
    run()

