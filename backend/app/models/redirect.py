from sqlalchemy import Column, String, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from backend.app.db.session import Base

class SlugRedirect(Base):
    __tablename__ = "slug_redirects"

    old_slug = Column(String(255), primary_key=True, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    asset = relationship("Asset", back_populates="slug_redirects")

