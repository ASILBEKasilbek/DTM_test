import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from config import BOT_TOKEN
from database import init_db
from handlers import register_handlers

logging.basicConfig(level=logging.INFO)

# ➕ Bu yerga komandalarni qo‘shamiz
async def set_default_commands(dp):
    await dp.bot.set_my_commands(
        [
            types.BotCommand("start", "⚪️Botni ishga tushirish"),
            types.BotCommand("register", "📋Ro'yxatdan o'tish"),
        ]
    )

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    init_db()
    register_handlers(dp)

    # ✅ Komandalarni o‘rnatamiz
    await set_default_commands(dp)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
