import uuid
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime,
    ForeignKey, Enum as SQLEnum, JSON, Index, func
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base
from backend.app.models.enums import AssetType, SourceType

class Asset(Base):
    __tablename__ = "assets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(255), unique=True, index=True, nullable=False)
    seo_title = Column(Text, nullable=False)
    short_description = Column(Text, nullable=False)
    
    # Direct answer summary for AEO 120-word citation block (<p data-aeo="citation-summary">)
    tldr_summary = Column(Text, nullable=True)
    
    section_id = Column(String(36), ForeignKey("sections.id", ondelete="SET NULL"), nullable=True, index=True)
    category_id = Column(String(36), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    
    asset_type = Column(SQLEnum(AssetType), index=True, nullable=False)
    
    # Protected content: raw prompt text, SKILL.md, mcp.json, code, workflow graph
    raw_content = Column(Text, nullable=False)
    
    # Pre-compiled live preview with default variables interpolated (never blank {{var}} in SSR DOM)
    prefilled_preview_text = Column(Text, nullable=True)
    
    # Public teaser / redacted snippet for locked marketplace prompts
    preview_snippet = Column(Text, nullable=True)
    
    # Sample output trace / benchmark result
    example_output = Column(Text, nullable=True)
    sample_output_markdown = Column(Text, nullable=True)
    
    # Pre-compiled zero-noise token-dense Markdown twin for AEO .md and Accept: text/markdown endpoints
    aeo_markdown_twin = Column(Text, nullable=True)
    
    media_preview_url = Column(Text, nullable=True)
    gif_preview_url = Column(Text, nullable=True)
    archive_path = Column(Text, nullable=True)
    
    file_name = Column(String(255), nullable=False)
    file_extension = Column(String(30), nullable=False)
    
    # License for SoftwareSourceCode schema (default MIT)
    source_license = Column(String(60), default="MIT", nullable=False)
    
    # Dynamic variables {{topic}}, {{language}}, etc.
    variables_schema = Column(JSON, default=list, nullable=False)
    
    # Technical metadata (model parameters, loop conditions, tool requirements, reference media)
    technical_metadata = Column(JSON, default=dict, nullable=False)
    reference_media = Column(JSON, default=list, nullable=False)
    usage_instructions = Column(Text, nullable=True)
    
    # Sibling internal linking mesh (12 related slugs/titles: 8 semantic + 4 same-category)
    related_artifacts = Column(JSON, default=list, nullable=False)
    
    source_type = Column(SQLEnum(SourceType), default=SourceType.INGESTED, nullable=False)
    source_repo_url = Column(Text, nullable=True)
    
    author_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Marketplace monetization & access flags
    is_paid = Column(Boolean, default=False, index=True, nullable=False)
    price_cents = Column(Integer, default=0, nullable=False)
    price_inr_paise = Column(Integer, default=0, nullable=False)
    seller_dodo_product_id = Column(String(120), nullable=True)
    is_published = Column(Boolean, default=True, index=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    # Deterministic SEO Quality Gate (False for thin content < 450 chars or near-duplicates)
    is_indexable = Column(Boolean, default=True, index=True, nullable=False)

    # Admin curation priority (higher values appear first in default catalog ordering)
    display_priority = Column(Integer, default=0, server_default="0", index=True, nullable=False)
    
    # Interaction counters
    copy_count = Column(Integer, default=0, nullable=False)
    download_count = Column(Integer, default=0, nullable=False)
    view_count = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    section = relationship("Section", back_populates="assets")
    category = relationship("Category", back_populates="assets")
    author = relationship("User", back_populates="assets")
    
    tags = relationship("Tag", secondary="asset_tags", back_populates="assets")
    target_models = relationship("TargetModel", secondary="asset_models", back_populates="assets")
    
    collection_items = relationship("CollectionItem", back_populates="asset", cascade="all, delete-orphan")
    purchases = relationship("AssetPurchase", back_populates="asset", passive_deletes='all')
    slug_redirects = relationship("SlugRedirect", back_populates="asset", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_assets_section_cat", "section_id", "category_id", "is_published"),
        Index("idx_assets_filter", "asset_type", "is_paid", "is_published"),
        Index("idx_assets_indexable", "is_indexable", "is_published"),
        Index("idx_assets_priority", "is_published", "display_priority"),
    )
