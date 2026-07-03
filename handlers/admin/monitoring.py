"""
Мониторинг воронки (A2) на MVP.

Обоснование in-memory реестра:
aiogram MemoryStorage не даёт публичного API для перечисления всех активных
FSM-контекстов (данные лежат в приватной структуре по ключам chat/user).
Итерировать её напрямую хрупко. Поэтому ведём лёгкий in-memory реестр
{chat_id: (step, updated_at)} — обновляется при каждом шаге воронки.
На Stage 3 это заменит персист user_sessions в БД.
"""
from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery
from config import settings

router = Router()


class SessionRegistry:
    def __init__(self):
        self._data: dict[int, tuple[str, datetime]] = {}

    def set(self, chat_id: int, step: str):
        self._data[chat_id] = (step, datetime.now(timezone.utc))

    def clear(self, chat_id: int):
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
    sessions = registry.all()
    if not sessions:
        await cb.message.answer("📊 Активных сессий нет.")
        await cb.answer()
        return
    now = datetime.now(timezone.utc)
    lines = ["📊 <b>Активные сессии воронки:</b>\n"]
    for chat_id, (step, ts) in sessions.items():
        mins = int((now - ts).total_seconds() // 60)
        lines.append(f"• chat {chat_id} — шаг «{step}» ({mins} мин назад)")
    await cb.message.answer("\n".join(lines), parse_mode="HTML")
    await cb.answer()