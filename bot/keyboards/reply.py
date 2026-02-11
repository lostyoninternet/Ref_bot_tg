from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


CONTACTS_BUTTON_TEXT = "📞 Остались вопросы? Связаться"


def get_main_menu_keyboard(show_contacts: bool = False) -> ReplyKeyboardMarkup:
    """Main menu reply keyboard. show_contacts: показывать кнопку «Связаться» (управляется админом)."""
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
    if show_contacts:
        builder.row(
            KeyboardButton(text=CONTACTS_BUTTON_TEXT),
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
