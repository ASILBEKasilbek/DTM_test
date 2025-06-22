import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from config import BOT_TOKEN
from database import init_db
from handlers import register_handlers

logging.basicConfig(level=logging.INFO)

# ➕ Bot komandalarini belgilaymiz
async def set_default_commands(bot: Bot):
    await bot.set_my_commands([
        types.BotCommand(command="start", description="⚪️Botni ishga tushirish"),
        types.BotCommand(command="register", description="📋Ro'yxatdan o'tish"),
    ])

# 🚀 Asosiy ishga tushirish funksiyasi
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    init_db()  # 📦 Ma'lumotlar bazasini boshlash
    register_handlers(dp)  # 🔗 Handlerlarni ro'yxatdan o'tkazish

    await set_default_commands(bot)  # ✅ Bot komandalarini o‘rnatish

    try:
        await dp.start_polling(bot)  # ▶️ Botni ishga tushirish
    finally:
        await bot.session.close()  # 🔒 Bot sessiyasini yopish

# ⏱ Dastur ishga tushishi
if __name__ == "__main__":
    asyncio.run(main())
