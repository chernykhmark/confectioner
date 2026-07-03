import asyncio
import logging

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest

log = logging.getLogger(__name__)


def image_input(image_url: str):
    """Return a Telegram-compatible image input: URL/file_id string or local file."""
    if image_url.startswith(("/", ".")):
        return FSInputFile(image_url)
    return image_url


def last_bot_message_ids(data: dict) -> list[int]:
    ids = list(data.get("last_bot_message_ids") or [])
    if mid := data.get("last_bot_message_id"):
        if mid not in ids:
            ids.append(mid)
    return ids


async def delete_message_ids(bot: Bot, chat_id: int, ids: list[int]):
    if not ids:
        return

    async def delete_one(mid: int):
        try:
            await bot.delete_message(chat_id, mid)
        except TelegramBadRequest as exc:
            if "message to delete not found" in str(exc):
                log.info("delete_message_not_found chat_id=%s message_id=%s", chat_id, mid)
                return
            log.exception("delete_message_bad_request chat_id=%s message_id=%s", chat_id, mid)
        except Exception:
            log.exception("delete_message_failed chat_id=%s message_id=%s", chat_id, mid)

    await asyncio.gather(*(delete_one(mid) for mid in ids))


async def delete_last_bot_messages(bot: Bot, chat_id: int, state: FSMContext):
    data = await state.get_data()
    await delete_message_ids(bot, chat_id, last_bot_message_ids(data))
    await state.update_data(last_bot_message_id=None, last_bot_message_ids=[])


async def remember_bot_messages(state: FSMContext, messages):
    ids = [msg.message_id for msg in messages if msg]
    await state.update_data(
        last_bot_message_id=ids[-1] if ids else None,
        last_bot_message_ids=ids,
    )


async def send_step(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    text: str,
    kb=None,
    parse_mode: str | None = None,
):
    old_ids = last_bot_message_ids(await state.get_data())
    try:
        msg = await bot.send_message(chat_id, text, parse_mode=parse_mode, reply_markup=kb)
    except Exception:
        log.exception("send_step_failed chat_id=%s", chat_id)
        raise
    await remember_bot_messages(state, [msg])
    asyncio.create_task(delete_message_ids(bot, chat_id, old_ids))
    return msg


async def send_photo_or_message(
    bot: Bot,
    chat_id: int,
    image_url: str | None,
    text: str,
    *,
    reply_markup=None,
    parse_mode: str | None = None,
    log_context: str = "",
):
    if image_url:
        try:
            return await bot.send_photo(
                chat_id,
                image_input(image_url),
                caption=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
        except Exception:
            log.warning(
                "send_photo_failed_fallback_to_message chat_id=%s context=%s image_url=%r",
                chat_id,
                log_context,
                image_url,
                exc_info=True,
            )

    return await bot.send_message(
        chat_id,
        text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


async def send_replacing_message(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    text: str,
    kb=None,
    parse_mode: str | None = None,
):
    await delete_last_bot_messages(bot, chat_id, state)
    try:
        msg = await bot.send_message(
            chat_id,
            text,
            parse_mode=parse_mode,
            reply_markup=kb,
        )
    except Exception:
        log.exception("send_replacing_message_failed chat_id=%s", chat_id)
        raise
    await remember_bot_messages(state, [msg])
    return msg
