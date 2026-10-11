"""rolls, orders, reservation lines, idempotency keys, outbox

Revision ID: 0001
Revises:
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rolls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sku", sa.String(8), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("total > 0", name="ck_rolls_total_positive"),
    )
    op.create_index("ix_rolls_sku", "rolls", ["sku"])

    op.create_table(
        "production_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sku", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("consumption_per_unit", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("quantity > 0", name="ck_orders_quantity_positive"),
        sa.CheckConstraint("consumption_per_unit > 0", name="ck_orders_consumption_positive"),
    )

    op.create_table(
        "reservation_lines",
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("production_orders.id"), primary_key=True),
        sa.Column("roll_id", sa.Uuid(), sa.ForeignKey("rolls.id"), primary_key=True),
        sa.Column("meters", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("meters > 0", name="ck_lines_meters_positive"),
    )
    op.create_index("ix_reservation_lines_roll_id", "reservation_lines", ["roll_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "outbox",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("idempotency_keys")
    op.drop_table("reservation_lines")
    op.drop_table("production_orders")
    op.drop_index("ix_rolls_sku", table_name="rolls")
    op.drop_table("rolls")
