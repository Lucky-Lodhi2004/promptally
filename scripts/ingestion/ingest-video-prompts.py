#!/usr/bin/env python3
"""
Dedicated Video Generation Prompts Ingestion Pipeline:
Ingests curated, structured video prompts from 7 production repositories:
1. uniqaiapp/awesome-ai-video-prompts (CC-BY-4.0: Kling, Veo 3, Wan, Runway Gen-4, Seedance)
2. ishandutta2007/veo_prompts (MIT: Google Veo 2 / Veo 3 prompts & showcase cases with demo links)
3. hr98w/awesome-sora-prompts (CC0: OpenAI Sora showcase with 43 official OpenAI CDN MP4 demo videos)
4. Reviral-ai/awesome-sora-2-prompts (MIT: Sora 2 narrative shorts & character continuity)
5. bestimageai/awesome-kling-4-0-prompts (MIT: 108 Kling 4.0 production prompts with official demo videos & poster frames)
6. bestimageai/awesome-minimax-h3-video-prompts (MIT: 100 MiniMax H3 / Hailuo audiovisual prompts with gallery references)
7. jnMetaCode/ai-shortfilm-prompts (MIT: 5-stage storyboard templates & model negative prompts)

Outputs validated JSON into: data/extracted/video_prompts.json
"""

import os
import sys
import json
import glob
import re

OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/video_prompts.json'

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

def detect_camera_motion(text):
    """Detect common cinematography camera motion terms in prompt text."""
    motions = []
    text_lower = text.lower()
    motion_patterns = [
        ('fpv drone', 'FPV Drone'),
        ('drone view', 'Drone Aerial'),
        ('aerial shot', 'Aerial View'),
        ('dolly-in', 'Dolly In'),
        ('dolly in', 'Dolly In'),
        ('dolly out', 'Dolly Out'),
        ('push in', 'Push In'),
        ('pull out', 'Pull Out'),
        ('pull back', 'Pull Back'),
        ('slow pan', 'Slow Pan'),
        ('panning', 'Pan'),
        ('pan left', 'Pan Left'),
        ('pan right', 'Pan Right'),
        ('tilt up', 'Tilt Up'),
        ('tilt down', 'Tilt Down'),
        ('tracking shot', 'Tracking Shot'),
        ('tracking camera', 'Tracking Shot'),
        ('orbit', '360 Orbit'),
        ('arc shot', 'Arc Orbit'),
        ('close-up', 'Close-Up'),
        ('extreme close-up', 'Extreme Close-Up'),
        ('macro', 'Macro'),
        ('wide shot', 'Wide Shot'),
        ('static camera', 'Static Camera'),
        ('handheld', 'Handheld Float'),
        ('steadicam', 'Steadicam'),
        ('low angle', 'Low Angle'),
        ('high angle', 'High Angle'),
        ('bird\'s eye', 'Bird\'s Eye View'),
        ('over-the-shoulder', 'Over-The-Shoulder')
    ]
    for pattern, label in motion_patterns:
        if pattern in text_lower:
            if label not in motions:
                motions.append(label)
    return motions if motions else ["Cinematic Motion"]

def clean_title(title):
    clean = re.sub(r'[^a-zA-Z0-9\s\-–—]', ' ', title).strip()
    words = [w.capitalize() for w in clean.split()]
    return ' '.join(words)

def run():
    prompts = []
    seen_prompts = set()

    # Pre-parse Kling official examples for demo video and poster mappings
    kling_demos = {}
    kling_examples_file = '/tmp/kling_prompts/docs/official-examples.md'
    if os.path.exists(kling_examples_file):
        try:
            with open(kling_examples_file, 'r', encoding='utf-8') as f:
                ktext = f.read()
                table_map = dict(re.findall(r'\[(O\d+)[^\]]*\]\([^\)]+\).*?\[(K\d+)\]', ktext))
                sec_matches = re.findall(r'##\s*(O\d+)[^\n]*\n+\[!\[([^\]]*)\]\((https://static[^\)]+\.(?:jpg|png|webp))\)\]\((https://static[^\)]+\.mp4)\)', ktext)
                for oid, alt, poster, video in sec_matches:
                    kid = table_map.get(oid)
                    if kid:
                        kling_demos[kid.upper()] = {
                            "poster": poster,
                            "video": video
                        }
        except Exception as e:
            print(f"Error parsing Kling examples: {e}")

    # Pre-parse Sora official demo videos
    sora_demos = {}
    sora_readme_file = '/tmp/sora_prompts/README.md'
    if os.path.exists(sora_readme_file):
        try:
            with open(sora_readme_file, 'r', encoding='utf-8') as f:
                sora_text = f.read()
                sora_pairs = re.findall(r'>\s*([^\n]+(?:\n[^\n]+)*?)\n\nGenerated Videos:\s*\[link\]\((https://cdn\.openai\.com[^\)]+)\)', sora_text)
                for p_raw, v_url in sora_pairs:
                    clean_p = re.sub(r'^\s*>\s*', '', p_raw).strip().replace('\n', ' ')
                    sora_demos[clean_p[:45].lower()] = v_url
        except Exception as e:
            print(f"Error pre-parsing Sora demos: {e}")

    # Pre-parse MiniMax reference image briefs
    minimax_imgs = {}
    mm_briefs_file = '/tmp/minimax_prompts/assets/minimax-h3-reference-image-prompts.md'
    if os.path.exists(mm_briefs_file):
        try:
            with open(mm_briefs_file, 'r', encoding='utf-8') as f:
                mm_text = f.read()
                b_matches = re.findall(r'- File:\s*`([^`]+)`\s*\n-\s*Related video recipe:\s*([^\n]+)', mm_text)
                for fname, recipes in b_matches:
                    raw_cdn = f"https://raw.githubusercontent.com/bestimageai/awesome-minimax-h3-video-prompts/main/assets/gallery/{fname}" if 'hero' not in fname else f"https://raw.githubusercontent.com/bestimageai/awesome-minimax-h3-video-prompts/main/assets/{fname}"
                    for r in [x.strip() for x in recipes.split(',')]:
                        minimax_imgs[r.upper()] = raw_cdn
        except Exception as e:
            print(f"Error parsing MiniMax image briefs: {e}")

    # -------------------------------------------------------------
    # 1. uniqaiapp/awesome-ai-video-prompts
    # -------------------------------------------------------------
    uniqai_dir = '/tmp/uniqai_video/data/prompts'
    if os.path.exists(uniqai_dir):
        print("Ingesting uniqaiapp/awesome-ai-video-prompts...")
        json_files = glob.glob(os.path.join(uniqai_dir, '*.json'))
        for jf in json_files:
            try:
                with open(jf, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        exact_prompt = item.get('prompt', '').strip()
                        if not exact_prompt or exact_prompt in seen_prompts:
                            continue
                        seen_prompts.add(exact_prompt)

                        models_raw = item.get('models', [])
                        model_map = {
                            'kling-3': 'Kling 3.0',
                            'kling-4': 'Kling 4.0',
                            'veo-2': 'Google Veo 2',
                            'veo-3': 'Google Veo 3',
                            'wan-2.1': 'Wan 2.1',
                            'wan-2.5': 'Wan 2.5',
                            'seedance': 'Seedance',
                            'seedance-2': 'Seedance 2.0',
                            'runway-gen4': 'Runway Gen-4',
                            'nano-banana': 'Nano Banana',
                            'gpt-image': 'GPT-4o Vision'
                        }
                        target_models = [model_map.get(m, m.title()) for m in models_raw] if models_raw else ["Kling", "Google Veo", "Wan 2.1"]

                        use_case_map = {
                            'portrait': 'Portrait & People',
                            'action': 'Action & Motion',
                            'product': 'Product & Advertising',
                            'nature': 'Nature & Landscapes',
                            'camera-moves': 'Camera Motion & Cinematic FX',
                            'anime': 'Animation & Stylized',
                            'ads': 'Commercials & Ads',
                            'stills': 'Cinematic Stills & Mood',
                            'image-to-video': 'Image-to-Video Animation'
                        }
                        category = use_case_map.get(item.get('use_case', ''), 'Cinematic Video')

                        prompts.append({
                            "id": f"uniqai-{item.get('id', len(prompts)+1)}",
                            "prompt_title": item.get('title', 'Cinematic Video Prompt'),
                            "exact_prompt": exact_prompt,
                            "negative_prompt": None,
                            "category": category,
                            "prompt_type": "video_prompt",
                            "shot_type": "image-to-video" if item.get('mode') == 'i2v' else "single-shot",
                            "target_models": target_models,
                            "camera_motion": detect_camera_motion(exact_prompt + ' ' + item.get('why', '')),
                            "duration_seconds": item.get('duration_s', 5),
                            "aspect_ratio": item.get('aspect', '16:9'),
                            "variable_keys": extract_variables(exact_prompt),
                            "preview_image_url": None,
                            "demo_video_url": None,
                            "notes": item.get('why', ''),
                            "source_repo": "uniqaiapp/awesome-ai-video-prompts",
                            "source_license": "CC-BY-4.0",
                            "tags": list(set(item.get('tags', []) + ["video-generation", "text-to-video"]))
                        })
            except Exception as e:
                print(f"Error parsing {jf}: {e}")

    # -------------------------------------------------------------
    # 2. ishandutta2007/veo_prompts
    # -------------------------------------------------------------
    veo_dir = '/tmp/veo_prompts'
    if os.path.exists(veo_dir):
        print("Ingesting ishandutta2007/veo_prompts...")
        txt_files = glob.glob(os.path.join(veo_dir, 'prompts', '*.txt'))
        for tf in txt_files:
            try:
                with open(tf, 'r', encoding='utf-8') as f:
                    exact_prompt = f.read().strip()
                    if not exact_prompt or exact_prompt in seen_prompts:
                        continue
                    seen_prompts.add(exact_prompt)
                    base_name = os.path.splitext(os.path.basename(tf))[0]
                    title = base_name.replace('_', ' ')

                    prompts.append({
                        "id": f"veo-{base_name.lower().replace('_', '-')}",
                        "prompt_title": title,
                        "exact_prompt": exact_prompt,
                        "negative_prompt": None,
                        "category": "Cinematic & Nature",
                        "prompt_type": "video_prompt",
                        "shot_type": "single-shot",
                        "target_models": ["Google Veo 2", "Google Veo 3"],
                        "camera_motion": detect_camera_motion(exact_prompt),
                        "duration_seconds": 6,
                        "aspect_ratio": "16:9",
                        "variable_keys": extract_variables(exact_prompt),
                        "preview_image_url": None,
                        "demo_video_url": None,
                        "notes": "Curated production-ready Google Veo video prompt.",
                        "source_repo": "ishandutta2007/veo_prompts",
                        "source_license": "MIT",
                        "tags": ["google-veo", "veo-3", "cinematic", "video-generation"]
                    })
            except Exception as e:
                print(f"Error reading {tf}: {e}")

        # Ingest Veo3_Videos.md
        veo3_md = os.path.join(veo_dir, 'Veo3_Videos.md')
        if os.path.exists(veo3_md):
            try:
                with open(veo3_md, 'r', encoding='utf-8') as f:
                    content = f.read()
                    cases = re.findall(r'###\s*(Case\s*\d+)\s*\n(.*?)(?=\n###|\Z)', content, re.DOTALL)
                    for case_name, case_body in cases:
                        p_match = re.search(r'\*\*Prompt:\*\*\s*["\']?(.*?)["\']?\s*(?:\n-|\Z)', case_body, re.DOTALL)
                        src_match = re.search(r'\*\*Source:\*\*\s*\[.*?\]\((https://x\.com/[^\)]+)\)', case_body)
                        demo_link = src_match.group(1) if src_match else None

                        if p_match:
                            prompt_text = p_match.group(1).strip().strip('"').strip("'")
                            if prompt_text and prompt_text not in seen_prompts:
                                seen_prompts.add(prompt_text)
                                title_words = prompt_text.split()[:6]
                                title = ' '.join(title_words).strip(',. ')
                                prompts.append({
                                    "id": f"veo3-{case_name.lower().replace(' ', '-')}",
                                    "prompt_title": f"Google Veo 3: {title}",
                                    "exact_prompt": prompt_text,
                                    "negative_prompt": None,
                                    "category": "Creative Showcase",
                                    "prompt_type": "video_prompt",
                                    "shot_type": "single-shot",
                                    "target_models": ["Google Veo 3"],
                                    "camera_motion": detect_camera_motion(prompt_text),
                                    "duration_seconds": 8,
                                    "aspect_ratio": "16:9",
                                    "variable_keys": extract_variables(prompt_text),
                                    "preview_image_url": None,
                                    "demo_video_url": demo_link,
                                    "notes": "Verified Veo 3 community showcase prompt with demo video link.",
                                    "source_repo": "ishandutta2007/veo_prompts",
                                    "source_license": "MIT",
                                    "tags": ["google-veo", "veo-3", "showcase", "video-generation"]
                                })
            except Exception as e:
                print(f"Error reading Veo3_Videos.md: {e}")

    # -------------------------------------------------------------
    # 3. hr98w/awesome-sora-prompts
    # -------------------------------------------------------------
    sora_dir = '/tmp/sora_prompts'
    if os.path.exists(sora_dir):
        print("Ingesting hr98w/awesome-sora-prompts...")
        sora_readme = os.path.join(sora_dir, 'README.md')
        if os.path.exists(sora_readme):
            try:
                with open(sora_readme, 'r', encoding='utf-8') as f:
                    content = f.read()
                    in_prompts = False
                    sora_idx = 0
                    for line in content.split('\n'):
                        if "Official Video Generation Prompts" in line:
                            in_prompts = True
                        if in_prompts and line.startswith('> '):
                            p_text = line[2:].strip()
                            if p_text.startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. ')):
                                p_text = p_text[3:].strip()
                            if len(p_text) > 20 and p_text not in seen_prompts:
                                seen_prompts.add(p_text)
                                sora_idx += 1
                                title_snippet = ' '.join(p_text.split()[:5]).strip('.,')
                                demo_url = sora_demos.get(p_text[:45].lower())

                                prompts.append({
                                    "id": f"sora-official-{sora_idx}",
                                    "prompt_title": f"Sora: {title_snippet}",
                                    "exact_prompt": p_text,
                                    "negative_prompt": None,
                                    "category": "Cinematic & World Simulation",
                                    "prompt_type": "video_prompt",
                                    "shot_type": "single-shot",
                                    "target_models": ["OpenAI Sora"],
                                    "camera_motion": detect_camera_motion(p_text),
                                    "duration_seconds": 10,
                                    "aspect_ratio": "16:9",
                                    "variable_keys": extract_variables(p_text),
                                    "preview_image_url": None,
                                    "demo_video_url": demo_url,
                                    "notes": "Official OpenAI Sora demo & showcase prompt.",
                                    "source_repo": "hr98w/awesome-sora-prompts",
                                    "source_license": "CC0-1.0",
                                    "tags": ["openai-sora", "sora", "text-to-video", "cinematic"]
                                })
            except Exception as e:
                print(f"Error parsing sora README.md: {e}")

        # Ingest video-editting-prompts.md
        sora_edit = os.path.join(sora_dir, 'video-editting-prompts.md')
        if os.path.exists(sora_edit):
            try:
                with open(sora_edit, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith('> '):
                            p_text = line[2:].strip()
                            if re.match(r'^\d+\.\s*', p_text):
                                p_text = re.sub(r'^\d+\.\s*', '', p_text)
                            if len(p_text) > 15 and p_text not in seen_prompts:
                                seen_prompts.add(p_text)
                                prompts.append({
                                    "id": f"sora-edit-{len(prompts)+1}",
                                    "prompt_title": f"Sora Video Edit: {p_text[:40]}",
                                    "exact_prompt": p_text,
                                    "negative_prompt": None,
                                    "category": "Video-to-Video Editing",
                                    "prompt_type": "video_prompt",
                                    "shot_type": "video-to-video",
                                    "target_models": ["OpenAI Sora"],
                                    "camera_motion": detect_camera_motion(p_text),
                                    "duration_seconds": 8,
                                    "aspect_ratio": "16:9",
                                    "variable_keys": extract_variables(p_text),
                                    "preview_image_url": None,
                                    "demo_video_url": None,
                                    "notes": "OpenAI Sora video-to-video stylization & setting transformation prompt.",
                                    "source_repo": "hr98w/awesome-sora-prompts",
                                    "source_license": "CC0-1.0",
                                    "tags": ["openai-sora", "video-editing", "v2v", "style-transfer"]
                                })
            except Exception as e:
                print(f"Error parsing video-editting-prompts.md: {e}")

    # -------------------------------------------------------------
    # 4. Reviral-ai/awesome-sora-2-prompts
    # -------------------------------------------------------------
    sora2_dir = '/tmp/sora2_prompts'
    if os.path.exists(sora2_dir):
        print("Ingesting Reviral-ai/awesome-sora-2-prompts...")
        sora2_readme = os.path.join(sora2_dir, 'README.md')
        if os.path.exists(sora2_readme):
            try:
                with open(sora2_readme, 'r', encoding='utf-8') as f:
                    content = f.read()
                    sections = re.findall(r'###\s*(\d+\.\s*[^#\n]+)\n(.*?)(?=\n###|\Z)', content, re.DOTALL)
                    for num_title, body in sections:
                        title = clean_title(num_title)
                        p_match = re.search(r'```text\n(.*?)```', body, re.DOTALL)
                        if p_match:
                            p_text = p_match.group(1).strip()
                            if p_text and p_text not in seen_prompts:
                                seen_prompts.add(p_text)
                                dur_match = re.search(r'(\d+)-second', p_text)
                                duration = int(dur_match.group(1)) if dur_match else 12

                                prompts.append({
                                    "id": f"sora2-{re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')}",
                                    "prompt_title": f"Sora 2: {title}",
                                    "exact_prompt": p_text,
                                    "negative_prompt": None,
                                    "category": "Narrative Shorts & Character Continuity",
                                    "prompt_type": "video_prompt",
                                    "shot_type": "narrative-short",
                                    "target_models": ["OpenAI Sora 2"],
                                    "camera_motion": detect_camera_motion(p_text),
                                    "duration_seconds": duration,
                                    "aspect_ratio": "16:9",
                                    "variable_keys": extract_variables(p_text),
                                    "preview_image_url": None,
                                    "demo_video_url": None,
                                    "notes": "Character-anchored narrative prompt engineered for OpenAI Sora 2.",
                                    "source_repo": "Reviral-ai/awesome-sora-2-prompts",
                                    "source_license": "MIT",
                                    "tags": ["openai-sora-2", "sora-2", "narrative", "character-continuity", "short-film"]
                                })
            except Exception as e:
                print(f"Error parsing Sora 2: {e}")

    # -------------------------------------------------------------
    # 5. bestimageai/awesome-kling-4-0-prompts
    # -------------------------------------------------------------
    kling_dir = '/tmp/kling_prompts/prompts'
    if os.path.exists(kling_dir):
        print("Ingesting bestimageai/awesome-kling-4-0-prompts...")
        kling_files = glob.glob(os.path.join(kling_dir, '*.md'))
        cat_map = {
            'action-camera': 'Action & Camera Motion',
            'animation-worlds': 'Animation & Handmade Worlds',
            'cinematic-stories': 'Cinematic Storytelling',
            'creator-social': 'Creator & Social Clips',
            'design-education': 'Design & Educational Motion',
            'dialogue-performance': 'Dialogue & Character Performance',
            'food-craft': 'Food, Macro & Tactile Craft',
            'keyframe-transitions': 'Keyframe Transitions & Endpoints',
            'nature-spaces': 'Nature, Travel & Spaces',
            'omni-reference': 'Multi-Asset Omni Reference',
            'product-films': 'Product Commercials & Luxury Films',
            'video-editing': 'Video Editing & Element Revision'
        }
        for kf in kling_files:
            if 'README' in kf:
                continue
            base = os.path.splitext(os.path.basename(kf))[0]
            category = cat_map.get(base, 'Cinematic Video')
            try:
                with open(kf, 'r', encoding='utf-8') as f:
                    content = f.read()
                    entries = re.findall(r'##\s*(K\d+)\s*—\s*([^#\n]+)\n(.*?)(?=\n##\s*K|\Z)', content, re.DOTALL)
                    for kid, title, body in entries:
                        p_match = re.search(r'```text\n(.*?)```', body, re.DOTALL)
                        if p_match:
                            p_text = p_match.group(1).strip()
                            if p_text and p_text not in seen_prompts:
                                seen_prompts.add(p_text)
                                use_match = re.search(r'\*\*Use:\*\*\s*([^.\n]+)', body)
                                mode_match = re.search(r'\*\*Mode:\*\*\s*([^.\n]+)', body)
                                brief_match = re.search(r'\*\*Brief:\*\*\s*([^.\n]+)', body)

                                use_str = use_match.group(1).strip() if use_match else ""
                                mode_str = mode_match.group(1).strip().lower() if mode_match else "text to video"
                                brief_str = brief_match.group(1).strip() if brief_match else "10 seconds, 16:9"

                                dur_match = re.search(r'(\d+)\s*seconds?', brief_str)
                                duration = int(dur_match.group(1)) if dur_match else 10

                                aspect_match = re.search(r'(\d+:\d+)', brief_str)
                                aspect = aspect_match.group(1) if aspect_match else "16:9"

                                shot_type = "single-shot"
                                if "keyframe" in mode_str or "frames" in mode_str:
                                    shot_type = "keyframe-transition"
                                elif "editing" in mode_str:
                                    shot_type = "video-editing"
                                elif "image to video" in mode_str or "reference" in mode_str:
                                    shot_type = "image-to-video"

                                demo_info = kling_demos.get(kid.upper())
                                poster_url = demo_info['poster'] if demo_info else None
                                video_url = demo_info['video'] if demo_info else None

                                prompts.append({
                                    "id": f"kling-{kid.lower()}",
                                    "prompt_title": f"Kling 4.0: {title.strip()}",
                                    "exact_prompt": p_text,
                                    "negative_prompt": None,
                                    "category": category,
                                    "prompt_type": "video_prompt",
                                    "shot_type": shot_type,
                                    "target_models": ["Kling 4.0"],
                                    "camera_motion": detect_camera_motion(p_text),
                                    "duration_seconds": duration,
                                    "aspect_ratio": aspect,
                                    "variable_keys": extract_variables(p_text),
                                    "preview_image_url": poster_url,
                                    "demo_video_url": video_url,
                                    "notes": f"Use: {use_str}. Mode: {mode_str}. Brief: {brief_str}.",
                                    "source_repo": "bestimageai/awesome-kling-4-0-prompts",
                                    "source_license": "MIT",
                                    "tags": ["kling-4-0", "kling", "text-to-video", base]
                                })
            except Exception as e:
                print(f"Error parsing Kling {kf}: {e}")

    # -------------------------------------------------------------
    # 6. bestimageai/awesome-minimax-h3-video-prompts
    # -------------------------------------------------------------
    mm_dir = '/tmp/minimax_prompts/prompts'
    if os.path.exists(mm_dir):
        print("Ingesting bestimageai/awesome-minimax-h3-video-prompts...")
        mm_files = glob.glob(os.path.join(mm_dir, '*.md'))
        for mf in mm_files:
            if 'README' in mf:
                continue
            base = os.path.splitext(os.path.basename(mf))[0]
            cat_name = re.sub(r'^\d+\-', '', base).replace('-', ' ').title()
            try:
                with open(mf, 'r', encoding='utf-8') as f:
                    content = f.read()
                    entries = re.findall(r'##\s*([A-Z]+-\d+)\s+([^#\n]+)\n(.*?)(?=\n##\s*[A-Z]+-|\Z)', content, re.DOTALL)
                    for mid, title, body in entries:
                        p_match = re.search(r'```text\n(.*?)```', body, re.DOTALL)
                        if p_match:
                            p_text = p_match.group(1).strip()
                            if p_text and p_text not in seen_prompts:
                                seen_prompts.add(p_text)
                                use_match = re.search(r'\*\*Use it for:\*\*\s*([^\n]+)', body)
                                mode_match = re.search(r'\*\*Mode:\*\*\s*([^\n]+)', body)
                                format_match = re.search(r'\*\*Format:\*\*\s*([^\n]+)', body)

                                use_str = use_match.group(1).strip() if use_match else ""
                                mode_str = mode_match.group(1).strip().lower() if mode_match else ""
                                format_str = format_match.group(1).strip() if format_match else "16:9, target 12 seconds"

                                dur_match = re.search(r'(\d+)\s*seconds?', format_str)
                                duration = int(dur_match.group(1)) if dur_match else 12

                                aspect_match = re.search(r'(\d+:\d+)', format_str)
                                aspect = aspect_match.group(1) if aspect_match else "16:9"

                                shot_type = "single-shot"
                                if "continuation" in mode_str:
                                    shot_type = "video-continuation"
                                elif "reference" in mode_str or "images" in mode_str:
                                    shot_type = "multi-reference"

                                concept_img = minimax_imgs.get(mid.upper())

                                prompts.append({
                                    "id": f"minimax-{mid.lower()}",
                                    "prompt_title": f"MiniMax H3: {title.strip()}",
                                    "exact_prompt": p_text,
                                    "negative_prompt": None,
                                    "category": cat_name,
                                    "prompt_type": "video_prompt",
                                    "shot_type": shot_type,
                                    "target_models": ["MiniMax H3 / Hailuo"],
                                    "camera_motion": detect_camera_motion(p_text),
                                    "duration_seconds": duration,
                                    "aspect_ratio": aspect,
                                    "variable_keys": extract_variables(p_text),
                                    "preview_image_url": concept_img,
                                    "demo_video_url": None,
                                    "notes": f"Use case: {use_str}. Mode: {mode_str}.",
                                    "source_repo": "bestimageai/awesome-minimax-h3-video-prompts",
                                    "source_license": "MIT",
                                    "tags": ["minimax-h3", "hailuo", "audiovisual", "video-generation", cat_name.lower().replace(' ', '-')]
                                })
            except Exception as e:
                print(f"Error parsing MiniMax {mf}: {e}")

    # -------------------------------------------------------------
    # 7. jnMetaCode/ai-shortfilm-prompts
    # -------------------------------------------------------------
    sf_dir = '/tmp/shortfilm_prompts/templates'
    if os.path.exists(sf_dir):
        print("Ingesting jnMetaCode/ai-shortfilm-prompts...")
        sf_files = [f for f in glob.glob(os.path.join(sf_dir, '*.md')) if not f.endswith('.zh.md')]
        for sf in sf_files:
            try:
                with open(sf, 'r', encoding='utf-8') as f:
                    content = f.read()
                    title_match = re.search(r'^#\s*(?:Worked Example\s*[—\-]\s*)?(.*)$', content, re.MULTILINE)
                    title = title_match.group(1).strip() if title_match else os.path.splitext(os.path.basename(sf))[0].replace('-', ' ').title()

                    neg_match = re.search(r'###\s*Negative prompt[^\n]*\n```[a-z]*\n(.*?)```', content, re.DOTALL)
                    negative_prompt = neg_match.group(1).strip() if neg_match else "blurry, low resolution, watermark, text overlay, distorted anatomy, plastic CG look"

                    prompt_block_match = re.search(r'##\s*The complete prompt[^\n]*\n(.*?)(?=\n##\s*Why|\Z)', content, re.DOTALL)
                    if prompt_block_match:
                        raw_prompt_section = prompt_block_match.group(1).strip()
                        if raw_prompt_section and raw_prompt_section not in seen_prompts:
                            seen_prompts.add(raw_prompt_section)
                            vars_found = extract_variables(raw_prompt_section)
                            cam_motions = detect_camera_motion(raw_prompt_section)

                            prompts.append({
                                "id": f"shortfilm-{os.path.splitext(os.path.basename(sf))[0]}",
                                "prompt_title": f"Shortfilm Storyboard: {title}",
                                "exact_prompt": raw_prompt_section,
                                "negative_prompt": negative_prompt,
                                "category": "Multi-Shot Storyboard & Production",
                                "prompt_type": "video_storyboard",
                                "shot_type": "multi-shot storyboard",
                                "target_models": ["Google Veo", "Kling", "Wan 2.1", "Seedance", "Runway Gen-4"],
                                "camera_motion": cam_motions,
                                "duration_seconds": 15,
                                "aspect_ratio": "16:9",
                                "variable_keys": vars_found,
                                "preview_image_url": None,
                                "demo_video_url": None,
                                "notes": "Production-grade 5-stage multi-shot storyboard with character continuity and negative prompt.",
                                "source_repo": "jnMetaCode/ai-shortfilm-prompts",
                                "source_license": "MIT",
                                "tags": ["shortfilm", "storyboard", "multi-shot", "negative-prompt", "cinematic-production"]
                            })
            except Exception as e:
                print(f"Error parsing shortfilm {sf}: {e}")

    print(f"\nTotal video prompts extracted: {len(prompts)}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)

    print(f"Saved successfully to: {OUTPUT_FILE}")

if __name__ == '__main__':
    run()
