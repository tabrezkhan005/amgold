"""Initial schema with pgvector.

Revision ID: 20261029_0001
Revises:
Create Date: 2026-10-29

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20261029_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("pin_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("platform", sa.String(32), nullable=False),
        sa.Column("app_version", sa.String(32)),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "enrollment_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("used_by_device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column(
            "material", sa.String(64), nullable=False, server_default=sa.text("'rolled_gold'")
        ),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("weight_g", sa.Numeric(10, 3)),
        sa.Column("description", sa.Text()),
        sa.Column("difference_note", sa.Text()),
        sa.Column("hsn_code", sa.String(32)),
        sa.Column("gst_rate", sa.Numeric(5, 2)),
        sa.Column("unit", sa.String(16), nullable=False, server_default=sa.text("'pcs'")),
        sa.Column("in_stock", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("primary_photo_id", postgresql.UUID(as_uuid=True)),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_products_code", "products", ["code"])
    op.create_index("ix_products_updated_at", "products", ["updated_at"])

    op.create_table(
        "product_photos",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("thumb_key", sa.String(512), nullable=False),
        sa.Column("embedding", Vector(768)),
        sa.Column("embedding_model", sa.String(128), nullable=False),
        sa.Column("preprocessing_version", sa.String(64), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_product_photos_product_id", "product_photos", ["product_id"])

    op.create_table(
        "product_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "similar_product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("note", sa.Text()),
        sa.UniqueConstraint("product_id", "similar_product_id", name="uq_product_links_pair"),
    )

    op.create_table(
        "price_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("old_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("new_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("top_product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id")),
        sa.Column("top_score", sa.Numeric(8, 6)),
        sa.Column("margin", sa.Numeric(8, 6)),
        sa.Column("ambiguous", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("low_confidence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("image_key", sa.String(512)),
        sa.Column("chosen_product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id")),
    )

    op.create_table(
        "bill_drafts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_by_user", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id")),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id")),
        sa.Column("customer_name", sa.String(256)),
        sa.Column("customer_phone", sa.String(32)),
        sa.Column("notes", sa.Text()),
        sa.Column("discount_amount", sa.Numeric(10, 2)),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("imported_at", sa.DateTime(timezone=True)),
        sa.Column("desk_invoice_ref", sa.String(128)),
        sa.Column("failure_reason", sa.Text()),
    )
    op.create_index("ix_bill_drafts_status", "bill_drafts", ["status"])

    op.create_table(
        "desk_clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.String(64)),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("data", postgresql.JSONB()),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("desk_clients")
    op.drop_index("ix_bill_drafts_status", table_name="bill_drafts")
    op.drop_table("bill_drafts")
    op.drop_table("scans")
    op.drop_table("price_history")
    op.drop_table("product_links")
    op.drop_index("ix_product_photos_product_id", table_name="product_photos")
    op.drop_table("product_photos")
    op.drop_index("ix_products_updated_at", table_name="products")
    op.drop_index("ix_products_code", table_name="products")
    op.drop_table("products")
    op.drop_table("enrollment_codes")
    op.drop_table("devices")
    op.drop_table("users")
