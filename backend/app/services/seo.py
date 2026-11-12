import re
import html
import json
import unicodedata
from urllib.parse import quote
from typing import List, Dict, Any, Optional

from backend.app.core.config import settings

MIN_INDEXABLE_CHARS = 450
DUPLICATE_THRESHOLD = 0.90


def plain_metadata(value: Any) -> str:
    """Render untrusted metadata as one plain line, never Markdown structure."""
    text = html.unescape(str(value or ''))
    text = re.sub(r'<[^>]*>', ' ', text)
    text = ''.join(' ' if unicodedata.category(c).startswith('C') else c for c in text)
    text = re.sub(r'[\\`*_{}\[\]<>#|~!]', ' ', text)
    return ' '.join(text.split())


def fenced_content(value: str, language: str = '') -> str:
    # A prompt can itself contain fences. Choose a delimiter it cannot close.
    width = max([2, *(len(m.group()) for m in re.finditer(r'`+', value))]) + 1
    fence = '`' * width
    return f'{fence}{language}\n{value}\n{fence}'


def site_url() -> str:
    return settings.SITE_URL.rstrip("/")


def approx_token_count(text: Optional[str]) -> int:
    """Provider-neutral estimate (~4 characters per token); labelled approximate everywhere."""
    return max(0, round(len(text or "") / 4))


def evaluate_indexability(
    prompt_body: str,
    sample_output: Optional[str] = None,
    max_cosine_similarity_to_existing: float = 0.0,
    description: str = ""
) -> bool:
    """
    Determines whether an artifact page should emit `index, follow` or `noindex, follow`.
    1. Rejects near-duplicates (> 0.90 similarity).
    2. Requires substantive content length (prompt + description + sample output >= 450 chars).
    """
    if max_cosine_similarity_to_existing > DUPLICATE_THRESHOLD:
        return False

    total_char_length = len(prompt_body or "") + len(description or "") + len(sample_output or "")
    if total_char_length < MIN_INDEXABLE_CHARS:
        return False

    return True


def interpolate_variables(raw_content: str, variables_schema: List[Dict[str, Any]]) -> str:
    """
    Replaces {{variable}} placeholders with default values specified in variables_schema.
    Ensures pre-filled production examples in SSR HTML without empty brackets.
    """
    if not raw_content or not variables_schema:
        return raw_content or ""

    compiled = raw_content
    for var in variables_schema:
        if not isinstance(var, dict):
            continue
        name = var.get("name")
        default_val = var.get("default_value") or var.get("default") or var.get("example") or f"[{var.get('label', name)}]"
        if name:
            compiled = re.sub(rf"\{{\{{\s*{re.escape(name)}\s*\}}\}}", lambda _m, v=str(default_val): v, compiled)
    return compiled


def variable_names(variables_schema: Any) -> List[str]:
    return [v.get("name") for v in (variables_schema or []) if isinstance(v, dict) and v.get("name")]


def extract_variable_schema(raw_content: Optional[str]) -> List[Dict[str, Any]]:
    """Derive a variable schema from `{{name}}` placeholders in uploaded text."""
    names: List[str] = []
    for match in re.finditer(r"\{\{\s*([A-Za-z_][A-Za-z0-9_\-]{0,60})\s*\}\}", raw_content or ""):
        if match.group(1) not in names:
            names.append(match.group(1))
    return [{"name": n, "label": n.replace("_", " ").replace("-", " "), "required": True} for n in names[:25]]


def generate_tldr_summary(
    title: str,
    short_description: str,
    asset_type: str,
    category_name: Optional[str] = None,
    models: Optional[List[str]] = None,
    is_paid: bool = False,
    price_usd: Optional[float] = None,
) -> str:
    """
    Builds a 120-word atomic citation summary block suitable for AEO passage rerankers.
    Follows explicit entity triples: [Entity] is a [Type] on Promptally for [Models] to [Action].
    """
    model_str = ", ".join(models) if models else "leading AI models"
    cat_str = f" in {category_name}" if category_name else ""
    desc_clean = short_description.strip() if short_description else ""
    if desc_clean and not desc_clean.endswith("."):
        desc_clean += "."
    kind = asset_type.replace("_", " ").title()
    if is_paid:
        price = f" for ${price_usd:.2f}" if price_usd else ""
        access = (f"Public benchmark, specifications and sample output are visible; the full source is "
                  f"unlocked after purchase{price} directly from the creator.")
    else:
        access = "Available to explore, customize with pre-filled variables, and copy with zero authentication required."
    return f"{title} is a verified {kind} blueprint on Promptally{cat_str} optimized for {model_str}. {desc_clean} {access}".replace("  ", " ")


def build_faq(title: str, asset_type: str, section_name: Optional[str], variables: List[str],
              is_paid: bool, price_usd: Optional[float], license_name: str,
              file_name: Optional[str]) -> List[Dict[str, str]]:
    """Deterministic, page-specific Q&A (no invented claims) for FAQPage markup and AEO chunks."""
    kind = asset_type.replace("_", " ").lower()
    if variables:
        shown = ", ".join(variables[:6])
        var_answer = (f"{title} accepts {len(variables)} dynamic variable(s): {shown}. Replace each {{{{name}}}} "
                      f"placeholder with your own value before running it.")
    else:
        var_answer = f"{title} is a static blueprint with no dynamic variables. Copy it and use it as-is."
    if is_paid:
        access = (f"{title} is a paid creator blueprint" + (f" priced at ${price_usd:.2f}" if price_usd else "")
                  + ". The specifications, benchmark output and structure are public; the complete source unlocks "
                  "after purchase and payment goes directly to the creator.")
    else:
        access = (f"Yes. {title} is free to view, copy and download on Promptally without creating an account. "
                  f"It is published under the {license_name} license.")
    return [
        {"question": f"How do I use {title}?",
         "answer": (f"Open the {kind} on Promptally, review the pre-filled example, then copy the template"
                    + (f" or download {file_name}" if file_name and not is_paid else "")
                    + " and paste it into your model, IDE or workflow tool. " + var_answer)},
        {"question": f"Is {title} free?", "answer": access},
        {"question": f"What variables does {title} need?", "answer": var_answer},
    ]


def compile_aeo_markdown(asset: Any, is_locked: bool = False) -> str:
    """
    Pre-compiles a zero-noise, token-dense Markdown document for AI agents,
    .md URLs, and Accept: text/markdown content negotiation requests.
    """
    base = site_url()
    title = plain_metadata(asset.seo_title)
    slug = quote(asset.slug, safe='')
    if hasattr(asset, "target_models") and asset.target_models:
        vendors = ", ".join([plain_metadata(m.name) for m in asset.target_models])
    else:
        vendors = "Universal / Model Agnostic"

    var_names = variable_names(getattr(asset, "variables_schema", None))
    variables = ", ".join(plain_metadata(v) for v in var_names) or "None (Static Blueprint)"

    modality = asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type)
    category_title = plain_metadata(asset.category.name) if hasattr(asset, "category") and asset.category else "Directory"
    access_label = f"Paid Creator Blueprint (${asset.price_cents / 100:.2f})" if is_locked else "Free Public Artifact (No Auth Required)"

    preview_code = asset.prefilled_preview_text or asset.raw_content or ""
    sample_output = asset.sample_output_markdown or asset.example_output or "Verified execution output available on the canonical page."
    tokens = approx_token_count(asset.raw_content)
    summary = asset.tldr_summary or asset.short_description
    if is_locked:
        summary = generate_tldr_summary(asset.seo_title, asset.short_description, modality,
                                        asset.category.name if asset.category else None,
                                        is_paid=True, price_usd=asset.price_cents / 100)

    if is_locked:
        body_section = (
            f"### Locked Marketplace Blueprint (Teaser Preview)\n\n"
            f"{plain_metadata(asset.preview_snippet) or 'This is a premium creator asset.'}\n\n"
            f"> [!IMPORTANT]\n"
            f"> The complete source code and execution payload are protected. "
            f"Unlock this blueprint on Promptally: {base}/p/{slug}"
        )
    else:
        language = re.sub(r'[^A-Za-z0-9_-]', '', asset.file_extension.lstrip('.')) or 'text'
        body_section = '### Pre-Filled Template & Production Source\n\n' + fenced_content(preview_code, language)

    related_links = []
    if hasattr(asset, "related_artifacts") and asset.related_artifacts:
        for rel in asset.related_artifacts[:8]:
            if isinstance(rel, dict):
                r_title = rel.get("title", rel.get("slug", "Blueprint"))
                r_slug = rel.get("slug", "")
                if r_slug:
                    related_links.append(f"- [{plain_metadata(r_title)}]({base}/p/{quote(r_slug, safe='')})")

    related_section = "\n".join(related_links) if related_links else f"*Explore related blueprints in the Promptally directory: {base}/directory*"
    safe_title = json.dumps(title, ensure_ascii=False)
    summary = plain_metadata(summary)
    license_name = plain_metadata(asset.source_license)
    sample_block = fenced_content(sample_output, 'text')

    return f"""---
title: {safe_title}
platform: "Promptally"
canonical_url: "{base}/p/{slug}"
modality: "{modality}"
category: "{category_title}"
compatible_models: [{vendors}]
access_tier: "{access_label}"
license: {json.dumps(license_name)}
---

# {title}

**Summary:** {summary}

## Technical Specifications
| Property | Value |
| :--- | :--- |
| Platform Registry | Promptally ({base}) |
| Modality | {modality} |
| Category | {category_title} |
| Compatible Engines | {vendors} |
| Dynamic Variables | {variables} |
| Approx. Token Length | {tokens:,} |
| Access Tier | {access_label} |
| License | {license_name} |

{body_section}

## Verified Execution Output / Benchmark
{sample_block}

## Related Blueprints on Promptally
{related_section}
"""
