"""add promotion link tracking

Revision ID: d4e9a7b2c6f1
Revises: c1f7d5e8a2b4
Create Date: 2026-06-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d4e9a7b2c6f1"
down_revision: str | None = "c1f7d5e8a2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.add_column("promotion_links", sa.Column("tracking_code", sa.String(length=64), nullable=True))
    op.add_column("promotion_links", sa.Column("short_code", sa.String(length=32), nullable=True))
    op.add_column("promotion_links", sa.Column("tracking_url", sa.String(length=2048), nullable=True))
    op.add_column(
        "promotion_links",
        sa.Column("click_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_index(op.f("ix_promotion_links_tracking_code"), "promotion_links", ["tracking_code"], unique=True)
    op.create_index(op.f("ix_promotion_links_short_code"), "promotion_links", ["short_code"], unique=True)

    op.create_table(
        "promotion_link_clicks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("promotion_link_id", sa.Integer(), nullable=False),
        sa.Column("tracking_code", sa.String(length=64), nullable=True),
        sa.Column("referer", sa.String(length=2048), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("clicked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["promotion_link_id"], ["promotion_links.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_promotion_link_clicks_id"), "promotion_link_clicks", ["id"], unique=False)
    op.create_index(
        op.f("ix_promotion_link_clicks_product_id"),
        "promotion_link_clicks",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_promotion_link_clicks_promotion_link_id"),
        "promotion_link_clicks",
        ["promotion_link_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_promotion_link_clicks_tracking_code"),
        "promotion_link_clicks",
        ["tracking_code"],
        unique=False,
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.drop_index(op.f("ix_promotion_link_clicks_tracking_code"), table_name="promotion_link_clicks")
    op.drop_index(op.f("ix_promotion_link_clicks_promotion_link_id"), table_name="promotion_link_clicks")
    op.drop_index(op.f("ix_promotion_link_clicks_product_id"), table_name="promotion_link_clicks")
    op.drop_index(op.f("ix_promotion_link_clicks_id"), table_name="promotion_link_clicks")
    op.drop_table("promotion_link_clicks")

    op.drop_index(op.f("ix_promotion_links_short_code"), table_name="promotion_links")
    op.drop_index(op.f("ix_promotion_links_tracking_code"), table_name="promotion_links")
    op.drop_column("promotion_links", "click_count")
    op.drop_column("promotion_links", "tracking_url")
    op.drop_column("promotion_links", "short_code")
    op.drop_column("promotion_links", "tracking_code")
