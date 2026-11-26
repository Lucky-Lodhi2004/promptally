from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.security import get_current_admin_user, revoke_sessions
from backend.app.core.upload_routes import BoundedFormRoute
from backend.app.db.session import get_db
from backend.app.models.asset import Asset
from backend.app.models.collection import Collection, CollectionItem
from backend.app.models.enums import (
    AssetType,
    SourceType,
    SubscriptionGateway,
    SubscriptionStatus,
    UserTier,
)
from backend.app.models.marketplace import (
    CheckoutAttempt,
    PendingCheckout,
    SellerGatewayConfig,
    SellerOAuthState,
)
from backend.app.models.mcp_oauth import MCPAuthorization, MCPGrant, MCPToken
from backend.app.models.purchase import AssetPurchase, Subscription
from backend.app.models.redirect import SlugRedirect
from backend.app.models.registration import EmailChallenge, EmailOutbox
from backend.app.models.taxonomy import Category, Section
from backend.app.models.user import User
from backend.app.schemas.admin import (
    AdminAssetItem,
    AdminAssetPriorityRequest,
    AdminAssetReorderRequest,
    AdminAssetsResponse,
    AdminEndSubscriptionRequest,
    AdminUserCard,
    AdminUsersResponse,
)
from backend.app.services.analytics import capture_event
from backend.app.services.indexnow import submit_urls_to_indexnow
from backend.app.services.membership import refresh_tier
from backend.app.services.payments import platform_request
from backend.app.services.related import link_back, related_for_new_asset
from backend.app.services.seo import (
    compile_aeo_markdown,
    evaluate_indexability,
    extract_variable_schema,
    generate_tldr_summary,
)
from backend.app.services.storage import (
    save_folder_as_zip,
    save_media_file,
    save_single_file,
)
from backend.app.api.v1.endpoints.assets_actions import slugify

router = APIRouter(route_class=BoundedFormRoute)

SECTION_TO_ASSET_TYPE = {
    "prompts": AssetType.PROMPT,
    "skills": AssetType.SKILL,
    "mcp-configs": AssetType.MCP_CONFIG,
    "agents-commands": AssetType.SUBAGENT,
    "ide-design-specs": AssetType.IDE_RULE,
    "custom-gpts": AssetType.CUSTOM_GPT,
    "workflows": AssetType.WORKFLOW,
    "loops": AssetType.ENGINEERING_LOOP,
}


def _validate_media_url(raw_url: Optional[str], label: str) -> Optional[str]:
    if raw_url is None:
        return None
    cleaned = raw_url.strip()
    if not cleaned:
        return None
    if len(cleaned) > 2048 or any(ch.isspace() or ord(ch) < 32 for ch in cleaned):
        raise HTTPException(400, f"{label} must be a valid HTTP(S) URL without whitespace.")
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("https", "http") or not parsed.netloc:
        raise HTTPException(400, f"{label} must start with https:// or http://.")
    return cleaned


def _cancel_provider_subscription_best_effort(sub: Subscription) -> str:
    if not sub or not sub.gateway_subscription_id:
        return "skipped"
    gateway = sub.gateway.value.lower() if hasattr(sub.gateway, "value") else str(sub.gateway).lower()
    if gateway not in {"razorpay", "dodo"}:
        return "skipped"
    try:
        if gateway == "razorpay":
            if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
                return "skipped"
            platform_request(
                "POST",
                "razorpay",
                f"/subscriptions/{sub.gateway_subscription_id}/cancel",
                {"cancel_at_cycle_end": 0},
            )
        else:
            if not settings.DODO_API_KEY:
                return "skipped"
            platform_request(
                "PATCH",
                "dodo",
                f"/subscriptions/{sub.gateway_subscription_id}",
                {"status": "cancelled"},
            )
        return "canceled"
    except Exception:
        return "failed"


@router.get("/admin/users", response_model=AdminUsersResponse)
def get_admin_users(
    status_filter: Optional[str] = Query("all", alias="status", description="'all' or 'subscribed'"),
    q: Optional[str] = Query(None, description="Search by email, username, or name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """
    Admin-only endpoint:
    - Lists signed-up users and active $1 subscribers with server-side search.
    """
    total_signed_up = db.query(func.count(User.id)).scalar() or 0

    total_subscribed = (
        db.query(func.count(Subscription.id))
        .filter(Subscription.status == SubscriptionStatus.ACTIVE)
        .scalar()
        or 0
    )

    razorpay_subscribers = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.gateway == SubscriptionGateway.RAZORPAY,
        )
        .scalar()
        or 0
    )

    dodo_subscribers = (
        db.query(func.count(Subscription.id))
        .filter(
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.gateway == SubscriptionGateway.DODO,
        )
        .scalar()
        or 0
    )

    query = db.query(User)
    if status_filter == "subscribed":
        query = query.join(Subscription, Subscription.user_id == User.id).filter(
            Subscription.status == SubscriptionStatus.ACTIVE
        )

    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(User.email).like(term),
                func.lower(User.username).like(term),
                func.lower(User.name).like(term),
            )
        )

    total_filtered = query.count()
    total_pages = (total_filtered + page_size - 1) // page_size if total_filtered > 0 else 1

    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    user_ids = [u.id for u in users]
    asset_counts = {}
    if user_ids:
        rows = (
            db.query(Asset.author_id, func.count(Asset.id))
            .filter(Asset.author_id.in_(user_ids), Asset.is_published.is_(True))
            .group_by(Asset.author_id)
            .all()
        )
        asset_counts = {author_id: count for author_id, count in rows}

    user_cards = []
    for u in users:
        sub_gateway = None
        sub_status = None
        sub_period_end = None
        cancel_at_end = False
        if u.subscription:
            sub_gateway = (
                u.subscription.gateway.value
                if hasattr(u.subscription.gateway, "value")
                else str(u.subscription.gateway)
            )
            sub_status = (
                u.subscription.status.value
                if hasattr(u.subscription.status, "value")
                else str(u.subscription.status)
            )
            sub_period_end = (
                u.subscription.current_period_end.isoformat()
                if u.subscription.current_period_end
                else None
            )
            cancel_at_end = bool(u.subscription.cancel_at_period_end)

        user_cards.append(
            AdminUserCard(
                id=u.id,
                email=u.email,
                username=u.username,
                name=u.name,
                tier=u.tier.value if hasattr(u.tier, "value") else str(u.tier),
                signup_ip=u.signup_ip,
                country_code=u.country_code or "US",
                device_fingerprint=u.device_fingerprint,
                created_at=u.created_at.isoformat() if u.created_at else None,
                subscription_gateway=sub_gateway,
                subscription_status=sub_status,
                subscription_period_end=sub_period_end,
                cancel_at_period_end=cancel_at_end,
                asset_count=asset_counts.get(u.id, 0),
            )
        )

    return AdminUsersResponse(
        total_signed_up=total_signed_up,
        total_subscribed=total_subscribed,
        razorpay_subscribers=razorpay_subscribers,
        dodo_subscribers=dodo_subscribers,
        total_filtered=total_filtered,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        users=user_cards,
    )


@router.post("/admin/users/{user_id}/end-subscription")
def admin_end_user_subscription(
    user_id: str,
    req: Optional[AdminEndSubscriptionRequest] = Body(default=None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """Admin-only: immediately end any user's Pro subscription and revoke Pro tier."""
    target = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    sub = db.query(Subscription).filter_by(user_id=target.id).with_for_update().first()
    cancel_at_provider = True if req is None else req.cancel_at_provider
    now = datetime.now(timezone.utc)

    has_active_or_pending_sub = bool(sub and sub.status != SubscriptionStatus.CANCELED)
    if not has_active_or_pending_sub and target.tier != UserTier.PRO:
        return {
            "status": "noop",
            "message": "User does not have an active Pro subscription.",
            "provider_cancel": "skipped",
            "tier": target.tier.value,
        }

    provider_status = "skipped"
    if sub and cancel_at_provider and sub.status != SubscriptionStatus.CANCELED:
        provider_status = _cancel_provider_subscription_best_effort(sub)

    gateway_name = "manual"
    if sub:
        gateway_name = sub.gateway.value.lower() if hasattr(sub.gateway, "value") else str(sub.gateway).lower()
        sub.status = SubscriptionStatus.CANCELED
        sub.cancel_at_period_end = False
        sub.current_period_end = now
        sub.last_event_at = now

    if target.tier != UserTier.ADMIN:
        target.tier = UserTier.FREE
    refresh_tier(target)
    db.commit()

    capture_event(
        target.id,
        "pro_subscription_canceled",
        {
            "gateway": gateway_name,
            "cancel_at_period_end": False,
            "via": "admin",
            "admin_id": admin_user.id,
            "provider_cancel": provider_status,
        },
    )

    msg = "Subscription ended immediately."
    if provider_status == "failed":
        msg += " Local access was revoked, but remote provider cancellation failed—verify in the gateway dashboard."
    return {
        "status": "success",
        "message": msg,
        "provider_cancel": provider_status,
        "tier": target.tier.value,
    }


@router.delete("/admin/users/{user_id}")
def admin_delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """
    Admin-only: delete any user account (except your own).
    - Attempts best-effort remote subscription cancellation if active.
    - Detaches and soft-deletes any authored assets that have purchases so DB
      constraints are respected safely; removes unpurchased authored assets.
    - Preserves durable SignupQuota counters.
    """
    if user_id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own admin account.",
        )

    target = db.query(User).filter(User.id == user_id).with_for_update().first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    sub = db.query(Subscription).filter_by(user_id=target.id).with_for_update().first()
    provider_status = "skipped"
    if sub and sub.status != SubscriptionStatus.CANCELED:
        provider_status = _cancel_provider_subscription_best_effort(sub)

    now = datetime.now(timezone.utc)
    authored_assets = db.query(Asset).filter(Asset.author_id == target.id).all()
    for asset in authored_assets:
        has_purchases = (
            db.query(AssetPurchase.id).filter(AssetPurchase.asset_id == asset.id).first()
            is not None
        )
        if has_purchases:
            asset.author_id = None
            asset.is_published = False
            asset.is_indexable = False
            asset.display_priority = 0
            asset.deleted_at = asset.deleted_at or now
        else:
            db.query(CollectionItem).filter(CollectionItem.asset_id == asset.id).delete(
                synchronize_session=False
            )
            db.query(SlugRedirect).filter(SlugRedirect.asset_id == asset.id).delete(
                synchronize_session=False
            )
            db.delete(asset)
    db.flush()

    # Clean up dependent rows explicitly so both PostgreSQL and SQLite behave identically.
    grant_ids = [g.id for g in db.query(MCPGrant.id).filter(MCPGrant.user_id == target.id).all()]
    if grant_ids:
        db.query(MCPToken).filter(MCPToken.grant_id.in_(grant_ids)).delete(
            synchronize_session=False
        )
        db.query(MCPGrant).filter(MCPGrant.id.in_(grant_ids)).delete(synchronize_session=False)
    db.query(MCPAuthorization).filter(MCPAuthorization.user_id == target.id).delete(
        synchronize_session=False
    )
    db.query(EmailChallenge).filter(EmailChallenge.user_id == target.id).delete(
        synchronize_session=False
    )
    db.query(EmailOutbox).filter(EmailOutbox.user_id == target.id).delete(
        synchronize_session=False
    )
    db.query(SellerOAuthState).filter(SellerOAuthState.seller_id == target.id).delete(
        synchronize_session=False
    )
    db.query(PendingCheckout).filter(
        or_(PendingCheckout.buyer_id == target.id, PendingCheckout.seller_id == target.id)
    ).delete(synchronize_session=False)
    db.query(CheckoutAttempt).filter(CheckoutAttempt.user_id == target.id).delete(
        synchronize_session=False
    )
    db.query(AssetPurchase).filter(
        or_(AssetPurchase.buyer_id == target.id, AssetPurchase.seller_id == target.id)
    ).delete(synchronize_session=False)

    collection_ids = [
        c.id for c in db.query(Collection.id).filter(Collection.owner_id == target.id).all()
    ]
    if collection_ids:
        db.query(CollectionItem).filter(CollectionItem.collection_id.in_(collection_ids)).delete(
            synchronize_session=False
        )
        db.query(Collection).filter(Collection.id.in_(collection_ids)).delete(
            synchronize_session=False
        )

    db.query(Subscription).filter(Subscription.user_id == target.id).delete(
        synchronize_session=False
    )
    db.query(SellerGatewayConfig).filter(SellerGatewayConfig.seller_id == target.id).delete(
        synchronize_session=False
    )

    deleted_username = target.username
    revoke_sessions(db, target)
    db.delete(target)
    db.commit()

    capture_event(
        admin_user.id,
        "admin_user_deleted",
        {"deleted_user_id": user_id, "provider_cancel": provider_status},
    )
    return {
        "status": "success",
        "message": f"User @{deleted_username} has been deleted.",
        "provider_cancel": provider_status,
    }


@router.get("/admin/assets", response_model=AdminAssetsResponse)
def list_admin_assets(
    section: Optional[str] = Query(None),
    subcategory: Optional[str] = Query("all"),
    pricing: Optional[str] = Query("all"),
    q: Optional[str] = Query(None),
    pinned_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """Admin-only catalog view ordered by display_priority desc, copy_count desc, created_at desc."""
    base_published = db.query(Asset).filter(
        Asset.is_published.is_(True), Asset.deleted_at.is_(None)
    )
    total_published = base_published.count()
    total_pinned = base_published.filter(Asset.display_priority > 0).count()

    query = base_published

    if section and section != "all":
        sec_obj = db.query(Section).filter(Section.slug == section).first()
        if sec_obj:
            query = query.filter(Asset.section_id == sec_obj.id)
        else:
            return AdminAssetsResponse(
                total_published=total_published,
                total_pinned=total_pinned,
                total_filtered=0,
                page=page,
                page_size=page_size,
                total_pages=1,
                items=[],
            )

    if subcategory and subcategory != "all":
        cat_obj = db.query(Category).filter(Category.slug == subcategory).first()
        if cat_obj:
            query = query.filter(Asset.category_id == cat_obj.id)

    if pricing == "free":
        query = query.filter(Asset.is_paid.is_(False))
    elif pricing == "paid":
        query = query.filter(Asset.is_paid.is_(True))

    if pinned_only:
        query = query.filter(Asset.display_priority > 0)

    if q and q.strip():
        term = f"%{q.strip().lower()}%"
        query = query.outerjoin(User, Asset.author_id == User.id).filter(
            or_(
                func.lower(Asset.seo_title).like(term),
                func.lower(Asset.short_description).like(term),
                func.lower(Asset.slug).like(term),
                func.lower(User.username).like(term),
            )
        )

    total_filtered = query.count()
    total_pages = (total_filtered + page_size - 1) // page_size if total_filtered > 0 else 1

    assets = (
        query.order_by(
            Asset.display_priority.desc(),
            Asset.copy_count.desc(),
            Asset.download_count.desc(),
            Asset.created_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        AdminAssetItem(
            id=a.id,
            slug=a.slug,
            seo_title=a.seo_title,
            short_description=a.short_description,
            asset_type=a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type),
            section_slug=a.section.slug if a.section else None,
            section_name=a.section.name if a.section else None,
            category_slug=a.category.slug if a.category else None,
            category_name=a.category.name if a.category else None,
            author_username=a.author.username if a.author else "promptally",
            media_preview_url=a.media_preview_url,
            gif_preview_url=a.gif_preview_url,
            is_paid=a.is_paid,
            price_usd=round(a.price_cents / 100.0, 2),
            copy_count=a.copy_count,
            download_count=a.download_count,
            view_count=a.view_count,
            display_priority=a.display_priority or 0,
            is_indexable=a.is_indexable,
            created_at=a.created_at.isoformat() if a.created_at else None,
        )
        for a in assets
    ]

    return AdminAssetsResponse(
        total_published=total_published,
        total_pinned=total_pinned,
        total_filtered=total_filtered,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )


@router.post("/admin/assets", status_code=status.HTTP_201_CREATED)
async def admin_create_asset(
    background_tasks: BackgroundTasks,
    section_slug: str = Form(...),
    category_slug: str = Form(...),
    heading: str = Form(...),
    description: Optional[str] = Form(None),
    raw_text: Optional[str] = Form(None),
    example_output: Optional[str] = Form(None),
    pin_to_top: bool = Form(False),
    image_url: Optional[str] = Form(None),
    gif_url: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    gif: Optional[UploadFile] = File(None),
    files: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """
    Admin-only artifact publishing:
    - Shows `@promptally` as author (`author_id = None`).
    - Supports preview image/GIF via either file upload OR CDN URL.
    - Supports pasted text, single file, or multi-file folder upload (ZIP).
    - Optional `pin_to_top` immediately places the artifact at #1.
    """
    clean_heading = heading.strip()
    if not clean_heading:
        raise HTTPException(status_code=400, detail="Heading is required.")

    section = db.query(Section).filter(Section.slug == section_slug).first()
    if not section:
        raise HTTPException(status_code=400, detail=f"Invalid section: {section_slug}")

    category = (
        db.query(Category)
        .filter(Category.slug == category_slug, Category.section_id == section.id)
        .first()
    )
    if not category:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subcategory: {category_slug} for section {section_slug}",
        )

    has_image_file = bool(image and image.filename)
    has_gif_file = bool(gif and gif.filename)
    validated_image_url = _validate_media_url(image_url, "Image CDN URL")
    validated_gif_url = _validate_media_url(gif_url, "GIF CDN URL")

    if has_image_file and validated_image_url:
        raise HTTPException(400, "Provide either an uploaded image file or an image CDN URL, not both.")
    if has_gif_file and validated_gif_url:
        raise HTTPException(400, "Provide either an uploaded GIF file or a GIF CDN URL, not both.")

    media_preview_url: Optional[str] = None
    gif_preview_url: Optional[str] = None
    reference_media: List[str] = []

    if has_image_file:
        media_preview_url = await save_media_file(image, is_gif=False)
    elif validated_image_url:
        media_preview_url = validated_image_url
    if media_preview_url:
        reference_media.append(media_preview_url)

    if has_gif_file:
        gif_preview_url = await save_media_file(gif, is_gif=True)
    elif validated_gif_url:
        gif_preview_url = validated_gif_url
    if gif_preview_url and gif_preview_url not in reference_media:
        reference_media.append(gif_preview_url)

    raw_content = ""
    archive_path = None
    file_name = "blueprint.txt"
    file_extension = ".txt"

    if len(files or []) > settings.MAX_UPLOAD_FILES:
        raise HTTPException(413, "Too many uploaded files")
    valid_files = [f for f in (files or []) if f.filename]

    if len(valid_files) > 1:
        archive_path, file_name, _ = await save_folder_as_zip(
            valid_files, base_name=slugify(clean_heading)
        )
        file_extension = ".zip"
        raw_content = (
            f"# Bundle: {clean_heading}\n\n"
            f"Archive containing {len(valid_files)} files compressed into `{file_name}`."
        )
    elif len(valid_files) == 1:
        archive_path, file_name, file_extension, extracted_text = await save_single_file(
            valid_files[0]
        )
        raw_content = (raw_text or "").strip() or extracted_text
    elif raw_text and raw_text.strip():
        raw_content = raw_text.strip()
        file_extension = ".md" if section_slug in ("prompts", "skills") else ".json"
        file_name = f"{slugify(clean_heading)}{file_extension}"
    else:
        raise HTTPException(
            status_code=400,
            detail="Must provide either raw text, a file, or folder upload.",
        )

    asset_type = SECTION_TO_ASSET_TYPE.get(section_slug, AssetType.PROMPT)

    base_slug = slugify(clean_heading)
    unique_slug = base_slug
    counter = 1
    while db.query(Asset).filter(Asset.slug == unique_slug).first():
        unique_slug = f"{base_slug}-{counter}"
        counter += 1

    short_desc = (
        description.strip()
        if description and description.strip()
        else f"{clean_heading} blueprint on Promptally."
    )
    variables_schema = extract_variable_schema(raw_content)
    tldr = generate_tldr_summary(
        title=clean_heading,
        short_description=short_desc,
        asset_type=asset_type.value,
        category_name=category.name,
        is_paid=False,
        price_usd=None,
    )

    priority = 0
    if pin_to_top:
        max_priority = db.query(func.coalesce(func.max(Asset.display_priority), 0)).scalar() or 0
        priority = max_priority + 1

    new_asset = Asset(
        slug=unique_slug,
        seo_title=clean_heading,
        short_description=short_desc,
        tldr_summary=tldr,
        section_id=section.id,
        category_id=category.id,
        asset_type=asset_type,
        raw_content=raw_content,
        prefilled_preview_text=raw_content,
        preview_snippet=None,
        example_output=example_output or None,
        sample_output_markdown=example_output or None,
        media_preview_url=media_preview_url,
        gif_preview_url=gif_preview_url,
        reference_media=reference_media,
        variables_schema=variables_schema,
        archive_path=archive_path,
        file_name=file_name,
        file_extension=file_extension,
        source_type=SourceType.INGESTED,
        author_id=None,  # Displays as @promptally
        is_paid=False,
        price_cents=0,
        price_inr_paise=0,
        is_published=True,
        display_priority=priority,
        is_indexable=True,
    )

    new_asset.section, new_asset.category = section, category
    mesh = related_for_new_asset(db, new_asset)
    new_asset.related_artifacts = mesh["related"]
    new_asset.is_indexable = evaluate_indexability(
        prompt_body=raw_content,
        sample_output=example_output,
        max_cosine_similarity_to_existing=mesh["max_similarity"],
        description=short_desc,
    )
    new_asset.aeo_markdown_twin = compile_aeo_markdown(new_asset, is_locked=False)

    db.add(new_asset)
    db.commit()
    db.refresh(new_asset)

    capture_event(
        admin_user.id,
        "asset_published",
        {
            "asset_id": new_asset.id,
            "slug": new_asset.slug,
            "section": section_slug,
            "category": category_slug,
            "asset_type": asset_type.value,
            "is_paid": False,
            "via": "admin",
            "pin_to_top": pin_to_top,
        },
    )

    try:
        link_back(db, new_asset, mesh["related"])
        db.commit()
    except Exception:
        db.rollback()

    if new_asset.is_indexable:
        base = settings.SITE_URL.rstrip("/")
        background_tasks.add_task(submit_urls_to_indexnow, [f"{base}/p/{new_asset.slug}"])

    return {
        "status": "success",
        "asset_id": new_asset.id,
        "slug": new_asset.slug,
        "url": f"/p/{new_asset.slug}",
        "author_username": "promptally",
        "display_priority": new_asset.display_priority,
        "media_preview_url": new_asset.media_preview_url,
        "gif_preview_url": new_asset.gif_preview_url,
    }


@router.delete("/admin/assets/{asset_id}")
def admin_delete_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """Admin-only: soft-delete any artifact (preserves existing buyer entitlements)."""
    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    asset.is_published = False
    asset.is_indexable = False
    asset.display_priority = 0
    asset.deleted_at = asset.deleted_at or datetime.now(timezone.utc)
    db.commit()

    capture_event(
        admin_user.id,
        "admin_asset_deleted",
        {"asset_id": asset.id, "slug": asset.slug},
    )
    return {"status": "success", "message": f"Artifact '{asset.seo_title}' removed."}


@router.post("/admin/assets/{asset_id}/move-to-top")
def admin_move_asset_to_top(
    asset_id: str,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """Admin-only: shift any published artifact to the #1 top spot."""
    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.is_published.is_(True), Asset.deleted_at.is_(None))
        .first()
    )
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    max_priority = db.query(func.coalesce(func.max(Asset.display_priority), 0)).scalar() or 0
    new_priority = max_priority + 1
    db.query(Asset).filter(Asset.id == asset.id).update(
        {Asset.display_priority: new_priority}, synchronize_session="fetch"
    )
    db.commit()
    return {
        "status": "success",
        "asset_id": asset.id,
        "slug": asset.slug,
        "display_priority": new_priority,
    }


@router.patch("/admin/assets/{asset_id}/priority")
def admin_set_asset_priority(
    asset_id: str,
    req: AdminAssetPriorityRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """Admin-only: set an explicit display_priority (0 resets to default popularity order)."""
    asset = (
        db.query(Asset)
        .filter(Asset.id == asset_id, Asset.is_published.is_(True), Asset.deleted_at.is_(None))
        .first()
    )
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    db.query(Asset).filter(Asset.id == asset.id).update(
        {Asset.display_priority: req.display_priority}, synchronize_session="fetch"
    )
    db.commit()
    return {
        "status": "success",
        "asset_id": asset.id,
        "slug": asset.slug,
        "display_priority": req.display_priority,
    }


@router.post("/admin/assets/reorder")
def admin_reorder_assets(
    req: AdminAssetReorderRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_current_admin_user),
):
    """
    Admin-only: rearrange a list of artifacts into the exact `ordered_ids` order.
    - If every specified artifact is already pinned with distinct priorities, their
      existing priority slots are redistributed in the new order (so swapping two
      adjacent pinned items preserves the rest of the catalog).
    - Otherwise, assigns strictly descending priorities above the current max.
    """
    deduped = list(dict.fromkeys(req.ordered_ids))
    assets = (
        db.query(Asset)
        .filter(Asset.id.in_(deduped), Asset.is_published.is_(True), Asset.deleted_at.is_(None))
        .all()
    )
    by_id = {a.id: a for a in assets}
    if len(by_id) != len(deduped):
        raise HTTPException(status_code=404, detail="One or more artifacts were not found")

    existing_priorities = [by_id[aid].display_priority or 0 for aid in deduped]
    if all(p > 0 for p in existing_priorities) and len(set(existing_priorities)) == len(deduped):
        target_priorities = sorted(existing_priorities, reverse=True)
    else:
        max_priority = db.query(func.coalesce(func.max(Asset.display_priority), 0)).scalar() or 0
        start = max_priority + len(deduped)
        target_priorities = [start - i for i in range(len(deduped))]

    updated = []
    for aid, priority in zip(deduped, target_priorities):
        db.query(Asset).filter(Asset.id == aid).update(
            {Asset.display_priority: priority}, synchronize_session="fetch"
        )
        updated.append({"id": aid, "display_priority": priority})

    db.commit()
    return {"status": "success", "updated": updated}
