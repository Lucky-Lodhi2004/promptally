#!/usr/bin/env python3
"""
Enrich seeded database assets with:
- prefilled_preview_text (interpolated with variable defaults)
- variables_schema (derived from {{placeholders}} when missing)
- tldr_summary (120-word atomic citation block, paid-aware)
- sample_output_markdown
- is_indexable (length gate + near-duplicate gate against earlier pages)
- related_artifacts (8 semantic + 4 category-ring links; every indexable page gets inbound links)
- aeo_markdown_twin (pre-compiled token-dense markdown document)

Usage (from the repository root):  backend/venv/bin/python backend/scripts/enrich_seo_aeo.py
Safe to re-run: all derived fields are recomputed deterministically.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.db.session import SessionLocal
from backend.app.models.asset import Asset
from backend.app.models.taxonomy import Section
from backend.app.services.related import index_for_section, CONTENT_SNIPPET_CHARS
from backend.app.services.seo import (
    interpolate_variables,
    extract_variable_schema,
    generate_tldr_summary,
    evaluate_indexability,
    compile_aeo_markdown,
)

BATCH_SIZE = 1000


def kind(asset):
    return asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)


def enrich_all_assets():
    db = SessionLocal()
    try:
        sections = db.query(Section).order_by(Section.sort_order).all()
        total_indexable = 0
        for section in sections:
            print(f"\n== {section.name} ({section.slug}) ==")
            # Pass 1: content fields and the quality gate. Candidates are compared with
            # *earlier* pages only, so one copy of a duplicate pair stays indexable.
            full = index_for_section(db, section.id, section.slug, limit=None, indexable_only=False)
            offset = 0
            while True:
                batch = (db.query(Asset).filter(Asset.section_id == section.id)
                         .order_by(Asset.id).offset(offset).limit(BATCH_SIZE).all())
                if not batch:
                    break
                for a in batch:
                    if not a.variables_schema:
                        a.variables_schema = extract_variable_schema(a.raw_content)
                    a.prefilled_preview_text = interpolate_variables(a.raw_content, a.variables_schema) or a.raw_content
                    if not a.sample_output_markdown and a.example_output:
                        a.sample_output_markdown = a.example_output
                    a.tldr_summary = generate_tldr_summary(
                        a.seo_title, a.short_description, kind(a),
                        a.category.name if a.category else None,
                        is_paid=a.is_paid, price_usd=a.price_cents / 100.0 if a.is_paid else None)
                    text = f"{a.seo_title} {a.short_description or ''} {(a.raw_content or '')[:CONTENT_SNIPPET_CHARS]}"
                    position = full.by_slug.get(a.slug)
                    similarity = full.max_duplicate_similarity(text, exclude_slug=a.slug, only_before=position) \
                        if position is not None else 0.0
                    a.is_indexable = evaluate_indexability(
                        prompt_body=a.raw_content,
                        sample_output=a.sample_output_markdown or a.example_output,
                        max_cosine_similarity_to_existing=similarity,
                        description=a.short_description)
                db.commit()
                offset += BATCH_SIZE
            # Pass 2: links only point at pages that remain indexable.
            index = index_for_section(db, section.id, section.slug, limit=None, indexable_only=True)
            total_indexable += len(index.items)
            offset = done = 0
            while True:
                batch = (db.query(Asset).filter(Asset.section_id == section.id)
                         .order_by(Asset.id).offset(offset).limit(BATCH_SIZE).all())
                if not batch:
                    break
                for a in batch:
                    a.related_artifacts = index.related(
                        a.slug, a.seo_title, a.short_description, a.section_id, a.category_id)
                    a.aeo_markdown_twin = compile_aeo_markdown(a, is_locked=a.is_paid)
                db.commit()
                done += len(batch)
                offset += BATCH_SIZE
            print(f" - {done:,} assets enriched; {len(index.items):,} indexable")
        print(f"\nSUCCESS: SEO & AEO fields refreshed. Indexable pages: {total_indexable:,}")
    finally:
        db.close()


if __name__ == "__main__":
    enrich_all_assets()
