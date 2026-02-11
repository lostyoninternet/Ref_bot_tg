from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from bot.config import settings
from bot.keyboards.inline import get_tips_keyboard, get_back_to_cabinet_keyboard


router = Router(name="tips")


# Tips content
TIPS_SOCIAL = """
📱 <b>Соцсети</b>

Где размещать свою ссылку:

<b>TikTok:</b>
• В описании профиля
• В видео про подготовку к поступлению
• В комментариях к образовательным видео

<b>ВКонтакте:</b>
• В статусе
• В постах про выбор ВУЗа
• В группах для абитуриентов (где разрешено)

<b>Telegram:</b>
• В чатах для абитуриентов
• В личных сообщениях одноклассникам
• В школьных группах
"""

TIPS_MESSENGERS = """
💬 <b>Мессенджеры</b>

Как приглашать через личные сообщения:

<b>Правильный подход:</b>
✅ Расскажи про возможность поступления в «Алабуга Политех»
✅ Объясни, что очный этап бесплатный
✅ Подчеркни, что это реальный шанс для поступления

<b>Чего избегать:</b>
❌ Не спамь массовыми рассылками
❌ Не отправляй просто ссылку без пояснения
❌ Не давите на людей

<b>Пример сообщения:</b>
"Привет! Я участвую в программе для поступления в «Алабуга Политех». Там есть очный этап, после которого можно попасть в закрытое сообщество и участвовать в реферальной программе с наградами за рубежи. Если интересует поступление — регистрируйся: [твоя ссылка]"
"""

TIPS_FORUMS = """
🌐 <b>Форумы и сообщества</b>

Где искать аудиторию:

<b>Тематические форумы:</b>
• Найди форумы по теме канала
• Будь активным участником
• Размещай ссылку в подписи

<b>Reddit:</b>
• Ищи подходящие subreddits
• Соблюдай правила сообщества
• Не спамь — делись ценностью

<b>Discord-серверы:</b>
• Вступи в тематические сообщества
• Общайся и помогай людям
• Упоминай о наградах за рубежи уместно

<b>Важно:</b>
Всегда читай правила сообщества перед публикацией ссылок!
"""

TIPS_TEMPLATES = """
📝 <b>Готовые тексты для приглашения</b>

<b>Короткий вариант:</b>
"Привет! Хочешь учиться в «Алабуга Политех»? Регистрируйся на очный этап [ссылка]"

<b>Средний вариант:</b>
"Я хочу стать студентом «Алабуга Политех» и прохожу программу поступления. Хочешь узнать подробнее? Регистрируйся на очный этап по моей ссылке. После прохождения можно получить крутые призы!"

<b>Подробный вариант:</b>
"Привет! «Алабуга Политех» проводит очный этап постпуления для абитуриентов. После прохождения можно учавствовать в реферальной программе и получать награды (фирменный мерч от «Алабуги» и т.д.) Чем больше друзей пройдут очный этап — тем больше призов! Регистрируйся"
"""


@router.message(Command("tips"))
@router.message(F.text == "💡 Подсказки")
async def cmd_tips(message: Message):
    """Show tips menu."""
    await message.answer(
        "💡 <b>Подсказки по привлечению рефералов</b>\n\n"
        "Выбери категорию:",
        parse_mode="HTML",
        reply_markup=get_tips_keyboard()
    )


@router.callback_query(F.data == "tips")
async def show_tips_menu(callback: CallbackQuery):
    """Show tips menu from cabinet."""
    await callback.message.edit_text(
        "💡 <b>Подсказки по привлечению рефералов</b>\n\n"
        "Выбери категорию:",
        parse_mode="HTML",
        reply_markup=get_tips_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "tip_social")
async def show_tip_social(callback: CallbackQuery):
    """Show social media tips."""
    await callback.message.edit_text(
        TIPS_SOCIAL,
        parse_mode="HTML",
        reply_markup=get_back_to_tips_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "tip_messengers")
async def show_tip_messengers(callback: CallbackQuery):
    """Show messenger tips."""
    await callback.message.edit_text(
        TIPS_MESSENGERS,
        parse_mode="HTML",
        reply_markup=get_back_to_tips_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "tip_forums")
async def show_tip_forums(callback: CallbackQuery):
    """Show forum tips."""
    await callback.message.edit_text(
        TIPS_FORUMS,
        parse_mode="HTML",
        reply_markup=get_back_to_tips_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "tip_templates")
async def show_tip_templates(callback: CallbackQuery):
    """Show text templates with real UTM referral link (tokens in UTM, not raw PII)."""
    from bot.database import (
        get_session,
        get_user_by_telegram_id,
        get_referral_tokens_for_user,
        decrypt_email,
        decrypt_phone,
    )
    
    user_id = callback.from_user.id
    ref_link = ""
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, user_id)
        if user and user.email and user.phone:
            token_campaign, token_content = await get_referral_tokens_for_user(session, user)
            if not token_campaign and user.email:
                token_campaign = decrypt_email(user.email) or user.email
            if not token_content and user.phone:
                token_content = decrypt_phone(user.phone) or user.phone
            if token_campaign and token_content:
                ref_link = settings.get_referral_link(
                    username=user.username,
                    token_campaign=token_campaign,
                    token_content=token_content,
                )
    if not ref_link or (user and (not user.email or not user.phone)):
        ref_link = "[укажи email и телефон в /start — тогда здесь появится твоя ссылка]"
    
    # Replace [ссылка] with actual UTM link
    text = TIPS_TEMPLATES.replace("[ссылка]", ref_link)
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_back_to_tips_keyboard()
    )
    await callback.answer()


def get_back_to_tips_keyboard():
    """Get keyboard to go back to tips menu."""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="◀️ К подсказкам", callback_data="tips")
    )
    builder.row(
        InlineKeyboardButton(text="🏠 В кабинет", callback_data="back_to_cabinet")
    )
    return builder.as_markup()
