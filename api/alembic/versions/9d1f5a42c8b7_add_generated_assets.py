"""add generated assets

Revision ID: 9d1f5a42c8b7
Revises: 8c2b6e91d4aa
Create Date: 2026-06-01 11:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "9d1f5a42c8b7"
down_revision: str | None = "8c2b6e91d4aa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "generated_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("creative_plan_id", sa.Integer(), nullable=False),
        sa.Column("generation_job_id", sa.Integer(), nullable=True),
        sa.Column("asset_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("size", sa.String(length=50), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["creative_plan_id"], ["creative_plans.id"]),
        sa.ForeignKeyConstraint(["generation_job_id"], ["generation_jobs.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generated_assets_id"), "generated_assets", ["id"], unique=False)
    op.create_index(
        op.f("ix_generated_assets_product_id"),
        "generated_assets",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_generated_assets_creative_plan_id"),
        "generated_assets",
        ["creative_plan_id"],
        unique=False,
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_index(op.f("ix_generated_assets_creative_plan_id"), table_name="generated_assets")
    op.drop_index(op.f("ix_generated_assets_product_id"), table_name="generated_assets")
    op.drop_index(op.f("ix_generated_assets_id"), table_name="generated_assets")
    op.drop_table("generated_assets")
