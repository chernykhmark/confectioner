from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from db.models import OrderStatus

# MVP переходы статусов
NEXT_STATUS = {
    OrderStatus.created: [OrderStatus.confirmed, OrderStatus.cancelled],
    OrderStatus.confirmed: [OrderStatus.ready, OrderStatus.cancelled],
    OrderStatus.ready: [OrderStatus.closed, OrderStatus.cancelled],
}

STATUS_LABEL = {
    OrderStatus.created: "🆕 Создан",
    OrderStatus.confirmed: "✅ Подтверждён",
    OrderStatus.ready: "🎂 Готов",
    OrderStatus.closed: "📦 Закрыт",
    OrderStatus.cancelled: "❌ Отменён",
}


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Заказы", callback_data="adm:orders")],
        [InlineKeyboardButton(text="📊 Мониторинг воронки", callback_data="adm:monitor")],
    ])


def orders_filter_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Открытые", callback_data="adm:list:open")],
        [InlineKeyboardButton(text="⚪ Закрытые", callback_data="adm:list:closed")],
    ])


def orders_list_kb(orders) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=f"#{o.id} · {STATUS_LABEL.get(o.status, o.status)} · {int(o.total_price or 0)}₽",
        callback_data=f"adm:order:{o.id}")] for o in orders]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_card_kb(order) -> InlineKeyboardMarkup:
    rows = []
    for st in NEXT_STATUS.get(order.status, []):
        rows.append([InlineKeyboardButton(
            text=f"→ {STATUS_LABEL[st]}",
            callback_data=f"adm:setstatus:{order.id}:{st.value}")])
    rows.append([InlineKeyboardButton(text="⬅️ К списку", callback_data="adm:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def orders_filter_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Открытые", callback_data="adm:list:open")],
        [InlineKeyboardButton(text="⚪ Закрытые", callback_data="adm:list:closed")],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data="adm:menu")],  # NEW
    ])