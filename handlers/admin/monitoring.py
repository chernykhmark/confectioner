from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery
from config import settings
from db.base import async_session
from db.repositories import sessions as sessions_repo
from db.models import User

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


@router.callback_query(F.data == "adm:monitor")
async def show_monitoring(cb: CallbackQuery):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return

    async with async_session() as s:
        active = await sessions_repo.get_active_sessions(s)
        if not active:
            await cb.message.answer("📊 Активных сессий нет.")
            await cb.answer()
            return
        now = datetime.now(timezone.utc)
        lines = ["📊 <b>Активные сессии воронки:</b>\n"]
        for sess in active:
            user = await s.get(User, sess.user_id)
            uname = (f"@{user.username}" if user and user.username
                     else (user.first_name if user else "—"))
            mins = int((now - sess.updated_at).total_seconds() // 60)
            flag = " ⚠️брошена" if sess.draft.get("_abandoned_notified") else ""
            lines.append(f"• {uname} — «{sess.current_step}» ({mins} мин){flag}")
    await cb.message.answer("\n".join(lines), parse_mode="HTML")
    await cb.answer()