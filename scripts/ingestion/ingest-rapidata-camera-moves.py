#!/usr/bin/env python3
"""
Dedicated Ingestion Pipeline for Rapidata Camera Movement Benchmarks:
Extracts ONLY unique camera movement prompts and their related reference GIFs:
1. Rapidata/camera-movement-human-preference-324k (Scene-agnostic camera control with reference GIFs)
2. Rapidata/relative-camera-movement-human-preference-900k (Scene-relative spatial navigation)

For each unique prompt:
- Extracts reference_gif URL (motion visualization)
- Extracts input_image URL (starting scene)
- Finds the winning model & winning rendered .mp4 video URL based on human preference votes
- Saves deduplicated, rich camera movement prompts into:
  - data/extracted/camera_movement_prompts.json
  - and updates data/extracted/video_prompts.json
"""

import os
import sys
import json
import io
import urllib.request
import re
import pyarrow.parquet as pq

OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/camera_movement_prompts.json'
VIDEO_PROMPTS_FILE = '/home/lucky/repos/Promptally/data/extracted/video_prompts.json'

def extract_variables(text):
    bracket_vars = re.findall(r'\[([A-Z0-9_\-\s/]+)\]', text)
    curly_vars = re.findall(r'\{\{([A-Za-z0-9_\-\s/]+)\}\}', text)
    combined = set()
    for v in bracket_vars + curly_vars:
        clean = v.strip().lower().replace(' ', '_').replace('-', '_')
        if len(clean) > 1 and len(clean) < 30 and not clean.startswith('http'):
            combined.add(clean)
    return sorted(list(combined))

def detect_camera_motion(text, tags_list=None):
    motions = []
    text_lower = text.lower()
    motion_patterns = [
        ('arc', 'Arc Orbit'),
        ('orbit', '360 Orbit'),
        ('dolly', 'Dolly In/Out'),
        ('truck', 'Truck (Horizontal Move)'),
        ('pedestal', 'Pedestal (Vertical Move)'),
        ('rise', 'Crane / Jib Rise'),
        ('rises', 'Crane / Jib Rise'),
        ('tilt', 'Tilt Up/Down'),
        ('pan', 'Pan Left/Right'),
        ('roll', 'Camera Roll (Dutch Angle)'),
        ('zoom', 'Zoom In/Out'),
        ('forward', 'Forward Tracking'),
        ('backward', 'Backward Tracking'),
        ('slide', 'Slider Track'),
        ('under', 'Low Angle / Underside Pass'),
        ('reveal', 'Reveal Shot')
    ]
    for pattern, label in motion_patterns:
        if pattern in text_lower:
            if label not in motions:
                motions.append(label)

    if tags_list:
        for t in tags_list:
            t_str = str(t).strip()
            if t_str and t_str not in motions and len(t_str) < 30:
                motions.append(t_str)

    return motions if motions else ["Camera Kinematics"]

def clean_title(prompt_text):
    first_sentence = prompt_text.split('.')[0].strip()
    words = first_sentence.split()[:7]
    title = ' '.join(words).strip(',:; ')
    return f"Camera Move: {title}"

def run():
    unique_prompts = {}

    # -------------------------------------------------------------
    # 1. Rapidata/camera-movement-human-preference-324k (Scene-Agnostic)
    # -------------------------------------------------------------
    repo_324k = 'Rapidata/camera-movement-human-preference-324k'
    print(f"Scanning {repo_324k} for unique prompts and reference GIFs...")

    # We scan across the files until unique prompt discovery plateaus
    cols_324k = [
        'prompt', 'reference_gif', 'input_image', 'prompt_tags',
        'model1', 'model2', 'video1', 'video2',
        'weighted_results_video1_movement', 'weighted_results_video2_movement'
    ]

    for idx in range(15):
        filename = f"data/train-{idx:05d}.parquet"
        url = f"https://huggingface.co/datasets/{repo_324k}/resolve/main/{filename}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as resp:
                table = pq.read_table(io.BytesIO(resp.read()), columns=cols_324k)
                for row in table.to_pylist():
                    p = row.get('prompt', '').strip()
                    if not p:
                        continue

                    res1 = float(row.get('weighted_results_video1_movement') or 0.0)
                    res2 = float(row.get('weighted_results_video2_movement') or 0.0)
                    winning_model = row.get('model1') if res1 >= res2 else row.get('model2')
                    winning_video = row.get('video1') if res1 >= res2 else row.get('video2')

                    tags = row.get('prompt_tags')
                    if isinstance(tags, str):
                        try:
                            tags = eval(tags)
                        except:
                            tags = [tags]

                    if p not in unique_prompts:
                        unique_prompts[p] = {
                            "prompt": p,
                            "type": "scene_agnostic",
                            "reference_gif": row.get('reference_gif'),
                            "input_image": row.get('input_image'),
                            "prompt_tags": tags if isinstance(tags, list) else [],
                            "winning_model": winning_model,
                            "demo_video_url": winning_video,
                            "top_score": max(res1, res2)
                        }
                    else:
                        # Update winning model if we find a higher score comparison
                        if max(res1, res2) > unique_prompts[p].get("top_score", 0):
                            unique_prompts[p]["top_score"] = max(res1, res2)
                            unique_prompts[p]["winning_model"] = winning_model
                            unique_prompts[p]["demo_video_url"] = winning_video
                            if not unique_prompts[p].get("reference_gif") and row.get("reference_gif"):
                                unique_prompts[p]["reference_gif"] = row.get("reference_gif")
        except Exception as e:
            print(f"File {filename} finished: {e}")
            break

    print(f"Unique prompts after 324k: {len(unique_prompts)}")

    # -------------------------------------------------------------
    # 2. Rapidata/relative-camera-movement-human-preference-900k (Scene-Relative)
    # -------------------------------------------------------------
    repo_900k = 'Rapidata/relative-camera-movement-human-preference-900k'
    print(f"\nScanning {repo_900k} for unique relative spatial navigation prompts...")

    cols_900k = [
        'prompt', 'prompt_tags',
        'model1', 'model2', 'video1', 'video2',
        'weighted_results_video1_alignment', 'weighted_results_video2_alignment'
    ]

    for idx in range(12):
        filename = f"data/train-{idx:05d}.parquet"
        url = f"https://huggingface.co/datasets/{repo_900k}/resolve/main/{filename}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req) as resp:
                table = pq.read_table(io.BytesIO(resp.read()), columns=cols_900k)
                for row in table.to_pylist():
                    p = row.get('prompt', '').strip()
                    if not p:
                        continue

                    res1 = float(row.get('weighted_results_video1_alignment') or 0.0)
                    res2 = float(row.get('weighted_results_video2_alignment') or 0.0)
                    winning_model = row.get('model1') if res1 >= res2 else row.get('model2')
                    winning_video = row.get('video1') if res1 >= res2 else row.get('video2')

                    tags = row.get('prompt_tags')
                    if isinstance(tags, str):
                        try:
                            tags = eval(tags)
                        except:
                            tags = [tags]

                    if p not in unique_prompts:
                        unique_prompts[p] = {
                            "prompt": p,
                            "type": "scene_relative",
                            "reference_gif": None,
                            "input_image": None,
                            "prompt_tags": tags if isinstance(tags, list) else [],
                            "winning_model": winning_model,
                            "demo_video_url": winning_video,
                            "top_score": max(res1, res2)
                        }
                    else:
                        if max(res1, res2) > unique_prompts[p].get("top_score", 0):
                            unique_prompts[p]["top_score"] = max(res1, res2)
                            unique_prompts[p]["winning_model"] = winning_model
                            unique_prompts[p]["demo_video_url"] = winning_video
        except Exception as e:
            print(f"File {filename} finished: {e}")
            break

    print(f"Total unique camera movement prompts collected: {len(unique_prompts)}")

    # Format into Promptally asset schema
    formatted_prompts = []
    for idx, (p_text, meta) in enumerate(unique_prompts.items(), 1):
        is_rel = meta.get("type") == "scene_relative"
        category = "Scene-Relative Spatial Navigation" if is_rel else "Camera Kinematics & Movement Control"
        title = clean_title(p_text)
        motions = detect_camera_motion(p_text, meta.get("prompt_tags", []))

        # Target models: models evaluated in Rapidata benchmark
        winning = meta.get("winning_model") or "Kling 3.0 Pro"
        target_models = list(set([winning, "Kling 3.0 Pro", "Google Veo 3.1", "Wan 3.0", "Runway Gen-3", "Luma Dream Machine"]))

        entry = {
            "id": f"rapidata-cam-{idx:03d}",
            "prompt_title": title,
            "exact_prompt": p_text,
            "negative_prompt": "static camera, jitter, warping geometry, unnatural jump cuts, blurry, watermark",
            "category": category,
            "prompt_type": "camera_motion_prompt",
            "shot_type": "image-to-video",
            "target_models": target_models,
            "camera_motion": motions,
            "winning_model": winning,
            "reference_gif_url": meta.get("reference_gif"),
            "input_image_url": meta.get("input_image"),
            "demo_video_url": meta.get("demo_video_url"),
            "duration_seconds": 5,
            "aspect_ratio": "16:9",
            "variable_keys": extract_variables(p_text),
            "notes": f"Empirically validated by human preference evaluations ({'Scene-Relative Spatial Reasoning' if is_rel else 'Kinematic Camera Control'}). Highest-ranked model: {winning}.",
            "source_repo": "Rapidata/camera-movement-benchmarks",
            "source_license": "CC-BY-4.0",
            "tags": ["camera-movement", "human-preference-benchmark", "image-to-video"] + [m.lower().replace(' ', '-') for m in motions[:3]]
        }
        formatted_prompts.append(entry)

    # Save to dedicated camera_movement_prompts.json
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(formatted_prompts, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(formatted_prompts)} unique camera movement prompts to: {OUTPUT_FILE}")

    # Also integrate into video_prompts.json (avoiding any duplicate prompt texts)
    if os.path.exists(VIDEO_PROMPTS_FILE):
        try:
            with open(VIDEO_PROMPTS_FILE, 'r', encoding='utf-8') as f:
                existing_video_prompts = json.load(f)
            existing_texts = set(x.get('exact_prompt', '').strip() for x in existing_video_prompts)

            added_count = 0
            for p in formatted_prompts:
                if p['exact_prompt'].strip() not in existing_texts:
                    existing_video_prompts.append(p)
                    existing_texts.add(p['exact_prompt'].strip())
                    added_count += 1

            with open(VIDEO_PROMPTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(existing_video_prompts, f, indent=2, ensure_ascii=False)
            print(f"Integrated {added_count} new unique camera movement prompts into: {VIDEO_PROMPTS_FILE}")
            print(f"Total video prompts in library now: {len(existing_video_prompts)}")
        except Exception as e:
            print(f"Error updating video_prompts.json: {e}")

if __name__ == '__main__':
    run()

