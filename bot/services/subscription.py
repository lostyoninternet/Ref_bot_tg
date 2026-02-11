from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest


async def check_subscription(bot: Bot, user_id: int, channel_id: int) -> bool:
    """
    Check if user is subscribed to the channel.
    
    Args:
        bot: Bot instance
        user_id: Telegram user ID
        channel_id: Channel ID to check subscription
        
    Returns:
        True if user is subscribed, False otherwise
    """
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        # User is subscribed if they are member, admin, or creator
        return member.status not in ["left", "kicked"]
    except TelegramBadRequest:
        # Channel not found or bot is not admin in channel
        return False
    except Exception:
        # Any other error - assume not subscribed
        return False


def get_channel_preview_link(channel_id: int) -> str:
    """
    Ссылка на канал без инвайта: пользователь переходит в канал,
    но для приватного канала не видит посты и не может подписаться.
    Бот не создаёт и не отдаёт пригласительную ссылку.
    """
    raw = str(channel_id).replace("-100", "")
    return f"https://t.me/c/{raw}"


async def get_channel_invite_link(bot: Bot, channel_id: int) -> str:
    """
    Возвращает только «превью»-ссылку (без инвайта), чтобы бот не отдавал
    пригласительную ссылку. Пользователь переходит в канал, но без инвайта
    не видит посты и не может подписаться на приватный канал.
    """
    return get_channel_preview_link(channel_id)
