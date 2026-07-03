from aiogram import Bot
from config import settings
from keyboards.admin import STATUS_LABEL
from db.models import OrderStatus
from keyboards.user import review_offer_kb


async def notify_admin_new_order(bot: Bot, order, user):
    delivery_label = "Доставка" if order.delivery_type == "delivery" else "Самовывоз" if order.delivery_type == "pickup" else "не указано"
    time_text = (
        f"{order.delivery_time_from}-{order.delivery_time_to}"
        if order.delivery_time_from and order.delivery_time_to
        else "не указано"
    )
    text = (
        f"🔔 <b>Новый заказ #{order.id}</b>\n"
        f"От: {user.first_name or ''} @{user.username or '—'} (id {user.telegram_id})\n"
        f"Состав: {order.description or '—'}\n"
        f"Цена: <b>{int(order.total_price or 0)}₽</b>\n"
        f"Дата: {order.desired_date or 'не указана'}\n"
        f"Получение: {delivery_label}\n"
        f"Время: {time_text}"
        + (f"\nАдрес: {order.delivery_address}" if order.delivery_address else "")
        + (f"\nКомментарий клиента: {order.customer_comment}" if order.customer_comment else "")
    )
    await bot.send_message(settings.admin_telegram_id, text, parse_mode="HTML")


async def notify_user_status(bot: Bot, telegram_id: int, order):
    label = STATUS_LABEL.get(order.status, order.status)
    reply_markup = review_offer_kb(order.id) if order.status == OrderStatus.closed else None
    text = f"📢 Статус вашего заказа #{order.id} изменён: <b>{label}</b>"
    if order.status == OrderStatus.closed:
        text += "\n\nВы можете оставить отзыв и прикрепить фото по желанию."

    await bot.send_message(
        telegram_id,
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
