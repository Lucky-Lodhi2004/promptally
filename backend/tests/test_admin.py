import io
from datetime import datetime, timedelta, timezone
from PIL import Image

from backend.app.core.security import create_access_token
from backend.app.models import Asset, AssetPurchase, Category, Section, Subscription, User
from backend.app.models.enums import (
    AssetType,
    PurchaseStatus,
    SourceType,
    SubscriptionGateway,
    SubscriptionStatus,
    UserTier,
)
from backend.app.models.registration import SignupQuota


def _auth_header(user: User) -> dict:
    token = create_access_token(user.id, token_version=user.token_version)
    return {"Authorization": f"Bearer {token}"}


def _make_admin(db) -> User:
    admin = User(
        id="admin-1",
        email="admin@promptally.dev",
        username="rootadmin",
        name="Promptally Admin",
        tier=UserTier.ADMIN,
        email_verification_required=False,
    )
    db.add(admin)
    db.commit()
    return admin


def _make_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(242, 140, 40)).save(buf, format="PNG")
    return buf.getvalue()


def test_admin_endpoints_reject_anonymous_and_non_admin(client, db, users, asset):
    seller, buyer = users
    endpoints = [
        ("GET", "/api/v1/admin/users"),
        ("GET", "/api/v1/admin/assets"),
        ("POST", f"/api/v1/admin/assets/{asset.id}/move-to-top"),
        ("DELETE", f"/api/v1/admin/assets/{asset.id}"),
        ("POST", f"/api/v1/admin/users/{seller.id}/end-subscription"),
        ("DELETE", f"/api/v1/admin/users/{buyer.id}"),
    ]

    for method, path in endpoints:
        anon = client.request(method, path)
        assert anon.status_code == 401, f"{method} {path} should require auth"

        pro_res = client.request(method, path, headers=_auth_header(seller))
        assert pro_res.status_code == 403, f"{method} {path} should reject Pro user"

        free_res = client.request(method, path, headers=_auth_header(buyer))
        assert free_res.status_code == 403, f"{method} {path} should reject Free user"


def test_admin_add_artifact_with_cdn_links_shows_promptally_author(client, db):
    admin = _make_admin(db)
    sec = Section(id="sec-wf", slug="workflows", name="Workflows")
    cat = Category(id="cat-wf", section_id=sec.id, slug="comfyui", name="ComfyUI")
    db.add_all([sec, cat])
    db.commit()

    # Reject unsafe URL schemes
    bad = client.post(
        "/api/v1/admin/assets",
        headers=_auth_header(admin),
        data={
            "section_slug": "workflows",
            "category_slug": "comfyui",
            "heading": "Bad URL Workflow",
            "raw_text": '{"nodes": []}',
            "image_url": "javascript:alert(1)",
        },
    )
    assert bad.status_code == 400

    # Valid CDN image + CDN GIF URLs
    res = client.post(
        "/api/v1/admin/assets",
        headers=_auth_header(admin),
        data={
            "section_slug": "workflows",
            "category_slug": "comfyui",
            "heading": "Flux Schnell Upscale Graph",
            "description": "Official high-speed upscaling workflow.",
            "raw_text": '{"nodes": [{"id": 1, "type": "Upscale"}]}',
            "image_url": "https://cdn.example.com/images/flux.webp",
            "gif_url": "https://cdn.example.com/demos/flux.gif",
            "pin_to_top": "true",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["author_username"] == "promptally"
    assert body["display_priority"] == 1
    assert body["media_preview_url"] == "https://cdn.example.com/images/flux.webp"
    assert body["gif_preview_url"] == "https://cdn.example.com/demos/flux.gif"

    # Detail endpoint shows @promptally and both CDN media entries
    detail = client.get(f"/api/v1/assets/{body['slug']}")
    assert detail.status_code == 200
    detail_json = detail.json()
    assert detail_json["author"]["username"] == "promptally"
    assert detail_json["author"]["id"] is None
    media_urls = [m["url"] for m in detail_json["preview_media"]]
    assert "https://cdn.example.com/images/flux.webp" in media_urls
    assert "https://cdn.example.com/demos/flux.gif" in media_urls


def test_admin_add_artifact_with_uploaded_image_and_conflict_check(client, db):
    admin = _make_admin(db)
    sec = Section(id="sec-sk", slug="skills", name="Agentic Skills")
    cat = Category(id="cat-sk", section_id=sec.id, slug="backend", name="Backend")
    db.add_all([sec, cat])
    db.commit()

    # Reject providing both upload AND CDN URL for image
    conflict = client.post(
        "/api/v1/admin/assets",
        headers=_auth_header(admin),
        data={
            "section_slug": "skills",
            "category_slug": "backend",
            "heading": "Conflict Skill",
            "raw_text": "# Skill\nDo the thing.",
            "image_url": "https://cdn.example.com/a.webp",
        },
        files={"image": ("preview.png", _make_png_bytes(), "image/png")},
    )
    assert conflict.status_code == 400

    # Valid uploaded image file
    res = client.post(
        "/api/v1/admin/assets",
        headers=_auth_header(admin),
        data={
            "section_slug": "skills",
            "category_slug": "backend",
            "heading": "FastAPI Audit Skill",
            "raw_text": "# FastAPI Audit\nCheck routes, SQL queries, and auth boundaries.",
        },
        files={"image": ("preview.png", _make_png_bytes(), "image/png")},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["author_username"] == "promptally"
    assert body["media_preview_url"].startswith("/uploads/media/")


def test_admin_rearrange_pin_swap_unpin_and_delete_artifacts(client, db, users):
    admin = _make_admin(db)
    seller, buyer = users
    sec = Section(id="sec-p", slug="prompts", name="Prompts")
    cat = Category(id="cat-p", section_id=sec.id, slug="coding", name="Coding")
    a1 = Asset(
        id="a1", slug="alpha-prompt", seo_title="Alpha", short_description="Alpha desc",
        section_id=sec.id, category_id=cat.id, asset_type=AssetType.PROMPT,
        raw_content="Alpha content", file_name="a.md", file_extension=".md",
        source_type=SourceType.INGESTED, author_id=None, copy_count=100, is_published=True,
    )
    a2 = Asset(
        id="a2", slug="beta-prompt", seo_title="Beta", short_description="Beta desc",
        section_id=sec.id, category_id=cat.id, asset_type=AssetType.PROMPT,
        raw_content="Beta content", file_name="b.md", file_extension=".md",
        source_type=SourceType.INGESTED, author_id=None, copy_count=50, is_published=True,
    )
    a3 = Asset(
        id="a3", slug="gamma-prompt", seo_title="Gamma", short_description="Gamma desc",
        section_id=sec.id, category_id=cat.id, asset_type=AssetType.PROMPT,
        raw_content="Gamma content", file_name="c.md", file_extension=".md",
        source_type=SourceType.USER_CREATED, author_id=seller.id, copy_count=5, is_published=True,
    )
    db.add_all([sec, cat, a1, a2, a3])
    db.commit()

    # Default order by copy_count: Alpha, Beta, Gamma
    listed = client.get("/api/v1/assets?sort=popular").json()["items"]
    assert [x["slug"] for x in listed] == ["alpha-prompt", "beta-prompt", "gamma-prompt"]

    # Shift Gamma to top -> Gamma, Alpha, Beta
    top_res = client.post("/api/v1/admin/assets/a3/move-to-top", headers=_auth_header(admin))
    assert top_res.status_code == 200
    assert top_res.json()["display_priority"] == 1
    listed = client.get("/api/v1/assets?sort=popular").json()["items"]
    assert [x["slug"] for x in listed] == ["gamma-prompt", "alpha-prompt", "beta-prompt"]

    # Shift Beta to top -> Beta, Gamma, Alpha
    top_res2 = client.post("/api/v1/admin/assets/a2/move-to-top", headers=_auth_header(admin))
    assert top_res2.json()["display_priority"] == 2
    listed = client.get("/api/v1/assets?sort=popular").json()["items"]
    assert [x["slug"] for x in listed] == ["beta-prompt", "gamma-prompt", "alpha-prompt"]

    # Swap Beta and Gamma via reorder -> Gamma, Beta, Alpha
    swap = client.post(
        "/api/v1/admin/assets/reorder",
        headers=_auth_header(admin),
        json={"ordered_ids": ["a3", "a2"]},
    )
    assert swap.status_code == 200
    listed = client.get("/api/v1/assets?sort=popular").json()["items"]
    assert [x["slug"] for x in listed] == ["gamma-prompt", "beta-prompt", "alpha-prompt"]

    # Unpin Gamma -> Beta, Alpha, Gamma
    unpin = client.patch(
        "/api/v1/admin/assets/a3/priority",
        headers=_auth_header(admin),
        json={"display_priority": 0},
    )
    assert unpin.status_code == 200
    listed = client.get("/api/v1/assets?sort=popular").json()["items"]
    assert [x["slug"] for x in listed] == ["beta-prompt", "alpha-prompt", "gamma-prompt"]

    # Delete Beta -> only Alpha, Gamma remain
    deleted = client.delete("/api/v1/admin/assets/a2", headers=_auth_header(admin))
    assert deleted.status_code == 200
    listed = client.get("/api/v1/assets?sort=popular").json()["items"]
    assert [x["slug"] for x in listed] == ["alpha-prompt", "gamma-prompt"]


def test_admin_end_subscription_and_delete_user_account(client, db, users, asset, provider):
    admin = _make_admin(db)
    seller, buyer = users
    calls, responses = provider
    responses[("POST", "razorpay", "/subscriptions/sub_existing/cancel")] = {
        "id": "sub_existing",
        "status": "cancelled",
    }

    # Record a real purchase + signup quota so we verify safe FK deletion & quota preservation
    db.add(
        AssetPurchase(
            id="purchase-1",
            buyer_id=buyer.id,
            asset_id=asset.id,
            seller_id=seller.id,
            amount_cents=500,
            platform_fee_cents=0,
            seller_payout_cents=500,
            provider="razorpay",
            provider_payment_id="pay_123",
            currency="USD",
            payment_reference="razorpay:pay_123",
            status=PurchaseStatus.COMPLETED,
        )
    )
    db.add(SignupQuota(key="ip:1.2.3.4", kind="ip", used=2))
    db.commit()

    # 1. End seller's Pro subscription
    end_res = client.post(
        f"/api/v1/admin/users/{seller.id}/end-subscription",
        headers=_auth_header(admin),
        json={"cancel_at_provider": True},
    )
    assert end_res.status_code == 200, end_res.text
    assert end_res.json()["tier"] == "FREE"
    assert end_res.json()["provider_cancel"] == "canceled"

    db.refresh(seller)
    sub = db.query(Subscription).filter_by(user_id=seller.id).first()
    assert seller.tier == UserTier.FREE
    assert sub.status == SubscriptionStatus.CANCELED
    assert any(path == "/subscriptions/sub_existing/cancel" for _, _, path, _ in calls)

    # 2. Admin cannot delete own account
    self_del = client.delete(f"/api/v1/admin/users/{admin.id}", headers=_auth_header(admin))
    assert self_del.status_code == 400

    # 3. Admin deletes seller account cleanly despite purchased asset
    del_res = client.delete(f"/api/v1/admin/users/{seller.id}", headers=_auth_header(admin))
    assert del_res.status_code == 200, del_res.text
    assert db.get(User, seller.id) is None
    # Purchased asset was safely detached & soft-deleted (no FK IntegrityError)
    remaining_asset = db.get(Asset, asset.id)
    assert remaining_asset is not None
    assert remaining_asset.author_id is None
    assert remaining_asset.is_published is False
    # Durable signup quota untouched
    assert db.get(SignupQuota, "ip:1.2.3.4").used == 2

