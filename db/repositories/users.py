from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import User
from config import settings

from sqlalchemy import select
from db.models import User



from sqlalchemy import select
from db.models import User

async def get_by_username(session, username: str):
    res = await session.execute(select(User).where(User.username == username))
    return res.scalar_one_or_none()

async def get_by_telegram_id(session, telegram_id: int):
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return res.scalar_one_or_none()

async def get_or_create_user(session: AsyncSession, tg_user) -> User:
    res = await session.execute(select(User).where(User.telegram_id == tg_user.id))
    user = res.scalar_one_or_none()
    if user:
        return user
    user = User(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
        is_admin=(tg_user.id == settings.admin_telegram_id),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return res.scalar_one_or_none()