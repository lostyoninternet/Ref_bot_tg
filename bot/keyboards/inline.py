from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.config import settings
from bot.services.grade import parse_rewards


def get_subscription_keyboard(application_url: str) -> InlineKeyboardMarkup:
    """Клавиатура для неподписанных: заявка на очный этап + проверка подписки."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📋 Оставить заявку на очный этап",
            url=application_url
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ Проверить подписку",
            callback_data="check_subscription"
        )
    )
    return builder.as_markup()


def get_cabinet_keyboard() -> InlineKeyboardMarkup:
    """Main cabinet keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Моя статистика", callback_data="my_stats"),
        InlineKeyboardButton(text="🔗 Моя ссылка", callback_data="my_link"),
    )
    builder.row(
        InlineKeyboardButton(text="💡 Подсказки", callback_data="tips"),
        InlineKeyboardButton(text="📊 Грейды", callback_data="grades_info"),
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Топ рефереров", callback_data="leaderboard"),
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить контакты", callback_data="edit_profile"),
    )
    return builder.as_markup()


def get_profile_edit_keyboard() -> InlineKeyboardMarkup:
    """Keyboard for profile edit menu."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📧 Изменить email", callback_data="profile_edit_email"),
        InlineKeyboardButton(text="📱 Изменить номер", callback_data="profile_edit_phone"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_cabinet")
    )
    return builder.as_markup()


def get_back_to_cabinet_keyboard() -> InlineKeyboardMarkup:
    """Back to cabinet button."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_cabinet")
    )
    return builder.as_markup()


def get_tips_keyboard() -> InlineKeyboardMarkup:
    """Tips navigation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📱 Соцсети", callback_data="tip_social"),
        InlineKeyboardButton(text="💬 Мессенджеры", callback_data="tip_messengers"),
    )
    builder.row(
        InlineKeyboardButton(text="🌐 Форумы", callback_data="tip_forums"),
        InlineKeyboardButton(text="📝 Готовые тексты", callback_data="tip_templates"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_cabinet")
    )
    return builder.as_markup()


def get_admin_keyboard() -> InlineKeyboardMarkup:
    """Admin panel keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_broadcast"),
        InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
    )
    builder.row(
        InlineKeyboardButton(text="📥 Импорт из CRM", callback_data="admin_import_csv"),
        InlineKeyboardButton(text="📤 Экспорт CSV", callback_data="admin_export"),
    )
    builder.row(
        InlineKeyboardButton(text="📊 Управление грейдами", callback_data="admin_grades"),
    )
    builder.row(
        InlineKeyboardButton(text="📞 Кнопка «Связаться»", callback_data="admin_contacts"),
    )
    return builder.as_markup()


def get_confirm_broadcast_keyboard() -> InlineKeyboardMarkup:
    """Confirm broadcast keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_broadcast"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast"),
    )
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Cancel action keyboard."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_action")
    )
    return builder.as_markup()


# ============ Grades admin keyboards ============

def get_grades_list_keyboard(grades: list) -> InlineKeyboardMarkup:
    """Grades list: each grade as button, then Add and Back."""
    builder = InlineKeyboardBuilder()
    for g in grades:
        rewards_str = ", ".join(parse_rewards(g)) if parse_rewards(g) else "—"
        text = f"{g.referral_threshold} реф → {rewards_str}"
        if len(text) > 35:
            text = f"{g.referral_threshold} реф → …"
        builder.row(
            InlineKeyboardButton(text=text, callback_data=f"admin_grade_view_{g.id}")
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить грейд", callback_data="admin_grade_add"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_grades_back"),
    )
    return builder.as_markup()


def get_grade_manage_keyboard(grade_id: int) -> InlineKeyboardMarkup:
    """Single grade: Edit, Delete, Who reached, Back."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"admin_grade_edit_{grade_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"admin_grade_del_{grade_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Кто достиг", callback_data=f"admin_grade_users_{grade_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ К списку грейдов", callback_data="admin_grades"),
    )
    return builder.as_markup()


def get_grade_users_keyboard(grade_id: int, user_claimed_ids: list) -> InlineKeyboardMarkup:
    """List of users who reached grade; claim buttons. user_claimed_ids = list of user_id who already have claim."""
    builder = InlineKeyboardBuilder()
    # Buttons are added in handler per user
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_grade_view_{grade_id}"),
    )
    return builder.as_markup()


def get_back_to_grades_keyboard() -> InlineKeyboardMarkup:
    """Back to grades list."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ К списку грейдов", callback_data="admin_grades"),
    )
    return builder.as_markup()


# ============ Contacts admin keyboards ============

def get_contacts_manage_keyboard(visible: bool, entries: list) -> InlineKeyboardMarkup:
    """Клавиатура управления контактами: видимость, добавить, по каждому контакту — редактировать/удалить, назад."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🙈 Скрыть кнопку у пользователей" if visible else "👁 Показать кнопку у пользователей",
            callback_data="admin_contacts_toggle",
        )
    )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить контакт", callback_data="admin_contacts_add"),
    )
    for e in entries:
        builder.row(
            InlineKeyboardButton(text=f"✏️ {e.tg_username[:25]}…" if len(e.tg_username) > 25 else f"✏️ {e.tg_username}", callback_data=f"admin_contact_edit_{e.id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"admin_contact_del_{e.id}"),
        )
    builder.row(
        InlineKeyboardButton(text="◀️ В админ-панель", callback_data="admin_contacts_back"),
    )
    return builder.as_markup()


def get_contacts_cancel_keyboard() -> InlineKeyboardMarkup:
    """Отмена при добавлении/редактировании контакта."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_contacts"),
    )
    return builder.as_markup()
