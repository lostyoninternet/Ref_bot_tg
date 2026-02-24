import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import settings
from bot.database import (
    get_session,
    get_user_by_telegram_id,
    get_user_referral_count,
    get_top_referrers,
    get_all_grades,
    get_user_grade_claims,
    get_referral_tokens_for_user,
    get_contacts_section_visible,
    get_contact_entries,
    decrypt_email,
    decrypt_phone,
    decrypt_username,
)
from bot.database.crud import (
    get_user_rank,
    update_user_email,
    update_user_phone,
    normalize_phone,
)
from bot.services.grade import GradeService, parse_rewards
from bot.keyboards.inline import (
    get_cabinet_keyboard,
    get_back_to_cabinet_keyboard,
    get_profile_edit_keyboard,
)
from bot.keyboards.reply import CONTACTS_BUTTON_TEXT


router = Router(name="cabinet")


class ProfileStates(StatesGroup):
    edit_email = State()
    edit_phone = State()


def _is_valid_email(s: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", (s or "").strip()))


def _is_valid_phone(s: str) -> bool:
    p = normalize_phone(s or "")
    return len(p) >= 10 and p.replace("+", "").isdigit()


@router.message(F.text == CONTACTS_BUTTON_TEXT)
async def show_contacts_list(message: Message):
    """Показать список контактов (тг_ник — за что отвечает). Видимость и список задаёт админ."""
    async with get_session() as session:
        visible = await get_contacts_section_visible(session)
        if not visible:
            await message.answer("Сейчас раздел контактов недоступен.")
            return
        entries = await get_contact_entries(session, active_only=True)
    if not entries:
        await message.answer("Пока нет контактов для связи. Обратись к организаторам.")
        return
    lines = ["📞 <b>Остались вопросы? Свяжись с нами:</b>\n"]
    for e in entries:
        nick = (e.tg_username or "").strip()
        desc = (e.description or "").strip()
        if nick.startswith("@"):
            link_username = nick[1:].strip()
            lines.append(f"• <a href=\"https://t.me/{link_username}\">{nick}</a> — {desc}")
        else:
            lines.append(f"• {nick} — {desc}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("cabinet"))
@router.message(F.text == "👤 Личный кабинет")
async def cmd_cabinet(message: Message):
    """Show personal cabinet."""
    await message.answer(
        "📋 Личный кабинет\n\n"
        "Выбери нужный раздел:",
        reply_markup=get_cabinet_keyboard()
    )


@router.callback_query(F.data == "back_to_cabinet")
async def back_to_cabinet(callback: CallbackQuery, state: FSMContext):
    """Return to cabinet menu (clear any FSM state)."""
    await state.clear()
    await callback.message.edit_text(
        "📋 Личный кабинет\n\n"
        "Выбери нужный раздел:",
        reply_markup=get_cabinet_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "my_stats")
async def show_my_stats(callback: CallbackQuery):
    """Show user statistics."""
    user_id = callback.from_user.id
    
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, user_id)
        referral_count = await get_user_referral_count(session, user_id)
        rank = await get_user_rank(session, user_id)
    
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    
    stats_text = (
        f"📊 <b>Твоя статистика</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}\n\n"
        f"👥 Рефералов: <b>{referral_count}</b>\n"
        f"🏆 Место в рейтинге: <b>#{rank}</b>\n"
    )
    
    await callback.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=get_back_to_cabinet_keyboard()
    )
    await callback.answer()


@router.message(Command("stats"))
@router.message(F.text == "📊 Статистика")
async def cmd_stats(message: Message):
    """Show user statistics via command."""
    user_id = message.from_user.id
    
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, user_id)
        referral_count = await get_user_referral_count(session, user_id)
        rank = await get_user_rank(session, user_id)
    
    if not user:
        await message.answer("❌ Ты ещё не зарегистрирован. Напиши /start")
        return
    
    stats_text = (
        f"📊 <b>Твоя статистика</b>\n\n"
        f"👤 ID: <code>{user_id}</code>\n"
        f"📅 Дата регистрации: {user.created_at.strftime('%d.%m.%Y')}\n\n"
        f"👥 Рефералов: <b>{referral_count}</b>\n"
        f"🏆 Место в рейтинге: <b>#{rank}</b>\n"
    )
    
    await message.answer(stats_text, parse_mode="HTML")


async def _get_user_referral_link(session, user) -> str | None:
    """Строит UTM-ссылку: при включённом шифровании — короткие токены (ник, почта, телефон), иначе — открытые данные."""
    if not user or not user.email or not user.phone:
        return None
    token_medium, token_campaign, token_content = await get_referral_tokens_for_user(session, user)
    if not token_medium and user.username:
        token_medium = decrypt_username(user.username) or user.username or ""
    if not token_campaign and user.email:
        token_campaign = decrypt_email(user.email) or user.email
    if not token_content and user.phone:
        token_content = decrypt_phone(user.phone) or user.phone
    if not token_campaign or not token_content:
        return None
    return settings.get_referral_link(
        token_medium=token_medium or "",
        token_campaign=token_campaign,
        token_content=token_content,
    )


@router.callback_query(F.data == "my_link")
async def show_my_link(callback: CallbackQuery):
    """Show user's referral link (UTM: short tokens in campaign/content, not raw email/phone)."""
    user_id = callback.from_user.id
    
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, user_id)
        ref_link = await _get_user_referral_link(session, user)
    
    if not user or not user.email or not user.phone:
        await callback.message.edit_text(
            "🔗 <b>Реферальная ссылка</b>\n\n"
            "Чтобы получить ссылку, нужно указать <b>email</b> и <b>номер телефона</b>.\n\n"
            "Напиши /start и пройди регистрацию до конца (email + контакт).",
            parse_mode="HTML",
            reply_markup=get_back_to_cabinet_keyboard()
        )
        await callback.answer()
        return
    
    link_text = (
        f"🔗 <b>Твоя реферальная ссылка</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        "👆 Нажми на ссылку, чтобы скопировать.\n\n"
        "📢 <b>Как это работает:</b>\n"
        "1. Отправь эту ссылку другу\n"
        "2. Друг регистрируется на очный этап через неё\n"
        "3. Когда друг пройдёт очный этап — тебе засчитается реферал\n\n"
        "📊 Достигай рубежей и получай награды! Смотри раздел «Грейды»."
    )
    
    await callback.message.edit_text(
        link_text,
        parse_mode="HTML",
        reply_markup=get_back_to_cabinet_keyboard()
    )
    await callback.answer()


@router.message(Command("mylink"))
@router.message(F.text == "🔗 Моя ссылка")
async def cmd_mylink(message: Message):
    """Show referral link via command."""
    user_id = message.from_user.id
    
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, user_id)
    
    ref_link = _get_user_referral_link(user)
    
    if not user or not user.email or not user.phone:
        await message.answer(
            "🔗 Чтобы получить реферальную ссылку, укажи email и номер телефона. Напиши /start и пройди регистрацию."
        )
        return
    
    link_text = (
        f"🔗 <b>Твоя реферальная ссылка</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        "👆 Нажми на ссылку, чтобы скопировать.\n\n"
        "📌 Друг должен зарегистрироваться по этой ссылке и пройти очный этап. "
        "После этого тебе засчитается реферал — достигай рубежей и получай награды!"
    )
    
    await message.answer(link_text, parse_mode="HTML")


@router.callback_query(F.data == "leaderboard")
async def show_leaderboard(callback: CallbackQuery):
    """Show top referrers."""
    async with get_session() as session:
        top_users = await get_top_referrers(session, limit=10)
    
    if not top_users:
        await callback.message.edit_text(
            "🏆 <b>Топ рефереров</b>\n\n"
            "Пока никто не пригласил рефералов.\n"
            "Будь первым! 🚀",
            parse_mode="HTML",
            reply_markup=get_back_to_cabinet_keyboard()
        )
        await callback.answer()
        return
    
    leaderboard_text = "🏆 <b>Топ-10 рефереров</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, (user, count) in enumerate(top_users, 1):
        medal = medals[i-1] if i <= 3 else f"{i}."
        name = user.first_name or decrypt_username(user.username) or f"User {user.telegram_id}"
        leaderboard_text += f"{medal} {name} — <b>{count}</b> рефералов\n"
    
    await callback.message.edit_text(
        leaderboard_text,
        parse_mode="HTML",
        reply_markup=get_back_to_cabinet_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "grades_info")
@router.message(Command("grades"))
@router.message(F.text == "📊 Грейды")
async def show_grades_info(callback_or_message: CallbackQuery | Message):
    """Show user's grades: table of thresholds, rewards, status (achieved/locked/issued)."""
    is_callback = isinstance(callback_or_message, CallbackQuery)
    user_id = callback_or_message.from_user.id

    async with get_session() as session:
        referral_count = await get_user_referral_count(session, user_id)
        grades = await get_all_grades(session)
        claims = await get_user_grade_claims(session, user_id)
    claimed_grade_ids = {c.grade_id for c in claims}

    grade_svc = GradeService()
    next_grade = await grade_svc.get_next_grade(referral_count)

    lines = [
        f"📊 <b>Твои грейды</b>\n",
        f"👥 Рефералов: <b>{referral_count}</b>\n",
    ]
    if not grades:
        lines.append("\nПока нет рубежей. Следи за обновлениями!")
    else:
        for g in grades:
            rewards_str = ", ".join(parse_rewards(g))
            if referral_count >= g.referral_threshold:
                if g.id in claimed_grade_ids:
                    status = "✅ Выдано"
                else:
                    status = "✅ Достигнут (ожидает выдачи)"
                lines.append(f"\n• <b>{g.referral_threshold} реф</b> → {rewards_str} — {status}")
            else:
                need = g.referral_threshold - referral_count
                lines.append(f"\n• <b>{g.referral_threshold} реф</b> → {rewards_str} — 🔒 Ещё {need} реф.")
        if next_grade:
            need = next_grade.referral_threshold - referral_count
            lines.append(f"\n\n🎯 До следующего рубежа: <b>{need}</b> рефералов.")

    text = "".join(lines)

    if is_callback:
        await callback_or_message.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_back_to_cabinet_keyboard()
        )
        await callback_or_message.answer()
    else:
        await callback_or_message.answer(text, parse_mode="HTML")


# ============ Изменить контакты (email / телефон) ============

@router.callback_query(F.data == "edit_profile")
async def show_edit_profile(callback: CallbackQuery):
    """Show profile edit menu (email / phone)."""
    user_id = callback.from_user.id
    async with get_session() as session:
        user = await get_user_by_telegram_id(session, user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    plain_email = decrypt_email(user.email)
    plain_phone = decrypt_phone(user.phone)
    text = (
        "✏️ <b>Изменить контакты</b>\n\n"
        f"📧 Email: <code>{plain_email or '—'}</code>\n"
        f"📱 Телефон: <code>{plain_phone or '—'}</code>\n\n"
        "Выбери, что изменить. От этого зависит твоя реферальная ссылка."
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_profile_edit_keyboard()
    )
    await callback.answer()


@router.callback_query(F.data == "profile_edit_email")
async def start_edit_email(callback: CallbackQuery, state: FSMContext):
    """Ask for new email."""
    await state.set_state(ProfileStates.edit_email)
    await callback.message.edit_text(
        "📧 Введи новый <b>email</b>:\n\nПример: example@mail.ru",
        parse_mode="HTML",
        reply_markup=get_back_to_cabinet_keyboard()
    )
    await callback.answer()


@router.message(ProfileStates.edit_email, F.text)
async def process_edit_email(message: Message, state: FSMContext):
    """Save new email."""
    email = (message.text or "").strip()
    if not _is_valid_email(email):
        await message.answer("❌ Неверный формат email. Попробуй ещё раз.")
        return
    async with get_session() as session:
        await update_user_email(session, message.from_user.id, email)
    await state.clear()
    await message.answer(
        f"✅ Email обновлён: <code>{email}</code>\n\nРеферальная ссылка перегенерирована.",
        parse_mode="HTML",
        reply_markup=get_cabinet_keyboard()
    )


@router.callback_query(F.data == "profile_edit_phone")
async def start_edit_phone(callback: CallbackQuery, state: FSMContext):
    """Ask for new phone (share contact or type)."""
    await state.set_state(ProfileStates.edit_phone)
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="📱 Поделиться контактом", request_contact=True))
    await callback.message.edit_text(
        "📱 Укажи новый <b>номер телефона</b>:\n\n"
        "Нажми кнопку ниже или напиши номер вручную.",
        parse_mode="HTML",
        reply_markup=get_back_to_cabinet_keyboard()
    )
    await callback.message.answer(
        "Отправь номер:",
        reply_markup=kb.as_markup(resize_keyboard=True)
    )
    await callback.answer()


@router.message(ProfileStates.edit_phone, F.contact)
async def process_edit_phone_contact(message: Message, state: FSMContext):
    """Save phone from shared contact."""
    if message.contact.user_id != message.from_user.id:
        await message.answer("Поделись своим контактом.")
        return
    phone = message.contact.phone_number or ""
    async with get_session() as session:
        await update_user_phone(session, message.from_user.id, phone)
    await state.clear()
    await message.answer(
        f"✅ Номер обновлён: <code>{normalize_phone(phone)}</code>\n\nРеферальная ссылка перегенерирована.",
        parse_mode="HTML",
        reply_markup=get_cabinet_keyboard()
    )


@router.message(ProfileStates.edit_phone, F.text)
async def process_edit_phone_text(message: Message, state: FSMContext):
    """Save phone typed manually."""
    phone = (message.text or "").strip()
    if not _is_valid_phone(phone):
        await message.answer("❌ Введи корректный номер (например: +79001234567).")
        return
    async with get_session() as session:
        await update_user_phone(session, message.from_user.id, phone)
    await state.clear()
    await message.answer(
        f"✅ Номер обновлён: <code>{normalize_phone(phone)}</code>\n\nРеферальная ссылка перегенерирована.",
        parse_mode="HTML",
        reply_markup=get_cabinet_keyboard()
    )
