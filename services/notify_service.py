from aiogram import Bot
from config import settings
from keyboards.admin import STATUS_LABEL


async def notify_admin_new_order(bot: Bot, order, user):
    text = (
        f"🔔 <b>Новый заказ #{order.id}</b>\n"
        f"От: {user.first_name or ''} @{user.username or '—'} (id {user.telegram_id})\n"
        f"Состав: {order.description or '—'}\n"
        f"Цена: <b>{int(order.total_price or 0)}₽</b>\n"
        f"Дата: {order.desired_date or 'не указана'}"
    )
    await bot.send_message(settings.admin_telegram_id, text, parse_mode="HTML")


async def notify_user_status(bot: Bot, telegram_id: int, order):
    label = STATUS_LABEL.get(order.status, order.status)
    await bot.send_message(
        telegram_id,
        f"📢 Статус вашего заказа #{order.id} изменён: <b>{label}</b>",
        parse_mode="HTML",
    )