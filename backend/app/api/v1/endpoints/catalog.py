from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from backend.app.db.session import get_db
from backend.app.models.taxonomy import Section, Category
from backend.app.models.asset import Asset
from backend.app.models.redirect import SlugRedirect
from backend.app.models.user import User
from backend.app.models.enums import UserTier
from backend.app.schemas.taxonomy import TaxonomyResponse, SectionResponse, SubCategoryResponse
from backend.app.schemas.asset import AssetListResponse, AssetCardResponse, AssetDetailResponse, AuthorSummary
from backend.app.core.config import settings
from backend.app.core.avatars import avatar_url
from backend.app.core.security import get_optional_current_user
from backend.app.services.paywall import sanitize_asset_for_viewer, can_access_asset, can_view_asset
from backend.app.services.seo import compile_aeo_markdown
from backend.app.services.counters import bump_counter

PUBLIC_CACHE = "public, max-age=0, s-maxage=3600, stale-while-revalidate=86400"
_twin_cache: dict = {}


def markdown_twin(asset: Asset, locked: bool) -> str:
    """Markdown twin, memoized per (asset, updated_at, variant). Any content change moves updated_at."""
    key = (asset.id, asset.updated_at.isoformat() if asset.updated_at else "", locked)
    cached = _twin_cache.get(key)
    if cached is None:
        if len(_twin_cache) > 2000:
            _twin_cache.clear()
        cached = _twin_cache[key] = compile_aeo_markdown(asset, is_locked=locked)
    return cached

router = APIRouter()

@router.get("/taxonomy", response_model=TaxonomyResponse)
def get_taxonomy(response: Response, db: Session = Depends(get_db)):
    """
    Returns all 8 Core Categories, their nested Subcategories (plus the 'all' virtual count),
    and total item counts in a single call for the top navigation bar.
    Cached with s-maxage=3600 for edge CDN delivery.
    """
    sections = db.query(Section).order_by(Section.sort_order.asc()).all()
    
    total_assets = db.query(func.count(Asset.id)).filter(Asset.is_published.is_(True)).scalar() or 0

    section_responses = []
    for sec in sections:
        sec_count = (
            db.query(func.count(Asset.id))
            .filter(Asset.section_id == sec.id, Asset.is_published.is_(True))
            .scalar() or 0
        )

        categories_list = []
        # Prepend virtual "all" subcategory for this section
        categories_list.append(
            SubCategoryResponse(
                id=f"{sec.id}-all",
                slug="all",
                name="All",
                seo_title=f"All {sec.name}",
                seo_description=f"Browse all {sec.name} blueprints on Promptally",
                sort_order=0,
                item_count=sec_count
            )
        )

        for cat in sec.categories:
            cat_count = (
                db.query(func.count(Asset.id))
                .filter(Asset.category_id == cat.id, Asset.is_published.is_(True))
                .scalar() or 0
            )
            categories_list.append(
                SubCategoryResponse(
                    id=cat.id,
                    slug=cat.slug,
                    name=cat.name,
                    seo_title=cat.seo_title or f"{cat.name} Blueprints",
                    seo_description=cat.seo_description,
                    sort_order=cat.sort_order,
                    item_count=cat_count
                )
            )

        section_responses.append(
            SectionResponse(
                id=sec.id,
                slug=sec.slug,
                name=sec.name,
                description=sec.description,
                icon_name=sec.icon_name,
                sort_order=sec.sort_order,
                item_count=sec_count,
                categories=categories_list
            )
        )

    # Published counts only: identical for every visitor, so edge-cacheable.
    # The global middleware still forces `private` for authenticated requests.
    response.headers["Cache-Control"] = "public, max-age=0, s-maxage=1800, stale-while-revalidate=86400"
    response.headers["Vary"] = "Authorization, Cookie"
    return TaxonomyResponse(sections=section_responses, total_assets=total_assets)


@router.get("/assets", response_model=AssetListResponse)
def list_assets(
    request: Request,
    response: Response,
    section: Optional[str] = Query(None, description="Section slug, e.g. 'prompts'"),
    subcategory: Optional[str] = Query("all", description="Category slug or 'all'"),
    q: Optional[str] = Query(None, description="Keyword search query"),
    pricing: Optional[str] = Query("all", description="'all', 'free', or 'paid'"),
    sort: Optional[str] = Query("popular", description="'popular', 'downloads', or 'newest'"),
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Lists artifacts when a user clicks a category/subcategory.
    Returns card data: heading, short description, media_preview_url (image/GIF),
    author.username (if user-uploaded), is_paid badge, and price_cents.
    """
    query = db.query(Asset).filter(Asset.is_published.is_(True))

    # 1. Section filter
    sec_obj = None
    if section:
        sec_obj = db.query(Section).filter(Section.slug == section).first()
        if not sec_obj:
            # A real 404 (not an unfiltered 200 list) so crawlers never index soft-404 hubs.
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown section")
        query = query.filter(Asset.section_id == sec_obj.id)

    # 2. Subcategory filter
    cat_obj = None
    if subcategory and subcategory != "all":
        cat_query = db.query(Category).filter(Category.slug == subcategory)
        if sec_obj:
            cat_query = cat_query.filter(Category.section_id == sec_obj.id)
        cat_obj = cat_query.first()
        if not cat_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown subcategory")
        query = query.filter(Asset.category_id == cat_obj.id)

    # 3. Pricing filter
    if pricing == "free":
        query = query.filter(Asset.is_paid.is_(False))
    elif pricing == "paid":
        query = query.filter(Asset.is_paid.is_(True))

    # 4. Search query
    if q and q.strip():
        search_term = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(Asset.seo_title).like(search_term),
                func.lower(Asset.short_description).like(search_term),
                func.lower(Asset.slug).like(search_term)
            )
        )

    # 5. Sorting
    if sort == "downloads":
        query = query.order_by(Asset.download_count.desc(), Asset.copy_count.desc())
    elif sort == "newest":
        query = query.order_by(Asset.created_at.desc())
    else:  # 'popular'
        query = query.order_by(Asset.copy_count.desc(), Asset.download_count.desc())

    total = query.count()
    offset = (page - 1) * page_size
    assets = query.offset(offset).limit(page_size).all()

    # Build canonical path
    if sec_obj and cat_obj:
        canonical_path = f"/directory/{sec_obj.slug}/{cat_obj.slug}"
    elif sec_obj:
        canonical_path = f"/directory/{sec_obj.slug}"
    else:
        canonical_path = "/directory"

    items = []
    for a in assets:
        author_data = AuthorSummary(
            id=a.author.id if a.author else None,
            username=a.author.username if a.author else "promptally",
            name=a.author.name if a.author else "Promptally Curators",
            avatar_url=avatar_url(a.author.avatar_url if a.author else None)
        )
        items.append(
            AssetCardResponse(
                id=a.id,
                slug=a.slug,
                seo_title=a.seo_title,
                short_description=a.short_description,
                asset_type=a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type),
                media_preview_url=a.media_preview_url,
                gif_preview_url=a.gif_preview_url,
                reference_media=a.reference_media or [],
                author=author_data,
                is_paid=a.is_paid,
                price_cents=a.price_cents,
                price_usd=round(a.price_cents / 100.0, 2),
                copy_count=a.copy_count,
                download_count=a.download_count,
                is_indexable=a.is_indexable,
                canonical_path=canonical_path,
                section_slug=a.section.slug if a.section else None,
                category_slug=a.category.slug if a.category else None
            )
        )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    response.headers["Cache-Control"] = "public, max-age=0, s-maxage=1800, stale-while-revalidate=86400"

    return AssetListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        section_slug=section,
        subcategory_slug=subcategory
    )


@router.get("/assets/{slug}", response_model=AssetDetailResponse)
def get_asset_detail(
    slug: str,
    request: Request,
    response: Response,
    format: Optional[str] = Query(None),
    view: int = Query(0, ge=0, le=1, description="Set to 1 by the browser client to count a page view"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Powers the intent-driven page for a specific artifact (/p/[slug]).
    - Displays all attached images/GIFs (media_preview_url & reference_media) and author username.
    - If is_paid=False, returns full raw_content without login.
    - If is_paid=True, masks raw_content unless user purchased it.
    - Resolves 301 redirects via slug_redirects.
    - Supports Accept: text/markdown content negotiation & .md twins.
    """
    # 1. Clean .md suffix if passed in slug
    wants_markdown = slug.endswith(".md") or format == "md" or "text/markdown" in request.headers.get("Accept", "")
    clean_slug = slug[:-3] if slug.endswith(".md") else slug

    # 2. Query Asset
    asset = db.query(Asset).filter(Asset.slug == clean_slug).first()

    # 3. Handle 301 Permanent Redirects
    if not asset:
        redirect_entry = db.query(SlugRedirect).filter(SlugRedirect.old_slug == clean_slug).first()
        if redirect_entry:
            target_asset = db.query(Asset).filter(Asset.id == redirect_entry.asset_id).first()
            if target_asset and can_view_asset(target_asset, current_user, db):
                return RedirectResponse(
                    url=f"/api/v1/assets/{target_asset.slug}{'.md' if wants_markdown else ''}",
                    status_code=status.HTTP_301_MOVED_PERMANENTLY
                )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    if not can_view_asset(asset, current_user, db):
        raise HTTPException(404, "Artifact not found")

    # 4. Count a view only when the browser client asks (`?view=1`). Server renders,
    # crawlers, prefetches and payment polling must not inflate the counter.
    if view == 1:
        bump_counter(db, asset.id, "view_count")
        db.refresh(asset)

    anonymous = current_user is None

    # 5. AEO Content Negotiation (Raw Markdown Twin for AI crawlers & curl)
    if wants_markdown:
        locked = not can_access_asset(asset, current_user, db)
        md_content = markdown_twin(asset, locked)
        return PlainTextResponse(
            content=md_content,
            media_type="text/markdown; charset=utf-8",
            headers={
                # An anonymous viewer always gets the same (locked, for paid) twin: cacheable.
                "Cache-Control": PUBLIC_CACHE if anonymous else "private, no-store",
                "Vary": "Authorization, Cookie, Accept",
                "X-Robots-Tag": "index, follow, max-snippet:-1" if asset.is_indexable else "noindex, follow"
            }
        )

    # 6. ETag 304 Validation (anonymous payload is identical for all visitors, free or paid)
    etag = f'W/"{asset.id}-{int(asset.updated_at.timestamp())}"'
    if anonymous and request.headers.get("If-None-Match") == etag:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={
            "ETag": etag, "Cache-Control": PUBLIC_CACHE, "Vary": "Authorization, Cookie, Accept"})

    # 7. Zero-Leak Paywall Sanitization
    data = sanitize_asset_for_viewer(asset, current_user, db)

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = PUBLIC_CACHE if anonymous else "private, no-store"
    response.headers["Vary"] = "Authorization, Cookie, Accept"
    response.headers["X-Robots-Tag"] = "index, follow, max-snippet:-1, max-image-preview:large" if asset.is_indexable else "noindex, follow"
    response.headers["Link"] = f'<{settings.SITE_URL}/p/{asset.slug}.md>; rel="alternate"; type="text/markdown", <{settings.SITE_URL}/llms.txt>; rel="describedby"; type="text/markdown"'

    return AssetDetailResponse(**data)
