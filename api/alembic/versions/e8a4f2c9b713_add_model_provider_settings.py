"""add model provider settings

Revision ID: e8a4f2c9b713
Revises: d4e9a7b2c6f1
Create Date: 2026-06-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e8a4f2c9b713"
down_revision: str | None = "d4e9a7b2c6f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "model_provider_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target", sa.Enum("text", "image", "video", name="modeltarget"), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("base_url", sa.String(length=1024), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("size", sa.String(length=50), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("workspace_id", sa.String(length=120), nullable=True),
        sa.Column("poll_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("poll_max_attempts", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_model_provider_settings_id"), "model_provider_settings", ["id"], unique=False)
    op.create_index(
        op.f("ix_model_provider_settings_target"),
        "model_provider_settings",
        ["target"],
        unique=True,
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_index(op.f("ix_model_provider_settings_target"), table_name="model_provider_settings")
    op.drop_index(op.f("ix_model_provider_settings_id"), table_name="model_provider_settings")
    op.drop_table("model_provider_settings")
