"""add generation job queue fields

Revision ID: b9e8c7a6d513
Revises: a7c5e9f1d024
Create Date: 2026-06-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b9e8c7a6d513"
down_revision: str | None = "a7c5e9f1d024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 先补充队列控制字段，再创建索引；服务上线后才能安全认领、重试和回收超时任务。
    op.add_column("generation_jobs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("generation_jobs", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("generation_jobs", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("generation_jobs", sa.Column("locked_by", sa.String(length=120), nullable=True))
    op.add_column("generation_jobs", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_generation_jobs_next_run_at"), "generation_jobs", ["next_run_at"], unique=False)


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_index(op.f("ix_generation_jobs_next_run_at"), table_name="generation_jobs")
    op.drop_column("generation_jobs", "next_run_at")
    op.drop_column("generation_jobs", "locked_by")
    op.drop_column("generation_jobs", "locked_at")
    op.drop_column("generation_jobs", "max_attempts")
    op.drop_column("generation_jobs", "attempts")
