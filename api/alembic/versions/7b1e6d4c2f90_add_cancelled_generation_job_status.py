"""add cancelled generation job status

Revision ID: 7b1e6d4c2f90
Revises: 4f2d8c9b1a70
Create Date: 2026-06-02 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = "7b1e6d4c2f90"
down_revision: str | None = "4f2d8c9b1a70"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # MySQL 的 ENUM 需要显式扩展；SQLite 测试库由 SQLAlchemy metadata 直接创建，不依赖这条 DDL。
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    op.execute("ALTER TABLE generation_jobs MODIFY status ENUM('pending','running','succeeded','failed','cancelled') NOT NULL")
    op.execute("ALTER TABLE generation_job_events MODIFY status ENUM('pending','running','succeeded','failed','cancelled') NULL")


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    op.execute("ALTER TABLE generation_jobs MODIFY status ENUM('pending','running','succeeded','failed') NOT NULL")
    op.execute("ALTER TABLE generation_job_events MODIFY status ENUM('pending','running','succeeded','failed') NULL")
