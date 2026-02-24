import json
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.crypto import encrypt as crypto_encrypt, decrypt as crypto_decrypt, generate_token
from .models import User, Referral, Broadcast, Grade, GradeClaim, UtmToken, ContactEntry, BotSetting


def _encryption_enabled() -> bool:
    """Шифрование включено, если задан ключ (не пустой и не нули)."""
    key = getattr(settings, "encryption_key_bytes", None) or b""
    return len(key) >= 16 and key != b"\x00" * 32


def _encrypt(plain: str) -> str:
    if not plain or not _encryption_enabled():
        return plain
    return crypto_encrypt(plain, settings.encryption_key_bytes)


def _decrypt(cipher: str) -> str:
    if not cipher:
        return ""
    if not _encryption_enabled():
        return cipher
    try:
        return crypto_decrypt(cipher, settings.encryption_key_bytes)
    except Exception:
        return cipher  # legacy plain value


def decrypt_email(encrypted_email: Optional[str]) -> str:
    """Расшифровать email для отображения (или вернуть как есть, если не зашифрован)."""
    return ( _decrypt(encrypted_email) if encrypted_email else "" ) or ""


def decrypt_phone(encrypted_phone: Optional[str]) -> str:
    """Расшифровать телефон для отображения."""
    return ( _decrypt(encrypted_phone) if encrypted_phone else "" ) or ""


def decrypt_username(encrypted_username: Optional[str]) -> str:
    """Расшифровать ник Telegram для отображения и экспорта."""
    return ( _decrypt(encrypted_username) if encrypted_username else "" ) or ""


# ============ User CRUD ============

async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Get user by Telegram ID."""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    referrer_id: Optional[int] = None,
    is_admin: bool = False,
) -> tuple[User, bool]:
    """Get existing user or create new one. Returns (user, created)."""
    user = await get_user_by_telegram_id(session, telegram_id)
    
    if user:
        # Update user info if changed (username храним зашифрованным)
        if username is not None:
            enc_username = _encrypt(username.strip()) if username.strip() else None
            if user.username != enc_username:
                user.username = enc_username
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        await session.flush()
        return user, False
    
    # Create new user (referrer_id НЕ устанавливается при создании — будет установлен через CSV из CRM)
    enc_username = _encrypt(username.strip()) if (username and username.strip()) else None
    user = User(
        telegram_id=telegram_id,
        username=enc_username,
        first_name=first_name,
        referrer_id=None,  # Устанавливается через CSV
        is_admin=is_admin,
    )
    session.add(user)
    await session.flush()
    
    return user, True


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Get user by email (plain). Внутри ищем по зашифрованному значению."""
    email_clean = email.lower().strip()
    enc = _encrypt(email_clean)
    result = await session.execute(select(User).where(User.email == enc))
    row = result.scalar_one_or_none()
    if row:
        return row
    # Legacy: если в БД ещё хранится открытый email
    result = await session.execute(
        select(User).where(func.lower(User.email) == email_clean)
    )
    return result.scalar_one_or_none()


async def get_user_by_email_and_phone(
    session: AsyncSession, email: str, phone: str
) -> Optional[User]:
    """Get user by email and phone (for finding referrer from UTM)."""
    norm_phone = normalize_phone(phone)
    email_clean = email.lower().strip()
    enc_email = _encrypt(email_clean)
    enc_phone = _encrypt(norm_phone)
    result = await session.execute(
        select(User).where(
            User.email == enc_email,
            User.phone == enc_phone,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        return row
    # Legacy: plain in DB
    result = await session.execute(
        select(User).where(
            func.lower(User.email) == email_clean,
            User.phone == norm_phone,
        )
    )
    return result.scalar_one_or_none()


async def update_user_email(session: AsyncSession, telegram_id: int, email: str) -> Optional[User]:
    """Update user's email (сохраняем зашифрованным)."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.email = _encrypt(email.lower().strip())
        await session.flush()
    return user


def normalize_phone(phone: str) -> str:
    """Leave only digits and leading + for phone."""
    s = "".join(c for c in phone if c.isdigit() or c == "+")
    return s.strip() or phone.strip()


async def update_user_phone(session: AsyncSession, telegram_id: int, phone: str) -> Optional[User]:
    """Update user's phone number (сохраняем зашифрованным)."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.phone = _encrypt(normalize_phone(phone))
        await session.flush()
    return user


# ============ UTM Tokens (короткие токены для ссылок и выгрузки) ============

async def get_or_create_utm_token(
    session: AsyncSession, encrypted_value: str, value_type: str
) -> str:
    """Вернуть короткий токен для зашифрованного значения (email, phone или username). Один значение → один токен."""
    if not encrypted_value or value_type not in ("email", "phone", "username"):
        return ""
    result = await session.execute(
        select(UtmToken).where(
            UtmToken.encrypted_value == encrypted_value,
            UtmToken.value_type == value_type,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        return row.token
    token = generate_token(8)
    # Убедиться, что токен уникален
    while True:
        r = await session.execute(select(UtmToken).where(UtmToken.token == token))
        if r.scalar_one_or_none() is None:
            break
        token = generate_token(8)
    session.add(UtmToken(token=token, encrypted_value=encrypted_value, value_type=value_type))
    await session.flush()
    return token


async def get_encrypted_by_token(session: AsyncSession, token: str) -> Optional[str]:
    """По короткому токену из UTM вернуть зашифрованное значение (или None)."""
    if not token:
        return None
    result = await session.execute(select(UtmToken).where(UtmToken.token == token.strip()))
    row = result.scalar_one_or_none()
    return row.encrypted_value if row else None


async def get_referrer_by_utm_tokens(
    session: AsyncSession, token_campaign: str, token_content: str
) -> Optional[User]:
    """
    Найти реферера по токенам из UTM (utm_campaign, utm_content).
    token_campaign = токен почты, token_content = токен телефона.
    """
    enc_email = await get_encrypted_by_token(session, token_campaign)
    enc_phone = await get_encrypted_by_token(session, token_content)
    if not enc_email or not enc_phone:
        return None
    result = await session.execute(
        select(User).where(
            User.email == enc_email,
            User.phone == enc_phone,
        )
    )
    return result.scalar_one_or_none()


async def get_referral_tokens_for_user(
    session: AsyncSession, user: User
) -> Tuple[str, str, str]:
    """
    Вернуть (token_medium, token_campaign, token_content) для реферальной ссылки.
    token_medium = ник TG, token_campaign = email, token_content = телефон (все — токены или открытые при выключенном шифровании).
    """
    token_medium = ""
    token_campaign = ""
    token_content = ""
    if _encryption_enabled():
        if user.username:
            token_medium = await get_or_create_utm_token(session, user.username, "username")
        if user.email:
            token_campaign = await get_or_create_utm_token(session, user.email, "email")
        if user.phone:
            token_content = await get_or_create_utm_token(session, user.phone, "phone")
    else:
        token_medium = decrypt_username(user.username) or (user.username or "")
        token_campaign = decrypt_email(user.email) or (user.email or "")
        token_content = decrypt_phone(user.phone) or (user.phone or "")
    return token_medium, token_campaign, token_content


async def get_all_utm_tokens_for_key_export(
    session: AsyncSession,
) -> List[Tuple[str, str, str]]:
    """Список (token, value_type, decrypted_value) для выгрузки «ключ» в Excel."""
    result = await session.execute(select(UtmToken))
    rows = result.scalars().all()
    out = []
    for r in rows:
        dec = _decrypt(r.encrypted_value)
        out.append((r.token, r.value_type, dec))
    return out


async def link_referral_by_email(
    session: AsyncSession,
    email: str,
    referrer_id: int
) -> Optional[User]:
    """
    Link user to referrer by email (from CRM data).
    Creates referral record and marks user as verified.
    Returns the linked user or None if not found.
    """
    user = await get_user_by_email(session, email)
    if not user:
        return None
    
    # Check if already linked
    if user.referrer_id:
        return user
    
    # Check if user is subscribed to channel (= passed the event)
    if not user.is_subscribed:
        return None
    
    # Link to referrer
    user.referrer_id = referrer_id
    user.is_verified = True
    
    # Create referral record
    await create_referral(session, referrer_id, user.telegram_id)
    
    await session.flush()
    return user


async def get_pending_users(session: AsyncSession) -> List[User]:
    """Get users who are subscribed but not yet linked to referrer."""
    result = await session.execute(
        select(User).where(
            User.is_subscribed == True,
            User.referrer_id == None,
            User.email != None,
            User.is_active == True
        )
    )
    return list(result.scalars().all())


async def get_all_users(session: AsyncSession, active_only: bool = True) -> List[User]:
    """Get all users."""
    query = select(User)
    if active_only:
        query = query.where(User.is_active == True)
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_user_subscription(session: AsyncSession, telegram_id: int, is_subscribed: bool) -> None:
    """Update user subscription status."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.is_subscribed = is_subscribed
        await session.flush()


# ============ Referral CRUD ============

async def create_referral(session: AsyncSession, referrer_id: int, referred_id: int) -> Referral:
    """Create a new referral record."""
    referral = Referral(
        referrer_id=referrer_id,
        referred_id=referred_id,
    )
    session.add(referral)
    await session.flush()
    return referral


async def get_user_referrals(session: AsyncSession, telegram_id: int) -> List[Referral]:
    """Get all referrals for a user."""
    result = await session.execute(
        select(Referral).where(
            Referral.referrer_id == telegram_id,
            Referral.is_active == True
        )
    )
    return list(result.scalars().all())


async def get_user_referral_count(session: AsyncSession, telegram_id: int) -> int:
    """Get count of active referrals for a user."""
    result = await session.execute(
        select(func.count(Referral.id)).where(
            Referral.referrer_id == telegram_id,
            Referral.is_active == True
        )
    )
    return result.scalar() or 0


async def get_top_referrers(session: AsyncSession, limit: int = 10) -> List[tuple[User, int]]:
    """Get top referrers with their referral count."""
    # Subquery to count referrals
    referral_count = (
        select(
            Referral.referrer_id,
            func.count(Referral.id).label("count")
        )
        .where(Referral.is_active == True)
        .group_by(Referral.referrer_id)
        .subquery()
    )
    
    # Join with users
    result = await session.execute(
        select(User, referral_count.c.count)
        .join(referral_count, User.telegram_id == referral_count.c.referrer_id)
        .order_by(desc(referral_count.c.count))
        .limit(limit)
    )
    
    return [(row[0], row[1]) for row in result.all()]


async def get_user_rank(session: AsyncSession, telegram_id: int) -> int:
    """Get user's rank in the leaderboard."""
    user_count = await get_user_referral_count(session, telegram_id)
    
    # Count users with more referrals
    result = await session.execute(
        select(func.count(func.distinct(Referral.referrer_id))).where(
            Referral.is_active == True
        ).group_by(Referral.referrer_id).having(
            func.count(Referral.id) > user_count
        )
    )
    
    higher_count = len(result.all())
    return higher_count + 1


# ============ Broadcast CRUD ============

async def create_broadcast(
    session: AsyncSession,
    message_text: str,
    recipients_count: int
) -> Broadcast:
    """Record a broadcast message."""
    broadcast = Broadcast(
        message_text=message_text,
        recipients_count=recipients_count,
    )
    session.add(broadcast)
    await session.flush()
    return broadcast


# ============ Contact entries (кнопка «Связаться») ============

CONTACTS_VISIBLE_KEY = "contacts_section_visible"


async def get_contacts_section_visible(session: AsyncSession) -> bool:
    """Видимость кнопки «Связаться» и списка контактов для пользователей."""
    result = await session.execute(
        select(BotSetting).where(BotSetting.key == CONTACTS_VISIBLE_KEY)
    )
    row = result.scalar_one_or_none()
    if not row:
        return False
    return row.value.strip().lower() in ("1", "true", "yes")


async def set_contacts_section_visible(session: AsyncSession, visible: bool) -> None:
    """Включить/выключить видимость раздела контактов."""
    result = await session.execute(
        select(BotSetting).where(BotSetting.key == CONTACTS_VISIBLE_KEY)
    )
    row = result.scalar_one_or_none()
    value = "1" if visible else "0"
    if row:
        row.value = value
    else:
        session.add(BotSetting(key=CONTACTS_VISIBLE_KEY, value=value))
    await session.flush()


async def get_contact_entries(
    session: AsyncSession, active_only: bool = True
) -> List[ContactEntry]:
    """Список контактов для кнопки «Связаться», по sort_order."""
    query = select(ContactEntry).order_by(ContactEntry.sort_order, ContactEntry.id)
    if active_only:
        query = query.where(ContactEntry.is_active == True)
    result = await session.execute(query)
    return list(result.scalars().all())


async def create_contact_entry(
    session: AsyncSession,
    tg_username: str,
    description: str,
    sort_order: Optional[int] = None,
) -> ContactEntry:
    """Добавить контакт."""
    if sort_order is None:
        entries = await get_contact_entries(session, active_only=False)
        sort_order = max((e.sort_order for e in entries), default=0) + 1
    entry = ContactEntry(
        tg_username=tg_username.strip(),
        description=description.strip(),
        sort_order=sort_order,
    )
    session.add(entry)
    await session.flush()
    return entry


async def get_contact_entry_by_id(
    session: AsyncSession, entry_id: int
) -> Optional[ContactEntry]:
    """Получить контакт по id."""
    result = await session.execute(select(ContactEntry).where(ContactEntry.id == entry_id))
    return result.scalar_one_or_none()


async def update_contact_entry(
    session: AsyncSession,
    entry_id: int,
    tg_username: Optional[str] = None,
    description: Optional[str] = None,
    sort_order: Optional[int] = None,
    is_active: Optional[bool] = None,
) -> Optional[ContactEntry]:
    """Обновить контакт."""
    entry = await get_contact_entry_by_id(session, entry_id)
    if not entry:
        return None
    if tg_username is not None:
        entry.tg_username = tg_username.strip()
    if description is not None:
        entry.description = description.strip()
    if sort_order is not None:
        entry.sort_order = sort_order
    if is_active is not None:
        entry.is_active = is_active
    await session.flush()
    return entry


async def delete_contact_entry(session: AsyncSession, entry_id: int) -> bool:
    """Удалить контакт."""
    entry = await get_contact_entry_by_id(session, entry_id)
    if not entry:
        return False
    await session.delete(entry)
    await session.flush()
    return True


# ============ Grade CRUD ============

def _parse_rewards(rewards: str) -> List[str]:
    """Parse rewards from JSON string or return as single-item list."""
    if not rewards or not rewards.strip():
        return []
    s = rewards.strip()
    if s.startswith("["):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            return [r.strip() for r in s.strip("[]").split(",") if r.strip()]
    return [r.strip() for r in s.split(",") if r.strip()]


def _serialize_rewards(rewards_list: List[str]) -> str:
    """Serialize rewards list to JSON string."""
    return json.dumps(rewards_list, ensure_ascii=False)


async def get_all_grades(session: AsyncSession) -> List[Grade]:
    """Get all grades ordered by sort_order, then referral_threshold."""
    result = await session.execute(
        select(Grade).order_by(Grade.sort_order, Grade.referral_threshold)
    )
    return list(result.scalars().all())


async def get_grade_by_id(session: AsyncSession, grade_id: int) -> Optional[Grade]:
    """Get grade by ID."""
    result = await session.execute(select(Grade).where(Grade.id == grade_id))
    return result.scalar_one_or_none()


async def create_grade(
    session: AsyncSession,
    referral_threshold: int,
    rewards: List[str],
    sort_order: Optional[int] = None,
) -> Grade:
    """Create a new grade."""
    if sort_order is None:
        existing = await get_all_grades(session)
        sort_order = max((g.sort_order for g in existing), default=0) + 1
    grade = Grade(
        referral_threshold=referral_threshold,
        rewards=_serialize_rewards(rewards),
        sort_order=sort_order,
    )
    session.add(grade)
    await session.flush()
    return grade


async def update_grade(
    session: AsyncSession,
    grade_id: int,
    referral_threshold: Optional[int] = None,
    rewards: Optional[List[str]] = None,
    sort_order: Optional[int] = None,
) -> Optional[Grade]:
    """Update a grade."""
    grade = await get_grade_by_id(session, grade_id)
    if not grade:
        return None
    if referral_threshold is not None:
        grade.referral_threshold = referral_threshold
    if rewards is not None:
        grade.rewards = _serialize_rewards(rewards)
    if sort_order is not None:
        grade.sort_order = sort_order
    await session.flush()
    return grade


async def delete_grade(session: AsyncSession, grade_id: int) -> bool:
    """Delete a grade and its claims."""
    grade = await get_grade_by_id(session, grade_id)
    if not grade:
        return False
    await session.delete(grade)
    await session.flush()
    return True


async def get_users_for_grade(session: AsyncSession, grade_id: int) -> List[tuple[User, int]]:
    """Get users who have reached this grade (referral_count >= threshold)."""
    grade = await get_grade_by_id(session, grade_id)
    if not grade:
        return []
    referral_count = (
        select(
            Referral.referrer_id,
            func.count(Referral.id).label("count")
        )
        .where(Referral.is_active == True)
        .group_by(Referral.referrer_id)
        .subquery()
    )
    result = await session.execute(
        select(User, referral_count.c.count)
        .join(referral_count, User.telegram_id == referral_count.c.referrer_id)
        .where(referral_count.c.count >= grade.referral_threshold)
        .where(User.is_active == True)
    )
    return [(row[0], row[1]) for row in result.all()]


async def get_user_achieved_grade_ids(session: AsyncSession, telegram_id: int) -> List[int]:
    """Get list of grade IDs that user has achieved (referral_count >= threshold)."""
    ref_count = await get_user_referral_count(session, telegram_id)
    result = await session.execute(
        select(Grade.id).where(Grade.referral_threshold <= ref_count).order_by(Grade.referral_threshold)
    )
    return [row[0] for row in result.all()]


async def create_grade_claim(
    session: AsyncSession,
    user_id: int,
    grade_id: int,
    issued_by_admin: bool = True,
) -> GradeClaim:
    """Record that reward for grade was issued to user."""
    claim = GradeClaim(
        user_id=user_id,
        grade_id=grade_id,
        issued_by_admin=issued_by_admin,
    )
    session.add(claim)
    await session.flush()
    return claim


async def get_user_grade_claims(session: AsyncSession, telegram_id: int) -> List[GradeClaim]:
    """Get all grade claims for a user."""
    result = await session.execute(
        select(GradeClaim).where(GradeClaim.user_id == telegram_id)
    )
    return list(result.scalars().all())


async def has_grade_claim(session: AsyncSession, user_id: int, grade_id: int) -> bool:
    """Check if user already has a claim for this grade."""
    result = await session.execute(
        select(GradeClaim).where(
            GradeClaim.user_id == user_id,
            GradeClaim.grade_id == grade_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def get_total_users_count(session: AsyncSession) -> int:
    """Get total count of users."""
    result = await session.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )
    return result.scalar() or 0


async def get_total_referrals_count(session: AsyncSession) -> int:
    """Get total count of referrals."""
    result = await session.execute(
        select(func.count(Referral.id)).where(Referral.is_active == True)
    )
    return result.scalar() or 0


