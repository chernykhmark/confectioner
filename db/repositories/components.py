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


async def get(session: AsyncSession, component_id: int) -> Component | None:
    return await session.get(Component, component_id)


async def list_all(session: AsyncSession):
    res = await session.execute(select(Component).order_by(Component.type, Component.sort_order, Component.id))
    return res.scalars().all()


async def update_component(session: AsyncSession, component_id: int, **values) -> Component | None:
    component = await session.get(Component, component_id)
    if not component:
        return None
    for key, value in values.items():
        setattr(component, key, value)
    await session.commit()
    await session.refresh(component)
    return component
