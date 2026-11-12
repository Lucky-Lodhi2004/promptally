#!/usr/bin/env python3
"""
Dedicated Image Generation Prompts & Style JSONs Ingestion Pipeline:
- freestylefly/awesome-gpt-image-2 (541 GPT-4o image prompts with demo images)
- jamez-bondos/awesome-gpt4o-images (100 case.yml files with prompt_en and demo images)
- lllyasviel/Fooocus & twri/sdxl_prompt_styler (274 style presets with sample image previews)
- devanshug2307/Awesome-AI-Image-Prompts (commercial product photography, logos, studio headshots)
- Accurately links preview_image_url via GitHub Raw CDN
- Saves into: /home/lucky/repos/Promptally/data/extracted/image_prompts.json
"""

import os
import sys
import json
import yaml
import re

OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/image_prompts.json'

def extract_variables(text):
    bracket_vars = re.findall(r'\[([A-Z0-9_\-\s/]+)\]', text)
    curly_vars = re.findall(r'\{\{([A-Z0-9_\-\s/]+)\}\}', text)
    combined = set()
    for v in bracket_vars + curly_vars:
        clean = v.strip().upper().replace(' ', '_').replace('/', '_')
        if len(clean) > 1 and len(clean) < 30:
            combined.add(clean)
    return list(combined)

def normalize_to_curly(text):
    return re.sub(r'\[([A-Z0-9_\-\s/]+)\]', lambda m: '{{' + m.group(1).strip().upper().replace(' ', '_').replace('/', '_') + '}}', text)

def clean_title(title, prefix="Prompt to Generate"):
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', title).strip()
    words = [w.capitalize() for w in clean.split()]
    short = ' '.join(words)
    if short.lower().startswith('prompt to'):
        return short
    return f"{prefix} {short}"

def run():
    results = []
    seen = set()

    # 1. Ingest freestylefly/awesome-gpt-image-2
    gpt_image_path = '/tmp/gpt-image-2/data/cases.json'
    if os.path.exists(gpt_image_path):
        print("Ingesting freestylefly/awesome-gpt-image-2 with demo image CDN links...")
        try:
            with open(gpt_image_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            cases = data.get('cases', [])
            for c in cases:
                prompt = (c.get('prompt') or '').strip()
                if not prompt or len(prompt) < 20 or prompt in seen:
                    continue
                seen.add(prompt)

                title_raw = c.get('title') or c.get('category') or 'AI Visual Artwork'
                if re.search(r'[\u4e00-\u9fff]', title_raw):
                    cat = c.get('category') or 'Visual Artwork'
                    styles = ' '.join(c.get('styles', [])[:2])
                    title = f"Prompt to Generate {styles} {cat} for GPT-4o"
                else:
                    title = clean_title(title_raw, "Prompt to Generate")

                slug = re.sub(r'[^a-z0-9]+', '-', f"gpt-image-{c.get('id', '')}-{title}".lower()).strip('-')
                variables = extract_variables(prompt)
                normalized_prompt = normalize_to_curly(prompt)

                # Link demo image if available
                img_path = c.get('image', '').lstrip('/')
                preview_url = None
                if img_path:
                    preview_url = f"https://raw.githubusercontent.com/freestylefly/awesome-gpt-image-2/main/data/{img_path}"

                results.append({
                    "prompt_title": title,
                    "exact_prompt": normalized_prompt,
                    "prompt_type": "image_prompt",
                    "style_category": c.get('category', 'Creative Visuals'),
                    "target_models": ["GPT-4o", "DALL-E 3", "ChatGPT"],
                    "variables": variables,
                    "preview_image_url": preview_url,
                    "source_slug": slug,
                    "tags": ["gpt-4o", "dall-e-3", "image-generation"] + [s.lower() for s in c.get('styles', [])],
                    "source_repo": "https://github.com/freestylefly/awesome-gpt-image-2",
                    "license": "MIT"
                })
        except Exception as e:
            print("Error reading gpt-image-2:", e)

    # 2. Ingest jamez-bondos/awesome-gpt4o-images
    cases_dir = '/tmp/gpt4o-images/cases'
    if os.path.exists(cases_dir):
        print("Ingesting jamez-bondos/awesome-gpt4o-images with demo image CDN links...")
        for case_id in os.listdir(cases_dir):
            case_yml = os.path.join(cases_dir, case_id, 'case.yml')
            if not os.path.exists(case_yml):
                continue
            try:
                with open(case_yml, 'r', encoding='utf-8') as f:
                    cdata = yaml.safe_load(f)
                if not cdata:
                    continue
                prompt_en = (cdata.get('prompt_en') or cdata.get('prompt') or '').strip()
                if not prompt_en or len(prompt_en) < 20 or prompt_en in seen:
                    continue
                seen.add(prompt_en)

                title_en = cdata.get('title_en') or cdata.get('title') or f"Case {case_id}"
                title = clean_title(title_en, "Prompt to Generate")
                slug = re.sub(r'[^a-z0-9]+', '-', f"gpt4o-case-{case_id}-{title}".lower()).strip('-')
                variables = extract_variables(prompt_en)
                normalized_prompt = normalize_to_curly(prompt_en)

                img_file = cdata.get('image')
                preview_url = None
                if img_file:
                    preview_url = f"https://raw.githubusercontent.com/jamez-bondos/awesome-gpt4o-images/main/cases/{case_id}/{img_file}"

                results.append({
                    "prompt_title": title,
                    "exact_prompt": normalized_prompt,
                    "prompt_type": "image_prompt",
                    "style_category": "GPT-4o Photography & Art",
                    "target_models": ["GPT-4o", "DALL-E 3"],
                    "variables": variables,
                    "preview_image_url": preview_url,
                    "source_slug": slug,
                    "tags": ["gpt-4o", "image-generation", "case-study"],
                    "source_repo": "https://github.com/jamez-bondos/awesome-gpt4o-images",
                    "license": "MIT"
                })
            except Exception as e:
                pass

    # 3. Ingest Fooocus & sdxl_prompt_styler JSONs
    fooocus_dir = '/tmp/fooocus/sdxl_styles'
    samples_dir = '/tmp/fooocus/sdxl_styles/samples'
    sample_files = set(os.listdir(samples_dir)) if os.path.exists(samples_dir) else set()

    if os.path.exists(fooocus_dir):
        print("Ingesting Fooocus & SDXL prompt stylers with sample preview links...")
        for f in os.listdir(fooocus_dir):
            if not f.endswith('.json'):
                continue
            fpath = os.path.join(fooocus_dir, f)
            try:
                with open(fpath, 'r', encoding='utf-8') as jf:
                    styles = json.load(jf)
                for s in styles:
                    name = s.get('name', '').strip()
                    prompt_template = s.get('prompt', '').strip()
                    neg = s.get('negative_prompt', '').strip()
                    if not name or not prompt_template or prompt_template in seen:
                        continue
                    seen.add(prompt_template)

                    title_words = [w.capitalize() for w in name.replace('-', ' ').replace('_', ' ').split()]
                    title = f"Prompt Style: {' '.join(title_words)} (SDXL & Fooocus)"
                    slug = re.sub(r'[^a-z0-9]+', '-', f"sdxl-style-{name}".lower()).strip('-')
                    normalized_prompt = prompt_template.replace('{prompt}', '{{SUBJECT}}')

                    # Check sample image match (e.g., name.replace('-', '_') + '.jpg')
                    img_candidate = name.replace('-', '_') + '.jpg'
                    preview_url = None
                    if img_candidate in sample_files:
                        preview_url = f"https://raw.githubusercontent.com/lllyasviel/Fooocus/main/sdxl_styles/samples/{img_candidate}"

                    results.append({
                        "prompt_title": title,
                        "exact_prompt": normalized_prompt,
                        "negative_prompt": neg,
                        "prompt_type": "image_prompt",
                        "style_category": "SDXL Visual Style Preset",
                        "target_models": ["SDXL", "Fooocus", "Flux", "Midjourney"],
                        "variables": ["SUBJECT"],
                        "preview_image_url": preview_url,
                        "source_slug": slug,
                        "tags": ["sdxl", "fooocus", "style-preset", "image-generation", name.lower()],
                        "source_repo": "https://github.com/lllyasviel/Fooocus",
                        "license": "GPL-3.0"
                    })
            except Exception as e:
                pass

    # 4. Ingest devanshug2307/Awesome-AI-Image-Prompts
    devanshu_md = '/tmp/devanshu-prompts/README.md'
    if os.path.exists(devanshu_md):
        print("Ingesting devanshug2307/Awesome-AI-Image-Prompts...")
        try:
            with open(devanshu_md, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            current_category = "Commercial Photography"
            for line in lines:
                line_str = line.strip()
                if line_str.startswith('## '):
                    current_category = line_str.replace('## ', '').strip()
                elif line_str.startswith('- **') or line_str.startswith('1. ') or (len(line_str) > 30 and 'photo' in line_str.lower()):
                    clean_p = re.sub(r'^[-*\d.]+\s*(?:\*\*[^*]+\*\*:?)?\s*', '', line_str).strip('"` ')
                    if len(clean_p) > 25 and clean_p not in seen and not clean_p.startswith('http'):
                        seen.add(clean_p)
                        title = clean_title(clean_p, f"Prompt to Generate {current_category}")
                        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
                        results.append({
                            "prompt_title": title,
                            "exact_prompt": clean_p,
                            "prompt_type": "image_prompt",
                            "style_category": current_category,
                            "target_models": ["Midjourney", "Flux", "DALL-E 3"],
                            "variables": extract_variables(clean_p),
                            "preview_image_url": None,
                            "source_slug": slug,
                            "tags": ["commercial", "e-commerce", "image-generation", current_category.lower().replace(' ', '-')],
                            "source_repo": "https://github.com/devanshug2307/Awesome-AI-Image-Prompts",
                            "license": "MIT"
                        })
        except Exception as e:
            pass

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        json.dump(results, out, indent=2)

    with_imgs = sum(1 for p in results if p.get('preview_image_url'))
    print(f"\nSuccessfully updated {OUTPUT_FILE} with {len(results)} Image Generation Prompts!")
    print(f"Total Prompts with Live Demo Preview Image CDN Links: {with_imgs} ({round(with_imgs/len(results)*100, 1)}%)")

if __name__ == '__main__':
    run()
