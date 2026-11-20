from fastapi import APIRouter

from backend.app.api.v1.endpoints import (
    catalog,
    assets_actions,
    collections,
    auth,
    users,
    billing,
    marketplace,
    admin,
    seo_aeo,
    mcp_oauth,
)

api_router = APIRouter()

# 1. Categories, Subcategories & Browsing (3 Endpoints)
api_router.include_router(catalog.router, tags=["Catalog & Browsing"])

# 2. Copying, Downloading & Uploading Artifacts (3 Endpoints)
api_router.include_router(assets_actions.router, tags=["Artifacts & Actions"])

# 3. Collections for Paid Subscribers (5 Endpoints)
api_router.include_router(collections.router, tags=["Collections"])

# 4. Authentication & Device Limit (4 Endpoints)
api_router.include_router(auth.router, tags=["Authentication"])

# 5. User Profile & Account Settings (3 Endpoints)
api_router.include_router(users.router, tags=["Users"])

# 6. $1 Platform Subscription — Verified IP routing: Razorpay & Dodo
api_router.include_router(billing.router, tags=["Subscriptions & Billing"])

# 7. Direct buyer-to-seller checkouts and signed webhooks
api_router.include_router(marketplace.router, tags=["Direct Marketplace"])

# 8. Admin Panel (1 Endpoint)
api_router.include_router(admin.router, tags=["Admin"])

# Bonus: SEO & AEO Discovery Layer (Sitemaps, llms.txt, MCP)
api_router.include_router(seo_aeo.router, tags=["SEO & AEO"])
api_router.include_router(mcp_oauth.router, tags=["MCP OAuth"])

