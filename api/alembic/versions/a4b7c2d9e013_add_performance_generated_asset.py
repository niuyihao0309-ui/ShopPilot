"""add performance generated asset

Revision ID: a4b7c2d9e013
Revises: 9d1f5a42c8b7
Create Date: 2026-06-01 11:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "a4b7c2d9e013"
down_revision: str | None = "9d1f5a42c8b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.add_column("performance_records", sa.Column("generated_asset_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_performance_records_generated_asset_id"),
        "performance_records",
        ["generated_asset_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_performance_records_generated_asset_id",
        "performance_records",
        "generated_assets",
        ["generated_asset_id"],
        ["id"],
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_constraint(
        "fk_performance_records_generated_asset_id",
        "performance_records",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_performance_records_generated_asset_id"), table_name="performance_records")
    op.drop_column("performance_records", "generated_asset_id")
