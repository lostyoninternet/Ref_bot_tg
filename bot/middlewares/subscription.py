from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware, Bot
from aiogram.types import Message, CallbackQuery, TelegramObject

from bot.config import settings
from bot.services.subscription import check_subscription
from bot.keyboards.inline import get_subscription_keyboard


class SubscriptionMiddleware(BaseMiddleware):
    """
    Middleware that checks if user is subscribed to the required channel.
    
    Allows certain commands to pass through without subscription check:
    - /start (for registration flow)
    - check_subscription callback
    """
    
    ALLOWED_WITHOUT_SUBSCRIPTION = {
        "/start",
        "check_subscription",
    }
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Process the event."""
        # Get user_id and text/data from event
        user_id = None
        event_text = None
        
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
            event_text = event.text or ""
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
            event_text = event.data or ""
        
        if not user_id:
            return await handler(event, data)
        
        # Check if this is an allowed command/callback
        for allowed in self.ALLOWED_WITHOUT_SUBSCRIPTION:
            if event_text.startswith(allowed):
                return await handler(event, data)
        
        # Check if user is admin (admins bypass subscription check)
        if user_id in settings.ADMIN_IDS:
            return await handler(event, data)
        
        # Check subscription
        bot: Bot = data.get("bot")
        if not bot:
            return await handler(event, data)
        
        is_subscribed = await check_subscription(bot, user_id, settings.CHANNEL_ID)
        
        if is_subscribed:
            return await handler(event, data)
        
        # Пользователь не подписан — показываем кнопку заявки на очный этап
        application_url = settings.get_application_utm_url()
        subscription_text = (
            "⚠️ Чтобы пользоваться ботом, нужно пройти очный этап и подписаться на канал.\n\n"
            "Оставь заявку на очный этап по кнопке ниже. После прохождения — зайди в канал и нажми «Проверить подписку»."
        )
        if isinstance(event, Message):
            await event.answer(
                subscription_text,
                reply_markup=get_subscription_keyboard(application_url)
            )
        elif isinstance(event, CallbackQuery):
            await event.answer(
                "❌ Сначала пройди очный этап и подпишись на канал.",
                show_alert=True
            )
            await event.message.answer(
                subscription_text,
                reply_markup=get_subscription_keyboard(application_url)
            )
        
        # Don't call the handler - block the request
        return None
