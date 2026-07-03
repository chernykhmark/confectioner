from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from db.models import OrderStatus

# MVP переходы статусов
NEXT_STATUS = {
    OrderStatus.created: [OrderStatus.confirmed, OrderStatus.cancelled],
    OrderStatus.confirmed: [OrderStatus.in_progress, OrderStatus.cancelled],
    OrderStatus.in_progress: [OrderStatus.ready, OrderStatus.cancelled],
    OrderStatus.ready: [OrderStatus.paid, OrderStatus.closed, OrderStatus.cancelled],
    OrderStatus.paid: [OrderStatus.closed],
}

STATUS_LABEL = {
    OrderStatus.created: "Создан",
    OrderStatus.confirmed: "Подтверждён",
    OrderStatus.in_progress: "В работе",
    OrderStatus.ready: "Готов",
    OrderStatus.paid: "Оплачен",
    OrderStatus.closed: "Закрыт",
    OrderStatus.cancelled: "Отменён",
}

ORDER_LIST_STATUS_LABEL = {
    OrderStatus.created: "Открыт",
    OrderStatus.confirmed: "Подтвержден",
    OrderStatus.in_progress: "В работе",
    OrderStatus.ready: "Готов",
    OrderStatus.paid: "Оплачен",
    OrderStatus.closed: "Закрыт",
    OrderStatus.cancelled: "Отменен",
}

STATUS_ACTION_LABEL = {
    OrderStatus.created: "Создать",
    OrderStatus.confirmed: "Подтвердить",
    OrderStatus.in_progress: "В работу",
    OrderStatus.ready: "Отметить готовым",
    OrderStatus.paid: "Отметить оплаченным",
    OrderStatus.closed: "Закрыть",
    OrderStatus.cancelled: "Отменить",
}

BTN_OPEN_ADMIN_PANEL = "Открыть панель"


def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Открыть заказы", callback_data="adm:orders")],
        [InlineKeyboardButton(text="Статистика", callback_data="adm:stats")],
        [InlineKeyboardButton(text="Найти заказ", callback_data="adm:search")],
        [InlineKeyboardButton(text="Напомнить клиентам на завтра", callback_data="adm:remind_tomorrow")],
        [InlineKeyboardButton(text="Создать заказ", callback_data="adm:manual_order")],
        [InlineKeyboardButton(text="Открыть мониторинг", callback_data="adm:monitor")],
        [InlineKeyboardButton(text="Создать продукт", callback_data="adm:product:new")],
        [InlineKeyboardButton(text="Редактировать каталог", callback_data="adm:edit")],
    ])


def admin_reply_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_OPEN_ADMIN_PANEL)]],
        resize_keyboard=True,
        is_persistent=True,
    )


def orders_list_kb(orders) -> InlineKeyboardMarkup:
    rows = []
    for order in orders:
        description = (order.description or "без описания").replace("\n", " ")
        if len(description) > 28:
            description = f"{description[:25]}..."
        rows.append([InlineKeyboardButton(
            text=f"Открыть #{order.id} · {ORDER_LIST_STATUS_LABEL.get(order.status, order.status)} · {description}",
            callback_data=f"adm:order:{order.id}",
        )])
    rows.append([InlineKeyboardButton(text="Показать фильтры", callback_data="adm:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_card_kb(order) -> InlineKeyboardMarkup:
    rows = []
    for st in NEXT_STATUS.get(order.status, []):
        rows.append([InlineKeyboardButton(
            text=STATUS_ACTION_LABEL[st],
            callback_data=f"adm:setstatus:{order.id}:{st.value}")])
    if order.user:
        rows.append([InlineKeyboardButton(
            text="Написать клиенту",
            callback_data=f"relay:start:{order.user.telegram_id}",
        )])
    rows.append([InlineKeyboardButton(text="Открыть список", callback_data="adm:orders")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def orders_filter_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Показать открытые", callback_data="adm:list:open")],
        [InlineKeyboardButton(text="Показать закрытые", callback_data="adm:list:closed")],
        [InlineKeyboardButton(text="Открыть меню", callback_data="adm:menu")],
    ])


def product_image_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить изображение", callback_data="adm:product:skip_image")],
        [InlineKeyboardButton(text="Отменить создание", callback_data="adm:product:cancel")],
    ])


def product_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отменить создание", callback_data="adm:product:cancel")],
    ])


def product_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать", callback_data="adm:product:confirm")],
        [InlineKeyboardButton(text="Отменить", callback_data="adm:product:cancel")],
    ])


def product_component_kb(components) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=component.name, callback_data=f"adm:product:component:{component.id}")]
        for component in components
    ]
    rows.append([InlineKeyboardButton(text="Пропустить", callback_data="adm:product:component:skip")])
    rows.append([InlineKeyboardButton(text="Отменить создание", callback_data="adm:product:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_root_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Редактировать продукты", callback_data="adm:edit:products")],
        [InlineKeyboardButton(text="Редактировать компоненты", callback_data="adm:edit:components")],
        [InlineKeyboardButton(text="Открыть меню", callback_data="adm:menu")],
    ])


def edit_products_kb(products) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Открыть #{product.id} · {product.name}", callback_data=f"adm:edit:product:{product.id}")]
        for product in products
    ]
    rows.append([InlineKeyboardButton(text="Открыть каталог", callback_data="adm:edit")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_product_kb(product_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить фото", callback_data=f"adm:edit:product_field:{product_id}:image")],
        [InlineKeyboardButton(text="Изменить название", callback_data=f"adm:edit:product_field:{product_id}:name")],
        [InlineKeyboardButton(text="Изменить описание", callback_data=f"adm:edit:product_field:{product_id}:description")],
        [InlineKeyboardButton(text="Изменить цену", callback_data=f"adm:edit:product_field:{product_id}:price")],
        [InlineKeyboardButton(text="Изменить компоненты", callback_data=f"adm:edit:product_field:{product_id}:components")],
        [InlineKeyboardButton(text="Открыть продукты", callback_data="adm:edit:products")],
    ])


def edit_component_types_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Формы", callback_data="adm:edit:components:shape")],
        [InlineKeyboardButton(text="Начинки", callback_data="adm:edit:components:filling")],
        [InlineKeyboardButton(text="Оформление", callback_data="adm:edit:components:decor")],
        [InlineKeyboardButton(text="Персоны", callback_data="adm:edit:components:persons")],
        [InlineKeyboardButton(text="Поводы", callback_data="adm:edit:components:occasion")],
        [InlineKeyboardButton(text="Открыть каталог", callback_data="adm:edit")],
    ])


def edit_components_kb(components) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"Открыть #{component.id} · {component.name}", callback_data=f"adm:edit:component:{component.id}")]
        for component in components
    ]
    rows.append([InlineKeyboardButton(text="Открыть типы", callback_data="adm:edit:components")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_component_kb(component_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить фото", callback_data=f"adm:edit:component_field:{component_id}:image")],
        [InlineKeyboardButton(text="Изменить название", callback_data=f"adm:edit:component_field:{component_id}:name")],
        [InlineKeyboardButton(text="Изменить надбавку", callback_data=f"adm:edit:component_field:{component_id}:price_delta")],
        [InlineKeyboardButton(text="Переключить активность", callback_data=f"adm:edit:component_toggle:{component_id}")],
        [InlineKeyboardButton(text="Открыть компоненты", callback_data="adm:edit:components")],
    ])
