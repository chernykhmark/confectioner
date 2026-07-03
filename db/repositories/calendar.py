from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import CalendarDay

BUSY_STATUSES = {"busy", "blocked"}


async def get_day(session: AsyncSession, target_date: date) -> CalendarDay | None:
    res = await session.execute(select(CalendarDay).where(CalendarDay.date == target_date))
    return res.scalar_one_or_none()


async def is_available(session: AsyncSession, target_date: date) -> bool:
    day = await get_day(session, target_date)
    return day is None or day.status == "available"


async def nearest_available_dates(
    session: AsyncSession,
    start_date: date,
    *,
    limit: int = 3,
    horizon_days: int = 30,
) -> list[date]:
    dates: list[date] = []
    for offset in range(1, horizon_days + 1):
        candidate = start_date + timedelta(days=offset)
        if await is_available(session, candidate):
            dates.append(candidate)
            if len(dates) >= limit:
                break
    return dates
