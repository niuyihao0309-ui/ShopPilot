"""add agent platform foundation

Revision ID: f4a9c2e7d1b6
Revises: d8f3a1c7b5e2
Create Date: 2026-08-14 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f4a9c2e7d1b6"
down_revision: str | None = "d8f3a1c7b5e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


workspace_status = sa.Enum("active", "archived", name="workspacestatus")
membership_status = sa.Enum("active", "disabled", name="membershipstatus")
conversation_status = sa.Enum("active", "archived", name="agentconversationstatus")
task_status = sa.Enum(
    "queued",
    "running",
    "awaiting_approval",
    "completed",
    "failed",
    "cancelled",
    name="agenttaskstatus",
)
approval_status = sa.Enum(
    "pending", "approved", "rejected", "expired", "cancelled", name="agentapprovalstatus"
)
risk_level = sa.Enum("R0", "R1", "R2", "R3", name="agentrisklevel")
memory_status = sa.Enum("active", "revoked", "expired", name="agentmemorystatus")
outbox_status = sa.Enum("pending", "published", "failed", name="outboxeventstatus")
user_role = sa.Enum("owner", "operator", "viewer", name="userrole")


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("status", workspace_status, nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_workspaces_id"), "workspaces", ["id"], unique=False)
    op.create_index(op.f("ix_workspaces_slug"), "workspaces", ["slug"], unique=True)
    op.create_index(op.f("ix_workspaces_status"), "workspaces", ["status"], unique=False)
    op.execute(
        "INSERT INTO workspaces (id, slug, name, status, settings) "
        "VALUES (1, 'default', '默认工作区', 'active', '{}')"
    )

    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("status", membership_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_membership"),
    )
    for column in ("id", "workspace_id", "user_id", "role", "status"):
        op.create_index(
            op.f(f"ix_workspace_memberships_{column}"),
            "workspace_memberships",
            [column],
            unique=False,
        )
    op.execute(
        "INSERT INTO workspace_memberships "
        "(workspace_id, user_id, role, status, created_at, updated_at) "
        "SELECT 1, id, role, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM users"
    )

    op.add_column("stores", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_stores_workspace_id"), "stores", ["workspace_id"], unique=False)
    op.create_foreign_key(
        "fk_stores_workspace_id_workspaces", "stores", "workspaces", ["workspace_id"], ["id"]
    )
    op.execute("UPDATE stores SET workspace_id = 1 WHERE workspace_id IS NULL")
    op.alter_column("stores", "workspace_id", existing_type=sa.Integer(), nullable=False)
    op.add_column("products", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_products_workspace_id"), "products", ["workspace_id"], unique=False)
    op.create_foreign_key(
        "fk_products_workspace_id_workspaces", "products", "workspaces", ["workspace_id"], ["id"]
    )
    op.execute(
        "UPDATE products p LEFT JOIN stores s ON p.store_id = s.id "
        "SET p.workspace_id = COALESCE(s.workspace_id, 1) WHERE p.workspace_id IS NULL"
    )
    op.alter_column("products", "workspace_id", existing_type=sa.Integer(), nullable=False)

    op.create_table(
        "agent_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", conversation_status, nullable=False),
        sa.Column("context_scope", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "workspace_id", "created_by_user_id", "status"):
        op.create_index(
            op.f(f"ix_agent_conversations_{column}"),
            "agent_conversations",
            [column],
            unique=False,
        )

    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("workflow_key", sa.String(length=100), nullable=False),
        sa.Column("workflow_version", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("intent", sa.Text(), nullable=True),
        sa.Column("status", task_status, nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("context_scope", sa.JSON(), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("version_manifest", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "workspace_id", "conversation_id", "requested_by_user_id", "workflow_key", "status", "risk_level"):
        op.create_index(op.f(f"ix_agent_tasks_{column}"), "agent_tasks", [column], unique=False)

    op.create_table(
        "agent_conversation_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("author_user_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("structured_content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["agent_conversations.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "conversation_id", "workspace_id", "author_user_id", "role"):
        op.create_index(
            op.f(f"ix_agent_conversation_messages_{column}"),
            "agent_conversation_messages",
            [column],
            unique=False,
        )

    op.add_column("agent_runs", sa.Column("workspace_id", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("task_id", sa.Integer(), nullable=True))
    op.add_column("agent_runs", sa.Column("attempt", sa.Integer(), server_default="1", nullable=False))
    op.add_column("agent_runs", sa.Column("queue_name", sa.String(length=100), nullable=True))
    op.add_column("agent_runs", sa.Column("lease_owner", sa.String(length=120), nullable=True))
    op.add_column("agent_runs", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_runs", sa.Column("timeout_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_runs", sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("agent_runs", "product_id", existing_type=sa.Integer(), nullable=True)
    for column in ("workspace_id", "task_id", "lease_owner", "lease_expires_at", "timeout_at"):
        op.create_index(op.f(f"ix_agent_runs_{column}"), "agent_runs", [column], unique=False)
    op.create_foreign_key(
        "fk_agent_runs_workspace_id_workspaces",
        "agent_runs",
        "workspaces",
        ["workspace_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_agent_runs_task_id_agent_tasks", "agent_runs", "agent_tasks", ["task_id"], ["id"]
    )
    op.execute(
        "UPDATE agent_runs ar LEFT JOIN products p ON ar.product_id = p.id "
        "SET ar.workspace_id = COALESCE(p.workspace_id, 1) WHERE ar.workspace_id IS NULL"
    )
    op.alter_column("agent_runs", "workspace_id", existing_type=sa.Integer(), nullable=False)

    _create_approval_table()
    _create_memory_table()
    _create_outbox_table()


def _create_approval_table() -> None:
    """在数据库迁移中创建审批table，并保持升级与回滚的依赖顺序可控。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "agent_approvals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=False),
        sa.Column("decided_by_user_id", sa.Integer(), nullable=True),
        sa.Column("action_key", sa.String(length=120), nullable=False),
        sa.Column("risk_level", risk_level, nullable=False),
        sa.Column("status", approval_status, nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("decision_payload", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["decided_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["agent_tasks.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "action_key", name="uq_agent_approval_action"),
    )
    for column in ("id", "workspace_id", "task_id", "run_id", "decided_by_user_id", "risk_level", "status", "expires_at"):
        op.create_index(op.f(f"ix_agent_approvals_{column}"), "agent_approvals", [column], unique=False)


def _create_memory_table() -> None:
    """在数据库迁移中创建记忆table，并保持升级与回滚的依赖顺序可控。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("scope_type", sa.String(length=30), nullable=False),
        sa.Column("scope_id", sa.String(length=120), nullable=True),
        sa.Column("memory_key", sa.String(length=120), nullable=False),
        sa.Column("schema_version", sa.String(length=30), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("source_reference", sa.JSON(), nullable=False),
        sa.Column("status", memory_status, nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "workspace_id", "scope_type", "scope_id", "memory_key", "status", "expires_at"):
        op.create_index(op.f(f"ix_agent_memories_{column}"), "agent_memories", [column], unique=False)


def _create_outbox_table() -> None:
    """在数据库迁移中创建Outboxtable，并保持升级与回滚的依赖顺序可控。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("aggregate_type", sa.String(length=80), nullable=False),
        sa.Column("aggregate_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("status", outbox_status, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "workspace_id", "aggregate_type", "aggregate_id", "event_type", "idempotency_key", "status", "available_at"):
        op.create_index(
            op.f(f"ix_outbox_events_{column}"),
            "outbox_events",
            [column],
            unique=column == "idempotency_key",
        )


def downgrade() -> None:
    # 旧运行表要求 product_id 非空；先清理仅存在于新架构的店铺级运行，避免 MySQL DDL
    # 自动提交后在 ALTER 阶段失败并留下“半降级”数据库。
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    incompatible_runs = "SELECT id FROM agent_runs WHERE product_id IS NULL"
    op.execute(
        "UPDATE product_diagnoses SET agent_run_id = NULL "
        f"WHERE agent_run_id IN ({incompatible_runs})"
    )
    op.execute(
        "UPDATE creative_plans SET agent_run_id = NULL "
        f"WHERE agent_run_id IN ({incompatible_runs})"
    )
    for table in ("agent_approvals", "agent_run_operations", "agent_run_reviews", "agent_run_events"):
        op.execute(f"DELETE FROM {table} WHERE run_id IN ({incompatible_runs})")
    op.execute("DELETE FROM agent_runs WHERE product_id IS NULL")

    for table in ("outbox_events", "agent_memories", "agent_approvals"):
        op.drop_table(table)

    op.drop_constraint("fk_agent_runs_task_id_agent_tasks", "agent_runs", type_="foreignkey")
    op.drop_constraint("fk_agent_runs_workspace_id_workspaces", "agent_runs", type_="foreignkey")
    for column in ("timeout_at", "lease_expires_at", "lease_owner", "task_id", "workspace_id"):
        op.drop_index(op.f(f"ix_agent_runs_{column}"), table_name="agent_runs")
    op.alter_column("agent_runs", "product_id", existing_type=sa.Integer(), nullable=False)
    for column in (
        "cancel_requested_at",
        "timeout_at",
        "lease_expires_at",
        "lease_owner",
        "queue_name",
        "attempt",
        "task_id",
        "workspace_id",
    ):
        op.drop_column("agent_runs", column)

    op.drop_table("agent_conversation_messages")
    op.drop_table("agent_tasks")
    op.drop_table("agent_conversations")
    op.drop_constraint("fk_products_workspace_id_workspaces", "products", type_="foreignkey")
    op.drop_index(op.f("ix_products_workspace_id"), table_name="products")
    op.drop_column("products", "workspace_id")
    op.drop_constraint("fk_stores_workspace_id_workspaces", "stores", type_="foreignkey")
    op.drop_index(op.f("ix_stores_workspace_id"), table_name="stores")
    op.drop_column("stores", "workspace_id")
    op.drop_table("workspace_memberships")
    op.drop_table("workspaces")

    outbox_status.drop(op.get_bind(), checkfirst=True)
    memory_status.drop(op.get_bind(), checkfirst=True)
    risk_level.drop(op.get_bind(), checkfirst=True)
    approval_status.drop(op.get_bind(), checkfirst=True)
    task_status.drop(op.get_bind(), checkfirst=True)
    conversation_status.drop(op.get_bind(), checkfirst=True)
    membership_status.drop(op.get_bind(), checkfirst=True)
    workspace_status.drop(op.get_bind(), checkfirst=True)
