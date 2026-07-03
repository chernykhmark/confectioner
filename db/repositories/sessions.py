from datetime import datetime, timezone, timedelta

from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserSession


async def upsert_session(s: AsyncSession, user_id: int, current_step: str, draft: dict):
    """Создать/обновить сессию воронки. updated_at обновляется."""
    now = datetime.now(timezone.utc)
    stmt = insert(UserSession).values(
        user_id=user_id, current_step=current_step, draft=draft, updated_at=now,
    ).on_conflict_do_update(
        index_elements=[UserSession.user_id],
        set_={"current_step": current_step, "draft": draft, "updated_at": now},
    )
    await s.execute(stmt)
    await s.commit()


async def get_session(s: AsyncSession, user_id: int) -> UserSession | None:
    res = await s.execute(select(UserSession).where(UserSession.user_id == user_id))
    return res.scalar_one_or_none()


async def delete_session(s: AsyncSession, user_id: int):
    await s.execute(delete(UserSession).where(UserSession.user_id == user_id))
    await s.commit()


async def get_active_sessions(s: AsyncSession) -> list[UserSession]:
    """Все сессии с непустым draft (для мониторинга A2)."""
    res = await s.execute(select(UserSession))
    return [x for x in res.scalars().all() if x.draft]


async def get_abandoned_sessions(s: AsyncSession, timeout_min: int) -> list[UserSession]:
    """Сессии не обновлявшиеся дольше timeout и ещё не помеченные как уведомлённые."""
    threshold = datetime.now(timezone.utc) - timedelta(minutes=timeout_min)
    res = await s.execute(select(UserSession).where(UserSession.updated_at < threshold))
    out = []
    for sess in res.scalars().all():
        if sess.draft and not sess.draft.get("_abandoned_notified"):
            out.append(sess)
    return out


async def mark_notified(s: AsyncSession, user_id: int):
    """Пометить dra.._abandoned_notified, чтобы не слать повторно."""
    sess = await get_session(s, user_id)
    if sess:
        draft = dict(sess.draft)
        draft["_abandoned_notified"] = True
        sess.draft = draft
        await s.commit()