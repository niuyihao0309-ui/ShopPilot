"""add ad experiments

Revision ID: b6c2a1f4d8e9
Revises: a4b7c2d9e013
Create Date: 2026-06-01 12:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b6c2a1f4d8e9"
down_revision: str | None = "a4b7c2d9e013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "ad_experiments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("generated_asset_id", sa.Integer(), nullable=True),
        sa.Column("promotion_link_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("audience", sa.Text(), nullable=True),
        sa.Column("daily_budget", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("success_metric", sa.Text(), nullable=True),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["generated_asset_id"], ["generated_assets.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["promotion_link_id"], ["promotion_links.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ad_experiments_id"), "ad_experiments", ["id"], unique=False)
    op.create_index(op.f("ix_ad_experiments_product_id"), "ad_experiments", ["product_id"], unique=False)


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_index(op.f("ix_ad_experiments_product_id"), table_name="ad_experiments")
    op.drop_index(op.f("ix_ad_experiments_id"), table_name="ad_experiments")
    op.drop_table("ad_experiments")
