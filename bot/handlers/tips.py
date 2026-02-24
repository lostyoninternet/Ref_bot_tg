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

<b>Маленький:</b>
В «Алабуга Политех» дают не просто учебу, а карьеру управленца с 1 курса. Хватит искать подработки, начни строить будущее уже сейчас!
<b>Регистрируйся по ссылке:</b> [ссылка]

<b>Средний:</b>
Учеба — это не только подготовка к ОГЭ, присмотрись к «Алабуга Политех». Там всё по-взрослому: командные турниры, наставники с реальных заводов и мощная практика. Это шанс проявить себя как лидера и получить профессию в топовом месте.
<b>Записаться на вступительные можно тут:</b> [ссылка]

<b>Большой:</b>
«Алабуга Политех» — это место для тех, кто хочет расти и создавать будущее. Здесь всё четко: сначала осваиваешь профессию, потом руководишь подразделением, а дальше — запускаешь целые заводы.

Это не просто колледж, а сообщество амбициозных людей и мечтателей. Если готов брать ответственность и строить карьеру в ИТ или промышленности, поступай к нам. Мы в тебя верим!

<b>Твой карьерный путь начинается по ссылке:</b> [ссылка]
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
        decrypt_username,
    )
    
    user_id = callback.from_user.id
    ref_link = ""
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, user_id)
        if user and user.email and user.phone:
            token_medium, token_campaign, token_content = await get_referral_tokens_for_user(session, user)
            if not token_medium and user.username:
                token_medium = decrypt_username(user.username) or user.username or ""
            if not token_campaign and user.email:
                token_campaign = decrypt_email(user.email) or user.email
            if not token_content and user.phone:
                token_content = decrypt_phone(user.phone) or user.phone
            if token_campaign and token_content:
                ref_link = settings.get_referral_link(
                    token_medium=token_medium or "",
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
