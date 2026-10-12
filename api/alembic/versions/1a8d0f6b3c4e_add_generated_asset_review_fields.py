"""add generated asset review fields

Revision ID: 1a8d0f6b3c4e
Revises: 7b1e6d4c2f90
Create Date: 2026-06-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "1a8d0f6b3c4e"
down_revision: str | None = "7b1e6d4c2f90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    op.add_column(
        "generated_assets",
        sa.Column("asset_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("generated_assets", sa.Column("usage_contexts", sa.JSON(), nullable=True))
    op.execute("UPDATE generated_assets SET usage_contexts = JSON_ARRAY() WHERE usage_contexts IS NULL")
    op.alter_column("generated_assets", "usage_contexts", existing_type=sa.JSON(), nullable=False)


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_column("generated_assets", "usage_contexts")
    op.drop_column("generated_assets", "asset_version")
