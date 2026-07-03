from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from db.base import async_session
from db.repositories import products as product_repo
from states.order import OrderFSM
from keyboards.user import templates_kb, confirm_kb, template_date_kb
from handlers.admin.monitoring import registry

router = Router()


@router.callback_query(F.data == "menu:templates")
async def show_templates(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    async with async_session() as s:
        templates = await product_repo.list_templates(s)
    if not templates:
        await cb.answer("Пока нет готовых шаблонов", show_alert=True)
        return
    await state.set_state(OrderFSM.choosing_template)
    registry.set(cb.message.chat.id, "choosing_template")
    try:
        await cb.message.delete()
    except Exception:
        pass
    msg = await cb.message.answer("⭐ Популярные заказы:", reply_markup=templates_kb(templates))
    await state.update_data(last_bot_message_id=msg.message_id)
    await cb.answer()


@router.callback_query(F.data.startswith("tpl:"), ~F.data.in_({"tpl:nodate"}))
async def choose_template(cb: CallbackQuery, state: FSMContext):
    product_id = int(cb.data.split(":")[1])
    async with async_session() as s:
        product = await product_repo.get(s, product_id)
    if not product:
        await cb.answer("Шаблон не найден", show_alert=True)
        return

    await state.update_data(_is_template=True, template_id=product.id)
    await state.set_state(OrderFSM.template_date)
    registry.set(cb.message.chat.id, "template_date")

    try:
        await cb.message.delete()
    except Exception:
        pass
    msg = await cb.message.answer(
        "📅 Введите желаемую дату (ДД.ММ.ГГГГ) или нажмите «Без даты»:",
        reply_markup=template_date_kb(),
    )
    await state.update_data(last_bot_message_id=msg.message_id)
    await cb.answer()


@router.callback_query(OrderFSM.template_date, F.data == "tpl:nodate")
async def template_no_date(cb: CallbackQuery, state: FSMContext):
    await state.update_data(desired_date=None)
    await _show_template_confirm(cb.bot, cb.message.chat.id, state)
    await cb.answer()


@router.message(OrderFSM.template_date, F.text)
async def template_input_date(message: Message, state: FSMContext):
    await state.update_data(desired_date=message.text.strip())
    await _show_template_confirm(message.bot, message.chat.id, state)


async def _show_template_confirm(bot, chat_id, state):
    data = await state.get_data()
    async with async_session() as s:
        product = await product_repo.get(s, data["template_id"])

    date_str = data.get("desired_date") or "не указана"
    text = (
        f"🧾 <b>{product.name}</b>\n\n"
        f"{product.description or ''}\n\n"
        f"📅 Дата: {date_str}\n"
        f"💰 Цена: <b>{int(product.price)}₽</b>"
    )
    await state.set_state(OrderFSM.confirming)
    registry.set(chat_id, "confirming")

    if mid := data.get("last_bot_message_id"):
        try:
            await bot.delete_message(chat_id, mid)
        except Exception:
            pass

    if product.image_url:
        msg = await bot.send_photo(chat_id, product.image_url, caption=text,
                                   parse_mode="HTML", reply_markup=confirm_kb())
    else:
        msg = await bot.send_message(chat_id, text, parse_mode="HTML",
                                     reply_markup=confirm_kb())
    await state.update_data(last_bot_message_id=msg.message_id)