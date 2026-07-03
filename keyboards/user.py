from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards.common import nav_row, BTN_HOME


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ Популярные заказы", callback_data="menu:templates")],
        [InlineKeyboardButton(text="🛠 Создать самому", callback_data="menu:custom")],
        [InlineKeyboardButton(text="ℹ️ Справка", callback_data="menu:help")],
    ])


def components_kb(components) -> InlineKeyboardMarkup:
    """Клавиатура одного шага воронки: список компонентов + навигация."""
    rows = [[InlineKeyboardButton(text=c.name, callback_data=f"comp:{c.id}")]
            for c in components]
    rows.append(nav_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def templates_kb(products) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{p.name} — {int(p.price)}₽",
                                  callback_data=f"tpl:{p.id}")]
            for p in products]
    rows.append([BTN_HOME])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def date_wishes_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[nav_row()])


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