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


async def get_channel_invite_link(bot: Bot, channel_id: int) -> str:
    """
    Get or create invite link for the channel.
    
    Args:
        bot: Bot instance
        channel_id: Channel ID
        
    Returns:
        Invite link URL
    """
    try:
        chat = await bot.get_chat(channel_id)
        if chat.invite_link:
            return chat.invite_link
        # Try to create invite link
        link = await bot.create_chat_invite_link(channel_id)
        return link.invite_link
    except Exception:
        # Fallback - return placeholder
        return f"https://t.me/c/{str(channel_id).replace('-100', '')}"
