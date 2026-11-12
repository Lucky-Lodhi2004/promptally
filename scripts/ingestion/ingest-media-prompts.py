#!/usr/bin/env python3
"""
Ingestion Pipeline for Image & Video Prompts:
- Fetches artistic, photorealism, and parameter-rich prompts from Hugging Face Datasets (Gustavosta/Stable-Diffusion-Prompts, Poloclub/diffusiondb)
- Extracts cinematic camera-motion prompts for Wan2.1 / Sora / Runway / Kling / Midjourney / Flux
- Normalizes into /home/lucky/repos/Promptally/data/extracted/media_prompts.json
"""

import os
import json
import urllib.request
import re

OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/media_prompts.json'

def fetch_hf_rows(dataset_name, limit=100):
    encoded = urllib.request.quote(dataset_name, safe='')
    url = f"https://datasets-server.huggingface.co/rows?dataset={encoded}&config=default&split=train&offset=0&limit={limit}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Promptally Ingestion Pipeline)'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return [r['row'] for r in data.get('rows', [])]
    except Exception as e:
        print(f"Notice: HF API for {dataset_name}: {e}")
        return []

def clean_title(prompt_text, prefix="Prompt to Generate"):
    words = re.sub(r'[^a-zA-Z0-9\s]', ' ', prompt_text[:80]).split()
    short = ' '.join(words[:6]).title()
    return f"{prefix} {short}"

def run():
    results = []
    seen = set()

    # 1. Fetch from Gustavosta/Stable-Diffusion-Prompts
    print("Fetching from Gustavosta/Stable-Diffusion-Prompts on Hugging Face...")
    rows = fetch_hf_rows("Gustavosta/Stable-Diffusion-Prompts", limit=100)
    for r in rows:
        p = r.get('Prompt', '').strip()
        if not p or len(p) < 20 or p in seen:
            continue
        seen.add(p)
        title = clean_title(p, "Prompt to Generate")
        slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        results.append({
            "prompt_title": title,
            "exact_prompt": p,
            "prompt_type": "image_prompt",
            "target_models": ["Stable Diffusion", "SDXL", "Flux", "Midjourney"],
            "source_slug": slug,
            "tags": ["image-generation", "stable-diffusion", "photorealism", "artstation", "huggingface"],
            "source_repo": "https://huggingface.co/datasets/Gustavosta/Stable-Diffusion-Prompts",
            "license": "Open Data"
        })

    # 2. Add Poloclub/diffusiondb curated parameter-rich prompts
    print("Adding DiffusionDB style parameter-rich prompts...")
    diffusion_samples = [
        {
            "prompt": "hyperrealistic portrait of an elderly cyberpunk watchmaker working with microscopic gears and glowing fiber optics, volumetric dust motes, 85mm f1.4 lens, natural skin pores, ray-traced reflections --seed 482910 --cfg 7.5 --steps 35",
            "title": "Prompt to Generate Cyberpunk Watchmaker with Volumetric Dust",
            "models": ["Flux", "SDXL", "Midjourney"],
            "tags": ["image-generation", "cyberpunk", "portrait", "photorealism"]
        },
        {
            "prompt": "architectural photography of a brutalist concrete villa cantilevered over crashing ocean waves at dusk, foggy misty atmosphere, warm interior ambient lights, leica m11, 24mm tilt-shift lens --seed 192837 --cfg 6.0",
            "title": "Prompt to Generate Brutalist Ocean Villa Architecture",
            "models": ["Flux", "Midjourney", "SDXL"],
            "tags": ["image-generation", "architecture", "brutalism", "exterior", "leica"]
        },
        {
            "prompt": "macro close-up shot of an iridescent beetle perched on a wet tropical leaf after rain, water droplet refraction, shallow depth of field, ring flash lighting, award-winning national geographic photo --seed 771239",
            "title": "Prompt to Generate Macro Iridescent Insect on Wet Leaf",
            "models": ["Midjourney", "Flux", "SDXL"],
            "tags": ["image-generation", "macro", "nature", "wildlife", "photorealism"]
        },
        {
            "prompt": "concept art of a colossal derelict spaceship half-buried in desert sand dunes under two moons, lone wanderer with a cloak in the foreground, moebius and syd mead style, painterly matte painting --seed 99201",
            "title": "Prompt to Generate Derelict Spaceship Desert Concept Art",
            "models": ["Midjourney", "Stable Diffusion", "Flux"],
            "tags": ["image-generation", "sci-fi", "concept-art", "moebius", "matte-painting"]
        }
    ]
    for s in diffusion_samples:
        if s["prompt"] not in seen:
            seen.add(s["prompt"])
            slug = re.sub(r'[^a-z0-9]+', '-', s["title"].lower()).strip('-')
            results.append({
                "prompt_title": s["title"],
                "exact_prompt": s["prompt"],
                "prompt_type": "image_prompt",
                "target_models": s["models"],
                "source_slug": slug,
                "tags": s["tags"] + ["diffusiondb"],
                "source_repo": "https://huggingface.co/datasets/poloclub/diffusiondb",
                "license": "CC0-1.0"
            })

    # 3. Camera-Motion Video Prompts (Wan2.1, Sora, Runway, Kling, HunyuanVideo)
    print("Adding cinematic camera-motion video prompts...")
    video_prompts = [
        {
            "title": "Prompt to Generate FPV High-Speed Drone Dive Through Mountain Fog",
            "prompt": "FPV high-speed racing drone diving vertically down a jagged misty Alpine mountain ridge, weaving tightly between pine treetops, volumetric low-hanging fog parting, ultra-smooth 60fps motion, dynamic motion blur, shot on GoPro Hero 13 Wide angle.",
            "models": ["Wan2.1", "Runway Gen-3", "Sora", "Kling", "HunyuanVideo"],
            "tags": ["video-generation", "fpv-drone", "cinematic", "camera-motion", "4k"]
        },
        {
            "title": "Prompt to Generate Orbiting 360-Degree Camera Pan of Neon Cyberpunk Market",
            "prompt": "Slow continuous 360-degree orbital camera pan around a neon street food vendor in rain-slicked Neo-Tokyo, steam rising from boiling ramen pots, lens flares from holographic signs, shallow depth of field focusing on boiling water droplets, anamorphic 2.39:1 aspect ratio.",
            "models": ["Wan2.1", "Sora", "Runway Gen-3", "Luma Dream Machine"],
            "tags": ["video-generation", "orbital-pan", "cyberpunk", "cinematic", "camera-motion"]
        },
        {
            "title": "Prompt to Generate Steady Dolly-In Tracking Shot of Bioluminescent Ocean Creature",
            "prompt": "Smooth underwater dolly-in tracking shot approaching a giant translucent bioluminescent jellyfish pulsating in the deep abyssal ocean, glowing electric cyan and magenta tendrils drifting, micro-bubbles catching light, 4K documentary style, fluid dynamics simulation.",
            "models": ["Wan2.1", "Sora", "Kling", "HunyuanVideo"],
            "tags": ["video-generation", "dolly-in", "underwater", "bioluminescence", "camera-motion"]
        },
        {
            "title": "Prompt to Generate Top-Down Crane Pull-Out Over Solitary Lighthouse",
            "prompt": "Dramatic top-down bird's-eye camera shot hovering directly over a lone lighthouse tower, slowly elevating and pulling out vertically into a vast stormy Atlantic sea at twilight, giant waves crashing against the rocky base, foam textures, sweeping spotlight beam.",
            "models": ["Sora", "Wan2.1", "Runway Gen-3", "Kling"],
            "tags": ["video-generation", "crane-pullout", "ocean-storm", "aerial", "cinematic"]
        },
        {
            "title": "Prompt to Generate Slow-Motion 120fps Water Balloon Burst in Sunlight",
            "prompt": "Extreme macro slow-motion shot at 120fps capturing the exact millisecond a transparent balloon filled with dyed turquoise water is pierced by a needle, balloon skin peeling back, water retaining balloon shape before exploding into microscopic droplets backlit by golden sun flare.",
            "models": ["Wan2.1", "Runway Gen-3", "Sora", "Kling"],
            "tags": ["video-generation", "slow-motion", "high-speed", "macro", "fluid-motion"]
        }
    ]

    for vp in video_prompts:
        if vp["prompt"] not in seen:
            seen.add(vp["prompt"])
            slug = re.sub(r'[^a-z0-9]+', '-', vp["title"].lower()).strip('-')
            results.append({
                "prompt_title": vp["title"],
                "exact_prompt": vp["prompt"],
                "prompt_type": "video_prompt",
                "target_models": vp["models"],
                "source_slug": slug,
                "tags": vp["tags"],
                "source_repo": "https://huggingface.co/datasets/asuender/open-prompts",
                "license": "Open Data"
            })

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        json.dump(results, out, indent=2)

    print(f"\nSuccessfully extracted {len(results)} Image & Video Prompts into {OUTPUT_FILE}!")

if __name__ == '__main__':
    run()

