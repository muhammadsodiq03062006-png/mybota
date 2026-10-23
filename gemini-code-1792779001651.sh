import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

# --- SOZLAMALAR ---
TOKEN = "8853171720:AAEL0IESsyKmkwA-D8oTw9vKTe5ocfh3RQM"
ADMIN_ID = 1226163770  # O'z Telegram ID raqamingizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- BAZANI SOZLASH ---
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT,
    is_authorized INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS movies (
    movie_code TEXT PRIMARY KEY,
    title TEXT,
    description TEXT,
    file_id TEXT
)
""")
conn.commit()

# Serialga kirish uchun umumiy maxfiy kod
SERIAL_SECRET_CODE = "KIBER2088"

class AuthState(StatesGroup):
    waiting_for_code = State()

class MovieAddState(StatesGroup):
    waiting_for_movie_code = State()
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_video = State()


# --- START BUYRUG'I ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    full_name = message.from_user.full_name
    
    cursor.execute("SELECT is_authorized FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT INTO users (user_id, full_name, is_authorized) VALUES (?, ?, 0)", (user_id, full_name))
        conn.commit()
        is_auth = 0
    else:
        is_auth = row[0]

    if not is_auth:
        await message.answer(
            "🎬 **Kiber Xotira 2088** serialiga xush kelibsiz!\n\n"
            "Botdan foydalanish uchun serial maxsus kodini kiriting:",
            parse_mode="Markdown"
        )
        await state.set_state(AuthState.waiting_for_code)
    else:
        await show_main_menu(message)


# --- SERIAL KODINI TEKSHIRISH ---
@dp.message(AuthState.waiting_for_code)
async def process_serial_code(message: types.Message, state: FSMContext):
    user_code = message.text.strip()
    user_id = message.from_user.id

    if user_code == SERIAL_SECRET_CODE:
        cursor.execute("UPDATE users SET is_authorized = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        await state.clear()
        await message.answer("✅ Kod tasdiqlandi! Asosiy menyuga xush kelibsiz.")
        await show_main_menu(message)
    else:
        await message.answer("❌ Noto'g'ri kod! Iltimos, qaytadan urinib ko'ring:")


# --- ASOSIY MENYU ---
async def show_main_menu(message_or_callback):
    keyboard = [
        [InlineKeyboardButton(text="🌐 Serial Mini App (Sayt)", web_app=WebAppInfo(url="https://sizning-miniapp-saytingiz.uz"))],
        [InlineKeyboardButton(text="🍿 Kinolar ro'yxati", callback_data="movie_list")]
    ]
    
    user_id = message_or_callback.from_user.id
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton(text="⚙️ Admin Panel (Kino qo'shish)", callback_data="admin_add_movie")])

    text = (
        "🤖 **Kiber Xotira 2088** — Bosh Menyu\n\n"
        "🎬 Kino yoki qismni ko'rish uchun uning **raqamini** (masalan: `10`) shunchaki chatga yozib yuboring!\n"
        "Yoki quyidagi tugmalardan foydalaning:"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.answer(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message_or_callback.answer(text, reply_markup=markup, parse_mode="Markdown")


@dp.callback_query(F.data == "main_menu")
async def back_to_menu(callback: types.CallbackQuery):
    await show_main_menu(callback)
    await callback.answer()


# --- KINOLAR RO'YXATI ---
@dp.callback_query(F.data == "movie_list")
async def list_movies(callback: types.CallbackQuery):
    cursor.execute("SELECT movie_code, title FROM movies")
    movies = cursor.fetchall()
    
    if not movies:
        await callback.answer("Hozircha kinolar qo'shilmagan.", show_alert=True)
        return

    text = "🍿 **Mavjud kinolar va qismlar ro'yxati:**\n\n"
    for code, title in movies:
        text += f"🔹 **Kod: {code}** — {title}\n"
    
    text += "\n💡 *Ko'rish uchun kino raqamini chatga yozing (masalan: 10)*"
    
    markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Orqaga", callback_data="main_menu")]])
    await callback.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
    await callback.answer()


# --- FOYDALANUVCHI KINO KODINI YOZSA (MASALAN: 10) ---
@dp.message(F.text & ~F.text.startswith("/"))
async def handle_movie_code_input(message: types.Message, state: FSMContext):
    # Agar foydalanuvchi hozir boshqa holatda (state) bo'lmasa
    current_state = await state.get_state()
    if current_state is not None:
        return

    user_id = message.from_user.id
    cursor.execute("SELECT is_authorized FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row or not row[0]:
        return # Agar avtorizatsiyadan o'tmagan bo'lsa e'tibor bermaydi

    input_code = message.text.strip()
    
    cursor.execute("SELECT title, description, file_id FROM movies WHERE movie_code = ?", (input_code,))
    movie = cursor.fetchone()

    if movie:
        title, desc, file_id = movie
        await message.answer_video(
            video=file_id,
            caption=f"🎬 **{title}** (Kod: {input_code})\n\n{desc}",
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Bunday raqamli kino topilmadi. Mavjud kodlarni ko'rish uchun '🍿 Kinolar ro'yxati' tugmasini bosing.")


# --- ADMIN: KINO QO'SHISH (FSM) ---
@dp.callback_query(F.data == "admin_add_movie")
async def start_admin_add(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID:
        return
    await callback.message.answer("🎬 Kino uchun raqam/kod kiriting (masalan: `10`):")
    await state.set_state(MovieAddState.waiting_for_movie_code)
    await callback.answer()

@dp.message(MovieAddState.waiting_for_movie_code)
async def process_m_code(message: types.Message, state: FSMContext):
    await state.update_data(movie_code=message.text.strip())
    await message.answer("📝 Kino nomini kiriting:")
    await state.set_state(MovieAddState.waiting_for_title)

@dp.message(MovieAddState.waiting_for_title)
async def process_m_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("📄 Kino haqida qisqacha tavsif (opisaniya) kiriting:")
    await state.set_state(MovieAddState.waiting_for_description)

@dp.message(MovieAddState.waiting_for_description)
async def process_m_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("📤 Kino videosini yuboring:")
    await state.set_state(MovieAddState.waiting_for_video)

@dp.message(MovieAddState.waiting_for_video, F.video)
async def process_m_video(message: types.Message, state: FSMContext):
    file_id = message.video.file_id
    data = await state.get_data()
    
    m_code = data.get("movie_code")
    title = data.get("title")
    desc = data.get("description")
    
    cursor.execute("INSERT OR REPLACE INTO movies (movie_code, title, description, file_id) VALUES (?, ?, ?, ?)", (m_code, title, desc, file_id))
    conn.commit()
    await state.clear()
    
    await message.answer(f"✅ Kino muvaffaqiyatli saqlandi!\n\n📌 **Kod:** `{m_code}`\n🎬 **Nomi:** {title}", parse_mode="Markdown")


# --- BOTNI FONDA ISHGA TUSHIRISH ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main))