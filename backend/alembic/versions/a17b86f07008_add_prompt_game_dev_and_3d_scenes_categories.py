"""Add Game Development and 3D Scenes categories at the front of Prompts."""
import uuid
from alembic import op
import sqlalchemy as sa

revision = "a17b86f07008"
down_revision = "f36a75e96007"
branch_labels = None
depends_on = None

NEW_CATEGORIES = (
    (
        "game-development-prompts",
        "Game Development",
        "Game Development Prompts & Blueprints",
        "Game design docs, Godot 4, Unity, Unreal, shaders, mechanics, and interactive NPC prompts",
        1,
    ),
    (
        "3d-scenes",
        "3D Scenes",
        "3D Scenes Prompts & Blueprints",
        "Blender, Three.js, WebGL, Spline, PBR materials, lighting, and procedural 3D scene prompts",
        2,
    ),
)


def upgrade():
    conn = op.get_bind()
    prompts_section_id = conn.execute(
        sa.text("SELECT id FROM sections WHERE slug = 'prompts'")
    ).scalar()
    if not prompts_section_id:
        return

    min_existing_order = conn.execute(
        sa.text(
            "SELECT MIN(sort_order) FROM categories "
            "WHERE section_id = :sec_id AND slug NOT IN ('game-development-prompts', '3d-scenes')"
        ),
        {"sec_id": prompts_section_id},
    ).scalar()

    if min_existing_order is not None and min_existing_order <= 2:
        conn.execute(
            sa.text(
                "UPDATE categories SET sort_order = sort_order + 2 "
                "WHERE section_id = :sec_id AND slug NOT IN ('game-development-prompts', '3d-scenes')"
            ),
            {"sec_id": prompts_section_id},
        )

    for slug, name, seo_title, seo_description, sort_order in NEW_CATEGORIES:
        existing_id = conn.execute(
            sa.text("SELECT id FROM categories WHERE slug = :slug"),
            {"slug": slug},
        ).scalar()
        if existing_id:
            conn.execute(
                sa.text(
                    "UPDATE categories "
                    "SET section_id = :sec_id, name = :name, seo_title = :seo_title, "
                    "    seo_description = :seo_description, sort_order = :sort_order "
                    "WHERE id = :id"
                ),
                {
                    "id": existing_id,
                    "sec_id": prompts_section_id,
                    "name": name,
                    "seo_title": seo_title,
                    "seo_description": seo_description,
                    "sort_order": sort_order,
                },
            )
        else:
            conn.execute(
                sa.text(
                    "INSERT INTO categories (id, section_id, slug, name, seo_title, seo_description, sort_order) "
                    "VALUES (:id, :sec_id, :slug, :name, :seo_title, :seo_description, :sort_order)"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "sec_id": prompts_section_id,
                    "slug": slug,
                    "name": name,
                    "seo_title": seo_title,
                    "seo_description": seo_description,
                    "sort_order": sort_order,
                },
            )


def downgrade():
    conn = op.get_bind()
    prompts_section_id = conn.execute(
        sa.text("SELECT id FROM sections WHERE slug = 'prompts'")
    ).scalar()
    if not prompts_section_id:
        return

    conn.execute(
        sa.text(
            "DELETE FROM categories "
            "WHERE section_id = :sec_id AND slug IN ('game-development-prompts', '3d-scenes')"
        ),
        {"sec_id": prompts_section_id},
    )
    conn.execute(
        sa.text(
            "UPDATE categories SET sort_order = CASE WHEN sort_order > 2 THEN sort_order - 2 ELSE sort_order END "
            "WHERE section_id = :sec_id"
        ),
        {"sec_id": prompts_section_id},
    )

