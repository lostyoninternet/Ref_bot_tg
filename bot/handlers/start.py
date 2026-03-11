from pathlib import Path
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import re

from bot.config import settings
from bot.database import get_session, get_or_create_user, get_user_by_telegram_id, update_user_subscription, get_contacts_section_visible
from bot.database.crud import update_user_email, update_user_phone, normalize_phone
from bot.keyboards.inline import get_cabinet_keyboard
from bot.keyboards.reply import get_main_menu_keyboard, get_admin_reply_keyboard
from bot.services.subscription import check_subscription


router = Router(name="start")


class RegistrationStates(StatesGroup):
    """States for registration flow."""
    waiting_email = State()
    waiting_phone = State()


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, state: FSMContext):
    """Handle /start command."""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    # Check if user is admin
    is_admin = user_id in settings.ADMIN_IDS
    
    # Check subscription to private channel (= passed the event)
    is_subscribed = await check_subscription(bot, user_id, settings.CHANNEL_ID)
    
    if not is_subscribed:
        # Пользователь ещё не в закрытом канале — только текст, без кнопок
        async with get_session() as session:
            await get_or_create_user(
                session,
                telegram_id=user_id,
                username=username,
                first_name=first_name,
                is_admin=is_admin,
            )
        await message.answer(
            f"👋 Привет, {first_name}!\n\n"
            "Ты попал в бот реферальной программы.\n\n"
            "⛔️ Обрати внимание:\n"
            "Сейчас функции бота для тебя закрыты. Инструменты для приглашения друзей доступны только участникам нашего клуба.\n",
            parse_mode="HTML",
        )
        return
    
    # User is subscribed = passed the event
    async with get_session() as session:
        user, created = await get_or_create_user(
            session,
            telegram_id=user_id,
            username=username,
            first_name=first_name,
            is_admin=is_admin,
        )
        await update_user_subscription(session, user_id, True)
        
        # Check if user has email and phone
        has_email = bool(user.email)
        has_phone = bool(user.phone)
    
    if created or not has_email:
        # New user or user without email - request email
        await state.set_state(RegistrationStates.waiting_email)
        
        await message.answer(
            f"🎉 Отлично, {first_name or 'друг'}!\n\n"
            "Очный этап пройден. Для участия в реферальной программе и получения наград за рубежи "
            "введи свой <b>email</b>, который указывал при регистрации на сайте.\n\n"
            "Это нужно для связки анкеты с ботом.",
            parse_mode="HTML"
        )
        return
    
    if not has_phone:
        # Email есть, номера нет — просим контакт
        await state.set_state(RegistrationStates.waiting_phone)
        kb = ReplyKeyboardBuilder()
        kb.row(KeyboardButton(text="📱 Поделиться контактом", request_contact=True))
        await message.answer(
            "Теперь укажи <b>номер телефона</b>.\n\n"
            "Нажми кнопку ниже, чтобы поделиться контактом, или напиши номер вручную.",
            parse_mode="HTML",
            reply_markup=kb.as_markup(resize_keyboard=True)
        )
        return
    
    # Existing user with email and phone - show cabinet
    async with get_session() as session:
        show_contacts = await get_contacts_section_visible(session)
    reply_kb = get_admin_reply_keyboard() if is_admin else get_main_menu_keyboard(show_contacts=show_contacts)
    await message.answer(
        f"👋 С возвращением, {first_name}!\n\n"
        "Открывай личный кабинет и приглашай друзей на очный этап!",
        reply_markup=reply_kb
    )
    await message.answer(
        "📋 Личный кабинет:",
        reply_markup=get_cabinet_keyboard()
    )


@router.message(RegistrationStates.waiting_email)
async def process_email(message: Message, state: FSMContext, bot: Bot):
    """Process email input, then ask for phone."""
    email = message.text.strip() if message.text else ""
    
    if not is_valid_email(email):
        await message.answer(
            "❌ Неверный формат email. Попробуй ещё раз.\n\n"
            "Пример: example@mail.ru"
        )
        return
    
    user_id = message.from_user.id
    
    async with get_session() as session:
        await update_user_email(session, user_id, email)
    
    await state.set_state(RegistrationStates.waiting_phone)
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="📱 Поделиться контактом", request_contact=True))
    
    await message.answer(
        f"✅ Email <code>{email}</code> сохранён!\n\n"
        "Теперь укажи <b>номер телефона</b> — он будет в твоей реферальной ссылке.\n\n"
        "Нажми кнопку ниже или напиши номер вручную.",
        parse_mode="HTML",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )


def is_valid_phone(phone: str) -> bool:
    """Check if phone looks valid (digits, maybe +)."""
    cleaned = normalize_phone(phone)
    return len(cleaned) >= 10 and cleaned.replace("+", "").isdigit()


@router.message(RegistrationStates.waiting_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext, bot: Bot):
    """Process shared contact (phone from Telegram)."""
    phone = message.contact.phone_number or ""
    if message.contact.user_id != message.from_user.id:
        await message.answer("Пожалуйста, поделись именно своим контактом.")
        return
    await _save_phone_and_finish(message, state, phone, bot)


@router.message(RegistrationStates.waiting_phone, F.text)
async def process_phone_text(message: Message, state: FSMContext, bot: Bot):
    """Process phone typed manually."""
    phone = (message.text or "").strip()
    if not is_valid_phone(phone):
        await message.answer(
            "❌ Введи корректный номер (например: +79001234567 или 89001234567)."
        )
        return
    await _save_phone_and_finish(message, state, phone, bot)


async def _save_phone_and_finish(message: Message, state: FSMContext, phone: str, bot: Bot):
    """Save phone to DB and show cabinet."""
    user_id = message.from_user.id
    
    async with get_session() as session:
        await update_user_phone(session, user_id, phone)
    
    await state.clear()
    is_admin = user_id in settings.ADMIN_IDS
    async with get_session() as session:
        show_contacts = await get_contacts_section_visible(session)
    reply_kb = get_admin_reply_keyboard() if is_admin else get_main_menu_keyboard(show_contacts=show_contacts)

    # 1) Первое сообщение — только текст
    await message.answer(
        f"✅ Номер <code>{normalize_phone(phone)}</code> сохранён!\n\n"
        "Теперь можно участвовать в реферальной программе.\n\n"
        "📌 <b>Твоя задача:</b>\n"
        "1. Получаешь свою реферальную ссылку\n"
        "2. Приглашаешь друзей на очный этап по своей ссылке\n"
        "3. За каждого прошедшего тебе начисляются баллы\n"
        "4. Набираешь больше баллов — повышаешь грейд!\n\n"
        "🎁 Каждый новый грейд = классный лимитированный мерч от «Алабуги».\n\n"
        "Самое приятное — уже за 5 человек ты переходишь на 1 грейд и получаешь классный рюкзак 🎒 (фото ниже).",
        parse_mode="HTML",
        reply_markup=reply_kb,
    )

    # 2) Второе сообщение — стикер из стикерпака или картинка рюкзака
    if settings.WELCOME_STICKER_FILE_ID:
        await message.answer_sticker(sticker=settings.WELCOME_STICKER_FILE_ID)
    else:
        backpack_path = Path(__file__).resolve().parent.parent.parent / "img" / "backpack.png"
        if backpack_path.is_file():
            await message.answer_photo(photo=FSInputFile(backpack_path))

    # 3) Третье сообщение — текст и кнопка кабинета
    await message.answer(
        "Это не розыгрыш — ты точно знаешь, сколько нужно пригласить, чтобы получить конкретный приз.\n\n"
        "Сколько друзей приведёшь — такой грейд и закрепишь за собой.\n\n"
        "Готов забрать свой рюкзак и пойти дальше?",
        reply_markup=get_cabinet_keyboard(),
    )


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, bot: Bot, state: FSMContext):
    """Handle subscription check button."""
    user_id = callback.from_user.id
    first_name = callback.from_user.first_name
    
    is_subscribed = await check_subscription(bot, user_id, settings.CHANNEL_ID)
    
    if not is_subscribed:
        await callback.answer(
            "❌ Ты ещё не в закрытом канале.\n"
            "Подпишись после прохождения очного этапа.",
            show_alert=True
        )
        return
    
    # Update subscription status
    async with get_session() as session:
        await update_user_subscription(session, user_id, True)
        user = await get_user_by_telegram_id(session, user_id)
        has_email = bool(user.email) if user else False
        has_phone = bool(user.phone) if user else False
    
    await callback.answer("✅ Подписка подтверждена!")
    
    # Delete subscription message
    await callback.message.delete()
    
    if not has_email:
        await state.set_state(RegistrationStates.waiting_email)
        await callback.message.answer(
            f"🎉 Отлично, {first_name or 'друг'}! Добро пожаловать!\n\n"
            "Для участия в реферальной программе введи свой <b>email</b>, "
            "который указывал при регистрации на очный этап.",
            parse_mode="HTML"
        )
    elif not has_phone:
        await state.set_state(RegistrationStates.waiting_phone)
        kb = ReplyKeyboardBuilder()
        kb.row(KeyboardButton(text="📱 Поделиться контактом", request_contact=True))
        await callback.message.answer(
            "Укажи <b>номер телефона</b>: нажми кнопку или напиши номер вручную.",
            parse_mode="HTML",
            reply_markup=kb.as_markup(resize_keyboard=True)
        )
    else:
        is_admin = user_id in settings.ADMIN_IDS
        async with get_session() as session:
            show_contacts = await get_contacts_section_visible(session)
        reply_kb = get_admin_reply_keyboard() if is_admin else get_main_menu_keyboard(show_contacts=show_contacts)
        await callback.message.answer(
            "🎉 Отлично! Подписка подтверждена.\n\n"
            "Теперь у тебя есть доступ ко всем функциям бота.",
            reply_markup=reply_kb
        )
        await callback.message.answer(
            "📋 Личный кабинет:",
            reply_markup=get_cabinet_keyboard()
        )
