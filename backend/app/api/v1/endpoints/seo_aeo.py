import json
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.app.db.session import get_db
from backend.app.models.asset import Asset
from backend.app.models.collection import Collection
from backend.app.models.enums import CollectionVisibility
from backend.app.models.taxonomy import Section, Category
from backend.app.core.config import settings
from backend.app.services.seo import approx_token_count, variable_names, plain_metadata
from backend.app.api.v1.endpoints.mcp_oauth import require_mcp_user

router = APIRouter()
CHUNK_SIZE = 25000
# A public collection needs enough items to be a useful hub rather than a thin page.
MIN_COLLECTION_ITEMS = 3
SITEMAP_CACHE = "public, s-maxage=21600, stale-while-revalidate=86400"
TEXT_CACHE = "public, s-maxage=3600, stale-while-revalidate=86400"
MCP_PROTOCOL_VERSION = "2025-03-26"


def _base() -> str:
    return settings.SITE_URL.rstrip("/")


def _xml(body: str) -> Response:
    return Response(content=body, media_type="application/xml", headers={"Cache-Control": SITEMAP_CACHE})


def _collection_filter():
    return (Collection.visibility == CollectionVisibility.PUBLIC, Collection.is_indexable.is_(True),
            Collection.item_count >= MIN_COLLECTION_ITEMS)


@router.get("/seo/sitemap.xml")
def get_sitemap_index(db: Session = Depends(get_db)):
    """Dynamic root sitemap index pointing to the hub list, partitioned section chunks and collections."""
    base = _base()
    sections = db.query(Section).order_by(Section.sort_order).all()
    entries = [f"<sitemap><loc>{base}/api/v1/seo/sitemaps/pages.xml</loc></sitemap>"]

    for sec in sections:
        count = (
            db.query(func.count(Asset.id))
            .filter(Asset.section_id == sec.id, Asset.is_published.is_(True), Asset.is_indexable.is_(True))
            .scalar() or 0
        )
        chunks = (count + CHUNK_SIZE - 1) // CHUNK_SIZE if count > 0 else 1
        for ch in range(chunks):
            entries.append(f"<sitemap><loc>{base}/api/v1/seo/sitemaps/{escape(sec.slug)}-{ch}.xml</loc></sitemap>")

    if db.query(func.count(Collection.id)).filter(*_collection_filter()).scalar():
        entries.append(f"<sitemap><loc>{base}/api/v1/seo/sitemaps/collections-0.xml</loc></sitemap>")

    return _xml(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{''.join(entries)}</sitemapindex>"
    )


@router.get("/seo/sitemaps/pages.xml")
def get_pages_sitemap(db: Session = Depends(get_db)):
    """Home, directory and every populated section / category hub (the pages that distribute authority)."""
    base = _base()
    urls = [f"{base}/", f"{base}/directory", f"{base}/curated", f"{base}/contact"]
    for sec in db.query(Section).order_by(Section.sort_order).all():
        sec_count = (db.query(func.count(Asset.id))
                     .filter(Asset.section_id == sec.id, Asset.is_published.is_(True), Asset.is_indexable.is_(True))
                     .scalar() or 0)
        if not sec_count:
            continue
        urls.append(f"{base}/directory/{sec.slug}")
        for cat in sec.categories:
            cat_count = (db.query(func.count(Asset.id))
                         .filter(Asset.category_id == cat.id, Asset.is_published.is_(True),
                                 Asset.is_indexable.is_(True)).scalar() or 0)
            if cat_count:
                urls.append(f"{base}/directory/{sec.slug}/{cat.slug}")
    return _xml(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{escape(u)}</loc></url>" for u in urls) + "</urlset>"
    )


@router.get("/seo/sitemaps/collections-{chunk}.xml")
def get_collections_sitemap(chunk: int, db: Session = Depends(get_db)):
    rows = (db.query(Collection.slug, Collection.updated_at).filter(*_collection_filter())
            .order_by(Collection.id).offset(max(chunk, 0) * CHUNK_SIZE).limit(CHUNK_SIZE).all())
    base = _base()
    return _xml(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(f"<url><loc>{base}/collections/{escape(r.slug)}</loc>"
                  + (f"<lastmod>{r.updated_at.strftime('%Y-%m-%dT%H:%M:%SZ')}</lastmod>" if r.updated_at else "")
                  + "</url>" for r in rows)
        + "</urlset>"
    )


@router.get("/seo/sitemaps/{section}-{chunk}.xml")
def get_section_sitemap_chunk(
    section: str,
    chunk: int,
    db: Session = Depends(get_db)
):
    """Partitioned dynamic sitemap streaming only high-quality indexable URLs."""
    sec = db.query(Section).filter(Section.slug == section).first()
    if not sec or chunk < 0:
        return Response(status_code=404)

    offset = chunk * CHUNK_SIZE
    assets = (
        db.query(Asset.slug, Asset.updated_at)
        .filter(Asset.section_id == sec.id, Asset.is_published.is_(True), Asset.is_indexable.is_(True))
        .order_by(Asset.id)
        .offset(offset)
        .limit(CHUNK_SIZE)
        .all()
    )
    base = _base()
    urls_xml = "".join(
        f"<url><loc>{base}/p/{escape(a.slug)}</loc>"
        f"<lastmod>{a.updated_at.strftime('%Y-%m-%dT%H:%M:%SZ')}</lastmod></url>"
        for a in assets
    )
    return _xml(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{urls_xml}"
        '</urlset>'
    )


def _llms_text(body: str) -> PlainTextResponse:
    return PlainTextResponse(content=body, media_type="text/markdown; charset=utf-8",
                             headers={"Cache-Control": TEXT_CACHE})


LLMS_INTRO = ("> Open registry and marketplace for pre-filled AI prompts, looping workflows, ComfyUI/n8n node graphs, "
              "and SKILL.md agentic skills. Append `.md` to any artifact URL (or send `Accept: text/markdown`) for raw Markdown.")


@router.get("/llms.txt")
def get_llms_txt(db: Session = Depends(get_db)):
    """
    Dynamic /llms.txt index giving AI agents a clean semantic summary beside each link.
    """
    base = _base()
    sections = db.query(Section).order_by(Section.sort_order).all()
    section_lines = [f"- [{plain_metadata(s.name)}]({base}/directory/{quote(s.slug, safe='')}): {plain_metadata(s.description) or 'Blueprints catalog'}" for s in sections]

    top_assets = (
        db.query(Asset.seo_title, Asset.slug, Asset.short_description)
        .filter(Asset.is_published.is_(True), Asset.is_indexable.is_(True))
        .order_by(Asset.copy_count.desc(), Asset.id)
        .limit(20)
        .all()
    )
    top_lines = [f"- [{plain_metadata(a.seo_title)}]({base}/p/{quote(a.slug, safe='')}.md): {plain_metadata(a.short_description)}" for a in top_assets]

    body = f"""# Promptally ({base})
{LLMS_INTRO}

## Core Modality Directories
{chr(10).join(section_lines)}

## Top Intent-Driven Artifacts
{chr(10).join(top_lines)}

## Optional
- [Full index with every category]({base}/llms-full.txt): Categories and the top 200 artifacts with summaries.
- [MCP manifest]({base}/.well-known/mcp.json): Public read-only Model Context Protocol tools.
"""
    return _llms_text(body)


@router.get("/llms-full.txt")
def get_llms_full_txt(db: Session = Depends(get_db)):
    """Extended LLM index: every section and category plus the top 200 indexable artifacts."""
    base = _base()
    lines = [f"# Promptally ({base})", LLMS_INTRO, "", "## Directories"]
    for sec in db.query(Section).order_by(Section.sort_order).all():
        lines.append(f"### [{plain_metadata(sec.name)}]({base}/directory/{quote(sec.slug, safe='')})")
        if sec.description:
            lines.append(plain_metadata(sec.description))
        for cat in sec.categories:
            lines.append(f"- [{plain_metadata(cat.name)}]({base}/directory/{quote(sec.slug, safe='')}/{quote(cat.slug, safe='')}): {plain_metadata(cat.seo_description or cat.name)}")
        lines.append("")
    lines.append("## Artifacts")
    rows = (
        db.query(Asset.seo_title, Asset.slug, Asset.short_description, Asset.is_paid, Asset.price_cents)
        .filter(Asset.is_published.is_(True), Asset.is_indexable.is_(True))
        .order_by(Asset.copy_count.desc(), Asset.id).limit(200).all()
    )
    for r in rows:
        access = f"paid ${r.price_cents / 100:.2f}" if r.is_paid else "free"
        lines.append(f"- [{plain_metadata(r.seo_title)}]({base}/p/{quote(r.slug, safe='')}.md) ({access}): {plain_metadata(r.short_description)[:240]}")
    return _llms_text("\n".join(lines) + "\n")


MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "search_promptally",
        "description": "Search blueprints by keyword, modality (section slug) or model vendor.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keywords"},
                "modality": {"type": "string", "description": "Optional section slug: prompts, skills, mcp-configs, workflows, loops, ..."},
                "vendor": {"type": "string", "description": "Optional model/vendor keyword, e.g. claude, chatgpt, comfyui"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_free_artifact",
        "description": "Get full pre-filled text or source code of any free artifact by slug.",
        "parameters": {
            "type": "object",
            "properties": {"slug": {"type": "string", "description": "Artifact slug"}},
            "required": ["slug"],
        },
    },
    {
        "name": "preview_marketplace_artifact",
        "description": "View benchmark output, structure and checkout link for premium user-sold blueprints.",
        "parameters": {
            "type": "object",
            "properties": {"slug": {"type": "string", "description": "Artifact slug"}},
            "required": ["slug"],
        },
    },
]


@router.get("/.well-known/mcp.json")
def get_mcp_manifest():
    """Public discovery for the authenticated, read-only MCP server."""
    return {
        "schema_version": "1.0",
        "name": "Promptally Blueprint Registry",
        "description": "Search and fetch free prompts, SKILL.md packages, ComfyUI workflows, and deterministic engineering loops.",
        "endpoint": f"{_base()}/api/v1/mcp",
        "protocol": "json-rpc-2.0",
        "authorization": {"type": "oauth2", "resource_metadata": f"{_base()}/.well-known/oauth-protected-resource"},
        "tools": [{**t, "inputSchema": t["parameters"]} for t in MCP_TOOLS],
    }


def _text(text: str, error: bool = False) -> Dict[str, Any]:
    result: Dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if error:
        result["isError"] = True
    return result


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _call_tool(db: Session, name: Optional[str], args: Dict[str, Any]) -> Dict[str, Any]:
    base = _base()
    if name == "search_promptally":
        q = str(args.get("query", "")).strip()[:200]
        query = db.query(Asset).filter(Asset.is_published.is_(True))
        if q:
            query = query.filter((Asset.seo_title.ilike(_like(q), escape="\\"))
                                 | (Asset.short_description.ilike(_like(q), escape="\\")))
        modality = str(args.get("modality") or "").strip()
        if modality:
            query = query.join(Section, Asset.section_id == Section.id).filter(Section.slug == modality)
        vendor = str(args.get("vendor") or "").strip()[:80]
        if vendor:
            query = query.filter((Asset.seo_title.ilike(_like(vendor), escape="\\"))
                                 | (Asset.short_description.ilike(_like(vendor), escape="\\")))
        assets = query.order_by(Asset.copy_count.desc(), Asset.id).limit(10).all()
        return _text(json.dumps([{
            "title": a.seo_title, "slug": a.slug, "summary": a.tldr_summary or a.short_description,
            "url": f"{base}/p/{a.slug}", "markdown_url": f"{base}/p/{a.slug}.md",
            "is_paid": a.is_paid, "price_usd": round(a.price_cents / 100.0, 2),
        } for a in assets], ensure_ascii=False))

    asset = None
    if name in ("get_free_artifact", "preview_marketplace_artifact"):
        asset = db.query(Asset).filter(Asset.slug == str(args.get("slug", "")), Asset.is_published.is_(True)).first()
        if not asset:
            return _text("Artifact not found.", error=True)

    if name == "get_free_artifact":
        if asset.is_paid:
            return _text("This artifact is a paid blueprint. Use preview_marketplace_artifact.", error=True)
        return _text(asset.prefilled_preview_text or asset.raw_content)

    if name == "preview_marketplace_artifact":
        if not asset.is_paid:
            return _text("This artifact is free. Use get_free_artifact.", error=True)
        return _text(json.dumps({
            "title": asset.seo_title,
            "teaser": asset.preview_snippet,
            "benchmark_output": asset.sample_output_markdown or asset.example_output,
            "variables": variable_names(asset.variables_schema),
            "approx_token_count": approx_token_count(asset.raw_content),
            "price_usd": round(asset.price_cents / 100.0, 2),
            "checkout_url": f"{base}/p/{asset.slug}",
        }, ensure_ascii=False))

    return _text(f"Unknown tool: {name}", error=True)


def _rpc_error(rpc_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


def _handle_rpc(db: Session, message: Any) -> Optional[Dict[str, Any]]:
    """Handle one JSON-RPC 2.0 message. Notifications (no `id`) produce no response."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return _rpc_error(message.get("id") if isinstance(message, dict) else None, -32600, "Invalid Request")
    method, rpc_id = message["method"], message.get("id")
    params = message.get("params") if isinstance(message.get("params"), dict) else {}
    is_notification = "id" not in message
    if method == "initialize":
        result: Dict[str, Any] = {
            "protocolVersion": params.get("protocolVersion") or MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "promptally", "version": "1.0.0"},
        }
    elif method == "ping":
        result = {}
    elif method == "tools/list":
        result = {"tools": [{"name": t["name"], "description": t["description"], "inputSchema": t["parameters"]}
                            for t in MCP_TOOLS]}
    elif method == "tools/call":
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        result = _call_tool(db, params.get("name"), args)
    elif is_notification:
        return None
    else:
        return _rpc_error(rpc_id, -32601, f"Method not found: {method}")
    return None if is_notification else {"jsonrpc": "2.0", "id": rpc_id, "result": result}


@router.post("/mcp", dependencies=[Depends(require_mcp_user)])
async def handle_mcp_call(request: Request, db: Session = Depends(get_db)):
    """
    Authenticated read-only MCP endpoint (JSON-RPC 2.0 over HTTP POST).
    Requests without a `jsonrpc` field keep the original lightweight response shape.
    """
    try:
        payload = await request.json()
    except ValueError:
        return JSONResponse(_rpc_error(None, -32700, "Parse error"), status_code=400)

    if isinstance(payload, list):
        if not payload or len(payload) > 10:
            return JSONResponse(_rpc_error(None, -32600, 'Batch must contain between 1 and 10 requests'), status_code=400)
        responses = [r for r in (_handle_rpc(db, m) for m in payload) if r is not None]
        return JSONResponse(responses) if responses else Response(status_code=202)
    if isinstance(payload, dict) and "jsonrpc" in payload:
        response = _handle_rpc(db, payload)
        return JSONResponse(response) if response is not None else Response(status_code=202)

    # Legacy shape.
    payload = payload if isinstance(payload, dict) else {}
    method = payload.get("method")
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    if method == "tools/list":
        return {"tools": get_mcp_manifest()["tools"]}
    if method == "tools/call":
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        return _call_tool(db, params.get("name"), args)
    return _text(f"Unknown method or tool: {method}", error=True)
