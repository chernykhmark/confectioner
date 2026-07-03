import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import FunnelEvent, UserSession

log = logging.getLogger(__name__)


async def log_event(
    session: AsyncSession,
    *,
    user_id: int,
    event_type: str,
    step: str | None = None,
    payload: dict | None = None,
    session_id: int | None = None,
):
    if session_id is None:
        res = await session.execute(select(UserSession.id).where(UserSession.user_id == user_id))
        session_id = res.scalar_one_or_none()

    event = FunnelEvent(
        user_id=user_id,
        session_id=session_id,
        event_type=event_type,
        step=step,
        payload=payload or {},
    )
    session.add(event)
    await session.commit()
    log.info("funnel_event event_type=%s user_id=%s step=%s", event_type, user_id, step)
    return event
