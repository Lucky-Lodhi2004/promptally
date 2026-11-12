#!/usr/bin/env python3
"""
Ingestion Pipeline for ComfyUI Workflows:
- Extracts .json workflow graphs from /tmp/wyrde-workflows
- Extracts embedded workflow & prompt JSON graphs from /tmp/comfy_examples PNG metadata (Flux, SDXL, Wan, HunyuanVideo, LTX-Video)
- Normalizes into /home/lucky/repos/Promptally/data/extracted/comfyui_workflows.json
"""

import os
import json
import struct
import re

OUTPUT_FILE = '/home/lucky/repos/Promptally/data/extracted/comfyui_workflows.json'

def extract_png_metadata(file_path):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()
        if data[:8] != b'\x89PNG\r\n\x1a\n':
            return None
        pos = 8
        chunks = {}
        while pos < len(data):
            if pos + 8 > len(data):
                break
            length, chunk_type = struct.unpack('>I4s', data[pos:pos+8])
            pos += 8
            chunk_data = data[pos:pos+length]
            pos += length + 4 # skip CRC
            if chunk_type == b'tEXt':
                null_pos = chunk_data.find(b'\0')
                if null_pos != -1:
                    key = chunk_data[:null_pos].decode('latin1', errors='ignore')
                    val = chunk_data[null_pos+1:].decode('latin1', errors='ignore')
                    chunks[key] = val
        return chunks
    except Exception as e:
        return None

def clean_title_from_filename(filename):
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[-_]+', ' ', name)
    words = [w.capitalize() for w in name.split()]
    title = ' '.join(words)
    if not title.lower().startswith('comfyui'):
        title = f"ComfyUI Workflow for {title}"
    return title

def run():
    workflows = []
    seen_slugs = set()

    # 1. Ingest official ComfyUI_examples (PNG embedded workflows & JSONs)
    examples_dir = '/tmp/comfy_examples'
    if os.path.exists(examples_dir):
        print("Extracting official ComfyUI reference workflows...")
        for root, _, files in os.walk(examples_dir):
            if '.git' in root:
                continue
            folder_category = os.path.basename(root)
            for f in files:
                full_path = os.path.join(root, f)
                slug = os.path.splitext(f)[0].lower().replace('_', '-').replace(' ', '-')
                
                # Check for explicit .json workflow
                if f.endswith('.json'):
                    try:
                        with open(full_path, 'r', encoding='utf-8') as jf:
                            graph_data = json.load(jf)
                        title = f"ComfyUI Workflow for {clean_title_from_filename(f)}"
                        workflows.append({
                            "workflow_title": title,
                            "workflow_type": "comfyui_node_graph",
                            "model_compatibility": [folder_category.upper()],
                            "source_slug": slug,
                            "file_name": f,
                            "node_graph_json": graph_data,
                            "tags": ["comfyui", "node-graph", folder_category, "official-example"],
                            "source_repo": "https://github.com/comfyanonymous/ComfyUI_examples",
                            "license": "GPL-3.0"
                        })
                        seen_slugs.add(slug)
                    except Exception:
                        pass
                
                # Check for PNG embedded workflow
                elif f.endswith('.png') or f.endswith('.webp'):
                    if slug in seen_slugs:
                        continue
                    chunks = extract_png_metadata(full_path)
                    if chunks and ('workflow' in chunks or 'prompt' in chunks):
                        try:
                            graph = json.loads(chunks.get('workflow') or chunks.get('prompt'))
                            title = f"ComfyUI Workflow for {clean_title_from_filename(f)}"
                            workflows.append({
                                "workflow_title": title,
                                "workflow_type": "comfyui_node_graph",
                                "model_compatibility": [folder_category.upper()],
                                "source_slug": slug,
                                "file_name": f"{slug}.json",
                                "node_graph_json": graph,
                                "tags": ["comfyui", "node-graph", folder_category, "image-to-workflow"],
                                "source_repo": "https://github.com/comfyanonymous/ComfyUI_examples",
                                "license": "GPL-3.0"
                            })
                            seen_slugs.add(slug)
                        except Exception:
                            pass

    # 2. Ingest wyrde-comfyui-workflows (.json files)
    wyrde_dir = '/tmp/wyrde-workflows'
    if os.path.exists(wyrde_dir):
        print("Extracting wyrde-comfyui-workflows...")
        for root, _, files in os.walk(wyrde_dir):
            if '.git' in root:
                continue
            for f in files:
                if not f.endswith('.json'):
                    continue
                full_path = os.path.join(root, f)
                slug = os.path.splitext(f)[0].lower().replace('_', '-').replace(' ', '-')
                if slug in seen_slugs:
                    continue
                try:
                    with open(full_path, 'r', encoding='utf-8') as jf:
                        graph_data = json.load(jf)
                    title = f"ComfyUI Workflow: {clean_title_from_filename(f)}"
                    workflows.append({
                        "workflow_title": title,
                        "workflow_type": "comfyui_node_graph",
                        "model_compatibility": ["SDXL", "SD1.5", "Flux"],
                        "source_slug": slug,
                        "file_name": f,
                        "node_graph_json": graph_data,
                        "tags": ["comfyui", "node-graph", "upscaling", "latent-refiner"],
                        "source_repo": "https://github.com/wyrde/wyrde-comfyui-workflows",
                        "license": "MIT"
                    })
                    seen_slugs.add(slug)
                except Exception:
                    pass

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out:
        json.dump(workflows, out, indent=2)

    print(f"\nSuccessfully extracted {len(workflows)} ComfyUI Node Graphs into {OUTPUT_FILE}!")

if __name__ == '__main__':
    run()

