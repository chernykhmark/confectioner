from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from db.base import async_session
from db.repositories import products as product_repo
from states.order import OrderFSM
from keyboards.user import date_wishes_kb, templates_kb, template_card_kb
from handlers.admin.monitoring import registry
from utils.message import (
    delete_message_ids,
    image_input,
    last_bot_message_ids,
    remember_bot_messages,
    send_step,
)
import asyncio

router = Router()


def _template_text(product) -> str:
    return (
        f"🎂 <b>{product.name}</b>\n"
        f"{product.description or ''}\n\n"
        f"💰 <b>{int(product.price)}₽</b>"
    )


@router.callback_query(F.data == "menu:templates")
async def show_templates(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    async with async_session() as s:
        templates = await product_repo.list_templates(s)
    if not templates:
        await cb.answer("Пока нет готовых шаблонов", show_alert=True)
        return
    await cb.answer()
    await state.set_state(OrderFSM.choosing_template)
    registry.set(cb.message.chat.id, "choosing_template")
    try:
        await cb.message.delete()
    except Exception:
        pass

    if any(p.image_url for p in templates):
        messages = []
        title = await cb.message.answer("⭐ Популярные заказы:")
        messages.append(title)
        for product in templates:
            caption = _template_text(product)
            if product.image_url:
                try:
                    msg = await cb.message.answer_photo(
                        image_input(product.image_url),
                        caption=caption,
                        parse_mode="HTML",
                        reply_markup=template_card_kb(product.id),
                    )
                except Exception:
                    msg = await cb.message.answer(
                        caption,
                        parse_mode="HTML",
                        reply_markup=template_card_kb(product.id),
                    )
            else:
                msg = await cb.message.answer(
                    caption,
                    parse_mode="HTML",
                    reply_markup=template_card_kb(product.id),
                )
            messages.append(msg)
        await remember_bot_messages(state, messages)
    else:
        msg = await cb.message.answer("⭐ Популярные заказы:", reply_markup=templates_kb(templates))
        await remember_bot_messages(state, [msg])


@router.callback_query(F.data.startswith("tpl:"), ~F.data.in_({"tpl:nodate"}))
async def choose_template(cb: CallbackQuery, state: FSMContext):
    product_id = int(cb.data.split(":")[1])
    async with async_session() as s:
        product = await product_repo.get(s, product_id)
    if not product:
        await cb.answer("Шаблон не найден", show_alert=True)
        return
    await cb.answer()

    await state.update_data(_is_template=True, template_id=product.id)
    await state.set_state(OrderFSM.template_date)
    registry.set(cb.message.chat.id, "template_date")

    await send_step(
        cb.bot,
        cb.message.chat.id,
        state,
        "Выберите дату доставки/самовывоза.\n\nВведите дату в формате ДД.ММ.ГГГГ:",
        date_wishes_kb(),
    )


@router.callback_query(OrderFSM.template_date, F.data == "tpl:nodate")
async def template_no_date(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.update_data(desired_date=None)
    from handlers.user.checkout import ask_delivery_type
    await ask_delivery_type(cb.bot, cb.message.chat.id, state)


@router.message(OrderFSM.template_date, F.text)
async def template_input_date(message: Message, state: FSMContext):
    from handlers.user.checkout import process_date_text
    await process_date_text(message, state)


async def _show_template_confirm(bot, chat_id, state):
    from handlers.user.checkout import show_confirm
    await show_confirm(bot, chat_id, state)
