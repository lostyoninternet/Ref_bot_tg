import csv
import io
from datetime import datetime
from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import settings
from bot.database import (
    get_session,
    get_all_users,
    get_user_referral_count,
    get_user_by_telegram_id,
    get_all_grades,
    get_grade_by_id,
    create_grade,
    update_grade,
    delete_grade,
    get_users_for_grade,
    create_grade_claim,
    has_grade_claim,
    get_referrer_by_utm_tokens,
    decrypt_email,
    decrypt_phone,
    get_all_utm_tokens_for_key_export,
)
from bot.database.crud import (
    get_total_users_count,
    get_total_referrals_count,
    link_referral_by_email,
    get_pending_users,
    get_user_by_email_and_phone,
    get_user_by_email,
)
from bot.keyboards.inline import (
    get_admin_keyboard,
    get_confirm_broadcast_keyboard,
    get_cancel_keyboard,
    get_grades_list_keyboard,
    get_grade_manage_keyboard,
    get_back_to_grades_keyboard,
)
from bot.services.broadcast import BroadcastService
from bot.services.grade import GradeService


router = Router(name="admin")


class AdminStates(StatesGroup):
    """Admin FSM states."""
    waiting_broadcast_message = State()  # text or photo+caption
    waiting_csv_file = State()
    waiting_grade_threshold = State()
    waiting_grade_rewards = State()
    waiting_grade_edit_rewards = State()  # data: grade_id


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id in settings.ADMIN_IDS


@router.message(Command("admin"))
@router.message(F.text == "⚙️ Админ-панель")
async def cmd_admin(message: Message):
    """Show admin panel."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У тебя нет доступа к админ-панели.")
        return
    
    await message.answer(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выбери действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    """Show admin statistics."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    async with get_session() as session:
        total_users = await get_total_users_count(session)
        total_referrals = await get_total_referrals_count(session)
    
    stats_text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{total_users}</b>\n"
        f"🔗 Всего рефералов: <b>{total_referrals}</b>\n"
    )
    
    await callback.message.edit_text(
        stats_text,
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer()


# ============ Grades management ============

@router.callback_query(F.data == "admin_grades")
@router.callback_query(F.data == "admin_grades_back")
async def admin_grades_list(callback: CallbackQuery):
    """Show list of grades or back to admin panel."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    if callback.data == "admin_grades_back":
        await callback.message.edit_text(
            "⚙️ <b>Админ-панель</b>\n\nВыбери действие:",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        await callback.answer()
        return
    async with get_session() as session:
        grades = await get_all_grades(session)
    if not grades:
        text = "📊 <b>Грейды</b>\n\nПока нет ни одного рубежа.\nДобавь грейд — укажи количество рефералов и награды."
    else:
        text = "📊 <b>Грейды</b>\n\nВыбери грейд для редактирования или добавь новый:"
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_grades_list_keyboard(grades)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_grade_view_"))
async def admin_grade_view(callback: CallbackQuery):
    """Show single grade detail."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        grade_id = int(callback.data.replace("admin_grade_view_", ""))
    except ValueError:
        await callback.answer("Ошибка", show_alert=True)
        return
    async with get_session() as session:
        grade = await get_grade_by_id(session, grade_id)
    if not grade:
        await callback.answer("Грейд не найден", show_alert=True)
        return
    from bot.services.grade import parse_rewards
    rewards_str = ", ".join(parse_rewards(grade))
    text = (
        f"📊 <b>Рубеж: {grade.referral_threshold} рефералов</b>\n\n"
        f"Награды: {rewards_str or '—'}"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_grade_manage_keyboard(grade_id)
    )
    await callback.answer()


@router.callback_query(F.data == "admin_grade_add")
async def admin_grade_add_start(callback: CallbackQuery, state: FSMContext):
    """Start add grade: ask threshold."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    await state.set_state(AdminStates.waiting_grade_threshold)
    await callback.message.edit_text(
        "📊 <b>Добавить грейд</b>\n\nВведи <b>рубеж</b> — количество рефералов (число):\nНапример: 10",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.waiting_grade_threshold, F.text)
async def admin_grade_process_threshold(message: Message, state: FSMContext):
    """Process threshold, ask rewards."""
    if not is_admin(message.from_user.id):
        return
    try:
        threshold = int(message.text.strip())
    except ValueError:
        await message.answer("Введи число (например: 10).")
        return
    if threshold < 1:
        await message.answer("Рубеж должен быть не меньше 1.")
        return
    await state.update_data(grade_threshold=threshold)
    await state.set_state(AdminStates.waiting_grade_rewards)
    await message.answer(
        f"📊 Рубеж: <b>{threshold} рефералов</b>\n\n"
        "Введи <b>награды</b> через запятую:\nНапример: мерч, тд",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )


@router.message(AdminStates.waiting_grade_rewards, F.text)
async def admin_grade_process_rewards(message: Message, state: FSMContext):
    """Create grade and show list."""
    if not is_admin(message.from_user.id):
        return
    rewards_raw = [p.strip() for p in (message.text or "").split(",") if p.strip()]
    if not rewards_raw:
        await message.answer("Введи хотя бы одну награду через запятую.")
        return
    data = await state.get_data()
    threshold = data.get("grade_threshold", 0)
    async with get_session() as session:
        grade = await create_grade(session, threshold, rewards_raw)
    await state.clear()
    await message.answer(
        f"✅ Грейд добавлен: <b>{threshold} реф</b> → {', '.join(rewards_raw)}",
        parse_mode="HTML",
        reply_markup=get_back_to_grades_keyboard()
    )


@router.callback_query(F.data.startswith("admin_grade_edit_"))
async def admin_grade_edit_start(callback: CallbackQuery, state: FSMContext):
    """Start edit grade: ask new rewards."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        grade_id = int(callback.data.replace("admin_grade_edit_", ""))
    except ValueError:
        await callback.answer("Ошибка", show_alert=True)
        return
    async with get_session() as session:
        grade = await get_grade_by_id(session, grade_id)
    if not grade:
        await callback.answer("Грейд не найден", show_alert=True)
        return
    from bot.services.grade import parse_rewards
    current = ", ".join(parse_rewards(grade))
    await state.update_data(grade_edit_id=grade_id)
    await state.set_state(AdminStates.waiting_grade_edit_rewards)
    await callback.message.edit_text(
        f"✏️ <b>Редактировать грейд</b>\n\n"
        f"Рубеж: {grade.referral_threshold} реф (не меняется).\n\n"
        f"Текущие награды: {current or '—'}\n\n"
        "Введи новые награды через запятую:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.waiting_grade_edit_rewards, F.text)
async def admin_grade_edit_process(message: Message, state: FSMContext):
    """Save edited rewards."""
    if not is_admin(message.from_user.id):
        return
    rewards_raw = [p.strip() for p in (message.text or "").split(",") if p.strip()]
    if not rewards_raw:
        await message.answer("Введи хотя бы одну награду через запятую.")
        return
    data = await state.get_data()
    grade_id = data.get("grade_edit_id")
    await state.clear()
    if not grade_id:
        await message.answer("Ошибка. Начни заново.", reply_markup=get_admin_keyboard())
        return
    async with get_session() as session:
        await update_grade(session, grade_id, rewards=rewards_raw)
    await message.answer(
        f"✅ Награды грейда обновлены: {', '.join(rewards_raw)}",
        parse_mode="HTML",
        reply_markup=get_back_to_grades_keyboard()
    )


@router.callback_query(F.data.startswith("admin_grade_del_"))
async def admin_grade_delete(callback: CallbackQuery):
    """Delete grade."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        grade_id = int(callback.data.replace("admin_grade_del_", ""))
    except ValueError:
        await callback.answer("Ошибка", show_alert=True)
        return
    async with get_session() as session:
        ok = await delete_grade(session, grade_id)
    if not ok:
        await callback.answer("Грейд не найден", show_alert=True)
        return
    async with get_session() as session:
        grades = await get_all_grades(session)
    await callback.message.edit_text(
        "📊 <b>Грейды</b>\n\nГрейд удалён.",
        parse_mode="HTML",
        reply_markup=get_grades_list_keyboard(grades)
    )
    await callback.answer("Грейд удалён")


@router.callback_query(F.data.startswith("admin_grade_users_"))
async def admin_grade_users(callback: CallbackQuery):
    """Show users who reached this grade, with Claim buttons."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    try:
        grade_id = int(callback.data.replace("admin_grade_users_", ""))
    except ValueError:
        await callback.answer("Ошибка", show_alert=True)
        return
    async with get_session() as session:
        grade = await get_grade_by_id(session, grade_id)
        if not grade:
            await callback.answer("Грейд не найден", show_alert=True)
            return
        users_with_count = await get_users_for_grade(session, grade_id)
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder()
        for user, ref_count in users_with_count:
            has_claim = await has_grade_claim(session, user.telegram_id, grade_id)
            name = (user.first_name or user.username or f"id{user.telegram_id}")[:25]
            if has_claim:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{name} — ✅ Выдано",
                        callback_data="admin_noop"
                    )
                )
            else:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{name} — Выдать",
                        callback_data=f"admin_gc_{grade_id}_{user.telegram_id}"
                    )
                )
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_grade_view_{grade_id}")
        )
    from bot.services.grade import parse_rewards
    rewards_str = ", ".join(parse_rewards(grade))
    text = (
        f"👥 <b>Кто достиг: {grade.referral_threshold} реф</b>\n"
        f"Награды: {rewards_str}\n\n"
        f"Всего: {len(users_with_count)} чел."
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_noop")
async def admin_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("admin_gc_"))
async def admin_grade_claim(callback: CallbackQuery):
    """Mark reward as issued for user."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    parts = callback.data.replace("admin_gc_", "").split("_")
    if len(parts) != 2:
        await callback.answer("Ошибка", show_alert=True)
        return
    try:
        grade_id = int(parts[0])
        user_id = int(parts[1])
    except ValueError:
        await callback.answer("Ошибка", show_alert=True)
        return
    async with get_session() as session:
        if await has_grade_claim(session, user_id, grade_id):
            await callback.answer("Уже выдано", show_alert=True)
            return
        await create_grade_claim(session, user_id, grade_id, issued_by_admin=True)
    await callback.answer("Отмечено: награда выдана", show_alert=True)
    # Refresh the "who reached" list
    async with get_session() as session:
        grade = await get_grade_by_id(session, grade_id)
        if not grade:
            return
        users_with_count = await get_users_for_grade(session, grade_id)
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        builder = InlineKeyboardBuilder()
        for user, ref_count in users_with_count:
            has_claim = await has_grade_claim(session, user.telegram_id, grade_id)
            name = (user.first_name or user.username or f"id{user.telegram_id}")[:25]
            if has_claim:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{name} — ✅ Выдано",
                        callback_data="admin_noop"
                    )
                )
            else:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{name} — Выдать",
                        callback_data=f"admin_gc_{grade_id}_{user.telegram_id}"
                    )
                )
        builder.row(
            InlineKeyboardButton(text="◀️ Назад", callback_data=f"admin_grade_view_{grade_id}")
        )
    from bot.services.grade import parse_rewards
    rewards_str = ", ".join(parse_rewards(grade))
    text = (
        f"👥 <b>Кто достиг: {grade.referral_threshold} реф</b>\n"
        f"Награды: {rewards_str}\n\n"
        f"Всего: {len(users_with_count)} чел."
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


# ============ Broadcast ============

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    """Start broadcast process."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_broadcast_message)
    
    await callback.message.edit_text(
        "📨 <b>Рассылка</b>\n\n"
        "Отправь текст или <b>картинку с подписью</b> — разошлём всем.\n\n"
        "Поддерживается HTML в тексте.",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.waiting_broadcast_message, F.photo)
async def process_broadcast_photo(message: Message, state: FSMContext):
    """Process broadcast with photo."""
    if not is_admin(message.from_user.id):
        return
    photo_id = message.photo[-1].file_id
    caption = message.caption or ""
    await state.update_data(broadcast_text=caption, broadcast_photo_id=photo_id)
    async with get_session() as session:
        total_users = await get_total_users_count(session)
    await message.answer(
        f"📨 <b>Подтверждение рассылки</b>\n\n"
        f"Картинка + текст будут отправлены <b>{total_users}</b> пользователям.\n\n"
        f"Текст: <i>{caption or '(без текста)'}</i>\n\n"
        "Подтвердить отправку?",
        parse_mode="HTML",
        reply_markup=get_confirm_broadcast_keyboard()
    )


@router.message(AdminStates.waiting_broadcast_message, F.text)
async def process_broadcast_message(message: Message, state: FSMContext):
    """Process broadcast text-only message."""
    if not is_admin(message.from_user.id):
        return
    
    await state.update_data(broadcast_text=message.text, broadcast_photo_id=None)
    
    async with get_session() as session:
        total_users = await get_total_users_count(session)
    
    await message.answer(
        f"📨 <b>Подтверждение рассылки</b>\n\n"
        f"Сообщение будет отправлено <b>{total_users}</b> пользователям:\n\n"
        f"<i>{message.text}</i>\n\n"
        "Подтвердить отправку?",
        parse_mode="HTML",
        reply_markup=get_confirm_broadcast_keyboard()
    )


@router.callback_query(F.data == "confirm_broadcast")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Confirm and send broadcast (text and/or photo)."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text", "")
    broadcast_photo_id = data.get("broadcast_photo_id")
    
    if not broadcast_text and not broadcast_photo_id:
        await callback.answer("❌ Нужен текст или картинка", show_alert=True)
        return
    
    await callback.message.edit_text("⏳ Отправляю рассылку...")
    
    broadcast_service = BroadcastService(bot)
    successful, failed = await broadcast_service.broadcast_message(
        broadcast_text, photo_file_id=broadcast_photo_id
    )
    
    await callback.message.edit_text(
        f"✅ <b>Рассылка завершена</b>\n\n"
        f"📨 Отправлено: <b>{successful}</b>\n"
        f"❌ Ошибок: <b>{failed}</b>",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    
    await state.clear()


@router.callback_query(F.data == "cancel_broadcast")
@router.callback_query(F.data == "cancel_action")
async def cancel_action(callback: CallbackQuery, state: FSMContext):
    """Cancel current action."""
    await state.clear()
    
    await callback.message.edit_text(
        "⚙️ <b>Админ-панель</b>\n\n"
        "Выбери действие:",
        parse_mode="HTML",
        reply_markup=get_admin_keyboard()
    )
    await callback.answer("Отменено")


# ============ CSV Import from CRM ============

# Поддержка разных названий колонок из CRM (алиасы → наша колонка)
CRM_COLUMN_ALIASES = {
    "email": ["email", "e-mail", "e_mail", "email_registrant", "mail"],
    "utm_campaign": ["utm_campaign", "referrer_email", "email_referrer", "referrer mail"],
    "utm_content": ["utm_content", "referrer_phone", "phone_referrer", "referrer phone"],
}


def _norm_col(s: str) -> str:
    """Нормализация названия колонки для сравнения."""
    return (s or "").strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_csv_row(fieldnames: list, row: dict) -> dict:
    """Приводит строку CSV к полям (email, utm_campaign, utm_content) по алиасам колонок."""
    def find_value(aliases):
        for f in fieldnames:
            if not f:
                continue
            fn = _norm_col(f)
            for a in aliases:
                if fn == _norm_col(a):
                    return (row.get(f) or "").strip()
        return ""
    return {
        "email": find_value(CRM_COLUMN_ALIASES["email"]),
        "utm_campaign": find_value(CRM_COLUMN_ALIASES["utm_campaign"]),
        "utm_content": find_value(CRM_COLUMN_ALIASES["utm_content"]),
    }


@router.callback_query(F.data == "admin_import_csv")
async def start_csv_import(callback: CallbackQuery, state: FSMContext):
    """Start CSV import process."""
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    
    await state.set_state(AdminStates.waiting_csv_file)
    
    await callback.message.edit_text(
        "📥 <b>Импорт рефералов из CRM</b>\n\n"
        "Отправь CSV с выгрузкой из CRM.\n\n"
        "<b>Колонки (или алиасы):</b>\n"
        "• email школьника: <code>email</code>, <code>e-mail</code>, <code>email_registrant</code>\n"
        "• реферер: <code>utm_campaign</code>, <code>utm_content</code> — <i>короткие токены из ссылки бота</i> "
        "или открытые email/номер (как раньше)\n\n"
        "<b>Пример (токены из Битрикса):</b>\n"
        "<code>email,utm_campaign,utm_content\n"
        "student@mail.ru,a3Fk9xK2,mN7pQ1zR</code>\n\n"
        "Реферер определяется по токенам или по email+номер.",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@router.message(AdminStates.waiting_csv_file, F.document)
async def process_csv_import(message: Message, state: FSMContext, bot: Bot):
    """Process uploaded CSV file."""
    if not is_admin(message.from_user.id):
        return
    
    document = message.document
    
    # Check file extension
    if not document.file_name.endswith('.csv'):
        await message.answer(
            "❌ Пожалуйста, отправь файл в формате CSV.",
            reply_markup=get_cancel_keyboard()
        )
        return
    
    # Download file
    file = await bot.get_file(document.file_id)
    file_content = await bot.download_file(file.file_path)
    
    # Parse CSV
    try:
        content = file_content.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))
        fieldnames = [f.strip() for f in (reader.fieldnames or [])]
        rows = list(reader)
        
        if not rows:
            await message.answer("❌ В файле нет строк с данными.", reply_markup=get_cancel_keyboard())
            await state.clear()
            return
        norm0 = _normalize_csv_row(fieldnames, rows[0])
        if not norm0["email"] or not norm0["utm_campaign"]:
            await message.answer(
                "❌ Не найдены колонки: email (школьника) и utm_campaign/referrer_email (реферера).\n\n"
                "Поддерживаемые имена колонок см. в описании импорта.",
                parse_mode="HTML",
                reply_markup=get_cancel_keyboard()
            )
            await state.clear()
            return
        
        linked = 0
        skipped = 0
        not_found = 0
        errors = []
        
        async with get_session() as session:
            for row in rows:
                norm = _normalize_csv_row(fieldnames, row)
                email = norm["email"].lower()
                utm_campaign = norm["utm_campaign"]
                utm_content = norm["utm_content"]
                
                if not email or not utm_campaign:
                    skipped += 1
                    continue
                
                # Реферер: utm_campaign и utm_content могут быть короткими токенами (из Битрикса) или открытые email/phone
                referrer = await get_referrer_by_utm_tokens(
                    session, utm_campaign.strip(), (utm_content or "").strip()
                )
                if not referrer and utm_content:
                    referrer = await get_user_by_email_and_phone(
                        session, utm_campaign, utm_content
                    )
                if not referrer and utm_campaign.isdigit():
                    referrer = await get_user_by_telegram_id(session, int(utm_campaign))
                if not referrer:
                    referrer = await get_user_by_email(session, utm_campaign)
                if not referrer:
                    errors.append(f"Реферер не найден: {utm_campaign}, {utm_content}")
                    continue
                
                referrer_id = referrer.telegram_id
                linked_user = await link_referral_by_email(session, email, referrer_id)
                
                if linked_user:
                    linked += 1
                    # Notify referrer: if they crossed a grade threshold, send grade message
                    grade_service = GradeService()
                    newly_achieved = await grade_service.get_grades_newly_achieved_with_session(
                        session, referrer_id
                    )
                    try:
                        if newly_achieved:
                            for grade in newly_achieved:
                                await grade_service.notify_grade_achieved(bot, referrer_id, grade)
                        else:
                            await bot.send_message(
                                referrer_id,
                                "🎊 Твой реферал подтверждён!\n\n"
                                "Школьник прошёл очный этап."
                            )
                    except Exception:
                        pass
                else:
                    not_found += 1
        
        await state.clear()
        
        result_text = (
            f"✅ <b>Импорт завершён</b>\n\n"
            f"🔗 Связано рефералов: <b>{linked}</b>\n"
            f"⏭ Пропущено (пустые): <b>{skipped}</b>\n"
            f"❓ Не найдено в боте: <b>{not_found}</b>\n"
        )
        
        if errors[:5]:  # Show first 5 errors
            result_text += f"\n⚠️ Ошибки:\n" + "\n".join(f"• {e}" for e in errors[:5])
            if len(errors) > 5:
                result_text += f"\n... и ещё {len(errors) - 5} ошибок"
        
        await message.answer(
            result_text,
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при обработке файла:\n<code>{str(e)}</code>",
            parse_mode="HTML",
            reply_markup=get_admin_keyboard()
        )
        await state.clear()


@router.message(AdminStates.waiting_csv_file)
async def waiting_csv_wrong_type(message: Message):
    """Handle non-document message while waiting for CSV."""
    await message.answer(
        "❌ Пожалуйста, отправь CSV-файл.\n\n"
        "Для отмены нажми кнопку Отмена.",
        reply_markup=get_cancel_keyboard()
    )


# ============ Export ============

@router.callback_query(F.data == "admin_export")
@router.message(Command("export"))
async def export_users(callback_or_message: CallbackQuery | Message):
    """Export users to CSV."""
    is_callback = isinstance(callback_or_message, CallbackQuery)
    user_id = callback_or_message.from_user.id
    
    if not is_admin(user_id):
        if is_callback:
            await callback_or_message.answer("❌ Нет доступа", show_alert=True)
        else:
            await callback_or_message.answer("❌ Нет доступа")
        return
    
    async with get_session() as session:
        users = await get_all_users(session, active_only=False)
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            "telegram_id",
            "username",
            "first_name",
            "email",
            "phone",
            "referrer_id",
            "referral_count",
            "created_at",
            "is_subscribed",
            "is_verified",
            "is_active"
        ])
        
        # Data (email и phone в выгрузке — расшифрованные для админа)
        for user in users:
            ref_count = await get_user_referral_count(session, user.telegram_id)
            writer.writerow([
                user.telegram_id,
                user.username or "",
                user.first_name or "",
                decrypt_email(user.email) or "",
                decrypt_phone(user.phone) or "",
                user.referrer_id or "",
                ref_count,
                user.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                "Да" if user.is_subscribed else "Нет",
                "Да" if user.is_verified else "Нет",
                "Да" if user.is_active else "Нет"
            ])
    
    csv_bytes = output.getvalue().encode("utf-8-sig")
    filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    file = BufferedInputFile(csv_bytes, filename=filename)
    message = callback_or_message.message if is_callback else callback_or_message
    await message.answer_document(
        file,
        caption=f"📥 Экспорт пользователей ({len(users)} записей)"
    )
    
    # Второй файл — ключ для Битрикса: токен → расшифрованное значение (для VLOOKUP в Excel)
    key_rows = await get_all_utm_tokens_for_key_export(session)
    key_io = io.StringIO()
    key_writer = csv.writer(key_io)
    key_writer.writerow(["token", "type", "decrypted_value"])
    for token, value_type, decrypted in key_rows:
        key_writer.writerow([token, value_type, decrypted])
    key_bytes = key_io.getvalue().encode("utf-8-sig")
    key_filename = f"utm_key_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    key_file = BufferedInputFile(key_bytes, filename=key_filename)
    await message.answer_document(
        key_file,
        caption="🔑 Ключ UTM: token → расшифрованные email/phone (для подстановки в выгрузку Битрикса)"
    )
    
    if is_callback:
        await callback_or_message.answer("✅ Экспорт готов")


# ============ Broadcast Command ============

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    """Start broadcast via command."""
    if not is_admin(message.from_user.id):
        await message.answer("❌ У тебя нет доступа к этой команде.")
        return
    
    await state.set_state(AdminStates.waiting_broadcast_message)
    
    await message.answer(
        "📨 <b>Рассылка</b>\n\n"
        "Отправь сообщение для рассылки.\n"
        "Для отмены напиши /cancel",
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current action."""
    current_state = await state.get_state()
    if current_state is None:
        return
    
    await state.clear()
    await message.answer("❌ Действие отменено.")


