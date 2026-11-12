#!/usr/bin/env python3
"""
Dedicated System Prompts & Cross-Vendor Engineering Ingestion Pipeline:
Ingests curated, production-grade system prompts and Custom GPT architectures:
1. Adrian2016/awesome-prompts:
   - Engineering Split (372 prompts: Claude Code loops, OpenAI Codex guide, Jules proactive agents, arXiv harnesses)
   - Library Split (2,777 prompts: coding, image generation, business, research, games)
2. Nymbo/Official_LLM_System_Prompts (38 official baseline system instructions: OpenAI GPT Builder, Canvas, Voice, Claude 3.5 Sonnet, Devin, Cursor, Vercel v0, Grok, Copilot)
3. danielrosehill/System-Prompt-Library (1,257 Custom GPT system prompts with direct ChatGPT store URLs, capability flags, and full systemprompt text)
4. EricLu/System-Prompt-Instruction-Real-world-Implementation-Training-set (Top real-world Custom GPT system instructions & tool-use constraints)
5. archit11/claude-code-traces (Real system prompts extracted from Claude Code CLI subagents)
6. caio4279/gemini-notebook-prompts (Gemini document grounding & structured reasoning prompts)
7. pisterlabs/promptset (Developer system prompts scraped from production repositories)

Outputs validated JSON into: data/extracted/system_prompts.json
"""

import os
import sys
import json
import glob
import re

OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/system_prompts.json'

def extract_variables(text):
    """Extract template variables like {{var}} or [var]."""
    bracket_vars = re.findall(r'\[([A-Z0-9_\-\s/]+)\]', text)
    curly_vars = re.findall(r'\{\{([A-Za-z0-9_\-\s/]+)\}\}', text)
    combined = set()
    for v in bracket_vars + curly_vars:
        clean = v.strip().lower().replace(' ', '_').replace('-', '_')
        if len(clean) > 1 and len(clean) < 30 and not clean.startswith('http'):
            combined.add(clean)
    return sorted(list(combined))

def clean_title(title):
    clean = re.sub(r'[^a-zA-Z0-9\s\-–—]', ' ', title).strip()
    words = [w.capitalize() for w in clean.split()]
    return ' '.join(words)

def run():
    prompts = []
    seen_prompts = set()

    # -------------------------------------------------------------
    # 1. Adrian2016/awesome-prompts (Engineering Parquet - 372 rows)
    # -------------------------------------------------------------
    adrian_eng_file = '/tmp/hf_prompts/adrian_engineering.parquet'
    if os.path.exists(adrian_eng_file):
        print("Ingesting Adrian2016/awesome-prompts (engineering split)...")
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(adrian_eng_file)
            for row in table.to_pylist():
                p_text = str(row.get('prompt', '')).strip()
                if not p_text or p_text in seen_prompts:
                    continue
                seen_prompts.add(p_text)

                name = row.get('name', 'Engineering System Prompt')
                cat = row.get('category', 'Coding & Development')
                desc = row.get('description', '')
                url = row.get('url', '')

                target_models = []
                lower = (name + " " + desc + " " + p_text[:500]).lower()
                if 'claude' in lower or 'anthropic' in lower:
                    target_models.append("Anthropic Claude 3.5 Sonnet")
                if 'openai' in lower or 'codex' in lower or 'gpt' in lower:
                    target_models.append("OpenAI GPT-4o")
                if 'gemini' in lower or 'jules' in lower or 'google' in lower:
                    target_models.append("Google Gemini 1.5 Pro")
                if not target_models:
                    target_models = ["Cross-Vendor LLM", "Anthropic Claude", "OpenAI GPT-4o"]

                prompts.append({
                    "id": f"adrian-eng-{row.get('id', len(prompts)+1)}",
                    "prompt_title": f"System Architecture: {name}",
                    "exact_prompt": p_text,
                    "description": desc,
                    "category": cat,
                    "prompt_type": "system_prompt",
                    "target_models": target_models,
                    "variable_keys": extract_variables(p_text),
                    "source_url": url,
                    "source_repo": "Adrian2016/awesome-prompts",
                    "source_license": "MIT",
                    "tags": ["system-prompt", "agent-architecture", "developer-tools", cat.lower().replace(' ', '-')]
                })
            print(f"Loaded {len(prompts)} Adrian engineering system prompts.")
        except Exception as e:
            print(f"Error parsing Adrian engineering parquet: {e}")

    # -------------------------------------------------------------
    # 2. Adrian2016/awesome-prompts (Library Parquet - 2,777 rows)
    # -------------------------------------------------------------
    adrian_lib_file = '/tmp/hf_prompts/adrian_library.parquet'
    if os.path.exists(adrian_lib_file):
        print("Ingesting Adrian2016/awesome-prompts (library split)...")
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(adrian_lib_file)
            lib_count = 0
            for row in table.to_pylist():
                p_text = str(row.get('prompt_en', '')).strip()
                if not p_text or p_text in seen_prompts:
                    continue
                seen_prompts.add(p_text)

                title = row.get('title_en', 'General AI Prompt')
                cat = row.get('category', 'general').title()
                pid = row.get('id', f"lib-{lib_count+1}")

                target_models = ["OpenAI GPT-4o", "Anthropic Claude 3.5 Sonnet", "Google Gemini 1.5 Pro"]
                if cat.lower() == 'image':
                    target_models = ["Midjourney", "Flux.1", "DALL-E 3", "SDXL"]

                prompts.append({
                    "id": f"adrian-lib-{pid}",
                    "prompt_title": f"Prompt: {title}",
                    "exact_prompt": p_text,
                    "description": f"Curated {cat} prompt from awesome-prompts library split.",
                    "category": f"{cat} & Production",
                    "prompt_type": "library_prompt",
                    "target_models": target_models,
                    "variable_keys": extract_variables(p_text),
                    "source_repo": "Adrian2016/awesome-prompts",
                    "source_license": row.get('license', 'MIT'),
                    "tags": ["awesome-prompts", cat.lower().replace(' ', '-'), "curated-library"]
                })
                lib_count += 1
            print(f"Loaded {lib_count} Adrian library prompts.")
        except Exception as e:
            print(f"Error parsing Adrian library parquet: {e}")

    # -------------------------------------------------------------
    # 3. Nymbo/Official_LLM_System_Prompts (38 official system prompts)
    # -------------------------------------------------------------
    nymbo_dir = '/tmp/nymbo_prompts'
    if os.path.exists(nymbo_dir):
        print("Ingesting Nymbo/Official_LLM_System_Prompts...")
        nymbo_files = glob.glob(os.path.join(nymbo_dir, '*.md'))
        for nf in nymbo_files:
            if 'README' in nf:
                continue
            base = os.path.splitext(os.path.basename(nf))[0]
            try:
                with open(nf, 'r', encoding='utf-8') as f:
                    content = f.read()
                    code_match = re.search(r'```(?:markdown|text)?\n(.*?)```', content, re.DOTALL)
                    if code_match:
                        p_text = code_match.group(1).strip()
                    else:
                        p_text = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL).strip()

                    if len(p_text) > 40 and p_text not in seen_prompts:
                        seen_prompts.add(p_text)

                        vendor = "Cross-Vendor"
                        target_models = []
                        lower_name = base.lower()
                        if 'chatgpt' in lower_name or 'gpt' in lower_name or 'openai' in lower_name:
                            vendor = "OpenAI"
                            target_models = ["OpenAI ChatGPT", "OpenAI GPT-4o"]
                        elif 'claude' in lower_name:
                            vendor = "Anthropic"
                            target_models = ["Anthropic Claude 3.5 Sonnet", "Anthropic Claude 3 Opus"]
                        elif 'cursor' in lower_name:
                            vendor = "Cursor"
                            target_models = ["Cursor IDE Agent"]
                        elif 'devin' in lower_name:
                            vendor = "Cognition AI"
                            target_models = ["Devin 2.0 Agent"]
                        elif 'copilot' in lower_name:
                            vendor = "GitHub / Microsoft"
                            target_models = ["GitHub Copilot", "Microsoft Copilot"]
                        elif 'grok' in lower_name:
                            vendor = "xAI"
                            target_models = ["xAI Grok 2", "xAI Grok 3"]
                        elif 'vercel' in lower_name or 'v0' in lower_name:
                            vendor = "Vercel"
                            target_models = ["Vercel v0 Full-Stack Agent"]
                        elif 'perplexity' in lower_name:
                            vendor = "Perplexity"
                            target_models = ["Perplexity AI"]
                        else:
                            target_models = ["Official Foundation Model"]

                        prompts.append({
                            "id": f"nymbo-{re.sub(r'[^a-z0-9]+', '-', base.lower()).strip('-')}",
                            "prompt_title": f"Official System Instructions: {base}",
                            "exact_prompt": p_text,
                            "description": f"Verbatim extracted official baseline system context for {base}.",
                            "category": "Official System Instructions",
                            "prompt_type": "official_system_prompt",
                            "target_models": target_models,
                            "vendor": vendor,
                            "variable_keys": extract_variables(p_text),
                            "source_repo": "Nymbo/Official_LLM_System_Prompts",
                            "source_license": "Public Documentation",
                            "tags": ["official-system-prompt", "baseline-context", vendor.lower().replace(' ', '-')]
                        })
            except Exception as e:
                print(f"Error parsing Nymbo {nf}: {e}")

    # -------------------------------------------------------------
    # 4. danielrosehill/System-Prompt-Library (Custom GPTs)
    # -------------------------------------------------------------
    gpt_json_dir = '/tmp/system_prompt_library/system-prompts/json'
    if os.path.exists(gpt_json_dir):
        print("Ingesting danielrosehill/System-Prompt-Library (Custom GPTs)...")
        json_files = glob.glob(os.path.join(gpt_json_dir, '*.json'))
        for jf in json_files:
            if 'consolidated' in jf:
                continue
            try:
                with open(jf, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                    p_text = d.get('System Prompt', '')
                    if not p_text or len(p_text.strip()) < 30 or p_text in seen_prompts:
                        continue
                    seen_prompts.add(p_text)

                    name = d.get('agent_name', os.path.splitext(os.path.basename(jf))[0])
                    desc = d.get('Description', '') or d.get('One Line Summary', '')
                    store_url = d.get('ChatGPT Access URL', '')

                    caps = []
                    if d.get('Is Agent'): caps.append('agent')
                    if d.get('Structured Output (Workflow Type)'): caps.append('structured-output')
                    if d.get('Image Generation (Workflow Type)'): caps.append('image-generation')
                    if d.get('Vision (Req)'): caps.append('vision')
                    if d.get('Writing Assistant'): caps.append('writing')
                    if d.get('Roleplay (Behavior)'): caps.append('roleplay')
                    if d.get('Autonomous'): caps.append('autonomous')

                    category = "Custom GPT Assistant"
                    if 'writing' in caps: category = "Writing & Editorial GPT"
                    elif 'agent' in caps or 'autonomous' in caps: category = "Autonomous Agent GPT"
                    elif 'structured-output' in caps: category = "Structured Data & API GPT"

                    prompts.append({
                        "id": f"customgpt-{re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:50]}",
                        "prompt_title": f"Custom GPT: {name}",
                        "exact_prompt": p_text.strip(),
                        "description": desc,
                        "category": category,
                        "prompt_type": "custom_gpt_prompt",
                        "target_models": ["OpenAI ChatGPT (Custom GPT)", "OpenAI GPT-4o"],
                        "chatgpt_store_url": store_url,
                        "capability_flags": caps,
                        "variable_keys": extract_variables(p_text),
                        "source_repo": "danielrosehill/System-Prompt-Library",
                        "source_license": "MIT",
                        "tags": ["custom-gpt", "chatgpt-store", "system-prompt"] + caps
                    })
            except Exception as e:
                pass

    # -------------------------------------------------------------
    # 5. EricLu/System-Prompt-Instruction-Real-world-Implementation
    # -------------------------------------------------------------
    ericlu_file = '/tmp/hf_prompts/ericlu_gpts.jsonl'
    if os.path.exists(ericlu_file):
        print("Ingesting EricLu/System-Prompt-Instruction...")
        try:
            eric_count = 0
            with open(ericlu_file, 'r', encoding='utf-8') as f:
                for line in f:
                    d = json.loads(line)
                    msgs = d.get('messages', [])
                    if msgs and msgs[0].get('role') == 'system':
                        p_text = msgs[0].get('content', '').strip()
                        if len(p_text) > 150 and p_text not in seen_prompts:
                            seen_prompts.add(p_text)
                            h_match = re.search(r'#+\s*(.+?)(?:\n|\Z)', p_text)
                            title = h_match.group(1).strip() if h_match else f"Custom GPT Specification {eric_count+1}"
                            title = re.sub(r'[*_`]', '', title)[:60]

                            prompts.append({
                                "id": f"ericlu-gpt-{eric_count+1}",
                                "prompt_title": f"Production Custom GPT: {title}",
                                "exact_prompt": p_text,
                                "description": "Production Custom GPT instruction set with tool constraints and behavior parameters.",
                                "category": "Production Custom GPTs",
                                "prompt_type": "custom_gpt_prompt",
                                "target_models": ["OpenAI ChatGPT (Custom GPT)", "OpenAI GPT-4o"],
                                "variable_keys": extract_variables(p_text),
                                "source_repo": "EricLu/System-Prompt-Instruction-Real-world-Implementation-Training-set",
                                "source_license": "Apache-2.0",
                                "tags": ["custom-gpt", "system-prompt", "production-instructions"]
                            })
                            eric_count += 1
                            if eric_count >= 3000:
                                break
            print(f"Loaded {eric_count} EricLu Custom GPT instructions.")
        except Exception as e:
            print(f"Error parsing EricLu dataset: {e}")

    # -------------------------------------------------------------
    # 6. archit11/claude-code-traces (Claude Code CLI subagents)
    # -------------------------------------------------------------
    claude_trace_file = '/tmp/hf_prompts/claude_code_traces.parquet'
    if os.path.exists(claude_trace_file):
        print("Ingesting archit11/claude-code-traces...")
        try:
            import pyarrow.parquet as pq
            table = pq.read_table(claude_trace_file)
            for row in table.to_pylist():
                c_str = row.get('conversation_json', '')
                c_json = json.loads(c_str)
                req = c_json.get('request', {})
                sys_content = req.get('system', [])
                p_text = ""
                if isinstance(sys_content, list):
                    for item in sys_content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            p_text += item.get('text', '') + "\n"
                        elif isinstance(item, str):
                            p_text += item + "\n"
                elif isinstance(sys_content, str):
                    p_text = sys_content

                p_text = p_text.strip()
                if len(p_text) > 40 and p_text not in seen_prompts:
                    seen_prompts.add(p_text)
                    title_words = p_text.split()[:6]
                    title = ' '.join(title_words).strip(',.: ')

                    prompts.append({
                        "id": f"claude-trace-{len(prompts)+1}",
                        "prompt_title": f"Claude Code Subagent: {title}",
                        "exact_prompt": p_text,
                        "description": "Production system instruction executed by Anthropic Claude Code CLI subagent.",
                        "category": "Autonomous Coding Agent Subagent",
                        "prompt_type": "subagent_system_prompt",
                        "target_models": ["Anthropic Claude 3.5 Sonnet", "Claude Code CLI"],
                        "variable_keys": extract_variables(p_text),
                        "source_repo": "archit11/claude-code-traces",
                        "source_license": "Open Source Traces",
                        "tags": ["claude-code", "subagent", "system-prompt", "git-automation"]
                    })
        except Exception as e:
            print(f"Error parsing claude code traces: {e}")

    # -------------------------------------------------------------
    # 7. caio4279/gemini-notebook-prompts (Google Gemini Grounding)
    # -------------------------------------------------------------
    gemini_file = '/tmp/hf_prompts/gemini_notebook.jsonl'
    if os.path.exists(gemini_file):
        print("Ingesting caio4279/gemini-notebook-prompts...")
        try:
            with open(gemini_file, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        p_text = d.get('system_prompt', '')
                        if p_text and p_text not in seen_prompts:
                            seen_prompts.add(p_text)
                            task_name = d.get('tarefa', 'Document Grounding')
                            prompts.append({
                                "id": f"gemini-notebook-{len(prompts)+1}",
                                "prompt_title": f"Gemini NotebookLM: {task_name}",
                                "exact_prompt": p_text,
                                "description": f"Gemini long-context document synthesis & grounding prompt for {task_name}.",
                                "category": "Document Grounding & Synthesis",
                                "prompt_type": "grounding_system_prompt",
                                "target_models": ["Google Gemini 1.5 Pro", "NotebookLM"],
                                "variable_keys": extract_variables(p_text),
                                "source_repo": "caio4279/gemini-notebook-prompts",
                                "source_license": "MIT",
                                "tags": ["gemini", "notebooklm", "document-grounding", "synthesis"]
                            })
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error parsing Gemini notebook prompts: {e}")

    # -------------------------------------------------------------
    # 8. pisterlabs/promptset (Developer Prompts)
    # -------------------------------------------------------------
    promptset_filtered = '/tmp/promptset/opro/categorize/filtered_prompts.json'
    if os.path.exists(promptset_filtered):
        print("Ingesting pisterlabs/promptset (developer prompts)...")
        try:
            with open(promptset_filtered, 'r', encoding='utf-8') as f:
                p_list = json.load(f)
                for item in p_list:
                    p_text = item.strip() if isinstance(item, str) else str(item)
                    if len(p_text) > 40 and p_text not in seen_prompts:
                        seen_prompts.add(p_text)
                        title_snip = ' '.join(p_text.split()[:5]).strip('.,: ')

                        prompts.append({
                            "id": f"promptset-{len(prompts)+1}",
                            "prompt_title": f"Developer Prompt: {title_snip}",
                            "exact_prompt": p_text,
                            "description": "Production prompt extracted from developer Python & TypeScript codebases.",
                            "category": "Developer Tooling & API Prompts",
                            "prompt_type": "developer_prompt",
                            "target_models": ["OpenAI GPT-4o", "Anthropic Claude", "LangChain"],
                            "variable_keys": extract_variables(p_text),
                            "source_repo": "pisterlabs/promptset",
                            "source_license": "MIT",
                            "tags": ["developer-prompt", "langchain", "production-api"]
                        })
        except Exception as e:
            print(f"Error parsing promptset: {e}")

    print(f"\nTotal system & engineering prompts extracted: {len(prompts)}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)

    print(f"Saved successfully to: {OUTPUT_FILE}")

if __name__ == '__main__':
    run()
