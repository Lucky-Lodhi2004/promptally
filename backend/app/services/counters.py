"""Atomic interaction counters that never change `updated_at`.

`Asset.updated_at` has `onupdate=func.now()`, so a plain `asset.view_count += 1`
would move the ETag and the sitemap `<lastmod>` on every page view, and would
lose increments under concurrency. These helpers issue one atomic UPDATE that
pins `updated_at` to its current value.
"""
from sqlalchemy.orm import Session

from backend.app.models.asset import Asset

_COLUMNS = {"view_count": Asset.view_count, "copy_count": Asset.copy_count, "download_count": Asset.download_count}


def bump_counter(db: Session, asset_id: str, column: str) -> None:
    col = _COLUMNS[column]
    db.query(Asset).filter(Asset.id == asset_id).update(
        {col: col + 1, Asset.updated_at: Asset.updated_at}, synchronize_session=False)
    db.commit()
