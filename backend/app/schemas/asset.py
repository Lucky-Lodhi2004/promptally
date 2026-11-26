from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AuthorSummary(BaseModel):
    id: Optional[str] = None
    username: str
    name: str
    avatar_url: Optional[str] = None

class SectionSummary(BaseModel):
    id: str
    slug: str
    name: str

class CategorySummary(BaseModel):
    id: str
    slug: str
    name: str

class PreviewMedia(BaseModel):
    url: str
    kind: str

class ArtifactFilePreview(BaseModel):
    name: str
    content: str

class AssetCardResponse(BaseModel):
    id: str
    slug: str
    seo_title: str
    short_description: str
    asset_type: str
    media_preview_url: Optional[str] = None
    gif_preview_url: Optional[str] = None
    reference_media: List[Any] = []
    author: AuthorSummary
    is_paid: bool
    price_cents: int
    price_usd: float
    copy_count: int
    download_count: int
    display_priority: int = 0
    is_indexable: bool
    canonical_path: str
    section_slug: Optional[str] = None
    category_slug: Optional[str] = None

    class Config:
        from_attributes = True

class AssetListResponse(BaseModel):
    items: List[AssetCardResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    section_slug: Optional[str] = None
    subcategory_slug: Optional[str] = None

class AssetDetailResponse(BaseModel):
    id: str
    slug: str
    seo_title: str
    short_description: str
    tldr_summary: Optional[str] = None
    token_count: int = 0
    faq: List[Dict[str, str]] = []
    section: Optional[SectionSummary] = None
    category: Optional[CategorySummary] = None
    asset_type: str
    file_name: str
    file_extension: str
    source_license: str
    source_type: str
    source_repo_url: Optional[str] = None
    media_preview_url: Optional[str] = None
    gif_preview_url: Optional[str] = None
    reference_media: List[Any] = []
    preview_media: List[PreviewMedia] = Field(default_factory=list)
    file_previews: List[ArtifactFilePreview] = Field(default_factory=list)
    preview_snippet: Optional[str] = None
    sample_output_markdown: Optional[str] = None
    usage_instructions: Optional[str] = None
    technical_metadata: Dict[str, Any] = {}
    variables_schema: List[Dict[str, Any]] = []
    related_artifacts: List[Dict[str, Any]] = []
    is_paid: bool
    price_cents: int
    price_usd: float
    is_published: bool
    is_indexable: bool
    copy_count: int
    download_count: int
    view_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    author: AuthorSummary
    has_access: bool
    can_copy_download: bool
    raw_content: Optional[str] = None
    prefilled_preview_text: Optional[str] = None
    json_ld: Dict[str, Any]

