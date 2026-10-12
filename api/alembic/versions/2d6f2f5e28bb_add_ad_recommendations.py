"""add ad recommendations

Revision ID: 2d6f2f5e28bb
Revises: 9b1c8d4a1e6c
Create Date: 2026-06-01 01:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "2d6f2f5e28bb"
down_revision: str | None = "9b1c8d4a1e6c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "ad_recommendations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ad_recommendations_id"), "ad_recommendations", ["id"], unique=False)
    op.create_index(
        op.f("ix_ad_recommendations_product_id"),
        "ad_recommendations",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_index(op.f("ix_ad_recommendations_product_id"), table_name="ad_recommendations")
    op.drop_index(op.f("ix_ad_recommendations_id"), table_name="ad_recommendations")
    op.drop_table("ad_recommendations")
