import os
from pathlib import Path
from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import PlainTextResponse, JSONResponse, Response
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.rate_limit import RateLimitMiddleware
from backend.app.core.http_security import HttpSecurityMiddleware
from backend.app.core.security_configuration import security_configuration_issues
from backend.app.api.v1.router import api_router
from backend.app.db.session import get_db
from backend.app.api.v1.endpoints.seo_aeo import get_llms_txt, get_llms_full_txt, get_mcp_manifest, get_sitemap_index
from backend.app.api.v1.endpoints.mcp_oauth import protected_resource_metadata, authorization_server_metadata

if settings.ENVIRONMENT == 'production':
    issues = security_configuration_issues(settings)
    if issues:
        raise RuntimeError('Unsafe production configuration: ' + '; '.join(issues))

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Open Blueprint Registry & Marketplace for AI Prompts, Agentic Skills, MCP Configs, and Engineering Loops.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# 1. CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["WWW-Authenticate", "MCP-Session-Id", "MCP-Protocol-Version"],
)

# 2. Redis rate limiting: independent IP and device limits, shared across workers.
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.RATE_LIMIT_PER_MINUTE,
    max_read_requests=settings.RATE_LIMIT_READ_PER_MINUTE,
    window_seconds=60
)
app.add_middleware(HttpSecurityMiddleware)

@app.middleware("http")
async def prevent_private_response_caching(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    private_path = any(path.startswith(f"{settings.API_V1_STR}/{part}")
                       for part in ("auth/", "oauth/", "mcp", "users/", "collections", "billing/subscription", "sellers/"))
    if private_path or path.endswith("/download") or request.headers.get("authorization") or request.cookies.get("access_token"):
        response.headers["Cache-Control"] = "private, no-store"
        vary = {v.strip() for v in response.headers.get("Vary", "").split(",") if v.strip()}
        response.headers["Vary"] = ", ".join(sorted(vary | {"Cookie", "Authorization"}))
    return response


# 3. Mount Static Uploads (Media, Cover Images, Avatars, Archives)
app.mount("/avatars", StaticFiles(directory=str(Path(__file__).resolve().parent / "static" / "avatars")), name="default-avatars")
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
# Only previews are public. Archives (including legacy uploads/archives) must
# always pass the authenticated download endpoint.
for kind in ("media", "avatars", "collections"):
    directory = settings.UPLOAD_DIR / kind
    directory.mkdir(parents=True, exist_ok=True)
    app.mount(f"/uploads/{kind}", StaticFiles(directory=str(directory)), name=kind)

# 4. Root-level SEO & AEO Handshakes (Google, Perplexity, PerplexityBot, Perplexity-User, Claude-SearchBot)
@app.get("/llms.txt", tags=["Root SEO/AEO"])
def root_llms_txt(db: Session = Depends(get_db)):
    return get_llms_txt(db=db)

@app.get("/llms-full.txt", tags=["Root SEO/AEO"])
def root_llms_full_txt(db: Session = Depends(get_db)):
    return get_llms_full_txt(db=db)

@app.get("/.well-known/mcp.json", tags=["Root SEO/AEO"])
def root_mcp_manifest():
    return get_mcp_manifest()

@app.get('/.well-known/oauth-protected-resource', tags=['MCP OAuth'])
@app.get('/.well-known/oauth-protected-resource/api/v1/mcp', tags=['MCP OAuth'])
def mcp_resource_metadata():
    return protected_resource_metadata()

@app.get('/.well-known/oauth-authorization-server', tags=['MCP OAuth'])
def mcp_authorization_metadata():
    return authorization_server_metadata()

@app.get("/sitemap.xml", tags=["Root SEO/AEO"])
def root_sitemap(db: Session = Depends(get_db)):
    return get_sitemap_index(db=db)

@app.get(f"/{settings.INDEXNOW_KEY}.txt", tags=["Root SEO/AEO"])
def indexnow_key_verification():
    return PlainTextResponse(settings.INDEXNOW_KEY)

# 5. Health Check
@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "service": "Promptally API", "environment": settings.ENVIRONMENT}

# 6. Mount core V1 API routes
app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True, proxy_headers=False)

