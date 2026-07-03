from datetime import datetime, timezone, date, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Order, OrderComponent, OrderStatus

OPEN_STATUSES = [
    OrderStatus.created,
    OrderStatus.confirmed,
    OrderStatus.in_progress,
    OrderStatus.ready,
    OrderStatus.paid,
]
CLOSED_STATUSES = [OrderStatus.closed, OrderStatus.cancelled]


async def create_order(session: AsyncSession, *, user_id: int, product_id: int | None,
                       description: str | None, total_price, desired_date,
                       result_image_url: str | None, component_ids: list[int],
                       delivery_type: str | None = None,
                       delivery_address: str | None = None,
                       delivery_comment: str | None = None,
                       delivery_time_from: str | None = None,
                       delivery_time_to: str | None = None,
                       customer_comment: str | None = None) -> Order:
    order = Order(
        user_id=user_id,
        product_id=product_id,
        description=description[:255] if description else None,
        total_price=total_price,
        desired_date=desired_date,
        delivery_type=delivery_type,
        delivery_address=delivery_address,
        delivery_comment=delivery_comment,
        delivery_time_from=delivery_time_from,
        delivery_time_to=delivery_time_to,
        customer_comment=customer_comment,
        result_image_url=result_image_url,
        status=OrderStatus.created,
    )
    session.add(order)
    await session.flush()
    for cid in component_ids:
        session.add(OrderComponent(order_id=order.id, component_id=cid))
    await session.commit()
    await session.refresh(order)
    return order


async def get_with_relations(session: AsyncSession, order_id: int) -> Order | None:
    res = await session.execute(
        select(Order)
        .options(
            selectinload(Order.user),
            selectinload(Order.product),
            selectinload(Order.components).selectinload(OrderComponent.component),
        )
        .where(Order.id == order_id)
    )
    return res.scalar_one_or_none()


async def list_by_user(session: AsyncSession, user_id: int):
    res = await session.execute(
        select(Order)
        .options(
            selectinload(Order.product),
            selectinload(Order.components).selectinload(OrderComponent.component),
        )
        .where(Order.user_id == user_id)
        .order_by(Order.id.desc())
    )
    return res.scalars().all()


async def list_by_desired_date(session: AsyncSession, target_date: date):
    res = await session.execute(
        select(Order)
        .options(selectinload(Order.user))
        .where(Order.desired_date == target_date)
        .where(Order.status.not_in([OrderStatus.closed, OrderStatus.cancelled]))
        .order_by(Order.id)
    )
    return res.scalars().all()


async def update_order_fields(session: AsyncSession, order_id: int, **values) -> Order | None:
    order = await session.get(Order, order_id)
    if not order:
        return None
    for key, value in values.items():
        setattr(order, key, value)
    await session.commit()
    await session.refresh(order)
    return order


async def list_by_statuses(session: AsyncSession, statuses):
    res = await session.execute(
        select(Order).where(Order.status.in_(statuses)).order_by(Order.id.desc())
    )
    return res.scalars().all()


async def update_status(session: AsyncSession, order_id: int, new_status: OrderStatus) -> Order | None:
    order = await session.get(Order, order_id)
    if not order:
        return None
    order.status = new_status
    order.status_changed_at = datetime.now(timezone.utc)
    if new_status in CLOSED_STATUSES:
        order.closed_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(order)
    return order
