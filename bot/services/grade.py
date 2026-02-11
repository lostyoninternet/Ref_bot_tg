"""Service for grade (рубеж) logic: thresholds and rewards."""
import json
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database import (
    get_session,
    get_all_grades,
    get_user_referral_count,
)
from bot.database.models import Grade


def parse_rewards(grade: Grade) -> List[str]:
    """Parse rewards JSON from grade to list of strings."""
    if not grade or not grade.rewards:
        return []
    try:
        return json.loads(grade.rewards)
    except (json.JSONDecodeError, TypeError):
        s = (grade.rewards or "").strip()
        return [r.strip() for r in s.split(",") if r.strip()]


class GradeService:
    """Service for grade thresholds and notifications."""

    async def get_next_grade(self, referral_count: int) -> Optional[Grade]:
        """Get the next grade the user has not yet achieved."""
        async with get_session() as session:
            grades = await get_all_grades(session)
        for g in grades:
            if g.referral_threshold > referral_count:
                return g
        return None

    async def get_achieved_grades(self, referral_count: int) -> List[Grade]:
        """Get all grades achieved at this referral count."""
        async with get_session() as session:
            grades = await get_all_grades(session)
        return [g for g in grades if g.referral_threshold <= referral_count]

    async def get_grades_newly_achieved(self, referrer_id: int) -> List[Grade]:
        """Get grades whose threshold equals current referral count (just achieved)."""
        async with get_session() as session:
            return await self.get_grades_newly_achieved_with_session(session, referrer_id)

    async def get_grades_newly_achieved_with_session(
        self, session: AsyncSession, referrer_id: int
    ) -> List[Grade]:
        """Same as get_grades_newly_achieved but uses provided session (e.g. inside CSV import)."""
        new_count = await get_user_referral_count(session, referrer_id)
        grades = await get_all_grades(session)
        return [g for g in grades if g.referral_threshold == new_count]

    async def notify_grade_achieved(self, bot, user_id: int, grade: Grade) -> None:
        """Send congratulations to user for achieving a grade."""
        rewards_list = parse_rewards(grade)
        rewards_text = ", ".join(rewards_list) if rewards_list else "награды"
        text = (
            f"🎉 <b>Поздравляем!</b>\n\n"
            f"Ты достиг рубежа <b>{grade.referral_threshold} рефералов</b>.\n\n"
            f"Твои награды: <b>{rewards_text}</b>\n\n"
            "Свяжись с организаторами для получения."
        )
        try:
            await bot.send_message(user_id, text)
        except Exception:
            pass
