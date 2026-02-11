import asyncio
from typing import List
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from bot.database import get_session, get_all_users, create_broadcast


class BroadcastService:
    """Service for broadcasting messages to all users."""
    
    def __init__(self, bot: Bot):
        self.bot = bot
    
    async def broadcast_message(
        self,
        message_text: str,
        parse_mode: str = "HTML",
        photo_file_id: str | None = None
    ) -> tuple[int, int]:
        """
        Send message to all active users (text and/or photo).
        
        Args:
            message_text: Text (caption if photo)
            parse_mode: Message parse mode
            photo_file_id: Optional photo file_id for send_photo
            
        Returns:
            Tuple of (successful_count, failed_count)
        """
        async with get_session() as session:
            users = await get_all_users(session, active_only=True)
        
        successful = 0
        failed = 0
        
        for user in users:
            try:
                if photo_file_id:
                    await self.bot.send_photo(
                        user.telegram_id,
                        photo=photo_file_id,
                        caption=message_text or None,
                        parse_mode=parse_mode if message_text else None
                    )
                else:
                    await self.bot.send_message(
                        user.telegram_id,
                        message_text,
                        parse_mode=parse_mode
                    )
                successful += 1
                await asyncio.sleep(0.05)
            except TelegramForbiddenError:
                failed += 1
            except TelegramBadRequest:
                failed += 1
            except Exception:
                failed += 1
        
        async with get_session() as session:
            await create_broadcast(session, message_text or "[фото]", successful)
        
        return successful, failed
    
    async def send_to_user(self, user_id: int, message_text: str, parse_mode: str = "HTML") -> bool:
        """
        Send message to a specific user.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.bot.send_message(user_id, message_text, parse_mode=parse_mode)
            return True
        except Exception:
            return False
