import asyncio
import logging
from datetime import date, timedelta

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from db.base import async_session
from db.repositories import orders as order_repo
from services import order_service, notify_service
from db.models import OrderStatus
from config import settings
from keyboards.admin import (
    orders_filter_kb, orders_list_kb, order_card_kb, STATUS_LABEL, admin_menu,
)
from utils.message import remember_bot_messages, send_replacing_message

from states.admin_product import AdminManualOrderFSM
from states.order import OrderFSM
from db.repositories import users as users_repo
from aiogram.types import Message

from states.admin_product import AdminManualOrderFSM
from states.order import OrderFSM
from db.repositories import users as users_repo
from aiogram.types import Message

router = Router()
log = logging.getLogger(__name__)


def _is_admin(cb: CallbackQuery) -> bool:
    return cb.from_user.id == settings.admin_telegram_id


async def _show_admin_section(
    cb: CallbackQuery,
    state: FSMContext,
    text: str,
    kb,
    parse_mode: str | None = None,
):
    try:
        await cb.message.edit_text(text, parse_mode=parse_mode, reply_markup=kb)
        await remember_bot_messages(state, [cb.message])
    except Exception:
        await send_replacing_message(
            cb.bot,
            cb.message.chat.id,
            state,
            text,
            kb,
            parse_mode=parse_mode,
        )


@router.callback_query(F.data == "adm:orders")
async def orders_menu(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    await _show_admin_section(
        cb,
        state,
        "Заказы",
        orders_filter_kb(),
    )


@router.callback_query(F.data.startswith("adm:list:"))
async def orders_list(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    kind = cb.data.split(":")[2]
    statuses = order_repo.OPEN_STATUSES if kind == "open" else order_repo.CLOSED_STATUSES
    async with async_session() as s:
        orders = await order_repo.list_by_statuses(s, statuses)
    if not orders:
        title = "Открытых заказов нет" if kind == "open" else "Закрытых заказов нет"
        await _show_admin_section(cb, state, title, orders_filter_kb())
        return
    title = "Открытые заказы" if kind == "open" else "Закрытые заказы"
    await _show_admin_section(
        cb,
        state,
        title,
        orders_list_kb(orders),
    )


@router.callback_query(F.data.startswith("adm:order:"))
async def order_card(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    order_id = int(cb.data.split(":")[2])
    async with async_session() as s:
        order = await order_repo.get_with_relations(s, order_id)
    if not order:
        await _show_admin_section(cb, state, "Заказ не найден", orders_filter_kb())
        return

    comps = "\n".join(f"- {oc.component.name}" for oc in order.components) or order.description or "—"
    delivery_label = "Доставка" if order.delivery_type == "delivery" else "Самовывоз" if order.delivery_type == "pickup" else "не указано"
    time_text = (
        f"{order.delivery_time_from}-{order.delivery_time_to}"
        if order.delivery_time_from and order.delivery_time_to
        else "не указано"
    )
    text = (
        f"<b>Заказ #{order.id}</b>\n"
        f"Клиент: @{order.user.username or '—'} / {order.user.first_name or '—'}\n"
        f"Дата: {order.desired_date or 'не указана'}\n"
        f"Цена: <b>{int(order.total_price or 0)}₽</b>\n"
        f"Статус: {STATUS_LABEL.get(order.status, order.status)}\n"
        f"Получение: {delivery_label}\n"
        f"Время: {time_text}\n"
        + (f"Адрес: {order.delivery_address}\n" if order.delivery_address else "")
        + f"\n<b>Состав:</b>\n{comps}\n"
        + (f"\nПожелания/описание:\n{order.description}" if order.description else "")
        + (f"\nКомментарий клиента:\n{order.customer_comment}" if order.customer_comment else "")
        + (f"\n\nКомментарий администратора:\n{order.admin_comment}" if order.admin_comment else "")
    )
    await _show_admin_section(
        cb,
        state,
        text,
        order_card_kb(order),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm:setstatus:"))
async def set_status(cb: CallbackQuery):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    _, _, order_id_raw, status_raw = cb.data.split(":")
    order_id = int(order_id_raw)
    new_status = OrderStatus(status_raw)

    async with async_session() as s:
        order = await order_service.change_status(s, order_id, new_status)
        order = await order_repo.get_with_relations(s, order_id)

    if not order:
        try:
            await cb.message.edit_text("Заказ не найден", reply_markup=orders_filter_kb())
        except Exception:
            log.exception("order_not_found_edit_failed order_id=%s", order_id)
        return

    log.info("order_status_changed order_id=%s status=%s admin_id=%s", order.id, order.status.value, cb.from_user.id)

    async def notify_user():
        try:
            await notify_service.notify_user_status(cb.bot, order.user.telegram_id, order)
        except Exception:
            log.exception("notify_user_status_failed order_id=%s telegram_id=%s", order.id, order.user.telegram_id)

    asyncio.create_task(notify_user())

    await cb.message.edit_text(
        f"Статус заказа #{order.id}: {STATUS_LABEL.get(order.status, order.status)}",
        parse_mode="HTML", reply_markup=order_card_kb(order),
    )



@router.callback_query(F.data == "adm:remind_tomorrow")
async def remind_tomorrow(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    tomorrow = date.today() + timedelta(days=1)
    async with async_session() as s:
        orders = await order_repo.list_by_desired_date(s, tomorrow)

    sent = 0
    for order in orders:
        try:
            await cb.bot.send_message(
                order.user.telegram_id,
                f"Напоминаем, ваш заказ #{order.id} будет готов завтра. "
                "Пожалуйста, подтвердите, что дата и время актуальны.",
            )
            sent += 1
        except Exception:
            log.exception("tomorrow_reminder_failed order_id=%s telegram_id=%s", order.id, order.user.telegram_id)
    log.info("tomorrow_reminders_sent count=%s target_date=%s", sent, tomorrow)
    await _show_admin_section(
        cb,
        state,
        f"Напоминания на завтра отправлены: {sent}",
        admin_menu(),
    )




@router.callback_query(F.data == "adm:manual_order")
async def manual_order_start(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    await state.clear()
    await state.set_state(AdminManualOrderFSM.contact)
    await _show_admin_section(
        cb, state,
        "Создание заказа. Укажите контакт клиента (@ник или telegram_id):",
        None,
    )


@router.message(AdminManualOrderFSM.contact, F.text)
async def manual_order_contact(message: Message, state: FSMContext):
    if message.from_user.id != settings.admin_telegram_id:
        return
    raw = message.text.strip()
    async with async_session() as s:
        if raw.startswith("@"):
            user = await users_repo.get_by_username(s, raw[1:])
        elif raw.isdigit():
            user = await users_repo.get_by_telegram_id(s, int(raw))
        else:
            user = None
    if not user:
        await message.answer("Клиент не найден. Он должен хотя бы раз написать боту. Введите @ник или telegram_id ещё раз:")
        return

    # запускаем обычную воронку, но помечаем, что заказ для этого клиента
    await state.update_data(_manual_user_id=user.id)
    from handlers.user.funnel import start_funnel_from
    await start_funnel_from(message.bot, message.chat.id, state, message.from_user)




from states.admin_product import AdminManualOrderFSM, AdminSearchFSM


@router.callback_query(F.data == "adm:search")
async def admin_search(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    await state.clear()
    await state.set_state(AdminSearchFSM.query)
    await _show_admin_section(
        cb, state,
        "Введите @ник клиента или дату заказа в формате ДД.ММ.ГГГГ:",
        None,
    )


@router.message(AdminSearchFSM.query, F.text)
async def admin_search_query(message: Message, state: FSMContext):
    if message.from_user.id != settings.admin_telegram_id:
        return
    raw = message.text.strip()
    await state.clear()

    orders = []
    async with async_session() as s:
        # поиск по дате ДД.ММ.ГГГГ
        target_date = None
        try:
            target_date = date(*reversed([int(x) for x in raw.split(".")]))
        except Exception:
            target_date = None

        if target_date:
            orders = await order_repo.list_by_desired_date(s, target_date)
        else:
            username = raw[1:] if raw.startswith("@") else raw
            user = await users_repo.get_by_username(s, username)
            if not user and raw.isdigit():
                user = await users_repo.get_by_telegram_id(s, int(raw))
            if user:
                orders = await order_repo.list_by_user(s, user.id)

    if not orders:
        await message.answer("Заказы не найдены.", reply_markup=orders_filter_kb())
        return

    await message.answer(
        f"Найдено заказов: {len(orders)}",
        reply_markup=orders_list_kb(orders),
    )

@router.callback_query(F.data == "adm:menu")
async def back_to_admin_menu(cb: CallbackQuery, state: FSMContext):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.answer()
    await _show_admin_section(
        cb,
        state,
        "Панель администратора",
        admin_menu(),
    )
