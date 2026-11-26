import os
import re
from typing import Optional, List
from pathlib import Path
from fastapi import (
    APIRouter, Depends, HTTPException, Query, UploadFile, File,
    Form, Request, Response, BackgroundTasks, status
)
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.asset import Asset
from backend.app.models.taxonomy import Section, Category
from backend.app.models.user import User
from backend.app.models.enums import AssetType, SourceType, UserTier
from backend.app.core.security import get_current_user, get_optional_current_user, get_current_active_pro_user
from backend.app.services.paywall import can_access_asset
from backend.app.services.membership import is_pro
from backend.app.services.payments import inr_paise
from backend.app.api.v1.endpoints.marketplace import ensure_dodo_product
from backend.app.services.storage import (
    save_media_file, save_single_file, save_folder_as_zip
)
from backend.app.services.seo import (
    interpolate_variables, generate_tldr_summary,
    evaluate_indexability, compile_aeo_markdown, extract_variable_schema
)
from backend.app.services.related import related_for_new_asset, link_back
from backend.app.models.redirect import SlugRedirect
from backend.app.services.indexnow import submit_urls_to_indexnow
from backend.app.services.counters import bump_counter
from backend.app.services.analytics import capture_event

from backend.app.core.upload_routes import BoundedFormRoute
router = APIRouter(route_class=BoundedFormRoute)

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text[:200] or "blueprint"

@router.get("/assets/{slug}/download")
def download_asset(
    slug: str,
    action: Optional[str] = Query("download", description="'download' or 'copy'"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Downloads the artifact file or .zip folder and increments download/copy counters.
    Free artifacts require zero authentication; paid artifacts verify ownership or purchase.
    """
    clean_slug = slug[:-3] if slug.endswith(".md") else slug
    asset = db.query(Asset).filter(Asset.slug == clean_slug).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    from backend.app.services.paywall import can_view_asset
    if not can_view_asset(asset, current_user, db):
        raise HTTPException(404, "Artifact not found")

    # Access control
    if not can_access_asset(asset, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Purchase required to download this paid blueprint."
        )

    # Increment counter (atomic; does not touch updated_at/ETag)
    bump_counter(db, asset.id, "copy_count" if action == "copy" else "download_count")
    db.refresh(asset)
    capture_event(
        current_user.id if current_user else "anonymous",
        "asset_copied" if action == "copy" else "asset_downloaded",
        {
            "asset_id": asset.id,
            "slug": asset.slug,
            "asset_type": asset.asset_type.value,
            "is_paid": asset.is_paid,
            "authenticated": bool(current_user),
        },
    )

    # If action is 'copy', simply return raw text payload
    if action == "copy":
        return PlainTextResponse(
            content=asset.prefilled_preview_text or asset.raw_content,
            media_type="text/plain; charset=utf-8"
        )

    # 1. Check if compressed zip or file archive exists on disk
    if asset.archive_path and os.path.exists(asset.archive_path):
        return FileResponse(
            path=asset.archive_path,
            filename=asset.file_name,
            media_type="application/octet-stream"
        )

    # 2. Otherwise stream raw_content as a text file attachment
    filename = asset.file_name or f"{asset.slug}{asset.file_extension}"
    return Response(
        content=asset.raw_content.encode("utf-8"),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/assets", status_code=status.HTTP_201_CREATED)
async def upload_asset(
    background_tasks: BackgroundTasks,
    section_slug: str = Form(...),
    category_slug: str = Form(...),
    heading: str = Form(...),
    description: Optional[str] = Form(None),
    is_paid: bool = Form(False),
    price_usd: float = Form(0.0),
    raw_text: Optional[str] = Form(None),
    example_output: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    gif: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Unified endpoint for uploading Free or Paid artifacts:
    - Validates Category, Subcategory, Heading (required), Description (optional).
    - If Free: Image and GIF uploads are optional.
    - If Paid: Enforces Pro subscription, Image is mandatory, and price_usd > 0.
    - Accepts raw pasted text, a single file, or folder upload (compressed to .zip).
    - Uploaded free and paid artifacts show the author's username.
    - Compiles SEO/AEO metadata and triggers IndexNow ping.
    """
    # 1. Validate section & category
    section = db.query(Section).filter(Section.slug == section_slug).first()
    if not section:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid section: {section_slug}")

    category = db.query(Category).filter(Category.slug == category_slug, Category.section_id == section.id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid subcategory: {category_slug} for section {section_slug}")

    # 2. Validate Paid Asset Requirements
    if is_paid:
        if not is_pro(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active $1 Pro subscription required to sell paid blueprints."
            )
        config = current_user.gateway_config
        if not config or not (config.has_razorpay or config.has_dodo):
            raise HTTPException(409, "Connect a seller payment gateway before publishing paid assets")
        if price_usd <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Price must be greater than $0 for paid blueprints."
            )
        if not image or not image.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one preview image is mandatory when selling a paid blueprint."
            )

    import math
    if not math.isfinite(price_usd) or price_usd < 0 or price_usd > 100000:
        raise HTTPException(400, "Invalid asset price")
    price_cents = int(round(price_usd * 100)) if is_paid else 0
    if is_paid and price_cents < 1:
        raise HTTPException(400, "Paid price must be at least one cent")
    price_inr_paise = inr_paise(price_cents) if is_paid else 0

    # 3. Handle Media Uploads (Image and GIF)
    media_preview_url = None
    gif_preview_url = None
    reference_media = []

    if image and image.filename:
        media_preview_url = await save_media_file(image, is_gif=False)
        reference_media.append(media_preview_url)

    if gif and gif.filename:
        gif_preview_url = await save_media_file(gif, is_gif=True)
        reference_media.append(gif_preview_url)

    # 4. Handle Content / Files Upload (Pasted text, single file, or folder-to-zip)
    raw_content = ""
    archive_path = None
    file_name = "blueprint.txt"
    file_extension = ".txt"

    # Filter out empty files
    if len(files or []) > settings.MAX_UPLOAD_FILES:
        raise HTTPException(413, 'Too many uploaded files')
    valid_files = [f for f in (files or []) if f.filename]

    if len(valid_files) > 1:
        # Multiple files / folder upload -> Compress into ZIP
        base_slug = slugify(heading)
        archive_path, file_name, _ = await save_folder_as_zip(valid_files, base_name=base_slug)
        file_extension = ".zip"
        raw_content = f"# Bundle: {heading}\n\nArchive containing {len(valid_files)} files compressed into `{file_name}`."
    elif len(valid_files) == 1:
        # Single file upload
        archive_path, file_name, file_extension, extracted_text = await save_single_file(valid_files[0])
        raw_content = raw_text or extracted_text
    elif raw_text and raw_text.strip():
        # Pasted prompt / config text
        raw_content = raw_text.strip()
        file_extension = ".md" if section_slug in ("prompts", "skills") else ".json"
        file_name = f"{slugify(heading)}{file_extension}"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either raw text, a file, or folder upload."
        )

    # 5. Determine Asset Type from Section
    section_to_type = {
        "prompts": AssetType.PROMPT,
        "skills": AssetType.SKILL,
        "mcp-configs": AssetType.MCP_CONFIG,
        "agents-commands": AssetType.SUBAGENT,
        "ide-design-specs": AssetType.IDE_RULE,
        "custom-gpts": AssetType.CUSTOM_GPT,
        "workflows": AssetType.WORKFLOW,
        "loops": AssetType.ENGINEERING_LOOP,
    }
    asset_type = section_to_type.get(section_slug, AssetType.PROMPT)

    # 6. Generate Unique Slug
    base_slug = slugify(heading)
    unique_slug = base_slug
    counter = 1
    while db.query(Asset).filter(Asset.slug == unique_slug).first():
        unique_slug = f"{base_slug}-{counter}"
        counter += 1

    # 7. Compile SEO & AEO Metadata
    short_desc = description.strip() if description else f"{heading} blueprint on Promptally."
    prefilled_preview = raw_content
    variables_schema = extract_variable_schema(raw_content)
    tldr = generate_tldr_summary(
        title=heading,
        short_description=short_desc,
        asset_type=asset_type.value,
        category_name=category.name,
        is_paid=is_paid,
        price_usd=price_cents / 100.0 if is_paid else None,
    )
    # Provisional gate on length; refined below once duplicate similarity is known.
    is_indexable = evaluate_indexability(
        prompt_body=raw_content,
        sample_output=example_output,
        max_cosine_similarity_to_existing=0.0,
        description=short_desc
    )

    new_asset = Asset(
        slug=unique_slug,
        seo_title=heading,
        short_description=short_desc,
        tldr_summary=tldr,
        section_id=section.id,
        category_id=category.id,
        asset_type=asset_type,
        raw_content=raw_content,
        prefilled_preview_text=prefilled_preview,
        preview_snippet=short_desc if is_paid else None,
        example_output=example_output,
        sample_output_markdown=example_output,
        media_preview_url=media_preview_url,
        gif_preview_url=gif_preview_url,
        reference_media=reference_media,
        variables_schema=variables_schema,
        archive_path=archive_path,
        file_name=file_name,
        file_extension=file_extension,
        source_type=SourceType.USER_CREATED,
        author_id=current_user.id,
        is_paid=is_paid,
        price_cents=price_cents,
        price_inr_paise=price_inr_paise,
        is_published=True,
        is_indexable=is_indexable,
    )

    # Internal-link mesh + near-duplicate gate (lexical similarity against indexed siblings).
    new_asset.section, new_asset.category = section, category
    mesh = related_for_new_asset(db, new_asset)
    new_asset.related_artifacts = mesh["related"]
    new_asset.is_indexable = evaluate_indexability(
        prompt_body=raw_content, sample_output=example_output,
        max_cosine_similarity_to_existing=mesh["max_similarity"], description=short_desc)

    # Pre-compile AEO Markdown twin
    new_asset.aeo_markdown_twin = compile_aeo_markdown(new_asset, is_locked=is_paid)

    if is_paid and current_user.gateway_config.has_dodo:
        ensure_dodo_product(new_asset, current_user.gateway_config)

    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)
    capture_event(current_user.id, "asset_published", {
        "asset_id": new_asset.id,
        "slug": new_asset.slug,
        "section": section_slug,
        "category": category_slug,
        "asset_type": asset_type.value,
        "is_paid": new_asset.is_paid,
        "price_cents": new_asset.price_cents,
    })

    # Give the new page inbound links so it is never an orphan (best effort; never fails a publish).
    try:
        link_back(db, new_asset, mesh["related"])
        db.commit()
    except Exception:
        db.rollback()

    # 8. Dispatch Async IndexNow Notification
    if new_asset.is_indexable:
        base = settings.SITE_URL.rstrip('/')
        background_tasks.add_task(submit_urls_to_indexnow, [f"{base}/p/{new_asset.slug}"])

    return {
        "status": "success",
        "asset_id": new_asset.id,
        "slug": new_asset.slug,
        "url": f"/p/{new_asset.slug}",
        "is_paid": new_asset.is_paid,
        "price_usd": round(new_asset.price_cents / 100.0, 2),
        "author_username": current_user.username
    }


@router.patch("/assets/{asset_id}")
def update_asset(
    asset_id: str,
    background_tasks: BackgroundTasks,
    heading: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    example_output: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Edit title / description / sample output of your own artifact (or any, as Admin).
    Renaming changes the slug; the previous URL is recorded in `slug_redirects` so it
    keeps resolving with a permanent 301 instead of breaking inbound links.
    """
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    if asset.author_id != current_user.id and current_user.tier != UserTier.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this artifact.")

    if asset.deleted_at:
        raise HTTPException(404, 'Artifact was removed')
    old_slug = asset.slug
    if heading is not None:
        if not heading.strip():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Heading cannot be empty.")
        asset.seo_title = heading.strip()
        base_slug = slugify(asset.seo_title)
        if base_slug != old_slug and not re.fullmatch(re.escape(base_slug) + r"-\d+", old_slug):
            candidate, counter = base_slug, 1
            while db.query(Asset).filter(Asset.slug == candidate, Asset.id != asset.id).first():
                candidate = f"{base_slug}-{counter}"
                counter += 1
            if candidate != old_slug:
                asset.slug = candidate
    if description is not None:
        asset.short_description = description.strip() or f"{asset.seo_title} blueprint on Promptally."
        if asset.is_paid:
            asset.preview_snippet = asset.short_description
    if example_output is not None:
        asset.example_output = example_output or None
        asset.sample_output_markdown = example_output or None

    if asset.slug != old_slug:
        # The live slug always wins over a stale redirect row of the same name.
        db.query(SlugRedirect).filter(SlugRedirect.old_slug == asset.slug).delete()
        existing = db.get(SlugRedirect, old_slug)
        if existing:
            existing.asset_id = asset.id
        else:
            db.add(SlugRedirect(old_slug=old_slug, asset_id=asset.id))

    asset.tldr_summary = generate_tldr_summary(
        asset.seo_title, asset.short_description, asset.asset_type.value,
        asset.category.name if asset.category else None,
        is_paid=asset.is_paid, price_usd=asset.price_cents / 100.0 if asset.is_paid else None)
    mesh = related_for_new_asset(db, asset)
    asset.related_artifacts = mesh["related"]
    asset.is_indexable = evaluate_indexability(
        prompt_body=asset.raw_content, sample_output=asset.sample_output_markdown or asset.example_output,
        max_cosine_similarity_to_existing=mesh["max_similarity"], description=asset.short_description)
    asset.aeo_markdown_twin = compile_aeo_markdown(asset, is_locked=asset.is_paid)
    db.commit()
    db.refresh(asset)

    if asset.is_indexable and asset.is_published:
        background_tasks.add_task(submit_urls_to_indexnow, [f"{settings.SITE_URL.rstrip('/')}/p/{asset.slug}"])
    return {"status": "success", "asset_id": asset.id, "slug": asset.slug, "previous_slug": old_slug,
            "url": f"/p/{asset.slug}", "is_indexable": asset.is_indexable}


@router.delete("/assets/{asset_id}")
def delete_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Allows a user to delete their own uploaded artifact (or Admin)."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    if asset.author_id != current_user.id and current_user.tier != UserTier.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this artifact.")

    # Retain the source, archive, purchase records and pending payment targets.
    # Existing buyers keep access; removal only stops discovery and new sales.
    from datetime import datetime, timezone
    asset.is_published = False
    asset.is_indexable = False
    asset.deleted_at = asset.deleted_at or datetime.now(timezone.utc)
    db.commit()
    return {"status": "success", "message": f"Artifact {asset_id} deleted."}

