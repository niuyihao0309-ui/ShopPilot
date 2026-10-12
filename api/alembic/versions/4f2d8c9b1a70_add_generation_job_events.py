"""add generation job events

Revision ID: 4f2d8c9b1a70
Revises: e3a9b7c5d2f1
Create Date: 2026-06-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "4f2d8c9b1a70"
down_revision: str | None = "e3a9b7c5d2f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


generation_job_status_enum = sa.Enum("pending", "running", "succeeded", "failed", name="generationjobstatus")


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "generation_job_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("status", generation_job_status_enum, nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("worker_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["generation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_generation_job_events_event_type"), "generation_job_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_generation_job_events_id"), "generation_job_events", ["id"], unique=False)
    op.create_index(op.f("ix_generation_job_events_job_id"), "generation_job_events", ["job_id"], unique=False)
    op.create_index(op.f("ix_generation_job_events_status"), "generation_job_events", ["status"], unique=False)


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_index(op.f("ix_generation_job_events_status"), table_name="generation_job_events")
    op.drop_index(op.f("ix_generation_job_events_job_id"), table_name="generation_job_events")
    op.drop_index(op.f("ix_generation_job_events_id"), table_name="generation_job_events")
    op.drop_index(op.f("ix_generation_job_events_event_type"), table_name="generation_job_events")
    op.drop_table("generation_job_events")
