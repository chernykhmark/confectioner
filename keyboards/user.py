from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.common import nav_row, BTN_HOME
from db.models import OrderStatus


USER_STATUS_LABEL = {
    OrderStatus.created: "Создан",
    OrderStatus.confirmed: "Подтверждён",
    OrderStatus.in_progress: "В работе",
    OrderStatus.ready: "Готов",
    OrderStatus.paid: "Оплачен",
    OrderStatus.closed: "Закрыт",
    OrderStatus.cancelled: "Отменён",
}


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Популярные заказы", callback_data="menu:templates")],
        [InlineKeyboardButton(text="🛠 Создать самому", callback_data="menu:custom")],
        [InlineKeyboardButton(text="Подобрать из готовых вариантов", callback_data="menu:catalog")],
        [InlineKeyboardButton(text="Личный кабинет", callback_data="menu:account")],
        [InlineKeyboardButton(text="ℹ️ Справка", callback_data="menu:help")],
    ])


def components_kb(components) -> InlineKeyboardMarkup:
    """Клавиатура одного шага воронки: список компонентов + навигация."""
    rows = []
    for c in components:
        text = c.name
        if getattr(c, "short_description", None):
            text = f"{c.name} — {c.short_description}"
        if len(text) > 64:
            text = f"{text[:61]}..."
        rows.append([InlineKeyboardButton(text=text, callback_data=f"comp:{c.id}")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def budget_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="до 3000 ₽", callback_data="budget:до 3000 ₽")],
        [InlineKeyboardButton(text="3000–5000 ₽", callback_data="budget:3000–5000 ₽")],
        [InlineKeyboardButton(text="5000–8000 ₽", callback_data="budget:5000–8000 ₽")],
        [InlineKeyboardButton(text="8000+ ₽", callback_data="budget:8000+ ₽")],
        nav_row(),
    ])


def decoration_multi_kb(components, selected_ids: list[int]) -> InlineKeyboardMarkup:
    rows = []
    selected = set(selected_ids)
    for component in components:
        mark = "✓ " if component.id in selected else ""
        rows.append([InlineKeyboardButton(
            text=f"{mark}{component.name}",
            callback_data=f"decor:toggle:{component.id}",
        )])
    rows.append([InlineKeyboardButton(text="Подтвердить оформление", callback_data="decor:done")])
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def component_card_kb(component_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать", callback_data=f"comp:{component_id}")],
        nav_row(),
    ])


def templates_kb(products) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{p.name} — {int(p.price)}₽",
                                  callback_data=f"tpl:{p.id}")]
            for p in products]
    rows.append([BTN_HOME])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def template_card_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Выбрать", callback_data=f"tpl:{product_id}")],
        [BTN_HOME],
    ])


def catalog_options_kb(options, show_counts: bool = False, show_restart: bool = True) -> InlineKeyboardMarkup:
    rows = []
    for component, count in options:
        text = f"{component.name} — {count} вариантов" if show_counts else component.name
        rows.append([InlineKeyboardButton(
            text=text,
            callback_data=f"cat:comp:{component.id}",
        )])
    if show_restart:
        rows.append([InlineKeyboardButton(text="Подобрать заново", callback_data="cat:restart")])
    rows.append([InlineKeyboardButton(text="Создать индивидуальный заказ", callback_data="menu:custom")])
    rows.append([BTN_HOME])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_products_kb(products) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{product.name} — {int(product.price)}₽",
            callback_data=f"cat:preview:{product.id}",
        )]
        for product in products
    ]
    rows.append([InlineKeyboardButton(text="Подобрать заново", callback_data="cat:restart")])
    rows.append([InlineKeyboardButton(text="Создать индивидуальный заказ", callback_data="menu:custom")])
    rows.append([BTN_HOME])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def catalog_result_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Согласиться с выбором", callback_data=f"cat:product:{product_id}")],
        [InlineKeyboardButton(text="Вернуться назад", callback_data="cat:back")],
        [InlineKeyboardButton(text="Создать индивидуальный заказ", callback_data="menu:custom")],
        [BTN_HOME],
    ])


def catalog_empty_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подобрать заново", callback_data="cat:restart")],
        [InlineKeyboardButton(text="Создать индивидуальный заказ", callback_data="menu:custom")],
        [BTN_HOME],
    ])


def date_wishes_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[nav_row()])


def delivery_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Доставка", callback_data="delivery:type:delivery")],
        [InlineKeyboardButton(text="Самовывоз", callback_data="delivery:type:pickup")],
        nav_row(),
    ])


def delivery_time_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="10:00-12:00", callback_data="delivery:time:10:00:12:00")],
        [InlineKeyboardButton(text="12:00-14:00", callback_data="delivery:time:12:00:14:00")],
        [InlineKeyboardButton(text="14:00-16:00", callback_data="delivery:time:14:00:16:00")],
        [InlineKeyboardButton(text="16:00-18:00", callback_data="delivery:time:16:00:18:00")],
        nav_row(),
    ])


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Заказать", callback_data="order:confirm")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="order:cancel")],
    ])

def template_date_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Без даты", callback_data="tpl:nodate")],
        [BTN_HOME],
    ])


def review_offer_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оставить отзыв", callback_data=f"review:start:{order_id}")],
    ])


def review_image_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить фото", callback_data="review:skip_image")],
        [InlineKeyboardButton(text="Отменить отзыв", callback_data="review:cancel")],
    ])


def review_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отменить отзыв", callback_data="review:cancel")],
    ])


def account_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мои заказы", callback_data="acct:orders")],
        [InlineKeyboardButton(text="Написать кондитеру", callback_data="acct:contact")],
        [BTN_HOME],
    ])


def user_orders_kb(orders) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"Открыть #{order.id} · {order.desired_date or 'без даты'} · {USER_STATUS_LABEL.get(order.status, order.status.value)}",
            callback_data=f"acct:order:{order.id}",
        )]
        for order in orders
    ]
    rows.append([InlineKeyboardButton(text="Открыть кабинет", callback_data="menu:account")])
    rows.append([BTN_HOME])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_order_kb(order_id: int, can_edit: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text="Повторить заказ", callback_data=f"acct:repeat:{order_id}")]]
    if can_edit:
        rows.append([InlineKeyboardButton(text="Изменить дату", callback_data=f"acct:edit_date:{order_id}")])
        rows.append([InlineKeyboardButton(text="Изменить комментарий", callback_data=f"acct:edit_comment:{order_id}")])
        rows.append([InlineKeyboardButton(text="Отменить заказ", callback_data=f"acct:cancel:{order_id}")])
    rows.append([InlineKeyboardButton(text="Мои заказы", callback_data="acct:orders")])
    rows.append([BTN_HOME])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def repeat_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Повторить", callback_data=f"acct:repeat_confirm:{order_id}")],
        [InlineKeyboardButton(text="Изменить дату", callback_data=f"acct:repeat_date:{order_id}")],
        [InlineKeyboardButton(text="Назад", callback_data=f"acct:order:{order_id}")],
    ])
