from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BTN_BACK = InlineKeyboardButton(text="⬅️ Назад", callback_data="nav:back")
BTN_HOME = InlineKeyboardButton(text="🏠 В главное меню", callback_data="nav:home")


def nav_row():
    return [BTN_BACK, BTN_HOME]


def home_only():
    return InlineKeyboardMarkup(inline_keyboard=[[BTN_HOME]])