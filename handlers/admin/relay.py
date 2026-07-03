"""
Relay-хендлеры со стороны админа.
- «Написать пользователю» (из уведомления о брошенной сессии) → старт relay.
- Любое текстовое сообщение админа в активном relay → пересылается юзеру.
- «Завершить диалог» → стоп relay.
"""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from services.relay_service import relay

router = Router()
log = logging.getLogger(__name__)


def _is_admin(uid: int) -> bool:
    return uid == settings.admin_telegram_id


def _end_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🚪 Завершить диалог", callback_data="relay:end")
    return kb.as_markup()


@router.callback_query(F.data.startswith("relay:start:"))
async def relay_start(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    user_tg = int(cb.data.split(":")[2])
    relay.start(cb.from_user.id, user_tg)
    await cb.message.answer(
        f"💬 Диалог с пользователем <code>{user_tg}</code> начат.\n"
        "Все ваши сообщения пересылаются ему. Для выхода — кнопка ниже.",
        parse_mode="HTML", reply_markup=_end_kb(),
    )
    try:
        await cb.bot.send_message(
            user_tg, "👩‍🍳 Здравствуйте! С вами на связи кондитер. "
                     "Напишите, если остались вопросы по заказу 🎂"
        )
    except Exception:
        log.exception("relay_start_user_message_failed user_tg=%s", user_tg)
    await cb.answer()


@router.callback_query(F.data == "relay:end")
async def relay_end(cb: CallbackQuery):
    if not _is_admin(cb.from_user.id):
        await cb.answer("Нет доступа", show_alert=True)
        return
    user_tg = relay.stop_by_admin(cb.from_user.id)
    if user_tg:
        try:
            await cb.bot.send_message(user_tg, "✅ Диалог с кондитером завершён.")
        except Exception:
            log.exception("relay_end_user_message_failed user_tg=%s", user_tg)
    await cb.message.answer("🚪 Диалог завершён.")
    await cb.answer()


# Сообщения админа в активном relay. Высокий приоритет — регистрируется рано.
@router.message(F.text, lambda m: relay.user_for_admin(m.from_user.id) is not None)
async def admin_relay_message(message: Message):
    user_tg = relay.user_for_admin(message.from_user.id)
    try:
        await message.bot.send_message(user_tg, message.text)
    except Exception:
        log.exception("relay_admin_to_user_failed admin_id=%s user_tg=%s", message.from_user.id, user_tg)
