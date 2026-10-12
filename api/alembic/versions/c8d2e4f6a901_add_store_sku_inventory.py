"""add store sku inventory

Revision ID: c8d2e4f6a901
Revises: b9e8c7a6d513
Create Date: 2026-06-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c8d2e4f6a901"
down_revision: str | None = "b9e8c7a6d513"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


platform_enum = sa.Enum(
    "douyin",
    "taobao",
    "tmall",
    "pinduoduo",
    "jd",
    "tiktok_shop",
    "amazon",
    "other",
    name="platform",
)


def upgrade() -> None:
    """应用本版本数据库迁移，按依赖顺序创建或调整表、字段、索引与约束。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("status", sa.Enum("active", "paused", "closed", name="storestatus"), nullable=False),
        sa.Column("external_store_id", sa.String(length=120), nullable=True),
        sa.Column("owner_name", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_stores_external_store_id"), "stores", ["external_store_id"], unique=False)
    op.create_index(op.f("ix_stores_id"), "stores", ["id"], unique=False)
    op.create_index(op.f("ix_stores_name"), "stores", ["name"], unique=False)
    op.create_index(op.f("ix_stores_platform"), "stores", ["platform"], unique=False)
    op.create_index(op.f("ix_stores_status"), "stores", ["status"], unique=False)

    op.create_table(
        "platform_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=False),
        sa.Column("external_account_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.Enum("active", "expired", "disabled", name="platformaccountstatus"), nullable=False),
        sa.Column("auth_metadata", sa.JSON(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_platform_accounts_external_account_id"), "platform_accounts", ["external_account_id"], unique=False)
    op.create_index(op.f("ix_platform_accounts_id"), "platform_accounts", ["id"], unique=False)
    op.create_index(op.f("ix_platform_accounts_platform"), "platform_accounts", ["platform"], unique=False)
    op.create_index(op.f("ix_platform_accounts_status"), "platform_accounts", ["status"], unique=False)
    op.create_index(op.f("ix_platform_accounts_store_id"), "platform_accounts", ["store_id"], unique=False)

    op.add_column("products", sa.Column("store_id", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("external_product_id", sa.String(length=120), nullable=True))
    op.add_column("products", sa.Column("platform_status", sa.String(length=50), nullable=True))
    op.create_foreign_key(op.f("fk_products_store_id_stores"), "products", "stores", ["store_id"], ["id"])
    op.create_index(op.f("ix_products_store_id"), "products", ["store_id"], unique=False)
    op.create_index(op.f("ix_products_external_product_id"), "products", ["external_product_id"], unique=False)

    op.create_table(
        "product_skus",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("sku_code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=True),
        sa.Column("cost", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", sa.Enum("active", "inactive", name="productskustatus"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_product_skus_id"), "product_skus", ["id"], unique=False)
    op.create_index(op.f("ix_product_skus_product_id"), "product_skus", ["product_id"], unique=False)
    op.create_index(op.f("ix_product_skus_sku_code"), "product_skus", ["sku_code"], unique=False)
    op.create_index(op.f("ix_product_skus_status"), "product_skus", ["status"], unique=False)

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("locked_quantity", sa.Integer(), nullable=False),
        sa.Column("warning_threshold", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["sku_id"], ["product_skus.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_items_id"), "inventory_items", ["id"], unique=False)
    op.create_index(op.f("ix_inventory_items_sku_id"), "inventory_items", ["sku_id"], unique=True)

    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("movement_type", sa.Enum("inbound", "outbound", "adjustment", "lock", "release", name="inventorymovementtype"), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("locked_delta", sa.Integer(), nullable=False),
        sa.Column("before_quantity", sa.Integer(), nullable=False),
        sa.Column("after_quantity", sa.Integer(), nullable=False),
        sa.Column("before_locked_quantity", sa.Integer(), nullable=False),
        sa.Column("after_locked_quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column("reference_type", sa.String(length=50), nullable=True),
        sa.Column("reference_id", sa.String(length=120), nullable=True),
        sa.Column("operator_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory_items.id"]),
        sa.ForeignKeyConstraint(["sku_id"], ["product_skus.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_inventory_movements_id"), "inventory_movements", ["id"], unique=False)
    op.create_index(op.f("ix_inventory_movements_inventory_item_id"), "inventory_movements", ["inventory_item_id"], unique=False)
    op.create_index(op.f("ix_inventory_movements_movement_type"), "inventory_movements", ["movement_type"], unique=False)
    op.create_index(op.f("ix_inventory_movements_sku_id"), "inventory_movements", ["sku_id"], unique=False)

    op.create_table(
        "platform_product_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=True),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("external_product_id", sa.String(length=120), nullable=False),
        sa.Column("external_sku_id", sa.String(length=120), nullable=True),
        sa.Column("listing_url", sa.String(length=1024), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["sku_id"], ["product_skus.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_platform_product_mappings_external_product_id"), "platform_product_mappings", ["external_product_id"], unique=False)
    op.create_index(op.f("ix_platform_product_mappings_external_sku_id"), "platform_product_mappings", ["external_sku_id"], unique=False)
    op.create_index(op.f("ix_platform_product_mappings_id"), "platform_product_mappings", ["id"], unique=False)
    op.create_index(op.f("ix_platform_product_mappings_platform"), "platform_product_mappings", ["platform"], unique=False)
    op.create_index(op.f("ix_platform_product_mappings_product_id"), "platform_product_mappings", ["product_id"], unique=False)
    op.create_index(op.f("ix_platform_product_mappings_sku_id"), "platform_product_mappings", ["sku_id"], unique=False)
    op.create_index(op.f("ix_platform_product_mappings_store_id"), "platform_product_mappings", ["store_id"], unique=False)


def downgrade() -> None:
    """回滚本版本数据库迁移，按反向依赖顺序恢复上一版数据库结构。"""
    # 迁移步骤按依赖顺序执行，保证升级或回滚不会留下悬空约束。
    op.drop_index(op.f("ix_platform_product_mappings_store_id"), table_name="platform_product_mappings")
    op.drop_index(op.f("ix_platform_product_mappings_sku_id"), table_name="platform_product_mappings")
    op.drop_index(op.f("ix_platform_product_mappings_product_id"), table_name="platform_product_mappings")
    op.drop_index(op.f("ix_platform_product_mappings_platform"), table_name="platform_product_mappings")
    op.drop_index(op.f("ix_platform_product_mappings_id"), table_name="platform_product_mappings")
    op.drop_index(op.f("ix_platform_product_mappings_external_sku_id"), table_name="platform_product_mappings")
    op.drop_index(op.f("ix_platform_product_mappings_external_product_id"), table_name="platform_product_mappings")
    op.drop_table("platform_product_mappings")

    op.drop_index(op.f("ix_inventory_movements_sku_id"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_movement_type"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_inventory_item_id"), table_name="inventory_movements")
    op.drop_index(op.f("ix_inventory_movements_id"), table_name="inventory_movements")
    op.drop_table("inventory_movements")

    op.drop_index(op.f("ix_inventory_items_sku_id"), table_name="inventory_items")
    op.drop_index(op.f("ix_inventory_items_id"), table_name="inventory_items")
    op.drop_table("inventory_items")

    op.drop_index(op.f("ix_product_skus_status"), table_name="product_skus")
    op.drop_index(op.f("ix_product_skus_sku_code"), table_name="product_skus")
    op.drop_index(op.f("ix_product_skus_product_id"), table_name="product_skus")
    op.drop_index(op.f("ix_product_skus_id"), table_name="product_skus")
    op.drop_table("product_skus")

    op.drop_index(op.f("ix_products_external_product_id"), table_name="products")
    op.drop_index(op.f("ix_products_store_id"), table_name="products")
    op.drop_constraint(op.f("fk_products_store_id_stores"), "products", type_="foreignkey")
    op.drop_column("products", "platform_status")
    op.drop_column("products", "external_product_id")
    op.drop_column("products", "store_id")

    op.drop_index(op.f("ix_platform_accounts_store_id"), table_name="platform_accounts")
    op.drop_index(op.f("ix_platform_accounts_status"), table_name="platform_accounts")
    op.drop_index(op.f("ix_platform_accounts_platform"), table_name="platform_accounts")
    op.drop_index(op.f("ix_platform_accounts_id"), table_name="platform_accounts")
    op.drop_index(op.f("ix_platform_accounts_external_account_id"), table_name="platform_accounts")
    op.drop_table("platform_accounts")

    op.drop_index(op.f("ix_stores_status"), table_name="stores")
    op.drop_index(op.f("ix_stores_platform"), table_name="stores")
    op.drop_index(op.f("ix_stores_name"), table_name="stores")
    op.drop_index(op.f("ix_stores_id"), table_name="stores")
    op.drop_index(op.f("ix_stores_external_store_id"), table_name="stores")
    op.drop_table("stores")
