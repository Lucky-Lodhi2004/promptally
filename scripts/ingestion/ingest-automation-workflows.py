#!/usr/bin/env python3
"""
Ingestion Pipeline for Automation Node Graphs:
- Ingests n8n workflow graphs from /tmp/enes-n8n and /tmp/anb-n8n
- Ingests Langflow starter projects from /tmp/langflow
- Normalizes into /home/lucky/repos/Promptally/data/extracted/automation_workflows.json
"""

import os
import json
import re

OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/automation_workflows.json'

def clean_title(name, prefix):
    base = os.path.splitext(name)[0]
    base = re.sub(r'[-_]+', ' ', base)
    words = [w.capitalize() for w in base.split()]
    clean = ' '.join(words)
    if clean.lower().startswith('n8n'):
        return clean
    if clean.lower().startswith('langflow'):
        return clean
    return f"{prefix} to {clean}"

def extract_n8n_integrations(nodes):
    integrations = set()
    for n in nodes:
        node_type = n.get('type', '')
        if '.' in node_type:
            part = node_type.split('.')[-1]
            # remove common suffixes
            part = re.sub(r'(Trigger|Node)$', '', part, flags=re.IGNORECASE)
            if len(part) > 2 and part.lower() not in ['code', 'set', 'if', 'switch', 'merge', 'sticky']:
                integrations.add(part.capitalize())
        elif n.get('name'):
            integrations.add(n['name'])
    return list(integrations)[:8]

def extract_langflow_components(nodes):
    components = set()
    for n in nodes:
        t = n.get('data', {}).get('type') or n.get('type')
        if t and t.lower() not in ['note', 'group']:
            components.add(t)
    return list(components)[:8]

def run():
    workflows = []
    seen = set()

    # 1. Ingest enescingoz/awesome-n8n-templates
    enes_dir = '/tmp/enes-n8n'
    if os.path.exists(enes_dir):
        print("Extracting n8n templates from enescingoz/awesome-n8n-templates...")
        for root, _, files in os.walk(enes_dir):
            if '.git' in root or 'docs' in root:
                continue
            category = os.path.basename(root).replace('_', ' ')
            for f in files:
                if not f.endswith('.json'):
                    continue
                full_path = os.path.join(root, f)
                try:
                    with open(full_path, 'r', encoding='utf-8') as jf:
                        data = json.load(jf)
                    
                    if not isinstance(data, dict) or 'nodes' not in data:
                        continue
                    
                    title = clean_title(f, "n8n Workflow")
                    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                    if slug in seen:
                        continue
                    seen.add(slug)

                    nodes = data.get('nodes', [])
                    integrations = extract_n8n_integrations(nodes)

                    workflows.append({
                        "workflow_title": title,
                        "workflow_type": "n8n_workflow",
                        "source_slug": slug,
                        "file_name": f,
                        "file_extension": ".json",
                        "metadata": {
                            "node_count": len(nodes),
                            "integrations": integrations,
                            "category": category
                        },
                        "raw_graph": data,
                        "usage_instructions": "Import this JSON blueprint into n8n via 'Workflow Settings -> Import from File'. Connect your API credentials to the trigger/action nodes.",
                        "tags": ["n8n", "automation", "workflow", category.lower().replace(' ', '-')] + [i.lower() for i in integrations[:3]],
                        "source_repo": "https://github.com/enescingoz/awesome-n8n-templates",
                        "license": "MIT"
                    })
                except Exception:
                    pass

    # 2. Ingest Anb98/n8n-workflows
    anb_dir = '/tmp/anb-n8n/workflows'
    if os.path.exists(anb_dir):
        print("Extracting n8n workflows from Anb98/n8n-workflows...")
        for f in os.listdir(anb_dir):
            if not f.endswith('.json'):
                continue
            full_path = os.path.join(anb_dir, f)
            try:
                with open(full_path, 'r', encoding='utf-8') as jf:
                    data = json.load(jf)
                
                title = clean_title(f, "n8n Workflow")
                slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                if slug in seen:
                    continue
                seen.add(slug)

                nodes = data.get('nodes', [])
                integrations = extract_n8n_integrations(nodes)

                workflows.append({
                    "workflow_title": title,
                    "workflow_type": "n8n_workflow",
                    "source_slug": slug,
                    "file_name": f,
                    "file_extension": ".json",
                    "metadata": {
                        "node_count": len(nodes),
                        "integrations": integrations,
                        "category": "Document & Media Automation"
                    },
                    "raw_graph": data,
                    "usage_instructions": "Import this JSON into n8n. Configure your source input trigger and storage path.",
                    "tags": ["n8n", "automation", "workflow", "pdf-processing", "audio"],
                    "source_repo": "https://github.com/Anb98/n8n-workflows",
                    "license": "MIT"
                })
            except Exception:
                pass

    # 3. Ingest Langflow starter projects
    lf_dir = '/tmp/langflow/src/backend/base/langflow/initial_setup/starter_projects'
    if os.path.exists(lf_dir):
        print("Extracting Langflow starter projects...")
        for f in os.listdir(lf_dir):
            if not f.endswith('.json'):
                continue
            full_path = os.path.join(lf_dir, f)
            try:
                with open(full_path, 'r', encoding='utf-8') as jf:
                    data = json.load(jf)
                
                title = clean_title(f, "Langflow Graph")
                slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                if slug in seen:
                    continue
                seen.add(slug)

                flow_data = data.get('data', {})
                nodes = flow_data.get('nodes', [])
                components = extract_langflow_components(nodes)

                workflows.append({
                    "workflow_title": title,
                    "workflow_type": "langflow_blueprint",
                    "source_slug": slug,
                    "file_name": f,
                    "file_extension": ".json",
                    "metadata": {
                        "node_count": len(nodes),
                        "integrations": components,
                        "category": "Agentic AI & RAG"
                    },
                    "raw_graph": data,
                    "usage_instructions": "Open Langflow desktop or server, click 'New Project -> Import Project' and select this JSON blueprint.",
                    "tags": ["langflow", "rag", "ai-agents", "node-graph", "multi-agent"],
                    "source_repo": "https://github.com/langflow-ai/langflow",
                    "license": "MIT"
                })
            except Exception:
                pass

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        json.dump(workflows, out, indent=2)

    print(f"\nSuccessfully extracted {len(workflows)} Automation Node Graphs into {OUTPUT_FILE}!")

    # Breakdown by type
    counts = {}
    for w in workflows:
        t = w['workflow_type']
        counts[t] = counts.get(t, 0) + 1
    print("\nBreakdown by Workflow Type:", json.dumps(counts, indent=2))

if __name__ == '__main__':
    run()

