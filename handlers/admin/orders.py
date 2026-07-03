from aiogram import Router, F
from aiogram.types import CallbackQuery

from db.base import async_session
from db.repositories import orders as order_repo
from services import order_service, notify_service
from db.models import OrderStatus
from keyboards.admin import (
    orders_filter_kb, orders_list_kb, order_card_kb, STATUS_LABEL,
)
from config import settings

router = Router()


def _is_admin(cb: CallbackQuery) -> bool:
    return cb.from_user.id == settings.admin_telegram_id


@router.callback_query(F.data == "adm:orders")
async def orders_menu(cb: CallbackQuery):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    await cb.message.answer("📋 Заказы:", reply_markup=orders_filter_kb())
    await cb.answer()


@router.callback_query(F.data.startswith("adm:list:"))
async def orders_list(cb: CallbackQuery):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    kind = cb.data.split(":")[2]
    statuses = order_repo.OPEN_STATUSES if kind == "open" else order_repo.CLOSED_STATUSES
    async with async_session() as s:
        orders = await order_repo.list_by_statuses(s, statuses)
    if not orders:
        await cb.answer("Список пуст", show_alert=True)
        return
    title = "🟢 Открытые заказы:" if kind == "open" else "⚪ Закрытые заказы:"
    await cb.message.answer(title, reply_markup=orders_list_kb(orders))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:order:"))
async def order_card(cb: CallbackQuery):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    order_id = int(cb.data.split(":")[2])
    async with async_session() as s:
        order = await order_repo.get_with_relations(s, order_id)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return

    comps = ", ".join(oc.component.name for oc in order.components) or order.description or "—"
    text = (
        f"📦 <b>Заказ #{order.id}</b>\n"
        f"Статус: {STATUS_LABEL.get(order.status, order.status)}\n"
        f"Клиент: {order.user.first_name or ''} @{order.user.username or '—'}\n"
        f"Состав: {comps}\n"
        f"Цена: <b>{int(order.total_price or 0)}₽</b>\n"
        f"Дата: {order.desired_date or 'не указана'}"
    )
    await cb.message.answer(text, parse_mode="HTML", reply_markup=order_card_kb(order))
    await cb.answer()


@router.callback_query(F.data.startswith("adm:setstatus:"))
async def set_status(cb: CallbackQuery):
    if not _is_admin(cb):
        await cb.answer("Нет доступа", show_alert=True)
        return
    _, _, order_id_raw, status_raw = cb.data.split(":")
    order_id = int(order_id_raw)
    new_status = OrderStatus(status_raw)

    async with async_session() as s:
        order = await order_service.change_status(s, order_id, new_status)
        order = await order_repo.get_with_relations(s, order_id)

    if not order:
        await cb.answer("Ошибка", show_alert=True)
        return

    # уведомляем клиента
    try:
        await notify_service.notify_user_status(cb.bot, order.user.telegram_id, order)
    except Exception:
        pass

    await cb.message.edit_text(
        f"✅ Статус заказа #{order.id} → {STATUS_LABEL.get(order.status, order.status)}",
        parse_mode="HTML", reply_markup=order_card_kb(order),
    )
    await cb.answer("Статус обновлён")