from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Component, ComponentType, FunnelEvent, Order, OrderComponent, OrderStatus


async def orders_summary(session: AsyncSession, since: datetime):
    res = await session.execute(
        select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_price), 0),
            func.count(Order.id).filter(Order.status == OrderStatus.cancelled),
            func.count(Order.id).filter(Order.status == OrderStatus.closed),
        ).where(Order.created_at >= since)
    )
    count, revenue, cancelled, closed = res.one()
    count = int(count or 0)
    revenue = Decimal(revenue or 0)
    avg = revenue / count if count else Decimal(0)
    return {
        "count": count,
        "revenue": revenue,
        "avg": avg,
        "cancelled": int(cancelled or 0),
        "closed": int(closed or 0),
    }


async def status_counts(session: AsyncSession):
    res = await session.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    )
    raw = {status: int(count) for status, count in res.all()}
    active = sum(
        raw.get(s, 0) for s in (
            OrderStatus.created, OrderStatus.confirmed,
            OrderStatus.in_progress, OrderStatus.ready, OrderStatus.paid,
        )
    )
    return {
        "active": active,
        "closed": raw.get(OrderStatus.closed, 0),
        "cancelled": raw.get(OrderStatus.cancelled, 0),
    }


async def dashboard(session: AsyncSession):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    return {
        "today": await orders_summary(session, today_start),
        "month": await orders_summary(session, month_start),
        "week": await orders_summary(session, week_start),
        "statuses": await status_counts(session),
        "popular_fillings": await popular_components(session, ComponentType.filling, week_start),
        "funnel": await funnel_summary(session, week_start),
    }


async def popular_components(
    session: AsyncSession,
    component_type: ComponentType,
    since: datetime,
    limit: int = 5,
):
    res = await session.execute(
        select(Component.name, func.count(OrderComponent.id))
        .join(OrderComponent, OrderComponent.component_id == Component.id)
        .join(Order, Order.id == OrderComponent.order_id)
        .where(Component.type == component_type)
        .where(Order.created_at >= since)
        .group_by(Component.name)
        .order_by(func.count(OrderComponent.id).desc(), Component.name)
        .limit(limit)
    )
    return [(name, int(count)) for name, count in res.all()]


async def funnel_summary(session: AsyncSession, since: datetime):
    res = await session.execute(
        select(FunnelEvent.event_type, func.count(FunnelEvent.id))
        .where(FunnelEvent.created_at >= since)
        .group_by(FunnelEvent.event_type)
    )
    raw = {event_type: int(count) for event_type, count in res.all()}
    return {
        "started": raw.get("funnel_started", 0),
        "date_reached": raw.get("date_reached", 0),
        "confirmation_shown": raw.get("confirmation_shown", 0),
        "order_created": raw.get("order_created", 0),
        "abandoned": raw.get("funnel_abandoned", 0),
    }
