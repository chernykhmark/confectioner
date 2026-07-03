from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Component, ComponentType


async def list_by_type(session: AsyncSession, ctype: ComponentType):
    res = await session.execute(
        select(Component)
        .where(Component.type == ctype, Component.is_active.is_(True))
        .order_by(Component.sort_order, Component.id)
    )
    return res.scalars().all()


async def get_many(session: AsyncSession, ids: list[int]):
    if not ids:
        return []
    res = await session.execute(select(Component).where(Component.id.in_(ids)))
    return res.scalars().all()