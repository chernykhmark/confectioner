"""
APScheduler: детект брошенных сессий → уведомление админа с кнопкой «Написать».
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from db.base import async_session
from db.repositories import sessions as sessions_repo
from db.models import User
from sqlalchemy import select

log = logging.getLogger(__name__)


async def _check_abandoned(bot: Bot):
    async with async_session() as s:
        abandoned = await sessions_repo.get_abandoned_sessions(
            s, settings.session_timeout_min
        )
        for sess in abandoned:
            user = await s.get(User, sess.user_id)
            if not user:
                continue

            draft = {k: v for k, v in sess.draft.items() if not k.startswith("_")}
            draft_txt = "\n".join(f"  {k}: {v}" for k, v in draft.items()) or "  —"

            kb = InlineKeyboardBuilder()
            kb.button(text="✍️ Написать пользователю",
                      callback_data=f"relay:start:{user.telegram_id}")

            uname = f"@{user.username}" if user.username else user.first_name or "—"
            await bot.send_message(
                settings.admin_telegram_id,
                f"⚠️ <b>Брошенная сессия</b>\n\n"
                f"Пользователь: {uname} (<code>{user.telegram_id}</code>)\n"
                f"Шаг: <b>{sess.current_step}</b>\n"
                f"Черновик:\n{draft_txt}",
                parse_mode="HTML", reply_markup=kb.as_markup(),
            )
            await sessions_repo.mark_notified(s, sess.user_id)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    sched = AsyncIOScheduler()
    sched.add_job(
        _check_abandoned, "interval",
        minutes=settings.session_check_interval_min,
        args=[bot], id="abandoned_sessions",
    )
    sched.start()
    log.info("Scheduler запущен (проверка брошенных сессий)")
    return sched