from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from db.base import async_session
from db.models import OrderStatus
from db.repositories import calendar as calendar_repo, orders as order_repo, users as users_repo
from keyboards.admin import STATUS_LABEL
from keyboards.user import account_kb, repeat_order_kb, user_order_kb, user_orders_kb
from services import funnel_service
from services.relay_service import relay
from states.order import OrderFSM
from utils.message import image_input, remember_bot_messages, send_step
from . import checkout

router = Router()

TIMELINE = [
    (OrderStatus.created, "Заявка создана"),
    (OrderStatus.confirmed, "Заказ подтверждён"),
    (OrderStatus.in_progress, "Готовим"),
    (OrderStatus.ready, "Готов к выдаче"),
    (OrderStatus.paid, "Оплачен"),
    (OrderStatus.closed, "Закрыт"),
]

EDITABLE_STATUSES = {OrderStatus.created, OrderStatus.confirmed}


def _status_timeline(status: OrderStatus) -> str:
    if status == OrderStatus.cancelled:
        return "✅ Заявка создана\n❌ Заказ отменён"
    try:
        current_index = [item[0] for item in TIMELINE].index(status)
    except ValueError:
        current_index = 0
    lines = []
    for idx, (_, label) in enumerate(TIMELINE):
        mark = "✅" if idx < current_index else "🔄" if idx == current_index else "⬜"
        lines.append(f"{mark} {label}")
    return "\n".join(lines)


def _components_text(order) -> str:
    if order.components:
        return "\n".join(f"- {item.component.name}" for item in order.components)
    if order.product:
        return f"- {order.product.name}"
    return order.description or "—"


async def _weight_text(order) -> str | None:
    ids = [item.component_id for item in order.components]
    async with async_session() as session:
        weight = await funnel_service.calculate_weight_kg(session, ids)
    return f"{weight} кг" if weight else None


@router.callback_query(F.data == "menu:account")
async def show_account(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    await state.set_state(OrderFSM.account)
    await send_step(cb.bot, cb.message.chat.id, state, "Личный кабинет", account_kb())


@router.callback_query(F.data == "acct:orders")
async def show_orders(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    async with async_session() as session:
        user = await users_repo.get_or_create_user(session, cb.from_user)
        orders = await order_repo.list_by_user(session, user.id)
    if not orders:
        await send_step(cb.bot, cb.message.chat.id, state, "У вас пока нет заказов.", account_kb())
        return
    await send_step(cb.bot, cb.message.chat.id, state, "Мои заказы", user_orders_kb(orders))


@router.callback_query(F.data.startswith("acct:order:"))
async def show_order(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    order_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        user = await users_repo.get_or_create_user(session, cb.from_user)
        order = await order_repo.get_with_relations(session, order_id)
    if not order or order.user_id != user.id:
        await send_step(cb.bot, cb.message.chat.id, state, "Заказ не найден.", account_kb())
        return

    weight = await _weight_text(order)
    time_text = (
        f"{order.delivery_time_from}-{order.delivery_time_to}"
        if order.delivery_time_from and order.delivery_time_to
        else "не указано"
    )
    delivery_label = "Доставка" if order.delivery_type == "delivery" else "Самовывоз" if order.delivery_type == "pickup" else "не указан"
    text = (
        f"<b>Ваш заказ #{order.id}</b>\n\n"
        f"{_status_timeline(order.status)}\n\n"
        f"<b>Состав:</b>\n{_components_text(order)}\n\n"
        f"Цена: <b>{int(order.total_price or 0)}₽</b>\n"
        f"Желаемая дата: {order.desired_date or 'не указана'}\n"
        f"Получение: {delivery_label}\n"
        f"Время: {time_text}\n"
        f"Статус: {STATUS_LABEL.get(order.status, order.status)}\n"
    )
    if weight:
        text += f"Примерный вес: {weight}\n"
    if order.admin_comment:
        text += f"\nКомментарий администратора: {order.admin_comment}\n"
    if order.customer_comment:
        text += f"\nВаш комментарий: {order.customer_comment}\n"

    kb = user_order_kb(order.id, can_edit=order.status in EDITABLE_STATUSES)
    if order.result_image_url:
        msg = await cb.bot.send_photo(
            cb.message.chat.id,
            image_input(order.result_image_url),
            caption=text,
            parse_mode="HTML",
            reply_markup=kb,
        )
        await remember_bot_messages(state, [msg])
    else:
        await send_step(cb.bot, cb.message.chat.id, state, text, kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("acct:repeat:"))
async def repeat_prompt(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    order_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        user = await users_repo.get_or_create_user(session, cb.from_user)
        order = await order_repo.get_with_relations(session, order_id)
    if not order or order.user_id != user.id:
        await send_step(cb.bot, cb.message.chat.id, state, "Заказ не найден.", account_kb())
        return

    weight = await _weight_text(order)
    text = (
        f"Вы хотите повторить заказ #{order.id}?\n\n"
        f"🎂 Состав:\n{_components_text(order)}\n"
    )
    if weight:
        text += f"Примерный вес: {weight}\n"
    text += f"Цена в прошлый раз: {int(order.total_price or 0)} ₽"
    await state.update_data(
        _repeat_order_id=order.id,
        repeat_description=order.description,
        repeat_price=int(order.total_price or 0),
        repeat_weight=weight,
    )
    await send_step(cb.bot, cb.message.chat.id, state, text, repeat_order_kb(order.id))


@router.callback_query(F.data.startswith("acct:repeat_confirm:"))
async def repeat_confirm(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    order_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        user = await users_repo.get_or_create_user(session, cb.from_user)
        order = await order_repo.get_with_relations(session, order_id)
    if not order or order.user_id != user.id:
        await send_step(cb.bot, cb.message.chat.id, state, "Заказ не найден.", account_kb())
        return
    weight = await _weight_text(order)
    await state.update_data(
        _repeat_order_id=order_id,
        _is_template=False,
        repeat_description=_components_text(order),
        repeat_price=int(order.total_price or 0),
        repeat_weight=weight,
    )
    await checkout.ask_date(cb.bot, cb.message.chat.id, state)


@router.callback_query(F.data.startswith("acct:repeat_date:"))
async def repeat_change_date(cb: CallbackQuery, state: FSMContext):
    await repeat_confirm(cb, state)


async def _editable_order_for_user(session, cb: CallbackQuery, order_id: int):
    user = await users_repo.get_or_create_user(session, cb.from_user)
    order = await order_repo.get_with_relations(session, order_id)
    if not order or order.user_id != user.id:
        return None, "Заказ не найден."
    if order.status not in EDITABLE_STATUSES:
        return None, "Заказ уже в работе. Для изменений свяжитесь с администратором."
    return order, None


@router.callback_query(F.data.startswith("acct:edit_date:"))
async def edit_order_date(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    order_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        order, error = await _editable_order_for_user(session, cb, order_id)
    if error:
        await send_step(cb.bot, cb.message.chat.id, state, error, account_kb())
        return
    await state.update_data(edit_order_id=order.id)
    await state.set_state(OrderFSM.edit_date)
    await send_step(
        cb.bot,
        cb.message.chat.id,
        state,
        "Введите новую дату заказа в формате ДД.ММ.ГГГГ:",
        account_kb(),
    )


@router.message(OrderFSM.edit_date, F.text)
async def input_edit_order_date(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("edit_order_id")
    desired_date = checkout.parse_date(message.text.strip())
    if not desired_date:
        await message.answer("Не получилось распознать дату. Введите дату в формате ДД.ММ.ГГГГ.")
        return
    async with async_session() as session:
        if not await calendar_repo.is_available(session, desired_date):
            nearest = await calendar_repo.nearest_available_dates(session, desired_date)
            nearest_text = "\n".join(f"- {checkout.format_date(item)}" for item in nearest) or "- пока нет дат"
            await message.answer(
                f"К сожалению, на {checkout.format_date(desired_date)} заказы уже не принимаются.\n\n"
                f"Ближайшие доступные даты:\n{nearest_text}"
            )
            return
        await order_repo.update_order_fields(session, order_id, desired_date=desired_date)
    await state.clear()
    await message.answer(f"Дата заказа #{order_id} изменена на {checkout.format_date(desired_date)}.")


@router.callback_query(F.data.startswith("acct:edit_comment:"))
async def edit_order_comment(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    order_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        order, error = await _editable_order_for_user(session, cb, order_id)
    if error:
        await send_step(cb.bot, cb.message.chat.id, state, error, account_kb())
        return
    await state.update_data(edit_order_id=order.id)
    await state.set_state(OrderFSM.edit_comment)
    await send_step(
        cb.bot,
        cb.message.chat.id,
        state,
        "Введите новый комментарий к заказу:",
        account_kb(),
    )


@router.message(OrderFSM.edit_comment, F.text)
async def input_edit_order_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("edit_order_id")
    async with async_session() as session:
        await order_repo.update_order_fields(
            session,
            order_id,
            customer_comment=message.text.strip()[:1000],
        )
    await state.clear()
    await message.answer(f"Комментарий к заказу #{order_id} обновлён.")


@router.callback_query(F.data.startswith("acct:cancel:"))
async def cancel_user_order(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    order_id = int(cb.data.split(":")[2])
    async with async_session() as session:
        user = await users_repo.get_or_create_user(session, cb.from_user)
        order = await order_repo.get_with_relations(session, order_id)
        if not order or order.user_id != user.id:
            await send_step(cb.bot, cb.message.chat.id, state, "Заказ не найден.", account_kb())
            return
        if order.status not in EDITABLE_STATUSES:
            await send_step(
                cb.bot,
                cb.message.chat.id,
                state,
                "Заказ уже в работе. Для изменений свяжитесь с администратором.",
                account_kb(),
            )
            return
        await order_repo.update_status(session, order.id, OrderStatus.cancelled)
    await send_step(cb.bot, cb.message.chat.id, state, f"Заказ #{order_id} отменён.", account_kb())


@router.callback_query(F.data == "acct:contact")
async def contact_admin(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    relay.start(settings.admin_telegram_id, cb.from_user.id)
    await cb.bot.send_message(
        cb.from_user.id,
        "Напишите сообщение кондитеру. После ответа администратора диалог продолжится здесь.",
    )
    await cb.bot.send_message(
        settings.admin_telegram_id,
        f"Пользователь {cb.from_user.full_name} хочет связаться с кондитером.",
    )
