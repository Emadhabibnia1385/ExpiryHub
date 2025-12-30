import asyncio
from datetime import datetime, date
import aiosqlite

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage


# ================== CONFIG ==================
BOT_TOKEN = "8458299595:AAFKVFF0wQZzFTOzMaJfB0_6SJxDkLcKN7w"
ALLOWED_USER_ID = 6235953021
DB_NAME = "sales.db"
# ===========================================


# ================== STATES ==================
class SaleState(StatesGroup):
    ITEM_NAME = State()
    ITEM_PRICE = State()
    ITEM_QTY = State()
    ITEMS_MENU = State()

    PAYMENT = State()
    BOOTH = State()
    NOTE = State()
# ===========================================


# ================== DB ======================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS sales(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            booth TEXT,
            total INTEGER,
            note TEXT
        );
        CREATE TABLE IF NOT EXISTS items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            name TEXT,
            price INTEGER,
            qty INTEGER,
            total INTEGER
        );
        """)
        await db.commit()
# ===========================================


# ================== KEYBOARDS ===============
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ فروش جدید", callback_data="new_sale")],
        [InlineKeyboardButton(text="📋 فروش‌های امروز", callback_data="today_sales")]
    ])

def items_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ افزودن کالا", callback_data="add_item")],
        [InlineKeyboardButton(text="✅ بستن فاکتور", callback_data="close_invoice")]
    ])

def booth_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="کتاب بالا", callback_data="کتاب بالا")],
        [InlineKeyboardButton(text="اسباب‌بازی", callback_data="اسباب‌بازی")],
        [InlineKeyboardButton(text="عطر", callback_data="عطر")],
        [InlineKeyboardButton(text="کتاب پایین", callback_data="کتاب پایین")]
    ])
# ===========================================


# ================== HANDLERS ================
async def start(msg: Message, state: FSMContext):
    if msg.from_user.id != ALLOWED_USER_ID:
        return
    await state.clear()
    await msg.answer("منوی اصلی:", reply_markup=main_menu())


async def new_sale(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id != ALLOWED_USER_ID:
        return
    await state.clear()
    await state.update_data(items=[])
    await cb.message.answer("نام کالا را وارد کنید:")
    await state.set_state(SaleState.ITEM_NAME)


async def item_name(msg: Message, state: FSMContext):
    await state.update_data(item_name=msg.text)
    await msg.answer("قیمت تک (تومان):")
    await state.set_state(SaleState.ITEM_PRICE)


async def item_price(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("عدد وارد کن")
    await state.update_data(item_price=int(msg.text))
    await msg.answer("تعداد:")
    await state.set_state(SaleState.ITEM_QTY)


async def item_qty(msg: Message, state: FSMContext):
    if not msg.text.isdigit():
        return await msg.answer("عدد وارد کن")

    data = await state.get_data()
    item = {
        "name": data["item_name"],
        "price": data["item_price"],
        "qty": int(msg.text),
        "total": data["item_price"] * int(msg.text)
    }

    items = data["items"]
    items.append(item)
    await state.update_data(items=items)

    await msg.answer(
        f"{item['name']} — {item['total']:,} تومان",
        reply_markup=items_menu()
    )
    await state.set_state(SaleState.ITEMS_MENU)


async def add_item(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("نام کالا:")
    await state.set_state(SaleState.ITEM_NAME)


async def close_invoice(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    total = sum(i["total"] for i in data["items"])
    await state.update_data(total=total)

    await cb.message.answer(
        f"جمع کل: {total:,} تومان\nانتخاب غرفه:",
        reply_markup=booth_menu()
    )
    await state.set_state(SaleState.BOOTH)


async def booth(cb: CallbackQuery, state: FSMContext):
    await state.update_data(booth=cb.data)
    await cb.message.answer("توضیحات (یا -):")
    await state.set_state(SaleState.NOTE)


async def note(msg: Message, state: FSMContext):
    data = await state.get_data()

    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "INSERT INTO sales VALUES (NULL,?,?,?,?)",
            (datetime.now().isoformat(), data["booth"], data["total"], msg.text)
        )
        sale_id = cur.lastrowid

        for i in data["items"]:
            await db.execute(
                "INSERT INTO items VALUES (NULL,?,?,?,?,?)",
                (sale_id, i["name"], i["price"], i["qty"], i["total"])
            )
        await db.commit()

    text = f"✅ فروش ثبت شد\n\nفاکتور #{sale_id}\n"
    for i in data["items"]:
        text += f"{i['name']} — {i['total']:,}\n"
    text += f"\nجمع: {data['total']:,}\nغرفه: {data['booth']}"

    await msg.answer(text, reply_markup=main_menu())
    await state.clear()


async def today_sales(cb: CallbackQuery):
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute(
            "SELECT id,total,booth FROM sales WHERE created_at LIKE ?",
            (f"{today}%",)
        )
        rows = await cur.fetchall()

    if not rows:
        return await cb.message.answer("امروز فروشی ثبت نشده")

    text = "📋 فروش‌های امروز:\n"
    for r in rows:
        text += f"#{r[0]} | {r[1]:,} | {r[2]}\n"

    await cb.message.answer(text)
# ===========================================


# ================== MAIN ====================
async def main():
    await init_db()

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.register(start, F.text == "/start")
    dp.callback_query.register(new_sale, F.data == "new_sale")
    dp.callback_query.register(today_sales, F.data == "today_sales")

    dp.message.register(item_name, SaleState.ITEM_NAME)
    dp.message.register(item_price, SaleState.ITEM_PRICE)
    dp.message.register(item_qty, SaleState.ITEM_QTY)

    dp.callback_query.register(add_item, F.data == "add_item")
    dp.callback_query.register(close_invoice, F.data == "close_invoice")

    dp.callback_query.register(booth, SaleState.BOOTH)
    dp.message.register(note, SaleState.NOTE)

    print("Bot is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
