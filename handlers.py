from aiogram import Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import WEBSITE_URL
from database import register_user
from aiogram.utils.markdown import hlink


class Registration(StatesGroup):
    first_name = State()
    last_name = State()
    phone_number = State()

async def start_command(message: types.Message):
    await message.answer(
        "Xush kelibsiz! Ro'yxatdan o'tish uchun /register buyrug'ini yuboring."
    )

async def register_command(message: types.Message, state: FSMContext):
    await message.answer("Ismingizni kiriting:")
    await state.set_state(Registration.first_name)

async def get_first_name(message: types.Message, state: FSMContext):
    await state.update_data(first_name=message.text)
    await message.answer("Familiyangizni kiriting:")
    await state.set_state(Registration.last_name)

async def get_last_name(message: types.Message, state: FSMContext):
    await state.update_data(last_name=message.text)
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Kontakt yuborish", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Telefon raqamingizni yuborish uchun quyidagi tugmani bosing:", reply_markup=keyboard)
    await state.set_state(Registration.phone_number)

async def get_phone_number(message: types.Message, state: FSMContext):
    if not message.contact:
        # Agar user matn yozgan bo‘lsa va u + bilan boshlansa, raqam deb qabul qilamiz
        if message.text and message.text.startswith('+'):
            phone_number = message.text
        else:
            await message.answer("Iltimos, 'Kontakt yuborish' tugmasini bosing yoki telefon raqamingizni +998... formatida yozing.")
            return
    else:
        # Agar kontakt yuborilgan bo‘lsa, tekshiruv va raqamni olish
        if message.contact.user_id != message.from_user.id:
            await message.answer("Iltimos, faqat o‘z kontakt ma'lumotingizni yuboring.")
            return
        phone_number = message.contact.phone_number

    # Foydalanuvchi ma'lumotlarini olish
    user_data = await state.get_data()
    first_name = user_data["first_name"]
    last_name = user_data["last_name"]
    telegram_id = message.from_user.id

    # Ma'lumotlarni bazaga yozish
    if register_user(telegram_id, first_name, last_name, phone_number):
        auth_url = f"{WEBSITE_URL}/telegram-auth/{telegram_id}/"
        inline_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Test saytiga o'tish", url=auth_url)]
        ])
        await message.answer(
            f"Ro'yxatdan o'tdingiz!\n"
            f"Ism: {first_name}\n"
            f"Familiya: {last_name}\n"
            f"Telefon: {phone_number}\n\n"
            f"Test topshirish uchun quyidagi tugmani bosing:",
            parse_mode='HTML',
            reply_markup=inline_keyboard
        )
    else:
        await message.answer("Xatolik yuz berdi. Qayta urinib ko'ring.")
    
    await state.clear()

def register_handlers(dp: Dispatcher):
    dp.message.register(start_command, Command("start"))
    dp.message.register(register_command, Command("register"))
    dp.message.register(get_first_name, Registration.first_name)
    dp.message.register(get_last_name, Registration.last_name)
    dp.message.register(get_phone_number, Registration.phone_number)