import asyncio
import logging

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from db.base import async_session
from db.repositories import funnel_events, users as users_repo, orders as order_repo
from db.repositories import sessions as sessions_repo   # NEW
from services import order_service, notify_service
from states.order import OrderFSM
from keyboards.user import main_menu
from handlers.admin.monitoring import registry
from utils.message import delete_last_bot_messages

router = Router()
log = logging.getLogger(__name__)


@router.callback_query(OrderFSM.confirming, F.data == "order:confirm")
async def confirm_order(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    data = await state.get_data()
    is_template = data.get("_is_template", False)
    manual_user_id = data.get("_manual_user_id")

    async with async_session() as s:
        if manual_user_id:
            from db.models import User as _User
            user = await s.get(_User, manual_user_id)
        else:
            user = await users_repo.get_or_create_user(s, cb.from_user)

        if data.get("_repeat_order_id"):
            order = await order_service.create_repeat_order(
                s, user.id, data["_repeat_order_id"], data,
            )
        elif is_template:
            order = await order_service.create_template_order(
                s, user.id, data["template_id"],
                desired_date_raw=data.get("desired_date"),
                data=data,
            )
        else:
            order = await order_service.create_custom_order(s, user.id, data)
        order = await order_repo.get_with_relations(s, order.id)
        await funnel_events.log_event(
            s,
            user_id=user.id,
            event_type="order_created",
            step="order_created",
            payload={"order_id": order.id, "total_price": int(order.total_price or 0)},
        )
        await sessions_repo.delete_session(s, user.id)

    log.info(
        "order_created order_id=%s user_id=%s telegram_id=%s total_price=%s",
        order.id, order.user_id, order.user.telegram_id, int(order.total_price or 0),
    )

    async def notify_admin():
        try:
            await notify_service.notify_admin_new_order(cb.bot, order, order.user)
        except Exception:
            log.exception("notify_admin_new_order_failed order_id=%s", order.id)

    asyncio.create_task(notify_admin())

    # NEW: уведомить клиента, если заказ создан админом вручную
    if manual_user_id:
        async def notify_client():
            try:
                await cb.bot.send_message(
                    order.user.telegram_id,
                    f"🎂 Для вас создан заказ #{order.id}!\n"
                    f"Цена: {int(order.total_price or 0)}₽\n"
                    f"Дата: {order.desired_date or 'не указана'}\n\n"
                    f"Вы можете управлять им в Личном кабинете → Мои заказы.",
                    reply_markup=main_menu(),
                )
            except Exception:
                log.exception("notify_client_manual_order_failed order_id=%s", order.id)
        asyncio.create_task(notify_client())

    registry.clear(cb.message.chat.id)
    await delete_last_bot_messages(cb.bot, cb.message.chat.id, state)
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        log.exception("confirm_order_callback_delete_failed order_id=%s", order.id)

    if manual_user_id:
        final_text = f"✅ Заказ #{order.id} создан для клиента. Он получил уведомление."
    else:
        final_text = (
            f"✅ Заказ #{order.id} оформлен!\n"
            f"Цена: <b>{int(order.total_price or 0)}₽</b>\n"
            f"Мы свяжемся с вами. Спасибо! 🎂"
        )
    await cb.message.answer(final_text, parse_mode="HTML", reply_markup=main_menu())


@router.callback_query(OrderFSM.confirming, F.data == "order:cancel")
async def cancel_order(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    async with async_session() as s:                     # NEW
        user = await users_repo.get_or_create_user(s, cb.from_user)
        await sessions_repo.delete_session(s, user.id)   # NEW: отмена → сессия удалена
    registry.clear(cb.message.chat.id)
    await delete_last_bot_messages(cb.bot, cb.message.chat.id, state)
    await state.clear()
    try:
        await cb.message.delete()
    except Exception:
        log.exception("cancel_order_callback_delete_failed chat_id=%s", cb.message.chat.id)
    await cb.message.answer("❌ Сборка отменена.", reply_markup=main_menu())
