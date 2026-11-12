import zipfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from backend.app.models.asset import Asset
from backend.app.models.user import User
from backend.app.models.purchase import AssetPurchase
from backend.app.models.enums import UserTier, PurchaseStatus
from backend.app.core.avatars import DEFAULT_AVATAR_URL, avatar_url
from backend.app.core.config import settings
from backend.app.services.seo import (
    approx_token_count, build_faq, generate_tldr_summary, variable_names,
)


def _infer_preview_kind(url: str, declared_kind: Optional[str] = None) -> str:
    kind = (declared_kind or "").lower()
    if "gif" in kind:
        return "gif"
    if "video" in kind:
        return "video"

    clean_url = url.lower().split("?", 1)[0].split("#", 1)[0]
    if clean_url.endswith(".gif"):
        return "gif"
    if clean_url.endswith((".mp4", ".webm", ".mov", ".m4v")):
        return "video"
    return "image"


def build_preview_media(asset: Asset) -> List[Dict[str, str]]:
    """Return every preview attachment once, in its intended display order."""
    media: List[Dict[str, str]] = []
    seen = set()

    def add(value: Any, declared_kind: Optional[str] = None) -> None:
        if isinstance(value, dict):
            url = value.get("url") or value.get("src") or value.get("media_url")
            declared_kind = value.get("kind") or value.get("type") or declared_kind
        else:
            url = value

        if not isinstance(url, str) or not url.strip():
            return
        url = url.strip()
        if url in seen:
            return
        seen.add(url)
        media.append({"url": url, "kind": _infer_preview_kind(url, declared_kind)})

    add(asset.media_preview_url, "image")
    add(asset.gif_preview_url, "gif")
    for item in asset.reference_media or []:
        add(item)

    return media


_TEXT_PREVIEW_EXTENSIONS = {
    ".txt", ".md", ".mdc", ".json", ".jsonl", ".yaml", ".yml", ".toml",
    ".xml", ".csv", ".ts", ".tsx", ".js", ".jsx", ".py", ".sh", ".sql",
    ".html", ".css", ".env", ".ini", ".conf", ".cursorrules",
}
_MAX_PREVIEW_FILES = 20
_MAX_PREVIEW_FILE_BYTES = 64 * 1024
_MAX_PREVIEW_TOTAL_BYTES = 512 * 1024


def build_file_previews(asset: Asset, has_access: bool) -> List[Dict[str, str]]:
    """Read a bounded set of textual ZIP members without extracting the archive.

    Paid payloads remain invisible until the viewer has access. Limits keep artifact
    responses and SSR pages predictable even when the source archive is large.
    """
    if not has_access or not asset.archive_path or asset.file_extension.lower() != ".zip":
        return []

    archive = Path(asset.archive_path)
    if not archive.is_file() or not zipfile.is_zipfile(archive):
        return []

    previews: List[Dict[str, str]] = []
    total = 0
    try:
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                if member.is_dir() or member.flag_bits & 0x1 or member.file_size <= 0:
                    continue
                suffix = Path(member.filename).suffix.lower()
                basename = Path(member.filename).name.lower()
                if suffix not in _TEXT_PREVIEW_EXTENSIONS and basename not in {
                    "dockerfile", "makefile", "license", ".env", ".cursorrules",
                }:
                    continue
                if member.file_size > _MAX_PREVIEW_FILE_BYTES or total + member.file_size > _MAX_PREVIEW_TOTAL_BYTES:
                    continue
                content = bundle.read(member).decode("utf-8", errors="replace")
                previews.append({"name": member.filename, "content": content})
                total += member.file_size
                if len(previews) >= _MAX_PREVIEW_FILES:
                    break
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return []
    return previews

def has_purchase(asset: Asset, user: Optional[User], db: Session) -> bool:
    return bool(user and db.query(AssetPurchase.id).filter_by(
        buyer_id=str(user.id), asset_id=str(asset.id), status=PurchaseStatus.COMPLETED).first())


def can_view_asset(asset: Asset, user: Optional[User], db: Session) -> bool:
    return bool((asset.is_published and not asset.deleted_at)
                or (user and (str(user.id) == str(asset.author_id) or user.tier == UserTier.ADMIN))
                or has_purchase(asset, user, db))


def can_access_asset(asset: Asset, user: Optional[User], db: Session) -> bool:
    """
    Returns True if the viewer is authorized to view/copy/download the raw payload.
    - Free assets (is_paid=False): 100% accessible to everyone (no auth needed).
    - Paid assets (is_paid=True): Accessible only to author, Admin, or verified buyers.
    """
    if not can_view_asset(asset, user, db):
        return False
    if not asset.is_paid:
        return True

    if not user:
        return False

    # Author and Admins have full access
    if str(user.id) == str(asset.author_id) or user.tier == UserTier.ADMIN:
        return True

    # Check if user has purchased this asset
    purchase = (
        db.query(AssetPurchase)
        .filter(
            AssetPurchase.buyer_id == str(user.id),
            AssetPurchase.asset_id == str(asset.id),
            AssetPurchase.status == PurchaseStatus.COMPLETED
        )
        .first()
    )
    return purchase is not None

def citation_summary(asset: Asset) -> str:
    """The 120-word citation block. Paid items never claim to be free to copy."""
    if asset.is_paid:
        return generate_tldr_summary(
            asset.seo_title, asset.short_description,
            asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type),
            asset.category.name if asset.category else None,
            is_paid=True, price_usd=asset.price_cents / 100.0,
        )
    return asset.tldr_summary or asset.short_description


def asset_faq(asset: Asset):
    return build_faq(
        asset.seo_title,
        asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type),
        asset.section.name if asset.section else None,
        variable_names(asset.variables_schema), asset.is_paid,
        asset.price_cents / 100.0 if asset.is_paid else None,
        asset.source_license, asset.file_name,
    )


def target_vendors(asset: Asset) -> str:
    metadata = asset.technical_metadata or {}
    value = metadata.get("target_vendors") or metadata.get("compatible_models") or metadata.get("vendors") or metadata.get("models")
    if isinstance(value, list):
        vendors = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        vendors = [item.strip() for item in value.replace("|", ",").split(",") if item.strip()]
    else:
        vendors = []
    return ", ".join(vendors) if vendors else "Universal / Model Agnostic"


def generate_json_ld(asset: Asset, site_url: Optional[str] = None) -> Dict[str, Any]:
    """Generates the schema.org @graph for an artifact page: Breadcrumb, SoftwareSourceCode and FAQPage.

    Paid artifacts are declared `isAccessibleForFree: false` with the locked region marked up,
    so Google treats the paywall as legitimate rather than cloaked content.
    """
    site_url = (site_url or settings.SITE_URL).rstrip("/")
    section_name = asset.section.name if asset.section else "Catalog"
    section_slug = asset.section.slug if asset.section else None
    category_name = asset.category.name if asset.category else None
    category_slug = asset.category.slug if asset.category else None
    url = f"{site_url}/p/{asset.slug}"

    crumbs = [{"name": "Home", "item": f"{site_url}/"}]
    if section_slug:
        crumbs.append({"name": section_name, "item": f"{site_url}/directory/{section_slug}"})
        if category_slug:
            crumbs.append({"name": category_name, "item": f"{site_url}/directory/{section_slug}/{category_slug}"})
    crumbs.append({"name": asset.seo_title, "item": url})

    code: Dict[str, Any] = {
        "@type": "SoftwareSourceCode",
        "@id": f"{url}#artifact",
        "name": asset.seo_title,
        "url": url,
        "description": citation_summary(asset),
        "isAccessibleForFree": not asset.is_paid,
        "license": f"https://opensource.org/licenses/{asset.source_license}",
        "programmingLanguage": asset.file_extension.replace(".", "") or "text",
        "runtimePlatform": target_vendors(asset),
        "encodingFormat": "text/markdown",
        "author": {
            "@type": "Person" if asset.author else "Organization",
            "name": asset.author.username if asset.author else "Promptally Curators",
        },
        "publisher": {"@type": "Organization", "name": "Promptally", "url": f"{site_url}/"},
    }
    if asset.created_at:
        code["datePublished"] = asset.created_at.isoformat()
    if asset.updated_at:
        code["dateModified"] = asset.updated_at.isoformat()
    if asset.media_preview_url:
        code["image"] = asset.media_preview_url if asset.media_preview_url.startswith("http") else f"{site_url}{asset.media_preview_url}"
    if asset.is_paid:
        code["offers"] = {
            "@type": "Offer", "price": f"{asset.price_cents / 100.0:.2f}", "priceCurrency": "USD",
            "availability": "https://schema.org/InStock", "url": url,
        }
        code["hasPart"] = {
            "@type": "WebPageElement", "isAccessibleForFree": False, "cssSelector": "[data-paywall='locked']",
        }

    graph = [
        {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i, "name": c["name"], "item": c["item"]}
                for i, c in enumerate(crumbs, 1)
            ],
        },
        code,
        {
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": f["question"],
                 "acceptedAnswer": {"@type": "Answer", "text": f["answer"]}}
                for f in asset_faq(asset)
            ],
        },
    ]
    return {"@context": "https://schema.org", "@graph": graph}

def sanitize_asset_for_viewer(asset: Asset, user: Optional[User], db: Session) -> Dict[str, Any]:
    """
    Guarantees zero-leak payload sanitization before sending asset data to clients.
    If paid and unpurchased, strips raw_content and prefilled_preview_text while preserving
    public proof-of-work benchmark metadata for search engines and AI agents.
    """
    has_access = can_access_asset(asset, user, db)

    # Base payload structure
    data = {
        "id": asset.id,
        "slug": asset.slug,
        "seo_title": asset.seo_title,
        "short_description": asset.short_description,
        "tldr_summary": citation_summary(asset),
        "token_count": approx_token_count(asset.raw_content),
        "faq": asset_faq(asset),
        "section": {
            "id": asset.section.id,
            "slug": asset.section.slug,
            "name": asset.section.name,
        } if asset.section else None,
        "category": {
            "id": asset.category.id,
            "slug": asset.category.slug,
            "name": asset.category.name,
        } if asset.category else None,
        "asset_type": asset.asset_type.value if hasattr(asset.asset_type, "value") else str(asset.asset_type),
        "file_name": asset.file_name,
        "file_extension": asset.file_extension,
        "source_license": asset.source_license,
        "source_type": asset.source_type.value if hasattr(asset.source_type, "value") else str(asset.source_type),
        "source_repo_url": asset.source_repo_url,
        "media_preview_url": asset.media_preview_url,
        "gif_preview_url": asset.gif_preview_url,
        "reference_media": asset.reference_media or [],
        "preview_media": build_preview_media(asset),
        "file_previews": build_file_previews(asset, has_access),
        "preview_snippet": asset.preview_snippet,
        "sample_output_markdown": asset.sample_output_markdown or asset.example_output,
        "usage_instructions": asset.usage_instructions,
        "technical_metadata": asset.technical_metadata or {},
        "variables_schema": asset.variables_schema or [],
        "related_artifacts": asset.related_artifacts or [],
        "is_paid": asset.is_paid,
        "price_cents": asset.price_cents,
        "price_usd": round(asset.price_cents / 100.0, 2),
        "is_published": asset.is_published,
        "is_indexable": asset.is_indexable,
        "copy_count": asset.copy_count,
        "download_count": asset.download_count,
        "view_count": asset.view_count,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
        "updated_at": asset.updated_at.isoformat() if asset.updated_at else None,
        "author": {
            "id": asset.author.id,
            "username": asset.author.username,
            "name": asset.author.name,
            "avatar_url": avatar_url(asset.author.avatar_url),
        } if asset.author else {
            "id": None,
            "username": "promptally",
            "name": "Promptally Official",
            "avatar_url": DEFAULT_AVATAR_URL,
        },
        "has_access": has_access,
        "can_copy_download": has_access,
        "json_ld": generate_json_ld(asset),
    }

    if has_access:
        data["raw_content"] = asset.raw_content
        data["prefilled_preview_text"] = asset.prefilled_preview_text or asset.raw_content
    else:
        # Strictly sanitize protected payload for locked paid prompts
        data["raw_content"] = None
        data["prefilled_preview_text"] = None

    return data

