import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.database import init_db
from bot.handlers import get_all_routers
from bot.middlewares import SubscriptionMiddleware
from bot.scheduler import start_scheduler, shutdown_scheduler


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    """Actions to perform on bot startup."""
    logger.info("Initializing database...")
    await init_db()
    
    await start_scheduler(bot)
    
    # Get bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username}")
    
    # Notify admins
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🤖 Бот @{bot_info.username} запущен!"
            )
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")


async def on_shutdown(bot: Bot):
    """Actions to perform on bot shutdown."""
    logger.info("Bot is shutting down...")
    shutdown_scheduler()
    
    # Notify admins
    for admin_id in settings.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "🔴 Бот остановлен.")
        except Exception:
            pass


async def main():
    """Main entry point."""
    # Create bot instance
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Create dispatcher with memory storage for FSM
    dp = Dispatcher(storage=MemoryStorage())
    
    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Middleware: проверка подписки на канал (кроме /start и проверки подписки)
    dp.message.middleware(SubscriptionMiddleware())
    dp.callback_query.middleware(SubscriptionMiddleware())
    
    # Register all routers
    for router in get_all_routers():
        dp.include_router(router)
        logger.info(f"Registered router: {router.name}")
    
    # Start polling
    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot stopped with error: {e}")
        raise
