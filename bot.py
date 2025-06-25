import asyncio
import logging
from aiogram import Bot, Dispatcher, types
# from aiogram.utils.exceptions import TelegramAPIError
from config import BOT_TOKEN
from database import init_db
from handlers import register_handlers

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set default bot commands
async def set_default_commands(bot: Bot):
    await bot.set_my_commands([
        types.BotCommand(command="start", description="⚪️ Botni ishga tushirish"),
        types.BotCommand(command="register", description="📋 Ro'yxatdan o'tish"),
        types.BotCommand(command="test", description="📝 Test topshirish"),
        types.BotCommand(command="profile", description="👤 Profil ma'lumotlari"),
        types.BotCommand(command="help", description="❓ Yordam"),
        types.BotCommand(command="cancel", description="❌ Jarayonni bekor qilish"),
        types.BotCommand(command="admin", description="🔐 Admin panel (faqat adminlar uchun)"),
    ])

# Main function to start the bot
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    init_db()  # Initialize database
    register_handlers(dp)  # Register handlers

    await set_default_commands(bot)  # Set bot commands

    try:
        logger.info("Bot polling started")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot polling error: {e}")
    finally:
        await bot.session.close()
        logger.info("Bot session closed")

if __name__ == "__main__":
    asyncio.run(main())