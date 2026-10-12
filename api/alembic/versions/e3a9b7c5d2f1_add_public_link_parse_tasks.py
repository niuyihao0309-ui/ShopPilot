"""add public link parse tasks

Revision ID: e3a9b7c5d2f1
Revises: c8d2e4f6a901
Create Date: 2026-06-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e3a9b7c5d2f1"
down_revision: str | None = "c8d2e4f6a901"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


platform_enum = sa.Enum(
    "douyin",
    "taobao",
    "tmall",
    "pinduoduo",
    "jd",
    "tiktok_shop",
    "amazon",
    "other",
    name="platform",
)


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "public_link_parse_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_public_link_parse_tasks_id"), "public_link_parse_tasks", ["id"], unique=False)
    op.create_index(op.f("ix_public_link_parse_tasks_next_run_at"), "public_link_parse_tasks", ["next_run_at"], unique=False)
    op.create_index(op.f("ix_public_link_parse_tasks_platform"), "public_link_parse_tasks", ["platform"], unique=False)
    op.create_index(op.f("ix_public_link_parse_tasks_product_id"), "public_link_parse_tasks", ["product_id"], unique=False)
    op.create_index(op.f("ix_public_link_parse_tasks_status"), "public_link_parse_tasks", ["status"], unique=False)
    op.create_index(op.f("ix_public_link_parse_tasks_task_type"), "public_link_parse_tasks", ["task_type"], unique=False)


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    # 必须先删除依赖任务表的索引，再删除表本身，避免回滚阶段残留数据库对象。
    op.drop_index(op.f("ix_public_link_parse_tasks_task_type"), table_name="public_link_parse_tasks")
    op.drop_index(op.f("ix_public_link_parse_tasks_status"), table_name="public_link_parse_tasks")
    op.drop_index(op.f("ix_public_link_parse_tasks_product_id"), table_name="public_link_parse_tasks")
    op.drop_index(op.f("ix_public_link_parse_tasks_platform"), table_name="public_link_parse_tasks")
    op.drop_index(op.f("ix_public_link_parse_tasks_next_run_at"), table_name="public_link_parse_tasks")
    op.drop_index(op.f("ix_public_link_parse_tasks_id"), table_name="public_link_parse_tasks")
    op.drop_table("public_link_parse_tasks")
