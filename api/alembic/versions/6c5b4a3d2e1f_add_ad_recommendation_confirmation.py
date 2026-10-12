"""add ad recommendation confirmation

Revision ID: 6c5b4a3d2e1f
Revises: 1a8d0f6b3c4e
Create Date: 2026-06-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "6c5b4a3d2e1f"
down_revision: str | None = "1a8d0f6b3c4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.add_column(
        "ad_recommendations",
        sa.Column("confirmation_status", sa.String(length=50), nullable=False, server_default="pending"),
    )
    op.add_column("ad_recommendations", sa.Column("confirmed_by_user_id", sa.Integer(), nullable=True))
    op.add_column("ad_recommendations", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ad_recommendations", sa.Column("confirmation_note", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_ad_recommendations_confirmed_by_user_id_users",
        "ad_recommendations",
        "users",
        ["confirmed_by_user_id"],
        ["id"],
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.drop_constraint(
        "fk_ad_recommendations_confirmed_by_user_id_users",
        "ad_recommendations",
        type_="foreignkey",
    )
    op.drop_column("ad_recommendations", "confirmation_note")
    op.drop_column("ad_recommendations", "confirmed_at")
    op.drop_column("ad_recommendations", "confirmed_by_user_id")
    op.drop_column("ad_recommendations", "confirmation_status")
