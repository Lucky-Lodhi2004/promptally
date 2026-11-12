import uuid
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime,
    ForeignKey, Enum as SQLEnum, UniqueConstraint, func
)
from sqlalchemy.orm import relationship
from backend.app.db.session import Base
from backend.app.models.enums import CollectionVisibility

class Collection(Base):
    __tablename__ = "collections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(255), unique=True, index=True, nullable=False)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)
    
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    visibility = Column(SQLEnum(CollectionVisibility), default=CollectionVisibility.PRIVATE, nullable=False)
    item_count = Column(Integer, default=0, nullable=False)
    is_indexable = Column(Boolean, default=True, index=True, nullable=False)
    cover_image_url = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    owner = relationship("User", back_populates="collections")
    items = relationship("CollectionItem", back_populates="collection", cascade="all, delete-orphan", order_by="CollectionItem.sort_order")

class CollectionItem(Base):
    __tablename__ = "collection_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    collection_id = Column(String(36), ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    
    sort_order = Column(Integer, default=0, nullable=False)
    custom_note = Column(Text, nullable=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    collection = relationship("Collection", back_populates="items")
    asset = relationship("Asset", back_populates="collection_items")

    __table_args__ = (
        UniqueConstraint("collection_id", "asset_id", name="uq_collection_asset"),
    )

