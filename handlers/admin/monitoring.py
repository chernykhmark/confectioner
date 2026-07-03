from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from config import settings
from db.base import async_session
from db.repositories import analytics as analytics_repo
from db.repositories import sessions as sessions_repo
from keyboards.admin import admin_menu
from utils.message import remember_bot_messages, send_replacing_message

router = Router()


# --- registry оставлен для обратной совместимости с funnel.py ---
class SessionRegistry:
    def __init__(self):
        self._data = {}
    def set(self, chat_id, step):
        self._data[chat_id] = (step, datetime.now(timezone.utc))
    def clear(self, chat_id):
        self._data.pop(chat_id, None)
    def all(self):
        return dict(self._data)

registry = SessionRegistry()


def _is_admin(cb: CallbackQuery) -> bool:
    return cb.from_user.id == settings.admin_telegram_id


async def _show_admin_section(
    cb: CallbackQuery,
    state: FSMContext,
    text: str,
    parse_mode: str | None = None,
):
    try:
        await cb.message.edit_text(text, parse_mode=parse_mode, reply_markup=admin_menu())
        await remember_bot_messages(state, [cb.message])
    except Exception:
        await send_replacing_message(
            cb.bot,
            cb.message.chat.id,
            state,
            text,
            admin_menu(),
            parse_mode=parse_mode,
        )


@router.callback_query(F.data == "adm:monitor")
async def show_monitoring(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()

    async with async_session() as s:
        active = await sessions_repo.get_active_sessions(s)
        if not active:
            await _show_admin_section(cb, state, "Активных сессий нет.")
            return
        now = datetime.now(timezone.utc)
        lines = ["<b>Активные сессии воронки:</b>\n"]
        for sess in active:
            user = sess.user
            uname = (f"@{user.username}" if user and user.username
                     else (user.first_name if user else "—"))
            mins = int((now - sess.updated_at).total_seconds() // 60)
            flag = " брошена" if sess.draft.get("_abandoned_notified") else ""
            lines.append(f"• {uname} — «{sess.current_step}» ({mins} мин){flag}")
    await _show_admin_section(cb, state, "\n".join(lines), parse_mode="HTML")


@router.callback_query(F.data.startswith("adm:session:"))
async def open_session(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    user_id = int(cb.data.split(":")[2])
    async with async_session() as s:
        sess = await sessions_repo.get_session(s, user_id)
    if not sess:
        await _show_admin_section(cb, state, "Сессия не найдена.")
        return
    draft = {k: v for k, v in sess.draft.items() if not k.startswith("_")}
    draft_txt = "\n".join(f"{k}: {v}" for k, v in draft.items()) or "—"
    text = (
        f"<b>Сессия пользователя #{user_id}</b>\n\n"
        f"Шаг: <b>{sess.current_step or '—'}</b>\n"
        f"Обновлена: {sess.updated_at}\n\n"
        f"<b>Черновик:</b>\n{draft_txt}"
    )
    await _show_admin_section(cb, state, text, parse_mode="HTML")


@router.callback_query(F.data == "adm:stats")
async def show_stats(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    async with async_session() as s:
        data = await analytics_repo.dashboard(s)

    today = data["today"]
    week = data["week"]
    fillings = data["popular_fillings"]
    funnel = data["funnel"]
    fillings_text = "\n".join(
        f"{idx}. {name} — {count} заказов"
        for idx, (name, count) in enumerate(fillings, start=1)
    ) or "Пока нет данных"
    text = (
        "<b>Статистика</b>\n\n"
        "<b>Сегодня:</b>\n"
        f"Заказов: {today['count']}\n"
        f"Выручка: {int(today['revenue'])} ₽\n"
        f"Средний чек: {int(today['avg'])} ₽\n\n"
        "<b>Неделя:</b>\n"
        f"Заказов: {week['count']}\n"
        f"Отмен: {week['cancelled']}\n"
        f"Закрыто: {week['closed']}\n\n"
        "<b>Популярные начинки:</b>\n"
        f"{fillings_text}\n\n"
        "<b>Воронка за 7 дней:</b>\n"
        f"Начали конструктор: {funnel['started']}\n"
        f"Дошли до даты: {funnel['date_reached']}\n"
        f"Увидели итог: {funnel['confirmation_shown']}\n"
        f"Создали заказ: {funnel['order_created']}\n"
        f"Брошенные сессии: {funnel['abandoned']}"
    )
    await _show_admin_section(cb, state, text, parse_mode="HTML")
