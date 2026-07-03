from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from db.base import async_session
from db.repositories import users as users_repo, orders as order_repo
from db.repositories import sessions as sessions_repo   # NEW
from services import order_service, notify_service
from states.order import OrderFSM
from keyboards.user import main_menu
from handlers.admin.monitoring import registry

router = Router()


@router.callback_query(OrderFSM.confirming, F.data == "order:confirm")
async def confirm_order(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    is_template = data.get("_is_template", False)

    async with async_session() as s:
        user = await users_repo.get_or_create_user(s, cb.from_user)
        if is_template:
            order = await order_service.create_template_order(
                s, user.id, data["template_id"],
                desired_date_raw=data.get("desired_date"))
        else:
            order = await order_service.create_custom_order(s, user.id, data)
        order = await order_repo.get_with_relations(s, order.id)
        await sessions_repo.delete_session(s, user.id)   # NEW: заказ создан → сессия удалена

    await notify_service.notify_admin_new_order(cb.bot, order, order.user)

    await state.clear()
    registry.clear(cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer(
        f"✅ Заказ #{order.id} оформлен!\n"
        f"Цена: <b>{int(order.total_price or 0)}₽</b>\n"
        f"Мы свяжемся с вами. Спасибо! 🎂",
        parse_mode="HTML", reply_markup=main_menu(),
    )
    await cb.answer()


@router.callback_query(OrderFSM.confirming, F.data == "order:cancel")
async def cancel_order(cb: CallbackQuery, state: FSMContext):
    async with async_session() as s:                     # NEW
        user = await users_repo.get_or_create_user(s, cb.from_user)
        await sessions_repo.delete_session(s, user.id)   # NEW: отмена → сессия удалена
    await state.clear()
    registry.clear(cb.message.chat.id)
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.message.answer("❌ Сборка отменена.", reply_markup=main_menu())
    await cb.answer()