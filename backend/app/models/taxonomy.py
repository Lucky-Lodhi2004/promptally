import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.app.db.session import Base

class AssetTag(Base):
    __tablename__ = "asset_tags"

    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

class AssetModel(Base):
    __tablename__ = "asset_models"

    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True)
    model_id = Column(String(36), ForeignKey("target_models.id", ondelete="CASCADE"), primary_key=True)

class Section(Base):
    __tablename__ = "sections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(80), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    icon_name = Column(String(50), nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)

    # Relationships
    categories = relationship("Category", back_populates="section", cascade="all, delete-orphan", order_by="Category.sort_order")
    assets = relationship("Asset", back_populates="section")

class Category(Base):
    __tablename__ = "categories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    section_id = Column(String(36), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False, index=True)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(120), nullable=False)
    seo_title = Column(String(255), nullable=True)
    seo_description = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)

    # Relationships
    section = relationship("Section", back_populates="categories")
    assets = relationship("Asset", back_populates="category")

class Tag(Base):
    __tablename__ = "tags"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)

    assets = relationship("Asset", secondary="asset_tags", back_populates="tags")

class TargetModel(Base):
    __tablename__ = "target_models"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    slug = Column(String(80), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    vendor = Column(String(80), nullable=True)
    badge_color = Column(String(30), nullable=True)

    assets = relationship("Asset", secondary="asset_models", back_populates="target_models")

