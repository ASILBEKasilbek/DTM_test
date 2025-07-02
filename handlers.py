import logging
import re
from aiogram import Bot

from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError
from config import WEBSITE_URL, ADMIN_IDS, MANDATORY_CHANNELS
from database import (
    register_user, is_user_registered, is_user_banned, ban_user, unban_user, 
    get_all_users, get_user_count, get_users_today, add_channel, remove_channel, 
    get_channels, save_ad, get_ad_history, update_user, get_user, add_admin, remove_admin, get_admins
)
from html import escape

logger = logging.getLogger(__name__)

# Registration states
class Registration(StatesGroup):
    first_name = State()
    last_name = State()
    phone_number = State()

# Admin states
class AdminStates(StatesGroup):
    send_ad = State()
    add_channel = State()
    ban_user = State()
    unban_user = State()
    edit_user = State()
    edit_user_field = State()
    add_admin = State()
    remove_admin = State()

# Keyboards
def get_contact_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Kontakt yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        # 👤 Foydalanuvchilar bo‘limi
        [InlineKeyboardButton(text="👤 Foydalanuvchilarni ko'rish", callback_data="view_users"),
         InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="edit_user")],
        [InlineKeyboardButton(text="🚫 Ban qilish", callback_data="ban_user"),
         InlineKeyboardButton(text="✅ Banni olib tashlash", callback_data="unban_user")],

        # 📢 Reklama bo‘limi
        [InlineKeyboardButton(text="📢 Reklama yuborish", callback_data="send_ad"),
         InlineKeyboardButton(text="📜 Reklama tarixi", callback_data="view_ad_history")],

        # 📡 Kanal boshqaruvi
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel"),
         InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="remove_channel")],
        [InlineKeyboardButton(text="📊 Kanal statistikasi", callback_data="channel_stats")],

        # 👑 Adminlar
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_admin"),
         InlineKeyboardButton(text="➖ Admin o'chirish", callback_data="remove_admin")],

        # 📈 Umumiy
        [InlineKeyboardButton(text="📈 Statistika", callback_data="stats")],
    ])

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_subscription_keyboard():
    keyboard_buttons = []

    for channel_id in MANDATORY_CHANNELS:
        button = [InlineKeyboardButton(
            text="Kanalga obuna bo'lish",
            url=f"https://t.me/{channel_id.lstrip('@')}"
        )]
        keyboard_buttons.append(button)

    # "Tekshirish" tugmasi pastga qo‘shiladi
    keyboard_buttons.append([
        InlineKeyboardButton(
            text="✅ Tekshirish",
            callback_data="check_subscription"
        )
    ])

    # Endi InlineKeyboardMarkup ni to‘g‘ri hosil qilamiz
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    return keyboard


def get_edit_user_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ism", callback_data="edit_first_name")],
        [InlineKeyboardButton(text="Familiya", callback_data="edit_last_name")],
        [InlineKeyboardButton(text="Telefon", callback_data="edit_phone_number")]
    ])

# Utility function to check subscription
async def check_subscription(bot: Bot, user_id: int) -> bool:
    for channel_id in MANDATORY_CHANNELS:
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except TelegramAPIError as e:
            logger.error(f"Error checking subscription for channel {channel_id}: {e}")
            return False
    return True

# Handlers
async def start_command(message: types.Message, bot: Bot):
    if is_user_banned(message.from_user.id):
        await message.answer("Siz botdan foydalana olmaysiz, chunki siz ban qilingansiz.")
        return
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Iltimos, quyidagi kanallarga obuna bo'ling:",
            reply_markup=get_subscription_keyboard()
        )
        return
    if is_user_registered(message.from_user.id):
        await message.answer("Siz allaqachon ro'yxatdan o'tgansiz. Test topshirish uchun /test buyrug'ini yuboring yoki /profile orqali ma'lumotlaringizni ko'ring.")
        return
    await message.answer(
        "Xush kelibsiz! Ro'yxatdan o'tish uchun /register buyrug'ini yuboring. Qo'shimcha ma'lumot uchun /help ni bosing."
    )

async def help_command(message: types.Message):
    await message.answer(
        "📚 Botdan foydalanish bo'yicha qo'llanma:\n"
        "/start - Botni ishga tushirish\n"
        "/register - Ro'yxatdan o'tish\n"
        "/test - Test topshirish uchun saytga o'tish\n"
        "/profile - O'z ma'lumotlaringizni ko'rish\n"
        "/cancel - Jarayonni bekor qilish\n"
        "/help - Ushbu yordam xabari\n\n"
        "Savollaringiz bo'lsa, @Dasturch1_asilbek bilan bog'laning."
    )

async def profile_command(message: types.Message):
    if not is_user_registered(message.from_user.id):
        await message.answer("Siz hali ro'yxatdan o'tmagansiz. /register buyrug'ini yuboring.")
        return
    user = get_user(message.from_user.id)
    if user:
        await message.answer(
            f"👤 Profil ma'lumotlari:\n"
            f"Ism: {user[1]}\n"
            f"Familiya: {user[2]}\n"
            f"Telefon: {user[3]}\n"
            f"Ro'yxatdan o'tgan vaqt: {user[5]}\n\n"
            f"Test topshirish uchun /test buyrug'ini yuboring."
        )
    else:
        await message.answer("Ma'lumotlar topilmadi. Qayta urinib ko'ring.")

async def register_command(message: types.Message, state: FSMContext, bot: Bot):
    if is_user_banned(message.from_user.id):
        await message.answer("Siz botdan foydalana olmaysiz, chunki siz ban qilingansiz.")
        return
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Iltimos, quyidagi kanallarga obuna bo'ling:",
            reply_markup=get_subscription_keyboard()
        )
        return
    if is_user_registered(message.from_user.id):
        await message.answer("Siz allaqachon ro'yxatdan o'tgansiz. Test topshirish uchun /test buyrug'ini yuboring.")
        return
    logger.info(f"User {message.from_user.id} started registration")
    await message.answer("Ismingizni kiriting (faqat harflar, bo'shliq yoki defis):")
    await state.set_state(Registration.first_name)

async def get_first_name(message: types.Message, state: FSMContext):
    if not re.match(r'^[A-Za-z\s-]+$', message.text):
        await message.answer("Iltimos, faqat harflardan, bo'shliq yoki defisdan iborat ism kiriting.")
        return
    await state.update_data(first_name=escape(message.text))
    await message.answer("Familiyangizni kiriting (faqat harflar, bo'shliq yoki defis):")
    await state.set_state(Registration.last_name)

async def get_last_name(message: types.Message, state: FSMContext):
    if not re.match(r'^[A-Za-z\s-]+$', message.text):
        await message.answer("Iltimos, faqat harflardan, bo'shliq yoki defisdan iborat familiya kiriting.")
        return
    await state.update_data(last_name=escape(message.text))
    await message.answer(
        "Telefon raqamingizni yuborish uchun quyidagi tugmani bosing yoki +998XXXXXXXXX formatida kiriting:",
        reply_markup=get_contact_keyboard()
    )
    await state.set_state(Registration.phone_number)

async def get_phone_number(message: types.Message, state: FSMContext):
    if not message.contact:
        if message.text and re.match(r'^\+998\d{9}$', message.text):
            phone_number = message.text
        else:
            await message.answer("Iltimos, 'Kontakt yuborish' tugmasini bosing yoki telefon raqamingizni +998XXXXXXXXX formatida kiriting.")
            return
    else:
        if message.contact.user_id != message.from_user.id:
            await message.answer("Iltimos, faqat o‘z kontakt ma'lumotingizni yuboring.")
            return
        phone_number = message.contact.phone_number

    user_data = await state.get_data()
    first_name = user_data["first_name"]
    last_name = user_data["last_name"]
    telegram_id = message.from_user.id

    if register_user(telegram_id, first_name, last_name, phone_number):
        auth_url = f"{WEBSITE_URL}/telegram-auth/{telegram_id}/"
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Test saytiga o'tish", url=auth_url)]
        ])
        await message.answer(
            f"🎉 Ro'yxatdan muvaffaqiyatli o'tdingiz!\n"
            f"Ism: {first_name}\n"
            f"Familiya: {last_name}\n"
            f"Telefon: {phone_number}\n\n"
            f"Test topshirish uchun quyidagi tugmani bosing yoki /test buyrug'ini yuboring:",
            parse_mode='HTML',
            reply_markup=inline_keyboard
        )
        await message.answer(
            "ℹ️ Qo'shimcha ma'lumot: Test topshirish uchun saytdagi ko'rsatmalarga amal qiling. Savollar bo'lsa, /help ni bosing."
        )
    else:
        await message.answer("❌ Ma'lumotlarni saqlashda xatolik yuz berdi. Qayta urinib ko'ring yoki admin bilan bog'laning.")
    await state.clear()

async def cancel_command(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Jarayon bekor qilindi. /start buyrug'ini yuboring.")

async def test_command(message: types.Message, bot: Bot):
    if is_user_banned(message.from_user.id):
        await message.answer("Siz botdan foydalana olmaysiz, chunki siz ban qilingansiz.")
        return
    if not await check_subscription(bot, message.from_user.id):
        await message.answer(
            "Iltimos, quyidagi kanallarga obuna bo'ling:",
            reply_markup=get_subscription_keyboard()
        )
        return
    if not is_user_registered(message.from_user.id):
        await message.answer("Iltimos, avval ro'yxatdan o'ting: /register")
        return
    auth_url = f"{WEBSITE_URL}/telegram-auth/{message.from_user.id}/"
    inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Test saytiga o'tish", url=auth_url)]
    ])
    await message.answer("📝 Test topshirish uchun quyidagi tugmani bosing:", reply_markup=inline_keyboard)

async def admin_command(message: types.Message):
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("🚫 Sizda admin huquqlari yo'q.")
        return
    await message.answer("🔐 Admin panel:", reply_markup=get_admin_keyboard())

async def admin_callback_query(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot):
    data = callback_query.data
    if data == "view_users":
        users = get_all_users()
        if not users:
            await callback_query.message.answer("Foydalanuvchilar topilmadi.")
            return
        response = "👥 Foydalanuvchilar:\n"
        for user in users:
            telegram_id, first_name, last_name, phone_number, banned = user
            status = "🚫 Banlangan" if banned else "✅ Faol"
            response += f"ID: {telegram_id}, Ism: {first_name} {last_name}, Telefon: {phone_number}, Holat: {status}\n"
        await callback_query.message.answer(response[:4000])
    elif data == "edit_user":
        await callback_query.message.answer("Tahrir qilinadigan foydalanuvchi Telegram ID sini kiriting:")
        await state.set_state(AdminStates.edit_user)
    elif data == "edit_first_name":
        await state.update_data(edit_field="first_name")
        await callback_query.message.answer("Yangi ismni kiriting:")
        await state.set_state(AdminStates.edit_user_field)
    elif data == "edit_last_name":
        await state.update_data(edit_field="last_name")
        await callback_query.message.answer("Yangi familiyani kiriting:")
        await state.set_state(AdminStates.edit_user_field)
    elif data == "edit_phone_number":
        await state.update_data(edit_field="phone_number")
        await callback_query.message.answer("Yangi telefon raqamini kiriting (+998XXXXXXXXX):")
        await state.set_state(AdminStates.edit_user_field)
    elif data == "send_ad":
        await callback_query.message.answer("Reklama xabarini kiriting:")
        await state.set_state(AdminStates.send_ad)
    elif data == "view_ad_history":
        ads = get_ad_history()
        if not ads:
            await callback_query.message.answer("Reklama tarixi topilmadi.")
            return
        response = "📢 Reklama tarixi:\n"
        for ad in ads[:10]:  # So'nggi 10 ta reklama
            response += f"ID: {ad[0]}, Vaqt: {ad[2]}\nXabar: {ad[1][:100]}...\n\n"
        await callback_query.message.answer(response[:4000])
    elif data == "add_channel":
        await callback_query.message.answer("Kanal ID sini kiriting (masalan, @ChannelName yoki -100123456789):")
        await state.set_state(AdminStates.add_channel)
    elif data == "remove_channel":
        channels = get_channels()
        if not channels:
            await callback_query.message.answer("Majburiy kanallar topilmadi.")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=channel_id, callback_data=f"remove_{channel_id}")] for channel_id in channels
        ])
        await callback_query.message.answer("O'chiriladigan kanalni tanlang:", reply_markup=keyboard)
    elif data == "channel_stats":
        response = "📊 Kanal statistikasi:\n"
        for channel_id in MANDATORY_CHANNELS:
            try:
                count = sum(1 for user in get_all_users() if await check_subscription(bot, user[0]))
                response += f"{channel_id}: {count} obunachi\n"
            except Exception as e:
                logger.error(f"Error in channel stats for {channel_id}: {e}")
        await callback_query.message.answer(response or "Ma'lumot topilmadi.")
    elif data == "ban_user":
        await callback_query.message.answer("Ban qilinadigan foydalanuvchi Telegram ID sini kiriting:")
        await state.set_state(AdminStates.ban_user)
    elif data == "unban_user":
        await callback_query.message.answer("Ban o'chiriladigan foydalanuvchi Telegram ID sini kiriting:")
        await state.set_state(AdminStates.unban_user)
    elif data == "add_admin":
        await callback_query.message.answer("Yangi admin Telegram ID sini kiriting:")
        await state.set_state(AdminStates.add_admin)
    elif data == "remove_admin":
        admins = get_admins()
        if not admins:
            await callback_query.message.answer("Adminlar topilmadi.")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=admin_id, callback_data=f"remove_admin_{admin_id}")] for admin_id in admins
        ])
        await callback_query.message.answer("O'chiriladigan adminni tanlang:", reply_markup=keyboard)
    elif data == "stats":
        total_users = get_user_count()
        users_today = get_users_today()
        banned_users = len([u for u in get_all_users() if u[4]])
        await callback_query.message.answer(
            f"📈 Statistika:\n"
            f"Jami foydalanuvchilar: {total_users}\n"
            f"Bugun qo'shilganlar: {users_today}\n"
            f"Banlanganlar: {banned_users}"
        )
    elif data.startswith("remove_"):
        channel_id = data[len("remove_"):]
        if remove_channel(channel_id):
            await callback_query.message.answer(f"Kanal {channel_id} o'chirildi.")
        else:
            await callback_query.message.answer("Xatolik yuz berdi.")
    elif data.startswith("remove_admin_"):
        admin_id = data[len("remove_admin_"):]
        if remove_admin(admin_id):
            await callback_query.message.answer(f"Admin {admin_id} o'chirildi.")
        else:
            await callback_query.message.answer("Xatolik yuz berdi.")
    elif data == "check_subscription":
        if await check_subscription(bot, callback_query.from_user.id):
            await callback_query.message.answer("✅ Obuna tasdiqlandi! /register buyrug'ini yuboring.")
        else:
            await callback_query.message.answer("🚫 Iltimos, barcha kanallarga obuna bo'ling.", reply_markup=get_subscription_keyboard())
    await callback_query.answer()

async def handle_admin_input(message: types.Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    if current_state == AdminStates.send_ad:
        ad_message = message.text
        if save_ad(ad_message):
            users = get_all_users()
            sent_count = 0
            for user in users:
                telegram_id, _, _, _, banned = user
                if not banned:
                    try:
                        await bot.send_message(telegram_id, ad_message, parse_mode='HTML')
                        sent_count += 1
                    except TelegramAPIError as e:
                        logger.error(f"Failed to send ad to {telegram_id}: {e}")
            await message.answer(f"📢 Reklama {sent_count} foydalanuvchiga yuborildi.")
        else:
            await message.answer("❌ Xatolik yuz berdi.")
        await state.clear()
    elif current_state == AdminStates.add_channel:
        channel_id = message.text
        if add_channel(channel_id):
            await message.answer(f"✅ Kanal {channel_id} qo'shildi.")
        else:
            await message.answer("❌ Xatolik yuz berdi yoki kanal allaqachon mavjud.")
        await state.clear()
    elif current_state == AdminStates.ban_user:
        telegram_id = message.text
        if ban_user(telegram_id):
            await message.answer(f"🚫 Foydalanuvchi {telegram_id} ban qilindi.")
        else:
            await message.answer("❌ Xatolik yuz berdi yoki foydalanuvchi topilmadi.")
        await state.clear()
    elif current_state == AdminStates.unban_user:
        telegram_id = message.text
        if unban_user(telegram_id):
            await message.answer(f"✅ Foydalanuvchi {telegram_id} bandan chiqarildi.")
        else:
            await message.answer("❌ Xatolik yuz berdi yoki foydalanuvchi topilmadi.")
        await state.clear()
    elif current_state == AdminStates.edit_user:
        telegram_id = message.text
        if is_user_registered(telegram_id):
            await state.update_data(telegram_id=telegram_id)
            await message.answer("Qaysi ma'lumotni tahrir qilmoqchisiz?", reply_markup=get_edit_user_keyboard())
        else:
            await message.answer("❌ Foydalanuvchi topilmadi.")
        await state.clear()
    elif current_state == AdminStates.edit_user_field:
        user_data = await state.get_data()
        telegram_id = user_data.get("telegram_id")
        field = user_data.get("edit_field")
        value = message.text
        if field == "phone_number" and not re.match(r'^\+998\d{9}$', value):
            await message.answer("❌ Telefon raqami +998XXXXXXXXX formatida bo'lishi kerak.")
            return
        if field in ["first_name", "last_name"] and not re.match(r'^[A-Za-z\s-]+$', value):
            await message.answer("❌ Faqat harflar, bo'shliq yoki defis kiriting.")
            return
        if update_user(telegram_id, field, escape(value)):
            await message.answer(f"✅ {field} muvaffaqiyatli yangilandi.")
        else:
            await message.answer("❌ Xatolik yuz berdi.")
        await state.clear()
    elif current_state == AdminStates.add_admin:
        admin_id = message.text
        if add_admin(admin_id):
            await message.answer(f"✅ Admin {admin_id} qo'shildi.")
        else:
            await message.answer("❌ Xatolik yuz berdi yoki admin allaqachon mavjud.")
        await state.clear()
    elif current_state == AdminStates.remove_admin:
        admin_id = message.text
        if remove_admin(admin_id):
            await message.answer(f"✅ Admin {admin_id} o'chirildi.")
        else:
            await message.answer("❌ Xatolik yuz berdi yoki admin topilmadi.")
        await state.clear()
def register_handlers(dp: Dispatcher):
    from aiogram.filters import Command

    dp.message.register(start_command, Command("start"))
    dp.message.register(help_command, Command("help"))
    dp.message.register(profile_command, Command("profile"))
    dp.message.register(register_command, Command("register"))
    dp.message.register(cancel_command, Command("cancel"))
    dp.message.register(test_command, Command("test"))
    dp.message.register(admin_command, Command("admin"))

    dp.message.register(get_first_name, Registration.first_name)
    dp.message.register(get_last_name, Registration.last_name)
    dp.message.register(get_phone_number, Registration.phone_number)

    dp.callback_query.register(admin_callback_query)
    dp.message.register(handle_admin_input, lambda message: str(message.from_user.id) in ADMIN_IDS)
