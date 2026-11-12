import re
from typing import Optional, List
from fastapi import (
    APIRouter, Depends, HTTPException, Query, UploadFile, File,
    Form, Request, Response, status
)
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.db.session import get_db
from backend.app.models.collection import Collection, CollectionItem
from backend.app.models.asset import Asset
from backend.app.models.user import User
from backend.app.models.enums import CollectionVisibility, UserTier
from backend.app.core.security import get_current_user, get_optional_current_user, get_current_active_pro_user
from backend.app.schemas.collection import (
    CollectionListResponse, CollectionDetailResponse, CollectionItemCard
)
from backend.app.services.storage import save_collection_cover
from backend.app.services.paywall import can_access_asset, can_view_asset
from backend.app.core.avatars import DEFAULT_AVATAR_URL, avatar_url
from backend.app.core.config import settings
from backend.app.services.seo import approx_token_count, variable_names
from backend.app.core.upload_routes import BoundedFormRoute
from backend.app.core.config import settings

router = APIRouter(route_class=BoundedFormRoute)

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text[:200] or "collection"

@router.get("/collections", response_model=List[CollectionListResponse])
def get_user_collections(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetches the logged-in user's existing collections to populate
    the 'Add to collection' modal on list cards and intent-driven pages.
    """
    collections = (
        db.query(Collection)
        .filter(Collection.owner_id == current_user.id)
        .order_by(Collection.updated_at.desc())
        .all()
    )
    return [
        CollectionListResponse(
            id=c.id,
            slug=c.slug,
            title=c.title,
            description=c.description,
            cover_image_url=c.cover_image_url,
            visibility=c.visibility.value if hasattr(c.visibility, "value") else str(c.visibility),
            item_count=c.item_count,
            is_indexable=c.is_indexable,
            created_at=c.created_at.isoformat() if c.created_at else None
        )
        for c in collections
    ]


@router.post("/collections", status_code=status.HTTP_201_CREATED)
async def create_collection(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    visibility: str = Form("PRIVATE"),
    cover_image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_pro_user)
):
    """
    Creates a new collection (Name required, Description & Cover Image optional).
    Requires an active $1 Pro subscription.
    """
    if not title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Collection title is required.")

    vis_enum = CollectionVisibility.PUBLIC if visibility.upper() == "PUBLIC" else CollectionVisibility.PRIVATE

    # Cover image upload
    cover_image_url = None
    if cover_image and cover_image.filename:
        cover_image_url = await save_collection_cover(cover_image)

    # Generate unique slug
    base_slug = slugify(title)
    unique_slug = base_slug
    counter = 1
    while db.query(Collection).filter(Collection.slug == unique_slug).first():
        unique_slug = f"{base_slug}-{counter}"
        counter += 1

    new_collection = Collection(
        slug=unique_slug,
        title=title.strip(),
        description=description.strip() if description else None,
        cover_image_url=cover_image_url,
        owner_id=current_user.id,
        visibility=vis_enum,
        item_count=0,
        is_indexable=(vis_enum == CollectionVisibility.PUBLIC)
    )
    db.add(new_collection)
    db.commit()
    db.refresh(new_collection)

    return {
        "status": "success",
        "collection_id": new_collection.id,
        "slug": new_collection.slug,
        "title": new_collection.title,
        "visibility": new_collection.visibility.value
    }


@router.post("/collections/{collection_id}/items")
def add_item_to_collection(
    collection_id: str,
    asset_id: str = Form(...),
    custom_note: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_pro_user)
):
    """Adds an artifact into an existing collection."""
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    if collection.owner_id != current_user.id and current_user.tier != UserTier.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this collection")

    asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not asset or not can_view_asset(asset, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")

    # Check for duplicate
    existing = (
        db.query(CollectionItem)
        .filter(CollectionItem.collection_id == collection_id, CollectionItem.asset_id == asset_id)
        .first()
    )
    if existing:
        return {"status": "exists", "message": "Item already in collection."}

    max_order = (
        db.query(func.max(CollectionItem.sort_order))
        .filter(CollectionItem.collection_id == collection_id)
        .scalar() or 0
    )

    item = CollectionItem(
        collection_id=collection_id,
        asset_id=asset_id,
        sort_order=max_order + 1,
        custom_note=custom_note.strip() if custom_note else None
    )
    db.add(item)
    collection.item_count += 1
    db.commit()

    return {"status": "success", "message": f"Added {asset.seo_title} to collection."}


@router.delete("/collections/{collection_id}/items/{asset_id}")
def remove_item_from_collection(
    collection_id: str,
    asset_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Removes an artifact from a collection."""
    collection = db.query(Collection).filter(Collection.id == collection_id).first()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    if collection.owner_id != current_user.id and current_user.tier != UserTier.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this collection")

    item = (
        db.query(CollectionItem)
        .filter(CollectionItem.collection_id == collection_id, CollectionItem.asset_id == asset_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not in collection")

    db.delete(item)
    collection.item_count = max(0, collection.item_count - 1)
    db.commit()

    return {"status": "success", "message": "Item removed from collection."}


@router.get("/discover/collections")
def discover_public_collections(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Public, indexable collections with enough items to work as curated hub pages."""
    from backend.app.api.v1.endpoints.seo_aeo import MIN_COLLECTION_ITEMS
    query = db.query(Collection).filter(
        Collection.visibility == CollectionVisibility.PUBLIC,
        Collection.is_indexable.is_(True),
        Collection.item_count >= MIN_COLLECTION_ITEMS,
    )
    total = query.count()
    rows = query.order_by(Collection.updated_at.desc(), Collection.id).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [{
            "id": c.id, "slug": c.slug, "title": c.title, "description": c.description,
            "cover_image_url": c.cover_image_url, "item_count": c.item_count,
            "owner": {"username": c.owner.username, "name": c.owner.name},
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        } for c in rows],
        "total": total, "page": page, "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 1,
    }


@router.get("/collections/{slug}", response_model=CollectionDetailResponse)
def get_collection_detail(
    slug: str,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Displays the contents of a user's collection page.
    - If visibility=PRIVATE and viewer is not owner, raises 403.
    - Sanitizes all assets for the viewer (free items can be copied/downloaded directly; unpurchased items remain locked).
    - Assembles an AEO Comparative Matrix table of all items for Perplexity & search engines.
    """
    collection = db.query(Collection).filter(Collection.slug == slug).first()
    if not collection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")

    # Visibility check
    if collection.visibility == CollectionVisibility.PRIVATE:
        if not current_user or (current_user.id != collection.owner_id and current_user.tier != UserTier.ADMIN):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This collection is private.")

    items_data = []
    matrix = []

    for ci in collection.items:
        a = ci.asset
        if not can_view_asset(a, current_user, db):
            continue
        has_access = can_access_asset(a, current_user, db)
        items_data.append(
            CollectionItemCard(
                id=ci.id,
                asset_id=a.id,
                author={"id": a.author.id, "username": a.author.username, "name": a.author.name,
                        "avatar_url": avatar_url(a.author.avatar_url)} if a.author else {
                        "id": None, "username": "promptally", "name": "Promptally Curators", "avatar_url": DEFAULT_AVATAR_URL},
                reference_media=a.reference_media or [],
                price_cents=a.price_cents, copy_count=a.copy_count, download_count=a.download_count,
                is_indexable=a.is_indexable, canonical_path=f"/p/{a.slug}",
                section_slug=a.section.slug if a.section else None,
                category_slug=a.category.slug if a.category else None,
                slug=a.slug,
                seo_title=a.seo_title,
                short_description=a.short_description,
                asset_type=a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type),
                media_preview_url=a.media_preview_url,
                gif_preview_url=a.gif_preview_url,
                is_paid=a.is_paid,
                price_usd=round(a.price_cents / 100.0, 2),
                custom_note=ci.custom_note,
                sort_order=ci.sort_order,
                has_access=has_access,
                can_copy_download=has_access
            )
        )

        matrix.append({
            "name": a.seo_title,
            "modality": a.asset_type.value if hasattr(a.asset_type, "value") else str(a.asset_type),
            "category": a.category.name if a.category else None,
            "use_case": (a.short_description or "")[:160],
            "variables": variable_names(a.variables_schema),
            "approx_tokens": approx_token_count(a.raw_content),
            "access": "Free Blueprint" if not a.is_paid else f"Paid Blueprint (${round(a.price_cents / 100.0, 2)})",
            "url": f"{settings.SITE_URL.rstrip('/')}/p/{a.slug}"
        })

    owner_data = {
        "id": collection.owner.id,
        "username": collection.owner.username,
        "name": collection.owner.name,
        "avatar_url": avatar_url(collection.owner.avatar_url)
    }

    return CollectionDetailResponse(
        id=collection.id,
        slug=collection.slug,
        title=collection.title,
        description=collection.description,
        cover_image_url=collection.cover_image_url,
        visibility=collection.visibility.value if hasattr(collection.visibility, "value") else str(collection.visibility),
        item_count=len(items_data),
        is_indexable=collection.is_indexable,
        created_at=collection.created_at.isoformat() if collection.created_at else None,
        owner=owner_data,
        items=items_data,
        comparison_matrix=matrix
    )

