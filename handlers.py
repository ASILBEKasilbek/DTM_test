import logging
import re
from aiogram import Bot, Dispatcher, types
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
from asyncio import sleep

logger = logging.getLogger(__name__)

# Registration states
class Registration(StatesGroup):
    first_name = State()
    last_name = State()
    phone_number = State()

# Admin states
class AdminStates(StatesGroup):
    send_ad = State()
    confirm_ad = State()
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
        [InlineKeyboardButton(text="👤 Foydalanuvchilarni ko'rish", callback_data="view_users"),
         InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="edit_user")],
        [InlineKeyboardButton(text="🚫 Ban qilish", callback_data="ban_user"),
         InlineKeyboardButton(text="✅ Banni olib tashlash", callback_data="unban_user")],
        [InlineKeyboardButton(text="📢 Reklama yuborish", callback_data="send_ad"),
         InlineKeyboardButton(text="📜 Reklama tarixi", callback_data="view_ad_history")],
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel"),
         InlineKeyboardButton(text="➖ Kanal o'chirish", callback_data="remove_channel")],
        [InlineKeyboardButton(text="📊 Kanal statistikasi", callback_data="channel_stats")],
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="add_admin"),
         InlineKeyboardButton(text="➖ Admin o'chirish", callback_data="remove_admin")],
        [InlineKeyboardButton(text="📈 Statistika", callback_data="stats")]
    ])

def get_edit_user_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ism", callback_data="edit_first_name")],
        [InlineKeyboardButton(text="Familiya", callback_data="edit_last_name")],
        [InlineKeyboardButton(text="Telefon", callback_data="edit_phone_number")]
    ])

async def get_subscription_keyboard(bot: Bot) -> InlineKeyboardMarkup:
    keyboard_buttons = []
    for channel_id in MANDATORY_CHANNELS:
        try:
            chat = await bot.get_chat(channel_id)
            button = [InlineKeyboardButton(
                text=f"Obuna bo'lish: {chat.title}",
                url=f"https://t.me/{channel_id.lstrip('@')}"
            )]
            keyboard_buttons.append(button)
        except TelegramAPIError as e:
            logger.error(f"Error fetching channel {channel_id}: {e}")
            button = [InlineKeyboardButton(
                text=f"Kanalga obuna bo'lish ({channel_id})",
                url=f"https://t.me/{channel_id.lstrip('@')}"
            )]
            keyboard_buttons.append(button)
    keyboard_buttons.append([InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

# Utility Functions
def safe_db_operation(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Database error in {func.__name__}: {e}")
        return None

def is_valid_telegram_id(telegram_id: str) -> bool:
    return telegram_id.isdigit() and len(telegram_id) >= 5

async def validate_channel(bot: Bot, channel_id: str) -> bool:
    try:
        chat = await bot.get_chat(channel_id)
        return chat.type in ["channel", "supergroup"]
    except TelegramAPIError as e:
        logger.error(f"Invalid channel {channel_id}: {e}")
        return False

async def check_subscription(bot: Bot, user_id: int) -> tuple[bool, list]:
    unsubscribed_channels = []
    for channel_id in MANDATORY_CHANNELS:
        try:
            chat = await bot.get_chat(channel_id)
            if chat.type not in ["channel", "supergroup"]:
                logger.error(f"Invalid channel type for {channel_id}: {chat.type}")
                unsubscribed_channels.append(channel_id)
                continue
            bot_member = await bot.get_chat_member(channel_id, bot.id)
            if bot_member.status not in ["administrator", "creator"]:
                logger.warning(f"Bot is not an admin in {channel_id}")
            member = await bot.get_chat_member(channel_id, user_id)
            if member.status in ["left", "kicked"]:
                unsubscribed_channels.append(channel_id)
        except TelegramAPIError as e:
            if "chat not found" in str(e).lower():
                logger.error(f"Channel {channel_id} not found or bot lacks access")
            elif "user not found" in str(e).lower():
                logger.info(f"User {user_id} blocked the bot or is not in {channel_id}")
            else:
                logger.error(f"Error checking subscription for {channel_id}: {e}")
            unsubscribed_channels.append(channel_id)
    is_subscribed = len(unsubscribed_channels) == 0
    logger.info(f"User {user_id} subscription check: {'subscribed' if is_subscribed else 'not subscribed'}")
    return is_subscribed, unsubscribed_channels

async def send_paginated_users(callback_query: types.CallbackQuery, page: int = 1, page_size: int = 10):
    users = safe_db_operation(get_all_users) or []
    if not users:
        await callback_query.message.answer("Foydalanuvchilar topilmadi.")
        return

    total_users = len(users)
    total_pages = (total_users + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_users)

    response = f"👥 Foydalanuvchilar (sahifa {page}/{total_pages}):\n"
    for user in users[start_idx:end_idx]:
        telegram_id, first_name, last_name, phone_number, banned = user
        status = "🚫 Banlangan" if banned else "✅ Faol"
        response += f"ID: {telegram_id}, Ism: {first_name} {last_name}, Telefon: {phone_number}, Holat: {status}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    if page > 1:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"view_users_page_{page-1}")])
    if page < total_pages:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"view_users_page_{page+1}")])

    await callback_query.message.answer(response[:4000], reply_markup=keyboard)

async def send_user_selection(callback_query: types.CallbackQuery, state: FSMContext, page: int = 1, page_size: int = 5):
    users = safe_db_operation(get_all_users) or []
    if not users:
        await callback_query.message.answer("Foydalanuvchilar topilmadi.")
        return

    total_users = len(users)
    total_pages = (total_users + page_size - 1) // page_size
    start_idx = (page - 1) * page_size
    end_idx = min(start_idx + page_size, total_users)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for user in users[start_idx:end_idx]:
        telegram_id, first_name, last_name, _, _ = user
        keyboard.inline_keyboard.append([InlineKeyboardButton(
            text=f"{first_name} {last_name} (ID: {telegram_id})",
            callback_data=f"select_user_{telegram_id}"
        )])
    if page > 1:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"select_user_page_{page-1}")])
    if page < total_pages:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text="➡️ Keyingi", callback_data=f"select_user_page_{page+1}")])

    await callback_query.message.answer(f"👤 Tahrirlash uchun foydalanuvchini tanlang (sahifa {page}/{total_pages}):", reply_markup=keyboard)

async def send_ad_to_users(bot: Bot, ad_message: str) -> tuple[int, int, list]:
    users = safe_db_operation(get_all_users) or []
    sent_count = 0
    failed_count = 0
    failed_user_ids = []

    for i, user in enumerate(users):
        telegram_id, _, _, _, banned = user
        if banned:
            continue
        if not (await check_subscription(bot, telegram_id))[0]:
            logger.info(f"Skipping ad for {telegram_id}: not subscribed to all channels")
            continue
        try:
            await bot.send_message(telegram_id, ad_message, parse_mode='HTML')
            sent_count += 1
            if i % 30 == 29:
                await sleep(1)
        except TelegramAPIError as e:
            logger.error(f"Failed to send ad to {telegram_id}: {e}")
            failed_count += 1
            failed_user_ids.append(telegram_id)

    return sent_count, failed_count, failed_user_ids

async def notify_users_new_channel(bot: Bot, channel_id: str):
    users = safe_db_operation(get_all_users) or []
    for user in users:
        telegram_id, _, _, _, banned = user
        if banned:
            continue
        try:
            await bot.send_message(
                telegram_id,
                f"Yangi majburiy kanal qo'shildi! Iltimos, obuna bo'ling: https://t.me/{channel_id.lstrip('@')}",
                reply_markup=await get_subscription_keyboard(bot)
            )
        except TelegramAPIError as e:
            logger.error(f"Failed to notify {telegram_id} about new channel {channel_id}: {e}")

async def get_channel_stats(bot: Bot):
    response = "📊 Kanal statistikasi:\n"
    for channel_id in MANDATORY_CHANNELS:
        try:
            chat = await bot.get_chat(channel_id)
            member_count = await bot.get_chat_member_count(channel_id)
            response += f"{channel_id} ({chat.title}): {member_count} obunachi\n"
        except TelegramAPIError as e:
            logger.error(f"Error fetching stats for {channel_id}: {e}")
            response += f"{channel_id}: Ma'lumot olishda xatolik\n"
    return response or "Ma'lumot topilmadi."

# Handlers
async def start_command(message: types.Message, bot: Bot):
    if is_user_banned(message.from_user.id):
        await message.answer("Siz botdan foydalana olmaysiz, chunki siz ban qilingansiz.")
        return
    is_subscribed, unsubscribed_channels = await check_subscription(bot, message.from_user.id)
    if not is_subscribed:
        response = "Iltimos, quyidagi kanallarga obuna bo'ling:\n"
        for channel_id in unsubscribed_channels:
            try:
                chat = await bot.get_chat(channel_id)
                response += f"- {chat.title} (@{channel_id.lstrip('@')})\n"
            except TelegramAPIError:
                response += f"- @{channel_id.lstrip('@')}\n"
        await message.answer(response, reply_markup=await get_subscription_keyboard(bot))
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
    user = safe_db_operation(get_user, message.from_user.id)
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
    is_subscribed, unsubscribed_channels = await check_subscription(bot, message.from_user.id)
    if not is_subscribed:
        response = "Iltimos, quyidagi kanallarga obuna bo'ling:\n"
        for channel_id in unsubscribed_channels:
            try:
                chat = await bot.get_chat(channel_id)
                response += f"- {chat.title} (@{channel_id.lstrip('@')})\n"
            except TelegramAPIError:
                response += f"- @{channel_id.lstrip('@')}\n"
        await message.answer(response, reply_markup=await get_subscription_keyboard(bot))
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

    if safe_db_operation(register_user, telegram_id, first_name, last_name, phone_number):
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
    await message.answer("❌ Jarayon bekor Apar qilindi. /start buyrug'ini yuboring.")

async def test_command(message: types.Message, bot: Bot):
    if is_user_banned(message.from_user.id):
        await message.answer("Siz botdan foydalana olmaysiz, chunki siz ban qilingansiz.")
        return
    is_subscribed, unsubscribed_channels = await check_subscription(bot, message.from_user.id)
    if not is_subscribed:
        response = "Iltimos, quyidagi kanallarga obuna bo'ling:\n"
        for channel_id in unsubscribed_channels:
            try:
                chat = await bot.get_chat(channel_id)
                response += f"- {chat.title} (@{channel_id.lstrip('@')})\n"
            except TelegramAPIError:
                response += f"- @{channel_id.lstrip('@')}\n"
        await message.answer(response, reply_markup=await get_subscription_keyboard(bot))
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
    if data.startswith("view_users_page_"):
        page = int(data.split("_")[-1])
        await send_paginated_users(callback_query, page=page)
    elif data == "view_users":
        await send_paginated_users(callback_query)
    elif data == "edit_user":
        await send_user_selection(callback_query, state)
    elif data.startswith("select_user_page_"):
        page = int(data.split("_")[-1])
        await send_user_selection(callback_query, state, page=page)
    elif data.startswith("select_user_"):
        telegram_id = data.split("_")[-1]
        if safe_db_operation(is_user_registered, telegram_id):
            await state.update_data(telegram_id=telegram_id)
            await callback_query.message.answer("Qaysi ma'lumotni tahrir qilmoqchisiz?", reply_markup=get_edit_user_keyboard())
            await state.set_state(AdminStates.edit_user_field)
        else:
            await callback_query.message.answer("❌ Foydalanuvchi topilmadi.")
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
    elif data == "confirm_ad":
        ad_message = (await state.get_data()).get("ad_message")
        if safe_db_operation(save_ad, ad_message):
            sent_count, failed_count, failed_user_ids = await send_ad_to_users(bot, ad_message)
            response = f"📢 Reklama {sent_count} foydalanuvchiga yuborildi.\n"
            if failed_count:
                response += f"❌ {failed_count} foydalanuvchiga yuborilmadi.\n"
                if failed_user_ids:
                    response += f"Xatolik yuz bergan foydalanuvchilar: {', '.join(map(str, failed_user_ids[:10]))}"
                    if len(failed_user_ids) > 10:
                        response += "..."
            await callback_query.message.answer(response[:4000])
        else:
            await callback_query.message.answer("❌ Ma'lumotlarni saqlashda xatolik yuz berdi.")
        await state.clear()
    elif data == "cancel_ad":
        await callback_query.message.answer("❌ Reklama yuborish bekor qilindi.")
        await state.clear()
    elif data == "view_ad_history":
        ads = safe_db_operation(get_ad_history) or []
        if not ads:
            await callback_query.message.answer("Reklama tarixi topilmadi.")
            return
        response = "📢 Reklama tarixi:\n"
        for ad in ads[:10]:
            response += f"ID: {ad[0]}, Vaqt: {ad[2]}\nXabar: {ad[1][:200]}...\n\n"
        await callback_query.message.answer(response[:4000])
    elif data == "add_channel":
        await callback_query.message.answer("Kanal ID sini kiriting (masalan, @ChannelName yoki -100123456789):")
        await state.set_state(AdminStates.add_channel)
    elif data == "remove_channel":
        channels = safe_db_operation(get_channels) or []
        if not channels:
            await callback_query.message.answer("Majburiy kanallar topilmadi.")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=channel_id, callback_data=f"remove_{channel_id}")] for channel_id in channels
        ])
        await callback_query.message.answer("O'chiriladigan kanalni tanlang:", reply_markup=keyboard)
    elif data == "channel_stats":
        response = await get_channel_stats(bot)
        await callback_query.message.answer(response)
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
        admins = safe_db_operation(get_admins) or []
        if not admins:
            await callback_query.message.answer("Adminlar topilmadi.")
            return
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=admin_id, callback_data=f"remove_admin_{admin_id}")] for admin_id in admins
        ])
        await callback_query.message.answer("O'chiriladigan adminni tanlang:", reply_markup=keyboard)
    elif data == "stats":
        total_users = safe_db_operation(get_user_count) or 0
        users_today = safe_db_operation(get_users_today) or 0
        banned_users = len([u for u in safe_db_operation(get_all_users) or [] if u[4]])
        await callback_query.message.answer(
            f"📈 Statistika:\n"
            f"Jami foydalanuvchilar: {total_users}\n"
            f"Bugun qo'shilganlar: {users_today}\n"
            f"Banlanganlar: {banned_users}"
        )
    elif data.startswith("remove_"):
        channel_id = data[len("remove_"):]
        if safe_db_operation(remove_channel, channel_id):
            await callback_query.message.answer(f"Kanal {channel_id} o'chirildi.")
        else:
            await callback_query.message.answer("Xatolik yuz berdi.")
    elif data.startswith("remove_admin_"):
        admin_id = data[len("remove_admin_"):]
        if safe_db_operation(remove_admin, admin_id):
            await callback_query.message.answer(f"Admin {admin_id} o'chirildi.")
        else:
            await callback_query.message.answer("Xatolik yuz berdi.")
    elif data == "check_subscription":
        is_subscribed, unsubscribed_channels = await check_subscription(bot, callback_query.from_user.id)
        if is_subscribed:
            await callback_query.message.answer("✅ Obuna tasdiqlandi! /register buyrug'ini yuboring.")
        else:
            response = "🚫 Iltimos, quyidagi kanallarga obuna bo'ling:\n"
            for channel_id in unsubscribed_channels:
                try:
                    chat = await bot.get_chat(channel_id)
                    response += f"- {chat.title} (@{channel_id.lstrip('@')})\n"
                except TelegramAPIError:
                    response += f"- @{channel_id.lstrip('@')}\n"
            await callback_query.message.answer(response, reply_markup=await get_subscription_keyboard(bot))
    await callback_query.answer()

async def handle_admin_input(message: types.Message, state: FSMContext, bot: Bot):
    current_state = await state.get_state()
    if current_state == AdminStates.send_ad:
        ad_message = message.text
        if not ad_message.strip():
            await message.answer("❌ Reklama xabari bo'sh bo'lmasligi kerak.")
            return
        if len(ad_message) > 4096:
            await message.answer("❌ Reklama xabari 4096 belgidan uzun bo'lmasligi kerak.")
            return
        await state.update_data(ad_message=ad_message)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_ad")],
            [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_ad")]
        ])
        await message.answer(f"Reklama xabari:\n{ad_message}", parse_mode='HTML', reply_markup=keyboard)
        await state.set_state(AdminStates.confirm_ad)
    elif current_state == AdminStates.add_channel:
        channel_id = message.text
        if not await validate_channel(bot, channel_id):
            await message.answer("❌ Kanal ID si noto'g'ri yoki botda kanalga kirish huquqi yo'q.")
            return
        if safe_db_operation(add_channel, channel_id):
            chat = await bot.get_chat(channel_id)
            await message.answer(f"✅ Kanal {channel_id} ({chat.title}) qo'shildi.")
            await notify_users_new_channel(bot, channel_id)
        else:
            await message.answer("❌ Xatolik yuz berdi yoki kanal allaqachon mavjud.")
        await state.clear()
    elif current_state == AdminStates.ban_user:
        telegram_id = message.text
        if not is_valid_telegram_id(telegram_id):
            await message.answer("❌ Noto'g'ri Telegram ID. Faqat raqamlardan iborat bo'lishi kerak.")
            return
        if safe_db_operation(ban_user, telegram_id):
            await message.answer(f"🚫 Foydalanuvchi {telegram_id} ban qilindi.")
        else:
            await message.answer("❌ Foydalanuvchi topilmadi.")
        await state.clear()
    elif current_state == AdminStates.unban_user:
        telegram_id = message.text
        if not is_valid_telegram_id(telegram_id):
            await message.answer("❌ Noto'g'ri Telegram ID. Faqat raqamlardan iborat bo'lishi kerak.")
            return
        if safe_db_operation(unban_user, telegram_id):
            await message.answer(f"✅ Foydalanuvchi {telegram_id} bandan chiqarildi.")
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
        if safe_db_operation(update_user, telegram_id, field, escape(value)):
            await message.answer(f"✅ {field} muvaffaqiyatli yangilandi.")
        else:
            await message.answer("❌ Xatolik yuz berdi.")
        await state.clear()
    elif current_state == AdminStates.add_admin:
        admin_id = message.text
        if not is_valid_telegram_id(admin_id):
            await message.answer("❌ Noto'g'ri Telegram ID. Faqat raqamlardan iborat bo'lishi kerak.")
            return
        if safe_db_operation(add_admin, admin_id):
            await message.answer(f"✅ Admin {admin_id} qo'shildi.")
        else:
            await message.answer("❌ Xatolik yuz berdi yoki admin allaqachon mavjud.")
        await state.clear()
    elif current_state == AdminStates.remove_admin:
        admin_id = message.text
        if not is_valid_telegram_id(admin_id):
            await message.answer("❌ Noto'g'ri Telegram ID. Faqat raqamlardan iborat bo'lishi kerak.")
            return
        if safe_db_operation(remove_admin, admin_id):
            await message.answer(f"✅ Admin {admin_id} o'chirildi.")
        else:
            await message.answer("❌ Xatolik yuz berdi yoki admin topilmadi.")
        await state.clear()

def register_handlers(dp: Dispatcher):
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


