import json
from datetime import datetime
from typing import Optional, List
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, Referral, Broadcast, Grade, GradeClaim


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
        # Update user info if changed
        if username and user.username != username:
            user.username = username
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        await session.flush()
        return user, False
    
    # Create new user (referrer_id НЕ устанавливается при создании - 
    # будет установлен через CSV из CRM)
    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        referrer_id=None,  # Устанавливается через CSV
        is_admin=is_admin,
    )
    session.add(user)
    await session.flush()
    
    return user, True


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Get user by email."""
    result = await session.execute(
        select(User).where(func.lower(User.email) == email.lower())
    )
    return result.scalar_one_or_none()


async def get_user_by_email_and_phone(
    session: AsyncSession, email: str, phone: str
) -> Optional[User]:
    """Get user by email and phone (for finding referrer from UTM)."""
    norm_phone = normalize_phone(phone)
    result = await session.execute(
        select(User).where(
            func.lower(User.email) == email.lower(),
            User.phone == norm_phone,
        )
    )
    return result.scalar_one_or_none()


async def update_user_email(session: AsyncSession, telegram_id: int, email: str) -> Optional[User]:
    """Update user's email."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.email = email.lower().strip()
        await session.flush()
    return user


def normalize_phone(phone: str) -> str:
    """Leave only digits and leading + for phone."""
    s = "".join(c for c in phone if c.isdigit() or c == "+")
    return s.strip() or phone.strip()


async def update_user_phone(session: AsyncSession, telegram_id: int, phone: str) -> Optional[User]:
    """Update user's phone number."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user:
        user.phone = normalize_phone(phone)
        await session.flush()
    return user


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


