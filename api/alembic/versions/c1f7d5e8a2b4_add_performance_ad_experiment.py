"""add performance ad experiment

Revision ID: c1f7d5e8a2b4
Revises: b6c2a1f4d8e9
Create Date: 2026-06-01 12:58:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c1f7d5e8a2b4"
down_revision: str | None = "b6c2a1f4d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.add_column("performance_records", sa.Column("ad_experiment_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_performance_records_ad_experiment_id"),
        "performance_records",
        ["ad_experiment_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_performance_records_ad_experiment_id",
        "performance_records",
        "ad_experiments",
        ["ad_experiment_id"],
        ["id"],
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_constraint(
        "fk_performance_records_ad_experiment_id",
        "performance_records",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_performance_records_ad_experiment_id"), table_name="performance_records")
    op.drop_column("performance_records", "ad_experiment_id")
