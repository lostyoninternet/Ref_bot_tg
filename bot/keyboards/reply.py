from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu reply keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="👤 Личный кабинет"),
        KeyboardButton(text="🔗 Моя ссылка"),
    )
    builder.row(
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="💡 Подсказки"),
    )
    builder.row(
        KeyboardButton(text="📊 Грейды"),
    )
    return builder.as_markup(resize_keyboard=True)


def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    """Admin reply keyboard."""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="👤 Личный кабинет"),
        KeyboardButton(text="⚙️ Админ-панель"),
    )
    builder.row(
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="🔗 Моя ссылка"),
    )
    return builder.as_markup(resize_keyboard=True)
