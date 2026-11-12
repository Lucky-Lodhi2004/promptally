"""Internal-link mesh and near-duplicate detection without a vector database.

This is a lexical stand-in for the pgvector design: IDF-weighted token overlap
finds semantic neighbours, and a deterministic per-category ring distributes
inbound links evenly so that no indexable page is left orphaned.  The index is
pure Python, works on PostgreSQL and SQLite, and can later be replaced by an
embedding lookup that returns the same list-of-dict shape.
"""
import math
import re
import zlib
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.asset import Asset

SEMANTIC_LINKS = 8
CATEGORY_LINKS = 4
MAX_RELATED = SEMANTIC_LINKS + CATEGORY_LINKS
DUPLICATE_THRESHOLD = 0.90
CONTENT_SNIPPET_CHARS = 1500
_TOKEN = re.compile(r"[a-z0-9][a-z0-9+#]{1,}")
_STOP = frozenset(
    "the an and or of to for in on with by is are be this that it as at from your you into how what "
    "using use via can will has have not but all any more".split()
)


def tokenize(text: Optional[str]) -> frozenset:
    return frozenset(t for t in _TOKEN.findall((text or "").lower()) if t not in _STOP)


def jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter) if inter else 0.0


class RelatedIndex:
    """Index of *indexable, published* assets that other pages may link to."""

    def __init__(self, rows: Iterable[Dict[str, Any]]):
        self.items: List[Dict[str, Any]] = []
        postings: Dict[str, List[int]] = defaultdict(list)
        for row in rows:
            idx = len(self.items)
            tokens = tokenize(f"{row['title']} {row.get('description') or ''}")
            item = {
                "slug": row["slug"],
                "title": row["title"],
                "section_slug": row.get("section_slug"),
                "section_id": row.get("section_id"),
                "category_id": row.get("category_id"),
                "tokens": tokens,
                "ctokens": tokenize(f"{row['title']} {row.get('description') or ''} {row.get('content') or ''}"),
            }
            self.items.append(item)
            for token in tokens:
                postings[token].append(idx)
        n = max(1, len(self.items))
        # Very common tokens add noise and make candidate scans quadratic.
        self.max_df = max(50, int(n * 0.02))
        self.postings = {t: p for t, p in postings.items() if len(p) <= self.max_df}
        self.idf = {t: math.log(1 + n / len(p)) for t, p in self.postings.items()}
        for item in self.items:
            item["weight"] = math.sqrt(sum(self.idf.get(t, 0.0) for t in item["tokens"])) or 1.0
        self.by_slug = {item["slug"]: i for i, item in enumerate(self.items)}
        groups: Dict[Any, List[int]] = defaultdict(list)
        for i, item in enumerate(self.items):
            groups[item["category_id"] or item["section_id"]].append(i)
        self.groups = {k: sorted(v, key=lambda i: self.items[i]["slug"]) for k, v in groups.items()}

    def _scores(self, tokens: frozenset, exclude_slug: Optional[str]) -> Dict[int, float]:
        scores: Dict[int, float] = defaultdict(float)
        for token in tokens:
            idf = self.idf.get(token)
            if idf is None:
                continue
            for j in self.postings[token]:
                scores[j] += idf
        if exclude_slug in self.by_slug:
            scores.pop(self.by_slug[exclude_slug], None)
        return scores

    def max_duplicate_similarity(self, text: str, exclude_slug: Optional[str] = None,
                                 only_before: Optional[int] = None) -> float:
        """Highest content overlap with an already-indexed page (top 5 lexical candidates)."""
        tokens = tokenize(text)
        scores = self._scores(tokens, exclude_slug)
        if only_before is not None:
            scores = {j: s for j, s in scores.items() if j < only_before}
        best = 0.0
        for j, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:5]:
            best = max(best, jaccard(tokens, self.items[j]["ctokens"]))
        return best

    def related(self, slug: str, title: str, description: Optional[str], section_id: Optional[str],
                category_id: Optional[str], semantic: int = SEMANTIC_LINKS,
                category: int = CATEGORY_LINKS) -> List[Dict[str, Optional[str]]]:
        tokens = tokenize(f"{title} {description or ''}")
        scored = self._scores(tokens, slug)
        weight = math.sqrt(sum(self.idf.get(t, 0.0) for t in tokens)) or 1.0
        ranked = sorted(
            ((s / (weight * self.items[j]["weight"]), j) for j, s in scored.items()
             if self.items[j]["section_id"] == section_id or section_id is None),
            key=lambda pair: (-pair[0], self.items[pair[1]]["slug"]),
        )
        chosen: List[int] = [j for _, j in ranked[:semantic]]
        # Ring: each member links to the next peers in its category, so inbound
        # links are spread evenly instead of piling onto the same few pages.
        ring = self.groups.get(category_id or section_id, [])
        members = [i for i in ring if self.items[i]["slug"] != slug]
        if members and category:
            if slug in self.by_slug:
                here = ring.index(self.by_slug[slug])
                ordered = ring[here + 1:] + ring[:here]
            else:
                offset = zlib.crc32(slug.encode()) % len(members)
                ordered = members[offset:] + members[:offset]
            added = 0
            for j in ordered:
                if added >= category:
                    break
                if j not in chosen:
                    chosen.append(j)
                    added += 1
        return [
            {"slug": self.items[j]["slug"], "title": self.items[j]["title"],
             "section_slug": self.items[j]["section_slug"]}
            for j in chosen[:MAX_RELATED]
        ]


def _rows(db: Session, section_id: Optional[str], limit: Optional[int], exclude_id: Optional[str],
          indexable_only: bool = True) -> List[Dict[str, Any]]:
    query = (db.query(Asset.slug, Asset.seo_title, Asset.short_description, Asset.section_id, Asset.category_id,
                      func.substr(Asset.raw_content, 1, CONTENT_SNIPPET_CHARS))
             .filter(Asset.is_published.is_(True), Asset.is_paid.is_(False)))
    if indexable_only:
        query = query.filter(Asset.is_indexable.is_(True))
    if section_id:
        query = query.filter(Asset.section_id == section_id)
    if exclude_id:
        query = query.filter(Asset.id != exclude_id)
    query = query.order_by(Asset.copy_count.desc(), Asset.id)
    rows = (query.limit(limit) if limit else query).all()
    return [{"slug": r[0], "title": r[1], "description": r[2], "section_id": r[3], "category_id": r[4],
             "content": r[5]} for r in rows]


def index_for_section(db: Session, section_id: Optional[str], section_slug: Optional[str] = None,
                      exclude_id: Optional[str] = None, limit: Optional[int] = 3000,
                      indexable_only: bool = True) -> RelatedIndex:
    """`limit=None` indexes the whole section (batch jobs); uploads use a bounded top-N pool."""
    rows = _rows(db, section_id, limit, exclude_id, indexable_only)
    for row in rows:
        row["section_slug"] = section_slug
    return RelatedIndex(rows)


def related_for_new_asset(db: Session, asset: Asset) -> Dict[str, Any]:
    """Upload-time computation: neighbours for the asset plus its duplicate score."""
    section_slug = asset.section.slug if asset.section else None
    index = index_for_section(db, asset.section_id, section_slug, exclude_id=asset.id)
    text = f"{asset.seo_title} {asset.short_description or ''} {(asset.raw_content or '')[:CONTENT_SNIPPET_CHARS]}"
    return {
        "related": index.related(asset.slug, asset.seo_title, asset.short_description,
                                 asset.section_id, asset.category_id),
        "max_similarity": index.max_duplicate_similarity(text, exclude_slug=asset.slug),
    }


def link_back(db: Session, asset: Asset, related: Sequence[Dict[str, Any]]) -> List[Asset]:
    """Add the new page to its category peers' mesh so it is not an orphan."""
    from backend.app.services.seo import compile_aeo_markdown
    changed: List[Asset] = []
    entry = {"slug": asset.slug, "title": asset.seo_title,
             "section_slug": asset.section.slug if asset.section else None}
    if not asset.is_indexable:
        return changed
    for rel in list(related)[:CATEGORY_LINKS]:
        peer = db.query(Asset).filter(Asset.slug == rel["slug"]).first()
        if peer is None:
            continue
        links = [r for r in (peer.related_artifacts or []) if isinstance(r, dict) and r.get("slug") != asset.slug]
        peer.related_artifacts = (links[:MAX_RELATED - 1] + [entry])
        peer.aeo_markdown_twin = compile_aeo_markdown(peer, is_locked=peer.is_paid)
        changed.append(peer)
    return changed
