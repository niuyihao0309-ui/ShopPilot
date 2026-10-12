"""add generation jobs

Revision ID: 9b1c8d4a1e6c
Revises: 5fc93ddaa8e8
Create Date: 2026-06-01 00:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "9b1c8d4a1e6c"
down_revision: str | None = "5fc93ddaa8e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "generation_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("creative_plan_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("main_image_asset", "video_asset", name="generationjobkind"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "succeeded", "failed", name="generationjobstatus"),
            nullable=False,
        ),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["creative_plan_id"], ["creative_plans.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generation_jobs_id"), "generation_jobs", ["id"], unique=False)
    op.create_index(op.f("ix_generation_jobs_product_id"), "generation_jobs", ["product_id"], unique=False)
    op.create_index(
        op.f("ix_generation_jobs_creative_plan_id"),
        "generation_jobs",
        ["creative_plan_id"],
        unique=False,
    )
    op.create_index(op.f("ix_generation_jobs_status"), "generation_jobs", ["status"], unique=False)


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_index(op.f("ix_generation_jobs_status"), table_name="generation_jobs")
    op.drop_index(op.f("ix_generation_jobs_creative_plan_id"), table_name="generation_jobs")
    op.drop_index(op.f("ix_generation_jobs_product_id"), table_name="generation_jobs")
    op.drop_index(op.f("ix_generation_jobs_id"), table_name="generation_jobs")
    op.drop_table("generation_jobs")
