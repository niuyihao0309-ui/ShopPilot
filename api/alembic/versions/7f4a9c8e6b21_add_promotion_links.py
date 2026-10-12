"""add promotion links

Revision ID: 7f4a9c8e6b21
Revises: 2d6f2f5e28bb
Create Date: 2026-06-01 02:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "7f4a9c8e6b21"
down_revision: str | None = "2d6f2f5e28bb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "promotion_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("link_type", sa.String(length=50), nullable=False),
        sa.Column("scenario", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_promotion_links_id"), "promotion_links", ["id"], unique=False)
    op.create_index(
        op.f("ix_promotion_links_product_id"),
        "promotion_links",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_index(op.f("ix_promotion_links_product_id"), table_name="promotion_links")
    op.drop_index(op.f("ix_promotion_links_id"), table_name="promotion_links")
    op.drop_table("promotion_links")
