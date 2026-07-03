"""
Middleware перехвата сообщений пользователя, находящегося в relay.
Если юзер в relay — его сообщение уходит админу, дальнейшая обработка
(в т.ч. активная FSM-воронка) НЕ выполняется (return без вызова handler).

Так решается конфликт relay ↔ воронка: FSM-стейт юзера не трогается,
после «Завершить диалог» воронка продолжается с того же места.
"""
import logging

from aiogram import BaseMiddleware
from aiogram.types import Message

from config import settings
from services.relay_service import relay

log = logging.getLogger(__name__)


class RelayMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: Message, data):
        uid = event.from_user.id if event.from_user else None

        # админа не перехватываем — им занимается handlers/admin/relay.py
        if uid == settings.admin_telegram_id:
            return await handler(event, data)

        admin_id = relay.admin_for_user(uid) if uid else None
        if admin_id is not None and event.text:
            try:
                await event.bot.send_message(
                    admin_id,
                    f"👤 <b>{event.from_user.full_name}</b> "
                    f"(<code>{uid}</code>):\n{event.text}",
                    parse_mode="HTML",
                )
            except Exception:
                log.exception("relay_user_to_admin_failed user_id=%s admin_id=%s", uid, admin_id)
            return  # воронка/прочие хендлеры НЕ вызываются

        return await handler(event, data)
