from typing import List, Optional
from pydantic import BaseModel, Field


class AdminUserCard(BaseModel):
    id: str
    email: str
    username: str
    name: str
    tier: str
    signup_ip: Optional[str] = None
    country_code: str
    device_fingerprint: Optional[str] = None
    created_at: Optional[str] = None
    subscription_gateway: Optional[str] = None
    subscription_status: Optional[str] = None
    subscription_period_end: Optional[str] = None
    cancel_at_period_end: bool = False
    asset_count: int = 0


class AdminUsersResponse(BaseModel):
    total_signed_up: int
    total_subscribed: int
    razorpay_subscribers: int
    dodo_subscribers: int
    total_filtered: int = 0
    page: int = 1
    page_size: int = 50
    total_pages: int = 1
    users: List[AdminUserCard]


class AdminAssetItem(BaseModel):
    id: str
    slug: str
    seo_title: str
    short_description: str
    asset_type: str
    section_slug: Optional[str] = None
    section_name: Optional[str] = None
    category_slug: Optional[str] = None
    category_name: Optional[str] = None
    author_username: str
    media_preview_url: Optional[str] = None
    gif_preview_url: Optional[str] = None
    is_paid: bool
    price_usd: float
    copy_count: int
    download_count: int
    view_count: int
    display_priority: int = 0
    is_indexable: bool
    created_at: Optional[str] = None


class AdminAssetsResponse(BaseModel):
    total_published: int
    total_pinned: int
    total_filtered: int
    page: int
    page_size: int
    total_pages: int
    items: List[AdminAssetItem]


class AdminAssetPriorityRequest(BaseModel):
    display_priority: int = Field(..., ge=0, le=1_000_000_000)


class AdminAssetReorderRequest(BaseModel):
    ordered_ids: List[str] = Field(..., min_length=1, max_length=100)


class AdminEndSubscriptionRequest(BaseModel):
    cancel_at_provider: bool = True
