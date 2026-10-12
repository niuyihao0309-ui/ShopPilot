"""add agent runtime tables

Revision ID: d8f3a1c7b5e2
Revises: 6c5b4a3d2e1f
Create Date: 2026-08-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "d8f3a1c7b5e2"
down_revision: str | None = "6c5b4a3d2e1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


agent_run_status = sa.Enum(
    "queued",
    "running",
    "awaiting_review",
    "resume_queued",
    "completed",
    "rejected",
    "failed",
    "cancelled",
    name="agentrunstatus",
)
agent_review_decision = sa.Enum(
    "approve",
    "edit_and_approve",
    "reject",
    name="agentreviewdecision",
)


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("workflow_key", sa.String(length=100), nullable=False),
        sa.Column("workflow_version", sa.String(length=50), nullable=False),
        sa.Column("status", agent_run_status, nullable=False),
        sa.Column("current_agent", sa.String(length=100), nullable=True),
        sa.Column("revision_count", sa.Integer(), nullable=False),
        sa.Column("max_revisions", sa.Integer(), nullable=False),
        sa.Column("budget", sa.JSON(), nullable=False),
        sa.Column("usage", sa.JSON(), nullable=False),
        sa.Column("version_manifest", sa.JSON(), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("draft_output", sa.JSON(), nullable=False),
        sa.Column("quality_report", sa.JSON(), nullable=False),
        sa.Column("final_output", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_id"), "agent_runs", ["id"], unique=False)
    op.create_index(op.f("ix_agent_runs_product_id"), "agent_runs", ["product_id"], unique=False)
    op.create_index(
        op.f("ix_agent_runs_requested_by_user_id"),
        "agent_runs",
        ["requested_by_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"], unique=False)
    op.create_index(op.f("ix_agent_runs_thread_id"), "agent_runs", ["thread_id"], unique=True)

    op.create_table(
        "agent_run_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=True),
        sa.Column("operation_name", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("output_snapshot", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("span_id", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_run_events_agent_name"), "agent_run_events", ["agent_name"], unique=False)
    op.create_index(op.f("ix_agent_run_events_event_type"), "agent_run_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_agent_run_events_id"), "agent_run_events", ["id"], unique=False)
    op.create_index(op.f("ix_agent_run_events_run_id"), "agent_run_events", ["run_id"], unique=False)
    op.create_index(op.f("ix_agent_run_events_status"), "agent_run_events", ["status"], unique=False)
    op.create_index(op.f("ix_agent_run_events_trace_id"), "agent_run_events", ["trace_id"], unique=False)

    op.create_table(
        "agent_run_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=False),
        sa.Column("decision", agent_review_decision, nullable=False),
        sa.Column("edited_output", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_run_reviews_decision"), "agent_run_reviews", ["decision"], unique=False)
    op.create_index(op.f("ix_agent_run_reviews_id"), "agent_run_reviews", ["id"], unique=False)
    op.create_index(
        op.f("ix_agent_run_reviews_reviewed_by_user_id"),
        "agent_run_reviews",
        ["reviewed_by_user_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_run_reviews_run_id"), "agent_run_reviews", ["run_id"], unique=True)

    op.create_table(
        "agent_run_operations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("operation_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "operation_key", name="uq_agent_run_operation"),
    )
    op.create_index(op.f("ix_agent_run_operations_id"), "agent_run_operations", ["id"], unique=False)
    op.create_index(op.f("ix_agent_run_operations_run_id"), "agent_run_operations", ["run_id"], unique=False)
    op.create_index(op.f("ix_agent_run_operations_status"), "agent_run_operations", ["status"], unique=False)

    op.add_column("product_diagnoses", sa.Column("agent_run_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_product_diagnoses_agent_run_id"),
        "product_diagnoses",
        ["agent_run_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_product_diagnoses_agent_run_id_agent_runs",
        "product_diagnoses",
        "agent_runs",
        ["agent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("creative_plans", sa.Column("agent_run_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_creative_plans_agent_run_id"),
        "creative_plans",
        ["agent_run_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_creative_plans_agent_run_id_agent_runs",
        "creative_plans",
        "agent_runs",
        ["agent_run_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.drop_constraint(
        "fk_creative_plans_agent_run_id_agent_runs",
        "creative_plans",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_creative_plans_agent_run_id"), table_name="creative_plans")
    op.drop_column("creative_plans", "agent_run_id")
    op.drop_constraint(
        "fk_product_diagnoses_agent_run_id_agent_runs",
        "product_diagnoses",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_product_diagnoses_agent_run_id"), table_name="product_diagnoses")
    op.drop_column("product_diagnoses", "agent_run_id")
    op.drop_index(op.f("ix_agent_run_operations_status"), table_name="agent_run_operations")
    op.drop_index(op.f("ix_agent_run_operations_run_id"), table_name="agent_run_operations")
    op.drop_index(op.f("ix_agent_run_operations_id"), table_name="agent_run_operations")
    op.drop_table("agent_run_operations")
    op.drop_index(op.f("ix_agent_run_reviews_run_id"), table_name="agent_run_reviews")
    op.drop_index(op.f("ix_agent_run_reviews_reviewed_by_user_id"), table_name="agent_run_reviews")
    op.drop_index(op.f("ix_agent_run_reviews_id"), table_name="agent_run_reviews")
    op.drop_index(op.f("ix_agent_run_reviews_decision"), table_name="agent_run_reviews")
    op.drop_table("agent_run_reviews")
    op.drop_index(op.f("ix_agent_run_events_trace_id"), table_name="agent_run_events")
    op.drop_index(op.f("ix_agent_run_events_status"), table_name="agent_run_events")
    op.drop_index(op.f("ix_agent_run_events_run_id"), table_name="agent_run_events")
    op.drop_index(op.f("ix_agent_run_events_id"), table_name="agent_run_events")
    op.drop_index(op.f("ix_agent_run_events_event_type"), table_name="agent_run_events")
    op.drop_index(op.f("ix_agent_run_events_agent_name"), table_name="agent_run_events")
    op.drop_table("agent_run_events")
    op.drop_index(op.f("ix_agent_runs_thread_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_requested_by_user_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_product_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
    agent_review_decision.drop(op.get_bind(), checkfirst=True)
    agent_run_status.drop(op.get_bind(), checkfirst=True)
