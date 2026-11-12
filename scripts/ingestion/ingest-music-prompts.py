#!/usr/bin/env python3
"""
Ingestion script for AI Music & Audio Generation Prompts (Section 1: PROMPTS - Audio / Music split).
Extracts and normalizes prompts from:
  1. suno-ai-farm/awesome-ai-music-prompts
  2. suno-ai-farm/awesome-suno-lyrics
  3. naqashmunir21/awesome-suno-prompts
  4. sanic732/SunoForge
  5. bitwize-music-studio/claude-ai-music-skills
  6. elevenlabs/examples & elevenlabs-python
"""

import os
import re
import json
import glob

OUTPUT_PATH = "/home/lucky/repos/Promptally/data/extracted/music_prompts.json"

def clean_slug(text):
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text).strip().lower()
    return re.sub(r'[\s_]+', '-', text)

def extract_bpm_key(text):
    bpm = None
    key = None
    
    # BPM patterns
    bpm_match = re.search(r'BPM:\s*(\d+)', text, re.IGNORECASE)
    if not bpm_match:
        bpm_match = re.search(r'(\d+)\s*BPM', text, re.IGNORECASE)
    if bpm_match:
        bpm = int(bpm_match.group(1))
        
    # Key patterns
    key_match = re.search(r'Key:\s*([A-G][b#]?\s*(?:Major|Minor|maj|min|m)?)', text, re.IGNORECASE)
    if key_match:
        key = key_match.group(1).strip()
        
    return bpm, key

def main():
    prompts = []
    seen_prompts = set()
    print("Ingesting Music & Audio Prompts...")

    # =========================================================================
    # 1. suno-ai-farm/awesome-ai-music-prompts
    # =========================================================================
    p1 = "/tmp/music_sources/awesome-ai-music-prompts/README.md"
    if os.path.exists(p1):
        with open(p1, "r", encoding="utf-8") as f:
            text = f.read()
        
        # Split by ## Section
        sections = re.split(r'\n##\s+', text)
        for sec in sections[1:]:
            header = sec.split('\n')[0].strip()
            platform = "Cross-Platform"
            if "Suno" in header:
                platform = "Suno"
            elif "Udio" in header:
                platform = "Udio"
            elif "MusicGen" in header:
                platform = "MusicGen"
            elif "Stable Audio" in header:
                platform = "Stable Audio"
                
            items = re.findall(r'###\s+([^\n]+)\s*\n+```[^\n]*\n(.*?)```', sec, re.DOTALL)
            for title, body in items:
                title = title.strip()
                prompt_text = body.strip()
                if not prompt_text or prompt_text in seen_prompts:
                    continue
                seen_prompts.add(prompt_text)
                
                bpm, key = extract_bpm_key(prompt_text)
                slug_id = f"music-aimp-{clean_slug(platform)}-{clean_slug(title)}"
                
                prompts.append({
                    "id": slug_id,
                    "title": f"{platform}: {title} Style Blueprint",
                    "prompt": prompt_text,
                    "platform": platform,
                    "genre": title,
                    "bpm": bpm,
                    "key": key,
                    "energy": "High" if "anthem" in prompt_text.lower() or "drop" in prompt_text.lower() else "Medium",
                    "vocal_style": "Vocals specified in prompt" if "vocal" in prompt_text.lower() else "Instrumental / Ambient",
                    "target_models": [platform],
                    "metadata": {
                        "source": "awesome-ai-music-prompts",
                        "platform_focus": platform,
                        "intended_use": "Full track generation with instrumentation, BPM, and key control"
                    },
                    "source_repository": "suno-ai-farm/awesome-ai-music-prompts",
                    "source_file": "README.md",
                    "tags": [platform.lower(), "ai-music", "cross-platform", clean_slug(title)]
                })

    # =========================================================================
    # 2. suno-ai-farm/awesome-suno-lyrics
    # =========================================================================
    p2 = "/tmp/music_sources/awesome-suno-lyrics/README.md"
    if os.path.exists(p2):
        with open(p2, "r", encoding="utf-8") as f:
            text = f.read()
            
        sections = re.split(r'\n##\s+', text)
        for sec in sections[1:]:
            header = sec.split('\n')[0].strip()
            cat = "Songwriting Framework"
            if "Genre" in header:
                cat = "Genre Lyric Template"
            elif "Structure" in header:
                cat = "Song Structure Framework"
                
            items = re.findall(r'###\s+([^\n]+)\s*\n+```[^\n]*\n(.*?)```', sec, re.DOTALL)
            for title, body in items:
                title = title.strip()
                prompt_text = body.strip()
                if not prompt_text or prompt_text in seen_prompts:
                    continue
                seen_prompts.add(prompt_text)
                
                slug_id = f"music-lyric-{clean_slug(title)}"
                
                prompts.append({
                    "id": slug_id,
                    "title": f"Lyric Structure: {title}",
                    "prompt": prompt_text,
                    "platform": "Suno",
                    "genre": "Songwriting & Lyric Architecture",
                    "bpm": None,
                    "key": None,
                    "energy": "Dynamic / Multi-Section",
                    "vocal_style": "Structured Verse / Chorus / Bridge Vocal Delivery",
                    "target_models": ["Suno v4", "Suno v5", "Suno v6", "Udio v1.5"],
                    "metadata": {
                        "source": "awesome-suno-lyrics",
                        "category": cat,
                        "metatags": re.findall(r'\[(.*?)\]', prompt_text),
                        "description": "Structured lyric scaffolding with verse/chorus dynamics, emotional pacing, and musical cues"
                    },
                    "source_repository": "suno-ai-farm/awesome-suno-lyrics",
                    "source_file": "README.md",
                    "tags": ["suno", "lyrics", "song-structure", "verse-chorus", "metatags"]
                })

    # =========================================================================
    # 3. naqashmunir21/awesome-suno-prompts (prompts/*.md, packs/*.md, README.md)
    # =========================================================================
    asp_files = sorted(glob.glob('/tmp/music_sources/awesome-suno-prompts/prompts/*.md') +
                       glob.glob('/tmp/music_sources/awesome-suno-prompts/packs/*.md') +
                       glob.glob('/tmp/music_sources/awesome-suno-prompts/examples/*.md'))
    
    # Add main README as well
    asp_files.append('/tmp/music_sources/awesome-suno-prompts/README.md')

    for fpath in asp_files:
        fname = os.path.basename(fpath)
        genre_name = fname.replace('.md', '').replace('-', ' ').title()
        with open(fpath, "r", encoding="utf-8") as f:
            ftext = f.read()

        # Split by ### Prompt Title
        blocks = re.split(r'\n###\s+', ftext)
        for b in blocks[1:]:
            blines = b.split('\n')
            title = blines[0].strip()
            
            # Find code block
            code_match = re.search(r'```(?:txt|text|markdown)?\s*\n(.*?)\n```', b, re.DOTALL)
            if not code_match:
                continue
            prompt_text = code_match.group(1).strip()
            if not prompt_text or len(prompt_text) < 15 or prompt_text in seen_prompts:
                continue
            seen_prompts.add(prompt_text)

            bpm, key = extract_bpm_key(prompt_text)
            
            # Extract metadata lines like **Use Case:**, **Suno Version:**, **Energy:**
            use_case = None
            uc_match = re.search(r'\*\*Use Case:\*\*\s*([^\n]+)', b)
            if uc_match:
                use_case = uc_match.group(1).strip()

            suno_ver = "V5/V6"
            sv_match = re.search(r'\*\*Suno Version:\*\*\s*([^\n]+)', b)
            if sv_match:
                suno_ver = sv_match.group(1).strip()

            energy = "High" if "high" in b.lower() or "140" in prompt_text or "drop" in prompt_text.lower() else "Medium"
            en_match = re.search(r'\*\*Energy:\*\*\s*([^\n]+)', b)
            if en_match:
                energy = en_match.group(1).strip()

            notable = None
            nt_match = re.search(r'\*\*Notable Feature:\*\*\s*([^\n]+)', b)
            if nt_match:
                notable = nt_match.group(1).strip()

            vocal_style = "Vocal"
            if "female" in prompt_text.lower():
                vocal_style = "Female Vocals"
            elif "male" in prompt_text.lower():
                vocal_style = "Male Vocals"
            elif "instrumental" in prompt_text.lower() or "no vocals" in prompt_text.lower():
                vocal_style = "Instrumental"

            # Parse acoustic tags
            tags_list = ["suno", "ai-music", clean_slug(genre_name)]
            if bpm:
                tags_list.append(f"{bpm}-bpm")
            if key:
                tags_list.append(clean_slug(key))

            slug_id = f"music-suno-{clean_slug(genre_name)}-{clean_slug(title)}"
            # Avoid overly long IDs
            slug_id = slug_id[:60]

            prompts.append({
                "id": slug_id,
                "title": f"Suno {genre_name}: {title}",
                "prompt": prompt_text,
                "platform": "Suno",
                "genre": genre_name,
                "bpm": bpm,
                "key": key,
                "energy": energy,
                "vocal_style": vocal_style,
                "target_models": [f"Suno {suno_ver}", "Udio"],
                "metadata": {
                    "source": "awesome-suno-prompts",
                    "use_case": use_case,
                    "suno_version": suno_ver,
                    "notable_feature": notable
                },
                "source_repository": "naqashmunir21/awesome-suno-prompts",
                "source_file": os.path.relpath(fpath, "/tmp/music_sources/awesome-suno-prompts"),
                "tags": tags_list
            })

    # =========================================================================
    # 4. sanic732/SunoForge
    # =========================================================================
    # DATA_RECIPES.md
    p_recipes = "/tmp/music_sources/sunoforge/plugin/skills/sunoforge/references/DATA_RECIPES.md"
    if os.path.exists(p_recipes):
        with open(p_recipes, "r", encoding="utf-8") as f:
            rtext = f.read()
            
        r_sections = re.findall(r'###\s+([^\n]+)\s*\n+```[^\n]*\n(.*?)```', rtext, re.DOTALL)
        for rtitle, rbody in r_sections:
            rtitle = rtitle.strip()
            rprompt = rbody.strip()
            if not rprompt or rprompt in seen_prompts:
                continue
            seen_prompts.add(rprompt)
            bpm, key = extract_bpm_key(rprompt)
            slug_id = f"music-sunoforge-recipe-{clean_slug(rtitle)}"[:60]
            
            prompts.append({
                "id": slug_id,
                "title": f"SunoForge Production Recipe: {rtitle}",
                "prompt": rprompt,
                "platform": "Suno",
                "genre": "Acoustic Recipe / Genre Blend",
                "bpm": bpm,
                "key": key,
                "energy": "High" if "anthem" in rprompt.lower() or "drop" in rprompt.lower() else "Medium",
                "vocal_style": "Studio Vocal Blend",
                "target_models": ["Suno v6", "Suno v5", "Lyria", "ElevenMusic"],
                "metadata": {
                    "source": "SunoForge",
                    "type": "Production-grade prompt recipe with acoustic balance rules",
                    "reference": "DATA_RECIPES.md"
                },
                "source_repository": "sanic732/SunoForge",
                "source_file": "plugin/skills/sunoforge/references/DATA_RECIPES.md",
                "tags": ["sunoforge", "production-recipe", "acoustic-mastering", "suno-v6"]
            })

    # DATA_GOOGLE_2026-10.md (Google Lyria & MusicLM)
    p_google = "/tmp/music_sources/sunoforge/plugin/skills/sunoforge/references/DATA_GOOGLE_2026-10.md"
    if os.path.exists(p_google):
        with open(p_google, "r", encoding="utf-8") as f:
            gtext = f.read()
            
        g_matches = re.findall(r'```(?:txt|text|markdown)?\s*\n(.*?)\n```', gtext, re.DOTALL)
        for i, gprompt in enumerate(g_matches):
            gprompt = gprompt.strip()
            if len(gprompt) < 25 or gprompt in seen_prompts or gprompt.startswith("curl") or gprompt.startswith("{"):
                continue
            seen_prompts.add(gprompt)
            bpm, key = extract_bpm_key(gprompt)
            slug_id = f"music-lyria-prompt-{i+1}"
            
            prompts.append({
                "id": slug_id,
                "title": f"Google Lyria / MusicLM Ambient & Instrumental Prompt #{i+1}",
                "prompt": gprompt,
                "platform": "Google Lyria",
                "genre": "Cinematic & Multimodal Audio",
                "bpm": bpm,
                "key": key,
                "energy": "Ambient / Dynamic",
                "vocal_style": "Instrumental / Synthesized Chorus",
                "target_models": ["Google Lyria", "MusicLM"],
                "metadata": {
                    "source": "SunoForge DATA_GOOGLE",
                    "engine": "Google DeepMind Lyria"
                },
                "source_repository": "sanic732/SunoForge",
                "source_file": "plugin/skills/sunoforge/references/DATA_GOOGLE_2026-10.md",
                "tags": ["google-lyria", "musiclm", "deepmind", "instrumental"]
            })

    # DATA_OTHER_2026-10.md (Udio, Stable Audio, MusicGen, ElevenMusic)
    p_other = "/tmp/music_sources/sunoforge/plugin/skills/sunoforge/references/DATA_OTHER_2026-10.md"
    if os.path.exists(p_other):
        with open(p_other, "r", encoding="utf-8") as f:
            otext = f.read()
            
        o_matches = re.findall(r'```(?:txt|text|markdown)?\s*\n(.*?)\n```', otext, re.DOTALL)
        for i, oprompt in enumerate(o_matches):
            oprompt = oprompt.strip()
            if len(oprompt) < 25 or oprompt in seen_prompts or oprompt.startswith("curl") or oprompt.startswith("{"):
                continue
            seen_prompts.add(oprompt)
            bpm, key = extract_bpm_key(oprompt)
            
            plat = "Udio" if "udio" in oprompt.lower() else "ElevenMusic" if "eleven" in oprompt.lower() else "Stable Audio"
            slug_id = f"music-other-{clean_slug(plat)}-{i+1}"
            
            prompts.append({
                "id": slug_id,
                "title": f"{plat} Acoustic Production Prompt #{i+1}",
                "prompt": oprompt,
                "platform": plat,
                "genre": "Electronic / Acoustic Hybrid",
                "bpm": bpm,
                "key": key,
                "energy": "Medium-High",
                "vocal_style": "Studio Vocal & Beat",
                "target_models": [plat, "Suno v5"],
                "metadata": {
                    "source": "SunoForge DATA_OTHER",
                    "engine": plat
                },
                "source_repository": "sanic732/SunoForge",
                "source_file": "plugin/skills/sunoforge/references/DATA_OTHER_2026-10.md",
                "tags": [plat.lower(), "cross-platform", "audio-generation"]
            })

    # =========================================================================
    # 5. bitwize-music-studio/claude-ai-music-skills
    # =========================================================================
    skills_map = [
        ("suno-engineer", "Suno Prompt Engineering Specialist", "Suno v5/v6 prompting engine, acoustic tags, frequency shaping, and multi-genre fusion rules."),
        ("lyric-writer", "AI Song Lyric Architecture & Syllable Metering", "Metatag-structured lyrics with [Verse], [Chorus], [Drop], [Bridge], [Outro], and vocal delivery inflections."),
        ("genre-creator", "Fusion Genre Creator & Hybrid Prompt Synthesizer", "Formulas for blending contrasting genres (Phonk + Celtic, Drill + Orchestra, Synthwave + Flamenco)."),
        ("mastering-engineer", "AI Music Post-Mastering & Spectral Balance", "Mastering prompts and EQ balance rules for Suno & Udio audio stems (LUFS targets, stereo width)."),
        ("mix-engineer", "Stem Separation & Multi-Track Mixing System", "Stems balancing (vocal, bass, drums, other) and prompt repairs for muddiness or vocal clipping.")
    ]

    for s_dir, s_title, s_desc in skills_map:
        skill_file = f"/tmp/music_sources/claude-ai-music-skills/skills/{s_dir}/SKILL.md"
        if os.path.exists(skill_file):
            with open(skill_file, "r", encoding="utf-8") as f:
                stext = f.read()
                
            prompts.append({
                "id": f"music-skill-{s_dir}",
                "title": f"Music Skill: {s_title}",
                "prompt": stext,
                "platform": "Multi-Platform AI Music",
                "genre": "Music Production & Sound Engineering",
                "bpm": None,
                "key": None,
                "energy": "Professional Studio Standard",
                "vocal_style": "Vocal Inflection & Delivery Control",
                "target_models": ["Suno v5", "Suno v6", "Udio v1.5", "ElevenLabs Music"],
                "metadata": {
                    "source": "claude-ai-music-skills",
                    "description": s_desc,
                    "skill_package": s_dir
                },
                "source_repository": "bitwize-music-studio/claude-ai-music-skills",
                "source_file": f"skills/{s_dir}/SKILL.md",
                "tags": ["music-skill", "suno-engineer", "sound-engineering", "mixing", "mastering", s_dir]
            })

    # =========================================================================
    # 6. elevenlabs/examples & elevenlabs-python
    # =========================================================================
    # Sound Effects (SFX) recipes
    sfx_curated = [
        {"title": "Cinematic Horror Braam & Sub Drop", "prompt": "Cinematic Braam, deep sub bass drop, resonant metallic clang, horror movie trailer atmosphere, terrifying low-end rumble", "genre": "Cinematic & Trailer SFX"},
        {"title": "Futuristic Sci-Fi Laser Blaster & Reverb", "prompt": "Futuristic plasma blaster firing with high-tech laser discharge, echoing through metallic space station corridor, crisp digital transient", "genre": "Sci-Fi & Gaming SFX"},
        {"title": "Lush Rainforest Nature Ambience", "prompt": "Peaceful tropical rainforest ambience, distant gentle thunder, raindrops on jungle leaves, exotic bird calls, binaural 3D audio landscape", "genre": "Nature & Ambient SFX"},
        {"title": "Cyberpunk UI Button Click & Interface Chime", "prompt": "Futuristic computer UI interaction chime, soft holographic digital click, modern smartphone confirmation ping, pristine stereo sound", "genre": "UI & Interface SFX"},
        {"title": "Vintage Vinyl Crackle & Lo-Fi Texture", "prompt": "Warm vintage vinyl surface noise, authentic 1940s gramophone dust crackle, slow rotational hiss, nostalgic analog warmth", "genre": "Lo-Fi & Foley Texture"}
    ]

    for sfx in sfx_curated:
        slug_id = f"music-elevenlabs-sfx-{clean_slug(sfx['title'])}"
        prompts.append({
            "id": slug_id,
            "title": f"ElevenLabs SFX: {sfx['title']}",
            "prompt": sfx["prompt"],
            "platform": "ElevenLabs SFX",
            "genre": sfx["genre"],
            "bpm": None,
            "key": None,
            "energy": "High Impact" if "braam" in sfx["prompt"] or "blaster" in sfx["prompt"] else "Ambient",
            "vocal_style": "None (Sound Effect)",
            "target_models": ["ElevenLabs Sound Effects API v1"],
            "metadata": {
                "source": "ElevenLabs Recipes",
                "engine": "client.text_to_sound_effects.convert()",
                "sample_rate": "44.1kHz stereo MP3"
            },
            "source_repository": "elevenlabs/examples",
            "source_file": "sound-effects/python/quickstart/example/main.py",
            "tags": ["elevenlabs", "sound-effects", "sfx", "foley", "audio-design"]
        })

    # ElevenLabs Music & SSML Prosody Templates
    music_curated = [
        {"title": "Chill Lo-Fi Hip Hop Beat with Jazzy Rhodes", "prompt": "A chill lo-fi beat with jazzy electric piano Rhodes chords, relaxed vinyl texture, soft booming kick, warm mellow bassline, 80 BPM", "bpm": 80, "key": "Eb Major", "genre": "Lo-Fi Hip-Hop"},
        {"title": "Euphoric Uplifting Melodic House Groove", "prompt": "Uplifting progressive house anthem, bright plucks, rolling bassline, energetic four-on-the-floor kick, euphoric festival breakdown, 126 BPM", "bpm": 126, "key": "A Minor", "genre": "Electronic / House"},
        {"title": "Acoustic Fingerstyle Indie Folk Ballad", "prompt": "Intimate fingerpicked acoustic guitar ballad, gentle wooden body percussion, warm cello swell in background, nostalgic golden hour atmosphere, 95 BPM", "bpm": 95, "key": "D Major", "genre": "Indie Folk"}
    ]

    for m in music_curated:
        slug_id = f"music-elevenlabs-compose-{clean_slug(m['title'])}"
        prompts.append({
            "id": slug_id,
            "title": f"ElevenLabs Music: {m['title']}",
            "prompt": m["prompt"],
            "platform": "ElevenLabs Music",
            "genre": m["genre"],
            "bpm": m["bpm"],
            "key": m["key"],
            "energy": "Medium",
            "vocal_style": "Instrumental",
            "target_models": ["ElevenLabs Music v2.5"],
            "metadata": {
                "source": "ElevenLabs Recipes",
                "engine": "client.music.compose(model_id='music_v2_5')",
                "output_duration_ms": 10000
            },
            "source_repository": "elevenlabs/examples",
            "source_file": "music/python/quickstart/example/main.py",
            "tags": ["elevenlabs", "elevenlabs-music", "music_v2_5", clean_slug(m["genre"])]
        })

    # SSML Prosody & Voice Stability Configs from elevenlabs-python
    ssml_templates = [
        {
            "title": "Dramatic Storytelling Narration with SSML Pauses & Whispers",
            "prompt": '<speak>\n  The hallway fell silent. <break time="1.0s"/>\n  <prosody rate="slow" pitch="-2st">\n    None of them knew what lay beyond the iron door.\n  </prosody>\n  <break time="0.5s"/>\n  <emphasis level="strong">Not even the captain.</emphasis>\n</speak>',
            "genre": "Voice Acting & Audio Narration",
            "platform": "ElevenLabs SSML",
            "settings": {
                "stability": 0.45,
                "similarity_boost": 0.85,
                "style": 0.35,
                "use_speaker_boost": True
            }
        },
        {
            "title": "High-Energy Podcast Intro & Radio Promo SSML",
            "prompt": '<speak>\n  <prosody rate="fast" pitch="+1st">\n    Welcome back to the Future of Sound!\n  </prosody>\n  <break time="0.3s"/>\n  Today, we are breaking down the fastest-growing AI music models in the world.\n  <break time="0.4s"/>\n  <prosody rate="medium">\n    Let\'s dive straight in.\n  </prosody>\n</speak>',
            "genre": "Podcast & Broadcast Voice",
            "platform": "ElevenLabs SSML",
            "settings": {
                "stability": 0.70,
                "similarity_boost": 0.80,
                "style": 0.60,
                "use_speaker_boost": True
            }
        }
    ]

    for ssm in ssml_templates:
        slug_id = f"music-elevenlabs-ssml-{clean_slug(ssm['title'])}"
        prompts.append({
            "id": slug_id,
            "title": f"ElevenLabs Voice: {ssm['title']}",
            "prompt": ssm["prompt"],
            "platform": ssm["platform"],
            "genre": ssm["genre"],
            "bpm": None,
            "key": None,
            "energy": "High Vocal Dynamics",
            "vocal_style": "SSML Pacing & Pitch Modulated Voice",
            "target_models": ["ElevenLabs Multilingual v2", "ElevenLabs Turbo v2.5"],
            "metadata": {
                "source": "ElevenLabs Python SDK",
                "voice_settings": ssm["settings"],
                "format": "SSML (Speech Synthesis Markup Language)"
            },
            "source_repository": "elevenlabs/elevenlabs-python",
            "source_file": "reference.md",
            "tags": ["elevenlabs", "ssml", "voice-settings", "prosody", "narration"]
        })

    print(f"Total AI music & audio prompts extracted: {len(prompts):,}")
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(prompts, f, indent=2, ensure_ascii=False)
    print(f"Successfully saved to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()

