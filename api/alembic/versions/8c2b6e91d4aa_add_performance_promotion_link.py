"""add performance promotion link

Revision ID: 8c2b6e91d4aa
Revises: 7f4a9c8e6b21
Create Date: 2026-06-01 11:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "8c2b6e91d4aa"
down_revision: str | None = "7f4a9c8e6b21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.add_column("performance_records", sa.Column("promotion_link_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_performance_records_promotion_link_id"),
        "performance_records",
        ["promotion_link_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_performance_records_promotion_link_id",
        "performance_records",
        "promotion_links",
        ["promotion_link_id"],
        ["id"],
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_constraint(
        "fk_performance_records_promotion_link_id",
        "performance_records",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_performance_records_promotion_link_id"), table_name="performance_records")
    op.drop_column("performance_records", "promotion_link_id")
