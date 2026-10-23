import asyncio
import sqlite3
import time
import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from aiohttp import web

TOKEN = "8853171720:AAEL0IESsyKmkwA-D8oTw9vKTe5ocfh3RQM"
ADMIN_ID = 1226163770
CARD_NUMBER = "9860156601572555"
CARD_HOLDER = "Rasulov Muhammadsodiq"

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# --- BAZA JADVALLARI ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT,
    balance REAL DEFAULT 0,
    premium_until TEXT DEFAULT '0'
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS movies (
    movie_code INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    description TEXT,
    file_id TEXT,
    is_paid INTEGER DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,
    channel_url TEXT,
    channel_name TEXT
)
""")
conn.commit()

# --- FSM STATES ---
class MovieBulkAddState(StatesGroup):
    waiting_for_title = State()
    waiting_for_type = State()
    waiting_for_videos = State()

class ChannelAddState(StatesGroup):
    waiting_for_id = State()
    waiting_for_url = State()
    waiting_for_name = State()

class DepositState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_receipt = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()


# --- OBUNANI TEKSHIRISH ---
async def check_subscriptions(user_id: int):
    cursor.execute("SELECT channel_id FROM channels")
    channels = cursor.fetchall()
    for (ch_id,) in channels:
        try:
            member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            pass
    return True

async def send_sub_request(message_or_callback):
    cursor.execute("SELECT channel_url, channel_name FROM channels")
    channels = cursor.fetchall()
    kb = [[InlineKeyboardButton(text=f"📢 {name}", url=url)] for url, name in channels]
    kb.append([InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_sub")])
    text = "⚠️ **Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:**"
    
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")
    else:
        await message_or_callback.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@dp.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: types.CallbackQuery):
    await callback.answer()
    if await check_subscriptions(callback.from_user.id):
        await show_main_menu(callback)
    else:
        await callback.message.answer("❌ Hali barcha kanallarga obuna bo'lmadingiz!")

# --- START ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    full_name = message.from_user.full_name or "Foydalanuvchi"

    cursor.execute("INSERT OR IGNORE INTO users (user_id, full_name) VALUES (?, ?)", (user_id, full_name))
    conn.commit()

    if not await check_subscriptions(user_id):
        await send_sub_request(message)
        return

    await show_main_menu(message)

# --- ASOSIY MENYU ---
async def show_main_menu(message_or_callback):
    keyboard = [
        [InlineKeyboardButton(text="💎 Premium & Balans", callback_data="premium_menu")],
        [InlineKeyboardButton(text="🌐 Serial Mini App (Sayt)", web_app=WebAppInfo(url="https://sizning-miniapp-saytingiz.uz"))]
    ]
    text = (
        "🤖 **AI Films Bot — Asosiy Tizim**\n\n"
        "🎬 Serialni ko'rish uchun **qism raqamini** yuboring (masalan: `1` yoki `2`)."
    )
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    if isinstance(message_or_callback, types.CallbackQuery):
        await message_or_callback.message.answer(text, reply_markup=markup, parse_mode="Markdown")
    else:
        await message_or_callback.answer(text, reply_markup=markup, parse_mode="Markdown")

@dp.callback_query(F.data == "main_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await show_main_menu(callback)

# --- PREMIUM & SHAXSIY KABINET ---
@dp.callback_query(F.data == "premium_menu")
async def premium_menu(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    cursor.execute("SELECT balance, premium_until FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0
    prem_until = row[1] if row else "0"

    if prem_until != "0" and float(prem_until) > time.time():
        prem_date = datetime.datetime.fromtimestamp(float(prem_until)).strftime('%Y-%m-%d %H:%M')
        prem_text = f"✅ Faol (Muddat: {prem_date})"
    else:
        prem_text = "❌ Faol emas"

    text = (
        f"💎 **Shaxsiy Kabinet & Premium**\n\n"
        f"💰 Balansingiz: **{balance:,.0f} so'm**\n"
        f"👑 Premium status: {prem_text}\n\n"
        f"👇 Obuna turini tanlang yoki balansingizni to'ldiring:"
    )
    
    kb = [
        [InlineKeyboardButton(text="⚡️ 3 kunlik (7,000 so'm)", callback_data="buy_prem_3")],
        [InlineKeyboardButton(text="⚡️ 1 haftalik (15,000 so'm)", callback_data="buy_prem_7")],
        [InlineKeyboardButton(text="⚡️ 30 kunlik (30,000 so'm)", callback_data="buy_prem_30")],
        [InlineKeyboardButton(text="💳 Hisobni to'ldirish", callback_data="deposit_balance")],
        [InlineKeyboardButton(text="◀️ Bosh Menyu", callback_data="main_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

# --- PREMIUM SOTIB OLISH ---
@dp.callback_query(F.data.startswith("buy_prem_"))
async def buy_premium(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    days_map = {"3": (3, 7000), "7": (7, 15000), "30": (30, 30000)}
    days, price = days_map[callback.data.replace("buy_prem_", "")]

    cursor.execute("SELECT balance, premium_until FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    balance = row[0] if row else 0

    if balance < price:
        await callback.answer(f"❌ Mablag' yetarli emas! Balansingiz: {balance:,.0f} so'm.", show_alert=True)
        return

    current_time = time.time()
    old_until = float(row[1]) if row and row[1] != "0" else current_time
    base_time = max(current_time, old_until)
    new_until = base_time + (days * 86400)

    new_balance = balance - price
    cursor.execute("UPDATE users SET balance = ?, premium_until = ? WHERE user_id = ?", (new_balance, str(new_until), user_id))
    conn.commit()

    await callback.answer(f"🎉 Tabriklaymiz! {days} kunlik Premium faollashdi!", show_alert=True)
    await premium_menu(callback)

# --- HISOBNI TO'LDIRISH ---
@dp.callback_query(F.data == "deposit_balance")
async def start_deposit(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(DepositState.waiting_for_amount)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="premium_menu")]])
    await callback.message.edit_text("💳 **Hisobni to'ldirish**\n\nMinimal summa: **15 000 so'm**\n\nTo'ldirmoqchi bo'lgan summani kiriting (masalan: `20000`):", reply_markup=kb, parse_mode="Markdown")

@dp.message(DepositState.waiting_for_amount)
async def process_deposit_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        if amount < 15000:
            await message.answer("❌ Minimal summa **15 000 so'm**. Qaytadan kiriting:", parse_mode="Markdown")
            return
        
        await state.update_data(amount=amount)
        await state.set_state(DepositState.waiting_for_receipt)
        
        text = (
            f"💳 **To'lov Rekvizitlari:**\n\n"
            f"📌 Karta: `{CARD_NUMBER}`\n"
            f"👤 F.I.O: **{CARD_HOLDER}**\n"
            f"💵 Summa: **{amount:,.0f} so'm**\n\n"
            f"📸 Pul o'tkazmasi chekini (skrinshotini) rasm ko'rinishida yuboring!"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="premium_menu")]])
        await message.answer(text, reply_markup=kb, parse_mode="Markdown")
    except ValueError:
        await message.answer("❌ Faqat raqam kiriting (masalan: `20000`):")

@dp.message(DepositState.waiting_for_receipt, F.photo)
async def process_receipt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    amount = data.get("amount")
    user = message.from_user
    photo_id = message.photo[-1].file_id

    await state.clear()
    await message.answer("✅ **To'lov cheki adminga yuborildi!**\nTekshirilgandan so'ng balansingiz to'ldiriladi.", parse_mode="Markdown")
    await show_main_menu(message)

    admin_text = (
        f"🔔 **Yangi To'lov Cheki!**\n\n"
        f"👤 Foydalanuvchi: {user.full_name} (@{user.username or 'yoq'})\n"
        f"🆔 ID: `{user.id}`\n"
        f"💵 Summa: **{amount:,.0f} so'm**"
    )
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user.id}_{amount}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_{user.id}")
        ]
    ])
    await bot.send_photo(chat_id=ADMIN_ID, photo=photo_id, caption=admin_text, reply_markup=admin_kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    parts = callback.data.split("_")
    user_id, amount = int(parts[1]), float(parts[2])

    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

    await callback.message.edit_caption(caption=callback.message.caption + f"\n\n✅ **TASDIQLANDI (+{amount:,.0f} so'm)**", parse_mode="Markdown")
    try:
        await bot.send_message(chat_id=user_id, text=f"🎉 **To'lovingiz tasdiqlandi!** Balansingizga **{amount:,.0f} so'm** qo'shildi.", parse_mode="Markdown")
    except Exception: pass

@dp.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[1])

    await callback.message.edit_caption(caption=callback.message.caption + f"\n\n❌ **RAD ETILDI**", parse_mode="Markdown")
    try:
        await bot.send_message(chat_id=user_id, text="❌ To'lov chekingiz rad etildi.", parse_mode="Markdown")
    except Exception: pass


# --- ADMIN PANEL ---
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    await message.answer("⚡️ **Admin Boshqaruv Markazi**", reply_markup=admin_kb(), parse_mode="Markdown")

def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Serial qismlarini yuklash", callback_data="admin_add_bulk")],
        [InlineKeyboardButton(text="🗑️ Qismni o'chirish", callback_data="admin_delete")],
        [InlineKeyboardButton(text="📢 Majburiy Kanallar", callback_data="admin_channels")],
        [InlineKeyboardButton(text="✉️ Xabar tarqatish", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Statistikalar", callback_data="admin_stats")],
        [InlineKeyboardButton(text="◀️ Bosh Menyu", callback_data="main_menu")]
    ])

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await state.clear()
    await callback.message.edit_text("⚡️ **Admin Boshqaruv Markazi**", reply_markup=admin_kb(), parse_mode="Markdown")


# --- QISMLARNI YUKLASH ---
@dp.callback_query(F.data == "admin_add_bulk")
async def start_add_bulk(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(MovieBulkAddState.waiting_for_title)
    await callback.message.answer("🎬 **1-Qadam:** Serial nomini kiriting:", parse_mode="Markdown")

@dp.message(MovieBulkAddState.waiting_for_title)
async def p_bulk_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip(), count=0)
    await state.set_state(MovieBulkAddState.waiting_for_type)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Bepul (Hamma ko'radi)", callback_data="type_free")],
        [InlineKeyboardButton(text="💎 Pullik (Faqat Premium)", callback_data="type_paid")]
    ])
    await message.answer("🔒 **2-Qadam:** Yuklanadigan qismlar turini tanlang:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("type_"))
async def p_bulk_type(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    is_paid = 1 if callback.data == "type_paid" else 0
    await state.update_data(is_paid=is_paid)
    await state.set_state(MovieBulkAddState.waiting_for_videos)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏁 Yuklashni yakunlash", callback_data="finish_bulk")]])
    await callback.message.edit_text(
        "📤 **3-Qadam:** Serial qismlarini video ko'rinishida yuboravering!\n"
        "Tugatgach 'Yuklashni yakunlash' tugmasini bosing.",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@dp.message(MovieBulkAddState.waiting_for_videos)
async def p_bulk_video(message: types.Message, state: FSMContext):
    file_id = message.video.file_id if message.video else (message.document.file_id if message.document else None)
    if not file_id:
        await message.answer("❌ Iltimos, video yuboring!")
        return

    data = await state.get_data()
    current_count = data.get("count", 0) + 1
    await state.update_data(count=current_count)

    cursor.execute(
        "INSERT INTO movies (title, description, file_id, is_paid) VALUES (?, ?, ?, ?)",
        (data.get("title"), f"{current_count}-Qism", file_id, data.get("is_paid"))
    )
    conn.commit()

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏁 Yuklashni yakunlash", callback_data="finish_bulk")]])
    await message.answer(f"✅ **{current_count}-Qism saqlandi!** Keyingisini yuboring:", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data == "finish_bulk")
async def finish_bulk(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    total = data.get("count", 0)
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel")]])
    await callback.message.edit_text(f"🎉 **Yuklash yakunlandi!** Jami {total} ta qism saqlandi.", reply_markup=kb, parse_mode="Markdown")


# --- KANALLAR ---
@dp.callback_query(F.data == "admin_channels")
async def admin_channels(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await state.clear()
    cursor.execute("SELECT channel_id, channel_name FROM channels")
    channels = cursor.fetchall()
    
    kb = [[InlineKeyboardButton(text="➕ Yangi Kanal qo'shish", callback_data="add_channel")]]
    for ch_id, ch_name in channels:
        kb.append([InlineKeyboardButton(text=f"❌ O'chirish: {ch_name}", callback_data=f"del_ch_{ch_id}")])
    kb.append([InlineKeyboardButton(text="◀️ Admin Panel", callback_data="admin_panel")])
    await callback.message.edit_text(f"📢 **Majburiy Kanallar:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@dp.callback_query(F.data == "add_channel")
async def start_add_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(ChannelAddState.waiting_for_id)
    await callback.message.answer("📌 Kanal ID raqamini kiriting (masalan: `-100...`):", parse_mode="Markdown")

@dp.message(ChannelAddState.waiting_for_id)
async def p_ch_id(message: types.Message, state: FSMContext):
    await state.update_data(id=message.text.strip())
    await state.set_state(ChannelAddState.waiting_for_url)
    await message.answer("🔗 Kanal havolasini kiriting:", parse_mode="Markdown")

@dp.message(ChannelAddState.waiting_for_url)
async def p_ch_url(message: types.Message, state: FSMContext):
    await state.update_data(url=message.text.strip())
    await state.set_state(ChannelAddState.waiting_for_name)
    await message.answer("📝 Kanal nomini kiriting:", parse_mode="Markdown")

@dp.message(ChannelAddState.waiting_for_name)
async def p_ch_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    cursor.execute("INSERT OR REPLACE INTO channels (channel_id, channel_url, channel_name) VALUES (?, ?, ?)", 
                   (data.get("id"), data.get("url"), message.text.strip()))
    conn.commit()
    await state.clear()
    await message.answer("✅ Kanal qo'shildi!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⚙️ Kanallar", callback_data="admin_channels")]]))

@dp.callback_query(F.data.startswith("del_ch_"))
async def execute_del_channel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("O'chirildi!")
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("DELETE FROM channels WHERE channel_id = ?", (callback.data.replace("del_ch_", ""),))
    conn.commit()
    await admin_channels(callback, state)


# --- BOSHQA ADMIN FUNKSIYALARI ---
@dp.callback_query(F.data == "admin_delete")
async def start_delete(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT movie_code, title FROM movies")
    movies = cursor.fetchall()
    if not movies:
        await callback.message.answer("Qismlar yo'q.")
        return
    kb = [[InlineKeyboardButton(text=f"❌ {c}-Qism: {t}", callback_data=f"del_m_{c}")] for c, t in movies]
    kb.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_panel")])
    await callback.message.edit_text("🗑️ O'chirmoqchi bo'lgan qismni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del_m_"))
async def execute_delete(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("O'chirildi!")
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("DELETE FROM movies WHERE movie_code = ?", (callback.data.replace("del_m_", ""),))
    conn.commit()
    await cb_admin_panel(callback, state)

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(BroadcastState.waiting_for_message)
    await callback.message.answer("📢 Hammaga yuboriladigan xabarni yuboring:")

@dp.message(BroadcastState.waiting_for_message)
async def send_broadcast(message: types.Message, state: FSMContext):
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    await state.clear()
    sent = 0
    for u in users:
        try:
            await message.send_copy(chat_id=u[0])
            sent += 1
            await asyncio.sleep(0.02)
        except Exception: pass
    await message.answer(f"✅ Xabar tarqatildi! Yetib bordi: {sent} ta.")

@dp.callback_query(F.data == "admin_stats")
async def show_stats(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cursor.execute("SELECT COUNT(*) FROM users")
    u_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM movies")
    m_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM channels")
    c_count = cursor.fetchone()[0]
    await callback.message.edit_text(f"📊 **Statistika:**\n\n👥 Foydalanuvchilar: {u_count}\n📺 Qismlar: {m_count}\n📢 Kanallar: {c_count}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin_panel")]]), parse_mode="Markdown")


# --- QISM YUBORISH ---
def build_episodes_keyboard():
    cursor.execute("SELECT movie_code, is_paid FROM movies ORDER BY movie_code ASC")
    movies = cursor.fetchall()
    if not movies: return None
    row, keyboard = [], []
    for code, is_paid in movies:
        badge = "💎" if is_paid else ""
        row.append(InlineKeyboardButton(text=f"{code}-Qism {badge}".strip(), callback_data=f"get_ep_{code}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row: keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def send_episode_to_user(message_or_callback, episode_code: str):
    user_id = message_or_callback.from_user.id
    if not await check_subscriptions(user_id):
        await send_sub_request(message_or_callback)
        return

    cursor.execute("SELECT title, description, file_id, is_paid FROM movies WHERE movie_code = ?", (episode_code,))
    movie = cursor.fetchone()
    if not movie:
        text = "❌ Bunday raqamli qism topilmadi."
        if isinstance(message_or_callback, types.CallbackQuery):
            await message_or_callback.message.answer(text)
        else:
            await message_or_callback.answer(text)
        return

    title, desc, file_id, is_paid = movie
    if is_paid == 1:
        cursor.execute("SELECT premium_until FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        prem_until = float(row[0]) if row and row[0] != "0" else 0
        if prem_until <= time.time():
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Premium sotib olish", callback_data="premium_menu")]])
            text = f"🔒 **{title} ({episode_code}-Qism)** faqat Premium obunachilar uchun!"
            if isinstance(message_or_callback, types.CallbackQuery):
                await message_or_callback.message.answer(text, reply_markup=kb, parse_mode="Markdown")
            else:
                await message_or_callback.answer(text, reply_markup=kb, parse_mode="Markdown")
            return

    caption = f"🎬 **{title}** ({episode_code}-Qism)"
    episodes_kb = build_episodes_keyboard()
    target = message_or_callback.message if isinstance(message_or_callback, types.CallbackQuery) else message_or_callback
    try:
        await target.answer_video(video=file_id, caption=caption, reply_markup=episodes_kb, parse_mode="Markdown")
    except Exception:
        await target.answer_document(document=file_id, caption=caption, reply_markup=episodes_kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("get_ep_"))
async def handle_ep_button(callback: types.CallbackQuery):
    await callback.answer()
    await send_episode_to_user(callback, callback.data.replace("get_ep_", ""))

@dp.message(F.text & ~F.text.startswith("/"))
async def handle_movie_code(message: types.Message, state: FSMContext):
    if await state.get_state() is not None: return
    await send_episode_to_user(message, message.text.strip())


# --- RENDER WEB SERVER (KEEP-ALIVE) ---
async def handle(request):
    return web.Response(text="Bot 24/7 ishlamoqda!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 10000)
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
