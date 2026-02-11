"""Scheduler stub (raffle reminders removed; kept for compatibility)."""
import logging

from aiogram import Bot

logger = logging.getLogger(__name__)

_bot: Bot | None = None


async def start_scheduler(bot: Bot):
    """No-op: scheduler not used after removing raffles."""
    global _bot
    _bot = bot
    logger.info("Scheduler started (no jobs)")


def shutdown_scheduler():
    """No-op."""
    global _bot
    _bot = None
    logger.info("Scheduler stopped")
