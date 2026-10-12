"""add competitor monitors

Revision ID: f0a6d8c3b912
Revises: e8a4f2c9b713
Create Date: 2026-06-01 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f0a6d8c3b912"
down_revision: str | None = "e8a4f2c9b713"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "competitor_monitors",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_competitor_monitors_competitor_id"), "competitor_monitors", ["competitor_id"], unique=False)
    op.create_index(op.f("ix_competitor_monitors_id"), "competitor_monitors", ["id"], unique=False)
    op.create_index(op.f("ix_competitor_monitors_next_check_at"), "competitor_monitors", ["next_check_at"], unique=False)
    op.create_index(op.f("ix_competitor_monitors_product_id"), "competitor_monitors", ["product_id"], unique=False)
    op.create_index(op.f("ix_competitor_monitors_status"), "competitor_monitors", ["status"], unique=False)

    op.create_table(
        "competitor_monitor_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("monitor_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("competitor_id", sa.Integer(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("sales_hint", sa.String(length=255), nullable=True),
        sa.Column("main_image", sa.String(length=1024), nullable=True),
        sa.Column("selling_points", sa.JSON(), nullable=True),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["competitor_id"], ["competitors.id"]),
        sa.ForeignKeyConstraint(["monitor_id"], ["competitor_monitors.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_competitor_monitor_snapshots_competitor_id"), "competitor_monitor_snapshots", ["competitor_id"], unique=False)
    op.create_index(op.f("ix_competitor_monitor_snapshots_id"), "competitor_monitor_snapshots", ["id"], unique=False)
    op.create_index(op.f("ix_competitor_monitor_snapshots_monitor_id"), "competitor_monitor_snapshots", ["monitor_id"], unique=False)
    op.create_index(op.f("ix_competitor_monitor_snapshots_product_id"), "competitor_monitor_snapshots", ["product_id"], unique=False)
    op.create_index(op.f("ix_competitor_monitor_snapshots_status"), "competitor_monitor_snapshots", ["status"], unique=False)
    op.create_foreign_key(
        op.f("fk_competitor_monitors_last_snapshot_id_competitor_monitor_snapshots"),
        "competitor_monitors",
        "competitor_monitor_snapshots",
        ["last_snapshot_id"],
        ["id"],
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.drop_constraint(
        op.f("fk_competitor_monitors_last_snapshot_id_competitor_monitor_snapshots"),
        "competitor_monitors",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_competitor_monitors_status"), table_name="competitor_monitors")
    op.drop_index(op.f("ix_competitor_monitors_product_id"), table_name="competitor_monitors")
    op.drop_index(op.f("ix_competitor_monitors_next_check_at"), table_name="competitor_monitors")
    op.drop_index(op.f("ix_competitor_monitors_id"), table_name="competitor_monitors")
    op.drop_index(op.f("ix_competitor_monitors_competitor_id"), table_name="competitor_monitors")
    op.drop_table("competitor_monitors")
    op.drop_index(op.f("ix_competitor_monitor_snapshots_status"), table_name="competitor_monitor_snapshots")
    op.drop_index(op.f("ix_competitor_monitor_snapshots_product_id"), table_name="competitor_monitor_snapshots")
    op.drop_index(op.f("ix_competitor_monitor_snapshots_monitor_id"), table_name="competitor_monitor_snapshots")
    op.drop_index(op.f("ix_competitor_monitor_snapshots_id"), table_name="competitor_monitor_snapshots")
    op.drop_index(op.f("ix_competitor_monitor_snapshots_competitor_id"), table_name="competitor_monitor_snapshots")
    op.drop_table("competitor_monitor_snapshots")
