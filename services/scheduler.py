"""
APScheduler: детект брошенных сессий → уведомление админа с кнопкой «Написать».
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from db.base import async_session
from db.repositories import funnel_events, sessions as sessions_repo
from db.models import User
from sqlalchemy import select

log = logging.getLogger(__name__)


async def _check_abandoned(bot: Bot):
    try:
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
                uname = f"@{user.username}" if user.username else user.first_name or "—"

                user_kb = InlineKeyboardBuilder()
                user_kb.button(text="Продолжить", callback_data="resume:yes")
                user_kb.button(text="Начать заново", callback_data="resume:no")
                user_kb.adjust(1)
                try:
                    await bot.send_message(
                        user.telegram_id,
                        "Вы начали собирать торт, но не завершили заказ 🎂",
                        reply_markup=user_kb.as_markup(),
                    )
                except Exception:
                    log.exception("abandoned_user_reminder_failed user_id=%s telegram_id=%s", user.id, user.telegram_id)

                admin_kb = InlineKeyboardBuilder()
                admin_kb.button(text="Написать клиенту", callback_data=f"relay:start:{user.telegram_id}")
                admin_kb.button(text="Открыть сессию", callback_data=f"adm:session:{user.id}")
                admin_kb.adjust(1)
                try:
                    await bot.send_message(
                        settings.admin_telegram_id,
                        f"⚠️ <b>Брошенная сессия</b>\n\n"
                        f"Пользователь: {uname} (<code>{user.telegram_id}</code>)\n"
                        f"Шаг: <b>{sess.current_step}</b>\n"
                        f"Черновик:\n{draft_txt}",
                        parse_mode="HTML", reply_markup=admin_kb.as_markup(),
                    )
                except Exception:
                    log.exception("abandoned_admin_notification_failed user_id=%s", user.id)

                try:
                    await funnel_events.log_event(
                        s,
                        user_id=user.id,
                        session_id=sess.id,
                        event_type="funnel_abandoned",
                        step=sess.current_step,
                        payload={"telegram_id": user.telegram_id, "draft": draft},
                    )
                except Exception:
                    log.exception("funnel_abandoned_event_failed user_id=%s session_id=%s", user.id, sess.id)

                await sessions_repo.mark_notified(s, sess.user_id)
                log.info("abandoned_session_processed user_id=%s step=%s", user.id, sess.current_step)
    except Exception:
        log.exception("scheduler_abandoned_check_failed")


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
