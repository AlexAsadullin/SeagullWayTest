from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map = {  # noqa: RUF012
        Decimal: Numeric(12, 2),
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
    }


class RollRow(Base):
    __tablename__ = "rolls"
    __table_args__ = (CheckConstraint("total > 0", name="ck_rolls_total_positive"),)

    id: Mapped[UUID] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(8), index=True)
    total: Mapped[Decimal]
    version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # The domain bumps version itself, SQLAlchemy only adds "where version = old" to updates.
    __mapper_args__ = {"version_id_col": version, "version_id_generator": False}  # noqa: RUF012


class OrderRow(Base):
    __tablename__ = "production_orders"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_orders_quantity_positive"),
        CheckConstraint("consumption_per_unit > 0", name="ck_orders_consumption_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[int]
    consumption_per_unit: Mapped[Decimal]
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    lines: Mapped[list["ReservationLineRow"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class ReservationLineRow(Base):
    __tablename__ = "reservation_lines"
    __table_args__ = (CheckConstraint("meters > 0", name="ck_lines_meters_positive"),)

    order_id: Mapped[UUID] = mapped_column(ForeignKey("production_orders.id"), primary_key=True)
    roll_id: Mapped[UUID] = mapped_column(ForeignKey("rolls.id"), primary_key=True, index=True)
    meters: Mapped[Decimal]


class IdempotencyKeyRow(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int | None]
    response_body: Mapped[dict[str, Any] | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class OutboxRow(Base):
    __tablename__ = "outbox"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]]
    occurred_at: Mapped[datetime]
    published_at: Mapped[datetime | None]
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
