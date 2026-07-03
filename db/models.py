import enum
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    BigInteger, String, Boolean, Integer, Numeric, Text, Date, DateTime,
    ForeignKey, UniqueConstraint, Index, Enum as SAEnum, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


# ---------- ENUM-типы ----------
class OrderStatus(str, enum.Enum):
    created = "created"
    confirmed = "confirmed"
    in_progress = "in_progress"
    ready = "ready"
    paid = "paid"
    closed = "closed"
    cancelled = "cancelled"


class PaymentStatus(str, enum.Enum):
    none = "none"
    advance_paid = "advance_paid"
    fully_paid = "fully_paid"


class ProductStatus(str, enum.Enum):
    active = "active"
    unavailable = "unavailable"
    archived = "archived"


class ComponentType(str, enum.Enum):
    occasion = "occasion"
    persons = "persons"
    shape = "shape"
    filling = "filling"
    decor = "decor"


# ---------- Таблицы ----------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str | None] = mapped_column(String(64))
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped["UserSession"] = relationship(back_populates="user", uselist=False)
    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    reviews: Mapped[list["Review"]] = relationship(back_populates="user")


class UserSession(Base):
    __tablename__ = "user_sessions"
    __table_args__ = (UniqueConstraint("user_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(32))
    draft: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="session")


class Component(Base):
    __tablename__ = "components"
    __table_args__ = (Index("idx_components_type", "type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[ComponentType] = mapped_column(SAEnum(ComponentType), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text)
    weight_grams: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    price_delta: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    price: Mapped[Decimal] = mapped_column(Numeric(9, 2), nullable=False)
    image_url: Mapped[str | None] = mapped_column(Text)
    is_template: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[ProductStatus] = mapped_column(
        SAEnum(ProductStatus), nullable=False, default=ProductStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    components: Mapped[list["ProductComponent"]] = relationship(back_populates="product")
    orders: Mapped[list["Order"]] = relationship(back_populates="product")


class ProductComponent(Base):
    __tablename__ = "product_components"
    __table_args__ = (
        UniqueConstraint("product_id", "component_id"),
        Index("idx_prodcomp_product", "product_id"),
        Index("idx_prodcomp_component", "component_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    component_id: Mapped[int] = mapped_column(ForeignKey("components.id"), nullable=False)

    product: Mapped["Product"] = relationship(back_populates="components")
    component: Mapped["Component"] = relationship()


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("idx_orders_status", "status"),
        Index("idx_orders_user", "user_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    description: Mapped[str | None] = mapped_column(String(255))
    total_price: Mapped[Decimal | None] = mapped_column(Numeric(9, 2))
    desired_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus), nullable=False, default=OrderStatus.created
    )
    result_image_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="orders")
    product: Mapped["Product"] = relationship(back_populates="orders")
    components: Mapped[list["OrderComponent"]] = relationship(back_populates="order")
    payment: Mapped["Payment"] = relationship(back_populates="order", uselist=False)
    reviews: Mapped[list["Review"]] = relationship(back_populates="order")


class OrderComponent(Base):
    __tablename__ = "order_components"
    __table_args__ = (
        UniqueConstraint("order_id", "component_id"),
        Index("idx_ordercomp_order", "order_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    component_id: Mapped[int] = mapped_column(ForeignKey("components.id"), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="components")
    component: Mapped["Component"] = relationship()


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    advance_amount: Mapped[Decimal | None] = mapped_column(Numeric(9, 2))
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(9, 2))
    status: Mapped[PaymentStatus] = mapped_column(
        SAEnum(PaymentStatus), nullable=False, default=PaymentStatus.none
    )
    advance_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fully_paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    receipt_url: Mapped[str | None] = mapped_column(Text)
    status_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    order: Mapped["Order"] = relationship(back_populates="payment")


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    text: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    order: Mapped["Order"] = relationship(back_populates="reviews")
    user: Mapped["User"] = relationship(back_populates="reviews")


class ComponentConflict(Base):
    __tablename__ = "component_conflicts"
    __table_args__ = (UniqueConstraint("a_id", "b_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    a_id: Mapped[int] = mapped_column(ForeignKey("components.id"), nullable=False)
    b_id: Mapped[int] = mapped_column(ForeignKey("components.id"), nullable=False)