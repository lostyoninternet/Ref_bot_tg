from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from bot.config import settings
from bot.database import (
    get_session,
    get_user_referrals,
    get_user_by_telegram_id,
    get_referral_tokens_for_user,
    decrypt_email,
    decrypt_phone,
    decrypt_username,
)


router = Router(name="referral")


@router.message(Command("myreferrals"))
async def cmd_my_referrals(message: Message):
    """Show list of user's referrals (only confirmed ones)."""
    user_id = message.from_user.id
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
            ref_link = (
                settings.get_referral_link(
                    token_medium=token_medium or "",
                    token_campaign=token_campaign or "",
                    token_content=token_content or "",
                )
                if (token_campaign and token_content) else "Укажи email и телефон (/start), чтобы получить ссылку."
            )
        else:
            ref_link = "Укажи email и телефон (/start), чтобы получить ссылку."
    
    async with get_session() as session:
        referrals = await get_user_referrals(session, user_id)
    
    if not referrals:
        await message.answer(
            "👥 <b>Твои подтверждённые рефералы</b>\n\n"
            "У тебя пока нет подтверждённых рефералов.\n\n"
            "📌 <b>Как получить реферала:</b>\n"
            "1. Отправь ссылку другу\n"
            "2. Друг регистрируется на очный этап\n"
            "3. Друг проходит очный этап\n"
            "4. Реферал засчитывается!\n\n"
            f"🔗 Твоя ссылка:\n<code>{ref_link}</code>",
            parse_mode="HTML"
        )
        return
    
    text = f"👥 <b>Твои подтверждённые рефералы ({len(referrals)})</b>\n\n"
    text += "Это школьники, которые прошли очный этап по твоей ссылке:\n\n"
    
    async with get_session() as session:
        for i, ref in enumerate(referrals[:20], 1):  # Show max 20
            referred_user = await get_user_by_telegram_id(session, ref.referred_id)
            if referred_user:
                name = referred_user.first_name or decrypt_username(referred_user.username) or "Аноним"
                date = ref.created_at.strftime("%d.%m.%Y")
                text += f"{i}. {name} — {date}\n"
    
    if len(referrals) > 20:
        text += f"\n... и ещё {len(referrals) - 20} рефералов"
    
    text += f"\n\n📊 Рефералов: <b>{len(referrals)}</b> — смотри раздел «Грейды» для наград за рубежи."
    
    await message.answer(text, parse_mode="HTML")
