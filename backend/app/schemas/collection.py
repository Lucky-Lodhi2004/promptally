from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class CollectionItemCard(BaseModel):
    id: str
    asset_id: str
    author: Dict[str, Any]
    reference_media: List[str]
    price_cents: int
    copy_count: int
    download_count: int
    is_indexable: bool
    canonical_path: str
    section_slug: Optional[str] = None
    category_slug: Optional[str] = None
    slug: str
    seo_title: str
    short_description: str
    asset_type: str
    media_preview_url: Optional[str] = None
    gif_preview_url: Optional[str] = None
    is_paid: bool
    price_usd: float
    custom_note: Optional[str] = None
    sort_order: int
    has_access: bool
    can_copy_download: bool

class CollectionListResponse(BaseModel):
    id: str
    slug: str
    title: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    visibility: str
    item_count: int
    is_indexable: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

class CollectionDetailResponse(BaseModel):
    id: str
    slug: str
    title: str
    description: Optional[str] = None
    cover_image_url: Optional[str] = None
    visibility: str
    item_count: int
    is_indexable: bool
    created_at: Optional[str] = None
    owner: Dict[str, Any]
    items: List[CollectionItemCard]
    comparison_matrix: List[Dict[str, Any]]

