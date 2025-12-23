#!/usr/bin/env python3
"""
ExpiryHub - سیستم مدیریت تمدید اکانت‌ها
توسعه‌دهنده: @EmadHabibnia
کانال: @ExpiryHub
"""

import asyncio
import os
import sqlite3
import base64
import html
from datetime import datetime, date, timedelta, time as dtime

import jdatetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# ==================== CONFIG ====================
TOKEN = os.getenv("TOKEN", "").strip()
ADMIN_CHAT_ID_RAW = os.getenv("ADMIN_CHAT_ID", "").strip()

if not TOKEN:
    raise RuntimeError("TOKEN is not set. Set it in .env file")

try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_RAW)
except:
    raise RuntimeError("ADMIN_CHAT_ID must be a valid integer")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ExpiryHub.db")
PAGE_SIZE = 10
MAIN_ADMIN_KEY = f"id:{ADMIN_CHAT_ID}"

# ==================== STATES ====================
(
    MENU,
    CHOOSING_TYPE,
    START_CHOICE,
    START_GREGORIAN,
    START_JALALI,
    DURATION_CHOICE,
    DURATION_MANUAL,
    BUYER_TG,
    LOGIN,
    PASSWORD,
    DESCRIPTION,
    TYPES_ADD_WAIT,
    TYPES_EDIT_WAIT,
    WAIT_RESTORE_FILE,
    WAIT_TEXT_EDIT,
    WAIT_EDIT_FIELD,
    WAIT_SEARCH_QUERY,
    ADMIN_REQUEST_ORG,
    ADMIN_REQUEST_TEXT,
    ADMIN_REJECT_REASON,
    ADMIN_ADD_WAIT,
) = range(21)

# ==================== STRINGS ====================
STRINGS = {
    "menu_add": "➕ افزودن اکانت",
    "menu_list": "📋 لیست اکانت‌ها",
    "menu_settings": "⚙️ تنظیمات ربات",
    "choose_type": "✨ نوع اکانت را انتخاب کن:",
    "no_types": "❌ هیچ «نوع اکانتی» ثبت نشده.",
    "choose_start": "📅 تاریخ شروع را انتخاب کن:",
    "start_today": "1️⃣ از امروز (خودکار)",
    "start_greg": "2️⃣ وارد کردن تاریخ میلادی",
    "start_jalali": "3️⃣ وارد کردن تاریخ شمسی",
    "ask_greg": "📅 تاریخ میلادی را وارد کن:\nYYYY-MM-DD\nمثال: 2025-12-16",
    "ask_jalali": "📅 تاریخ شمسی را وارد کن:\nYYYY-MM-DD\nمثال: 1403-09-25",
    "bad_greg": "❌ فرمت اشتباهه. مثال: 2025-12-16",
    "bad_jalali": "❌ تاریخ شمسی نامعتبره. مثال: 1403-09-25",
    "choose_duration": "⏳ مدت زمان اکانت رو انتخاب کن (روز):",
    "dur_manual_btn": "✍️ مدت دستی (روز)",
    "dur_manual_ask": "✍️ مدت زمان را به روز وارد کن (فقط عدد).\nمثال: 45",
    "bad_number": "❌ فقط عدد بفرست. مثال: 45",
    "bad_range": "❌ عدد نامعتبره. (بین 1 تا 3650)",
    "ask_tg": "👤 آیدی تلگرام را وارد کن (مثلاً @username):",
    "ask_login": "📧 یوزر/ایمیل را وارد کن:",
    "ask_password": "🔑 پسورد را وارد کن:",
    "ask_description": "📝 توضیحات بیشتر را وارد کن:",
    "list_empty": "❌ هیچ اکانتی ثبت نشده.",
    "expired_label": "منقضی",
    "today_label": "امروز",
    "more_info": "ℹ️ اطلاعات بیشتر",
    "settings_title": "⚙️ تنظیمات ربات\nیکی از گزینه‌ها را انتخاب کن:",
    "settings_db": "🗄 دیتابیس",
    "settings_texts": "✍️ ویرایش متن‌ها",
    "settings_types": "🗂 مدیریت نوع اکانت",
    "types_title": "🗂 مدیریت نوع اکانت\nیکی را انتخاب کن:",
    "types_add": "➕ افزودن نوع اکانت",
    "types_list": "📋 لیست نوع‌ها",
    "types_add_ask": "✍️ نام نوع اکانت را ارسال کن:",
    "types_added": "✅ نوع اکانت اضافه شد.",
    "types_add_exists": "⚠️ این نوع اکانت از قبل وجود دارد.",
    "types_none": "❌ هیچ نوع اکانتی وجود ندارد.",
    "types_edit_ask": "✍️ نام جدید نوع اکانت را ارسال کن:",
    "types_edited": "✅ نوع اکانت ویرایش شد.",
    "types_deleted": "🗑 نوع اکانت حذف شد.",
    "types_delete_blocked": "⚠️ این نوع اکانت در اکانت‌ها استفاده شده.",
    "db_title": "🗄 مدیریت دیتابیس\nیکی را انتخاب کن:",
    "db_backup": "📦 بکاپ",
    "db_restore": "♻️ ریستور",
    "db_backup_caption": "✅ بکاپ آماده است. فایل را دانلود کن:",
    "db_restore_ask": "♻️ لطفاً فایل بکاپ را همینجا ارسال کن (Document).",
    "db_restore_done": "✅ ریستور با موفقیت انجام شد.",
    "db_restore_bad": "❌ این فایل بکاپ معتبر نیست.",
    "home": "🏠 منو",
    "back_filters": "⬅️ تغییر فیلتر",
    "unknown": "⚠️ ورودی نامعتبر است.",
    "welcome_user": (
        "به ربات ExpiryHub خوش آمدید 👋\n\n"
        "اینجا می‌توانید وضعیت اکانت‌های خریداری‌شده را ببینید،\n"
        "تاریخ پایان هر اکانت را بررسی کنید و همیشه به‌روز باشید.\n\n"
        "━━━━━━━━━━━━━━\n"
        "🛠 توسعه‌دهنده: @emadhabibnia"
    ),
    "welcome_admin": (
        "به ربات ExpiryHub خوش آمدید 👋\n\n"
        "از منوی زیر مدیریت اکانت‌ها و تنظیمات ربات را انجام دهید.\n\n"
        "━━━━━━━━━━━━━━\n"
        "🛠 توسعه‌دهنده: @emadhabibnia"
    ),
    "user_inquiry": "🔍 استعلام اکانت‌های دریافتی",
    "admin_request": "⭐ درخواست ادمین شدن",
    "admin_management": "👥 مدیریت ادمین",
    "admin_requests_disabled": "❌ درخواست ادمین شدن در حال حاضر غیرفعال است.",
    "admin_request_sent": "✅ درخواست شما ثبت شد و منتظر تایید ادمین اصلی است.",
    "admin_request_org": "🏢 نام مجموعه را وارد کن:",
    "admin_request_text": "✍️ متن درخواست را وارد کن:",
    "admin_reject_reason": "✍️ علت رد درخواست را وارد کن:",
    "admin_added": "✅ ادمین اضافه شد.",
    "admin_add_prompt": "➕ آیدی عددی یا یوزرنیم ادمین را وارد کن (مثال: 123456 یا @username):",
    "admin_request_title": "📩 درخواست ادمین جدید",
    "admin_request_approved": "✅ درخواست شما تایید شد. اکنون ادمین هستید.",
    "admin_request_rejected": "❌ درخواست شما رد شد.\n\nعلت: {reason}",
    "admin_menu_title": "👥 مدیریت ادمین\nیکی از گزینه‌ها را انتخاب کن:",
    "admin_request_toggle_on": "✅ درخواست ادمین: فعال",
    "admin_request_toggle_off": "❌ درخواست ادمین: غیرفعال",
    "admin_share_toggle_on": "✅ اطلاعات مشترک ادمین‌ها",
    "admin_share_toggle_off": "❌ اطلاعات جداگانه ادمین‌ها",
    "user_accounts_empty": "❌ اکانتی برای شما ثبت نشده است.",
    "user_accounts_title": "📋 لیست اکانت‌های شما",
}

def tr(key: str) -> str:
    return STRINGS.get(key, key)

# ==================== HELPERS ====================
def safe_bt(val) -> str:
    return str(val).replace("`", "ˋ")

def enc_cb(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode("utf-8")).decode("ascii").rstrip("=")

def dec_cb(s: str) -> str:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii")).decode("utf-8")

def compute_end_date(start_str: str, duration_days: int) -> str:
    d = datetime.strptime(start_str, "%Y-%m-%d").date()
    return (d + timedelta(days=duration_days)).strftime("%Y-%m-%d")

def remaining_days(end_str: str) -> int:
    try:
        end_d = datetime.strptime(end_str, "%Y-%m-%d").date()
        return (end_d - date.today()).days
    except:
        return -999

def to_jalali_str(gregorian_yyyy_mm_dd: str) -> str:
    g = datetime.strptime(gregorian_yyyy_mm_dd, "%Y-%m-%d").date()
    j = jdatetime.date.fromgregorian(date=g)
    return f"{j.year:04d}-{j.month:02d}-{j.day:02d}"

def start_text(role: str) -> str:
    if role == "user":
        return tr("welcome_user")
    return tr("welcome_admin")

def format_account_update_message(cid: int, title: str, admin_key: str):
    msg = get_account_full_text(cid, admin_key)
    if not msg:
        return None
    return f"{title}\n\n{msg}"

def normalize_username(username: str) -> str:
    return username.lower().lstrip("@")

def user_variants(user) -> list[str]:
    variants = [str(user.id)]
    if user.username:
        uname = normalize_username(user.username)
        variants.append(f"@{uname}")
        variants.append(uname)
    return list(dict.fromkeys(variants))

def get_admin_record(user):
    conn = connect()
    cur = conn.cursor()
    if user.id == ADMIN_CHAT_ID:
        cur.execute("SELECT admin_key, role, active FROM admins WHERE admin_key=?", (MAIN_ADMIN_KEY,))
    elif user.username:
        cur.execute(
            "SELECT admin_key, role, active FROM admins WHERE tg_id=? OR lower(username)=?",
            (user.id, normalize_username(user.username)),
        )
    else:
        cur.execute("SELECT admin_key, role, active FROM admins WHERE tg_id=?", (user.id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {"admin_key": row[0], "role": row[1], "active": bool(row[2])}

def get_user_role(user) -> str:
    if user.id == ADMIN_CHAT_ID:
        return "main_admin"
    record = get_admin_record(user)
    if record and record["active"]:
        return "admin"
    return "user"

def get_admin_key(user) -> str | None:
    role = get_user_role(user)
    if role == "user":
        return None
    if role == "main_admin":
        return MAIN_ADMIN_KEY
    record = get_admin_record(user)
    return record["admin_key"] if record else None

def admin_requests_enabled() -> bool:
    return get_setting("admin_requests_enabled", "1") == "1"

def share_admin_data_enabled() -> bool:
    return get_setting("share_admin_data", "0") == "1"

def data_owner_key(admin_key: str) -> str:
    if admin_key != MAIN_ADMIN_KEY and share_admin_data_enabled():
        return MAIN_ADMIN_KEY
    return admin_key

def upsert_admin(admin_key: str, tg_id: int | None, username: str | None, role: str = "admin"):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO admins(admin_key, tg_id, username, role, active)
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(admin_key) DO UPDATE SET tg_id=excluded.tg_id, username=excluded.username, active=1
        """,
        (admin_key, tg_id, username, role),
    )
    conn.commit()
    conn.close()

async def require_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    role = get_user_role(update.effective_user)
    if role == "user":
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(tr("unknown"), reply_markup=main_menu_kb(role))
        else:
            await update.message.reply_text(tr("unknown"), reply_markup=main_menu_kb(role))
        return False
    return True

# ==================== DATABASE ====================
def connect():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = connect()
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_type_id INTEGER NOT NULL,
        admin_key TEXT NOT NULL DEFAULT '',
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        duration_days INTEGER NOT NULL,
        buyer_tg TEXT NOT NULL,
        login TEXT NOT NULL,
        password TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT ''
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS account_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_key TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL,
        UNIQUE(admin_key, title)
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS bot_texts (
        admin_key TEXT NOT NULL,
        key TEXT NOT NULL,
        body TEXT NOT NULL,
        PRIMARY KEY (admin_key, key)
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_key TEXT NOT NULL UNIQUE,
        tg_id INTEGER,
        username TEXT,
        role TEXT NOT NULL DEFAULT 'admin',
        active INTEGER NOT NULL DEFAULT 1
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS admin_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        org_name TEXT NOT NULL,
        request_text TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        reason TEXT,
        created_at TEXT NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)
    
    conn.commit()
    conn.close()
    init_default_texts()
    ensure_accounts_description_column()
    ensure_accounts_admin_key()
    ensure_account_types_admin_key()
    ensure_bot_texts_admin_key()
    ensure_admins()
    ensure_app_settings()

def ensure_accounts_description_column():
    conn = connect()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(accounts)")
    columns = {row[1] for row in cur.fetchall()}
    if "description" not in columns:
        cur.execute("ALTER TABLE accounts ADD COLUMN description TEXT NOT NULL DEFAULT ''")
        conn.commit()
    conn.close()

def ensure_accounts_admin_key():
    conn = connect()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(accounts)")
    columns = {row[1] for row in cur.fetchall()}
    if "admin_key" not in columns:
        cur.execute("ALTER TABLE accounts ADD COLUMN admin_key TEXT NOT NULL DEFAULT ''")
        conn.commit()
    cur.execute("UPDATE accounts SET admin_key=? WHERE admin_key=''", (MAIN_ADMIN_KEY,))
    conn.commit()
    conn.close()

def ensure_account_types_admin_key():
    conn = connect()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(account_types)")
    columns = {row[1] for row in cur.fetchall()}
    if "admin_key" not in columns:
        cur.execute("ALTER TABLE account_types ADD COLUMN admin_key TEXT NOT NULL DEFAULT ''")
        conn.commit()
    cur.execute("UPDATE account_types SET admin_key=? WHERE admin_key=''", (MAIN_ADMIN_KEY,))
    conn.commit()
    cur.execute("PRAGMA index_list(account_types)")
    indexes = cur.fetchall()
    has_composite_unique = False
    for idx in indexes:
        if idx[2]:  # unique
            cur.execute(f"PRAGMA index_info({idx[1]})")
            cols = [row[2] for row in cur.fetchall()]
            if cols == ["admin_key", "title"]:
                has_composite_unique = True
    if not has_composite_unique:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS account_types_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_key TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                UNIQUE(admin_key, title)
            )
        """)
        cur.execute("INSERT INTO account_types_new(id, admin_key, title) SELECT id, admin_key, title FROM account_types")
        cur.execute("DROP TABLE account_types")
        cur.execute("ALTER TABLE account_types_new RENAME TO account_types")
        conn.commit()
    conn.close()

def ensure_bot_texts_admin_key():
    conn = connect()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(bot_texts)")
    columns = {row[1] for row in cur.fetchall()}
    if "admin_key" not in columns:
        cur.execute("ALTER TABLE bot_texts ADD COLUMN admin_key TEXT NOT NULL DEFAULT ''")
        conn.commit()
    cur.execute("UPDATE bot_texts SET admin_key=? WHERE admin_key=''", (MAIN_ADMIN_KEY,))
    conn.commit()
    cur.execute("PRAGMA table_info(bot_texts)")
    pk_cols = [row[1] for row in cur.fetchall() if row[5] > 0]
    if pk_cols != ["admin_key", "key"]:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_texts_new (
                admin_key TEXT NOT NULL,
                key TEXT NOT NULL,
                body TEXT NOT NULL,
                PRIMARY KEY (admin_key, key)
            )
        """)
        cur.execute("INSERT INTO bot_texts_new(admin_key, key, body) SELECT admin_key, key, body FROM bot_texts")
        cur.execute("DROP TABLE bot_texts")
        cur.execute("ALTER TABLE bot_texts_new RENAME TO bot_texts")
        conn.commit()
    conn.close()

def ensure_admins():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id FROM admins WHERE admin_key=?", (MAIN_ADMIN_KEY,))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO admins(admin_key, tg_id, username, role, active) VALUES (?, ?, ?, 'main', 1)",
            (MAIN_ADMIN_KEY, ADMIN_CHAT_ID, None),
        )
    conn.commit()
    conn.close()

def ensure_app_settings():
    conn = connect()
    cur = conn.cursor()
    defaults = {
        "admin_requests_enabled": "1",
        "share_admin_data": "0",
    }
    for key, value in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO app_settings(key, value) VALUES (?, ?)",
            (key, value),
        )
    conn.commit()
    conn.close()

def init_default_texts():
    defaults = {
        "reminder_2days": (
            "سلام وقت بخیر 👋\n"
            "کاربر عزیز {buyer_tg}\n\n"
            "اکانت `{account_type}` شما با یوزر/ایمیل `{login}`\n"
            "تا `{days_left}` روز دیگر به پایان می‌رسد.\n\n"
            "📝 توضیحات: `{description}`\n\n"
            "در صورت تمایل به تمدید، لطفاً اقدام کنید ✅"
        ),
        "due_day": (
            "سلام وقت بخیر 👋\n"
            "کاربر عزیز {buyer_tg}\n\n"
            "اکانت `{account_type}` شما با یوزر/ایمیل `{login}`\n"
            "امروز به پایان رسیده است.\n\n"
            "📝 توضیحات: `{description}`\n\n"
            "🏦 نام بانک: {bank_name}\n"
            "💳 شماره کارت: {card_number}\n"
            "👤 به نام: {card_owner}"
        ),
        "inquiry": (
            "سلام 👋\n"
            "اکانت `{account_type}` شما\n\n"
            "📅 شروع: `{start_date}`\n"
            "⏳ مدت: `{duration_days}`\n"
            "🧾 پایان میلادی: `{end_date}`\n"
            "🗓 پایان شمسی: `{end_date_jalali}`\n"
            "⌛️ مانده: `{days_left}` روز\n\n"
            "📝 توضیحات: `{description}`"
        ),
        "bank_name": "نام بانک",
        "card_number": "0000-0000-0000-0000",
        "card_owner": "نام صاحب کارت",
    }
    
    conn = connect()
    cur = conn.cursor()
    for k, v in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO bot_texts(admin_key, key, body) VALUES (?,?,?)",
            (MAIN_ADMIN_KEY, k, v),
        )
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = "") -> str:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT value FROM app_settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO app_settings(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()

def get_bot_text(key: str, admin_key: str) -> str:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT body FROM bot_texts WHERE key=? AND admin_key=?", (key, admin_key))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""

def set_bot_text(key: str, body: str, admin_key: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO bot_texts(admin_key, key, body) VALUES (?, ?, ?) "
        "ON CONFLICT(admin_key, key) DO UPDATE SET body=excluded.body",
        (admin_key, key, body),
    )
    conn.commit()
    conn.close()

def get_types(admin_key: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title FROM account_types WHERE admin_key=? ORDER BY id DESC",
        (admin_key,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def add_type(title: str, admin_key: str):
    title = title.strip()
    if not title:
        return False, "empty"
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO account_types(admin_key, title) VALUES(?, ?)",
            (admin_key, title),
        )
        conn.commit()
        return True, "ok"
    except sqlite3.IntegrityError:
        return False, "exists"
    finally:
        conn.close()

def edit_type(type_id: int, new_title: str, admin_key: str):
    new_title = new_title.strip()
    if not new_title:
        return False
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE account_types SET title=? WHERE id=? AND admin_key=?",
            (new_title, type_id, admin_key),
        )
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_type(type_id: int, admin_key: str, owner_key: str):
    conn = connect()
    cur = conn.cursor()
    if admin_key != owner_key:
        cur.execute("SELECT COUNT(*) FROM accounts WHERE account_type_id=?", (type_id,))
    else:
        cur.execute(
            "SELECT COUNT(*) FROM accounts WHERE account_type_id=? AND admin_key=?",
            (type_id, admin_key),
        )
    used = cur.fetchone()[0]
    if used and used > 0:
        conn.close()
        return False, "blocked"
    cur.execute("DELETE FROM account_types WHERE id=? AND admin_key=?", (type_id, owner_key))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok, "ok"

def type_title_by_id(type_id: int, admin_key: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT title FROM account_types WHERE id=? AND admin_key=?",
        (type_id, admin_key),
    )
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def search_accounts(query: str, admin_key: str):
    query_like = f"%{query}%"
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.login, t.title, c.buyer_tg, c.end_date
        FROM accounts c
        JOIN account_types t ON t.id = c.account_type_id
        WHERE c.admin_key=? AND (c.login LIKE ? OR c.buyer_tg LIKE ? OR t.title LIKE ? OR c.description LIKE ?)
        ORDER BY c.end_date DESC
        LIMIT 50
    """, (admin_key, query_like, query_like, query_like, query_like))
    results = cur.fetchall()
    conn.close()
    return results

def get_user_accounts(user):
    variants = [v.lower() for v in user_variants(user)]
    placeholders = ",".join("?" for _ in variants)
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT c.id, c.login, c.end_date, t.title, c.admin_key
        FROM accounts c
        JOIN account_types t ON t.id = c.account_type_id
        WHERE lower(c.buyer_tg) IN ({placeholders})
        ORDER BY c.end_date ASC
        """,
        variants,
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def get_user_account_detail(cid: int, user):
    variants = [v.lower() for v in user_variants(user)]
    placeholders = ",".join("?" for _ in variants)
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT t.title, c.start_date, c.end_date, c.duration_days,
               c.buyer_tg, c.login, c.password, c.description
        FROM accounts c
        JOIN account_types t ON t.id=c.account_type_id
        WHERE c.id=? AND lower(c.buyer_tg) IN ({placeholders})
        """,
        [cid] + variants,
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    type_title, start_date_s, end_date_s, duration_days, buyer_tg, login, password, description = row
    end_j = to_jalali_str(end_date_s)
    rem = remaining_days(end_date_s)
    rem_label = tr("expired_label") if rem < 0 else str(rem)
    return (
        f"✨ نوع اکانت: `{safe_bt(type_title)}`\n"
        f"📅 شروع: `{safe_bt(start_date_s)}`\n"
        f"⏳ مدت: `{safe_bt(duration_days)}`\n"
        f"⌛️ مانده: `{safe_bt(rem_label)}`\n"
        f"🧾 پایان میلادی: `{safe_bt(end_date_s)}`\n"
        f"🗓 پایان شمسی: `{safe_bt(end_j)}`\n"
        f"👤 تلگرام: {buyer_tg}\n"
        f"📧 یوزر/ایمیل: `{safe_bt(login)}`\n"
        f"🔑 پسورد: `{safe_bt(password)}`\n"
        f"📝 توضیحات: `{safe_bt(description)}`"
    )

def get_accounts_count_by_type(admin_key: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT account_type_id, COUNT(*) 
        FROM accounts 
        WHERE admin_key=?
        GROUP BY account_type_id
    """, (admin_key,))
    results = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return results

def get_account_full_text(cid: int, admin_key: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.title, c.start_date, c.end_date, c.duration_days,
               c.buyer_tg, c.login, c.password, c.description
        FROM accounts c
        JOIN account_types t ON t.id=c.account_type_id
        WHERE c.id=? AND c.admin_key=?
    """, (cid, admin_key))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return None
    
    type_title, start_date_s, end_date_s, duration_days, buyer_tg, login, password, description = row
    end_j = to_jalali_str(end_date_s)
    rem = remaining_days(end_date_s)
    rem_label = tr("expired_label") if rem < 0 else str(rem)
    
    return (
        f"✨ نوع اکانت: `{safe_bt(type_title)}`\n"
        f"📅 شروع: `{safe_bt(start_date_s)}`\n"
        f"⏳ مدت: `{safe_bt(duration_days)}`\n"
        f"⌛️ مانده: `{safe_bt(rem_label)}`\n"
        f"🧾 پایان میلادی: `{safe_bt(end_date_s)}`\n"
        f"🗓 پایان شمسی: `{safe_bt(end_j)}`\n"
        f"👤 تلگرام: {buyer_tg}\n"
        f"📧 یوزر/ایمیل: `{safe_bt(login)}`\n"
        f"🔑 پسورد: `{safe_bt(password)}`\n"
        f"📝 توضیحات: `{safe_bt(description)}`"
    )

def render_template_for_account(key: str, cid: int, admin_key: str, owner_key: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.title, c.start_date, c.end_date, c.duration_days, c.buyer_tg, c.login, c.description
        FROM accounts c
        JOIN account_types t ON t.id=c.account_type_id
        WHERE c.id=? AND c.admin_key=?
    """, (cid, admin_key))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        return None
    
    account_type, start_date_s, end_date_s, duration_days, buyer_tg, login, description = row
    days_left = remaining_days(end_date_s)
    
    tpl = get_bot_text(key, owner_key)
    return tpl.format(
        buyer_tg=buyer_tg,
        account_type=account_type,
        login=login,
        start_date=start_date_s,
        end_date=end_date_s,
        end_date_jalali=to_jalali_str(end_date_s),
        duration_days=duration_days,
        days_left=days_left,
        description=description,
        bank_name=get_bot_text("bank_name", owner_key),
        card_number=get_bot_text("card_number", owner_key),
        card_owner=get_bot_text("card_owner", owner_key),
    )

# ==================== KEYBOARDS ====================
def chunk2(items):
    for i in range(0, len(items), 2):
        yield items[i:i + 2]

def main_menu_kb(role: str):
    if role == "user":
        rows = [
            [InlineKeyboardButton(tr("user_inquiry"), callback_data="user_inquiry")],
        ]
        if admin_requests_enabled():
            rows.append([InlineKeyboardButton(tr("admin_request"), callback_data="admin_request")])
        rows.append([InlineKeyboardButton("❓ راهنما", callback_data="cmd_help")])
        return InlineKeyboardMarkup(rows)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن اکانت جدید", callback_data="menu_add")],
        [
            InlineKeyboardButton("🔍 جستجو", callback_data="cmd_search"),
            InlineKeyboardButton("📋 لیست اکانت‌ها", callback_data="menu_list"),
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات", callback_data="menu_settings"),
            InlineKeyboardButton("❓ راهنما", callback_data="cmd_help"),
        ],
    ])

def settings_kb(role: str):
    rows = [
        [InlineKeyboardButton(tr("settings_types"), callback_data="settings_types")],
        [InlineKeyboardButton(tr("settings_texts"), callback_data="settings_texts")],
    ]
    if role == "main_admin":
        rows.append([InlineKeyboardButton(tr("settings_db"), callback_data="settings_db")])
        rows.append([InlineKeyboardButton(tr("admin_management"), callback_data="admin_management")])
    rows.append([InlineKeyboardButton(tr("home"), callback_data="home")])
    return InlineKeyboardMarkup(rows)

def db_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr("db_backup"), callback_data="db_backup")],
        [InlineKeyboardButton(tr("db_restore"), callback_data="db_restore")],
        [InlineKeyboardButton(tr("home"), callback_data="home")],
    ])

def types_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr("types_add"), callback_data="types_add")],
        [InlineKeyboardButton(tr("types_list"), callback_data="types_list:0")],
        [InlineKeyboardButton(tr("home"), callback_data="home")],
    ])

def type_pick_kb(admin_key: str):
    types = get_types(data_owner_key(admin_key))
    if not types:
        return None
    btns = [InlineKeyboardButton(t[1], callback_data=f"type_pick:{t[0]}") for t in types]
    rows = []
    for pair in chunk2(btns):
        rows.append(pair)
    rows.append([InlineKeyboardButton(tr("home"), callback_data="home")])
    return InlineKeyboardMarkup(rows)

def start_choice_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr("start_today"), callback_data="start_today")],
        [InlineKeyboardButton(tr("start_greg"), callback_data="start_greg")],
        [InlineKeyboardButton(tr("start_jalali"), callback_data="start_jalali")],
    ])

def duration_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("30", callback_data="dur_30"),
         InlineKeyboardButton("90", callback_data="dur_90")],
        [InlineKeyboardButton("180", callback_data="dur_180"),
         InlineKeyboardButton("365", callback_data="dur_365")],
        [InlineKeyboardButton(tr("dur_manual_btn"), callback_data="dur_manual")],
    ])

def list_filter_kb(admin_key: str):
    types = get_types(data_owner_key(admin_key))
    rows = [[InlineKeyboardButton("📋 کلیه اکانت‌ها", callback_data="list_all:0")]]
    
    if types:
        type_btns = [InlineKeyboardButton(t[1], callback_data=f"list_type:{t[0]}:0") for t in types]
        for pair in chunk2(type_btns):
            rows.append(pair)
    
    rows.append([InlineKeyboardButton(tr("home"), callback_data="home")])
    return InlineKeyboardMarkup(rows)

def info_actions_kb(cid: int, back_cb: str):
    b = enc_cb(back_cb)
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✏️ ویرایش", callback_data=f"edit_menu:{cid}:{b}"),
            InlineKeyboardButton("✅ تمدید", callback_data=f"renew:{cid}:{b}"),
            InlineKeyboardButton("🗑 حذف", callback_data=f"delete:{cid}:{b}"),
        ],
        [InlineKeyboardButton("📨 متن‌های آماده", callback_data=f"texts_ready:{cid}:{b}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=back_cb)],
        [InlineKeyboardButton(tr("home"), callback_data="home")],
    ])

def edit_menu_kb(cid: int, enc_back: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📅 ویرایش تاریخ شروع", callback_data=f"edit_start:{cid}:{enc_back}")],
        [InlineKeyboardButton("⏳ ویرایش مدت زمان", callback_data=f"edit_duration:{cid}:{enc_back}")],
        [InlineKeyboardButton("👤 ویرایش تلگرام", callback_data=f"edit_tg:{cid}:{enc_back}")],
        [InlineKeyboardButton("📧 ویرایش یوزر/ایمیل", callback_data=f"edit_login:{cid}:{enc_back}")],
        [InlineKeyboardButton("🔑 ویرایش پسورد", callback_data=f"edit_password:{cid}:{enc_back}")],
        [InlineKeyboardButton("📝 ویرایش توضیحات", callback_data=f"edit_description:{cid}:{enc_back}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"info:{cid}:{enc_back}")],
    ])

def ready_texts_kb(cid: int, enc_back: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 یادآوری (۲ روز)", callback_data=f"send_txt:reminder_2days:{cid}:{enc_back}")],
        [InlineKeyboardButton("📨 روز سررسید", callback_data=f"send_txt:due_day:{cid}:{enc_back}")],
        [InlineKeyboardButton("📨 استعلام", callback_data=f"send_txt:inquiry:{cid}:{enc_back}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"info:{cid}:{enc_back}")],
    ])

def texts_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ متن یادآوری ۲ روز", callback_data="txt_edit:reminder_2days")],
        [InlineKeyboardButton("✏️ متن روز سررسید", callback_data="txt_edit:due_day")],
        [InlineKeyboardButton("✏️ متن استعلام", callback_data="txt_edit:inquiry")],
        [InlineKeyboardButton("🏠 منو", callback_data="home")],
    ])

def back_to_config_kb(cid: int, enc_back: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"info:{cid}:{enc_back}")]
    ])

def back_to_list_kb(back_cb: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=back_cb)]
    ])

def admin_management_kb():
    req_enabled = admin_requests_enabled()
    share_enabled = share_admin_data_enabled()
    rows = [
        [InlineKeyboardButton(
            tr("admin_request_toggle_on") if req_enabled else tr("admin_request_toggle_off"),
            callback_data="admin_toggle_requests",
        )],
        [InlineKeyboardButton(
            tr("admin_share_toggle_on") if share_enabled else tr("admin_share_toggle_off"),
            callback_data="admin_toggle_share",
        )],
        [InlineKeyboardButton("➕ افزودن ادمین", callback_data="admin_add")],
        [InlineKeyboardButton(tr("home"), callback_data="home")],
    ]
    return InlineKeyboardMarkup(rows)

# ==================== COMMANDS ====================
async def setup_bot_commands(app):
    commands = [
        BotCommand("start", "شروع ربات"),
        BotCommand("add", "افزودن اکانت"),
        BotCommand("list", "لیست اکانت‌ها"),
        BotCommand("search", "جستجوی اکانت"),
        BotCommand("settings", "تنظیمات"),
        BotCommand("backup", "بکاپ"),
        BotCommand("help", "راهنما"),
    ]
    await app.bot.set_my_commands(commands)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    role = get_user_role(update.effective_user)
    await update.message.reply_text(start_text(role), reply_markup=main_menu_kb(role))
    return MENU

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    role = get_user_role(update.effective_user)
    await update.message.reply_text(
        "✅ ریست شد.\n\n" + start_text(role),
        reply_markup=main_menu_kb(role),
    )
    return MENU

async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data.clear()
    role = get_user_role(update.effective_user)
    await q.edit_message_text(start_text(role), reply_markup=main_menu_kb(role))
    return MENU

async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return MENU
    context.user_data.clear()
    admin_key = get_admin_key(update.effective_user)
    kb = type_pick_kb(admin_key)
    if kb is None:
        await update.message.reply_text(
            tr("no_types"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗂 مدیریت نوع", callback_data="settings_types")],
                [InlineKeyboardButton(tr("home"), callback_data="home")]
            ])
        )
        return MENU
    await update.message.reply_text(tr("choose_type"), reply_markup=kb)
    return CHOOSING_TYPE

async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return MENU
    context.user_data.clear()
    admin_key = get_admin_key(update.effective_user)
    await update.message.reply_text("📋 انتخاب فیلتر:", reply_markup=list_filter_kb(admin_key))
    return MENU

async def cmd_addtype(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return MENU
    context.user_data.clear()
    await update.message.reply_text(tr("types_add_ask"))
    return TYPES_ADD_WAIT

async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_user_role(update.effective_user) != "main_admin":
        await update.message.reply_text(tr("unknown"))
        return MENU
    if not os.path.exists(DB_PATH):
        await update.message.reply_text(tr("db_restore_bad"))
        return MENU
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"ExpiryHub_{ts}.db"
    backup_path = os.path.join(BASE_DIR, backup_name)
    
    try:
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(backup_path)
        src.backup(dst)
        dst.close()
        src.close()
        
        with open(backup_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=backup_name,
                caption=tr("db_backup_caption"),
            )
    finally:
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except:
            pass
    
    return MENU

async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return MENU
    context.user_data.clear()
    await update.message.reply_text(
        "🔍 جستجوی اکانت\n\n"
        "یکی از موارد زیر را جستجو کنید:\n"
        "• نام کاربری تلگرام (مثال: @username)\n"
        "• یوزر/ایمیل اکانت\n"
        "• نوع اکانت\n"
        "• توضیحات اکانت\n\n"
        "✍️ متن جستجو را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ لغو", callback_data="home")]
        ])
    )
    return WAIT_SEARCH_QUERY

async def cmd_types(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return MENU
    context.user_data.clear()
    admin_key = get_admin_key(update.effective_user)
    types = get_types(data_owner_key(admin_key))
    
    if not types:
        await update.message.reply_text(
            "❌ هیچ نوع اکانتی ثبت نشده.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ افزودن", callback_data="types_add")],
                [InlineKeyboardButton("🏠 منو", callback_data="home")]
            ])
        )
        return MENU
    
    counts = get_accounts_count_by_type(admin_key)
    text = "🗂 لیست نوع اکانت‌ها\n\n"
    buttons = []
    
    for tid, title in types:
        count = counts.get(tid, 0)
        text += f"• {title} ({count} اکانت)\n"
        buttons.append([
            InlineKeyboardButton(f"{title} ({count})", callback_data=f"list_type:{tid}:0")
        ])
    
    text += f"\n📊 مجموع: {len(types)} نوع"
    buttons.append([InlineKeyboardButton("➕ افزودن", callback_data="types_add")])
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="home")])
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    return MENU

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_admin(update, context):
        return MENU
    context.user_data.clear()
    role = get_user_role(update.effective_user)
    await update.message.reply_text(tr("settings_title"), reply_markup=settings_kb(role))
    return MENU

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    role = get_user_role(update.effective_user)
    
    help_text = """
📖 راهنمای کامل ExpiryHub

━━━━━━━━━━━━━━━━━━
📌 دستورات:

/start - شروع ربات
/add - افزودن اکانت
/list - لیست اکانت‌ها
/search - جستجوی اکانت
/settings - تنظیمات
/backup - بکاپ
/help - راهنما
/cancel - لغو

━━━━━━━━━━━━━━━━━━
✨ قابلیت‌ها:

🗂 مدیریت کامل اکانت‌ها
⏰ یادآوری خودکار
📨 متن‌های آماده
🔍 جستجوی پیشرفته
📊 دسته‌بندی

━━━━━━━━━━━━━━━━━━
📞 پشتیبانی:

توسعه‌دهنده: @EmadHabibnia
کانال: @ExpiryHub
━━━━━━━━━━━━━━━━━━
"""
    
    if role == "user":
        keyboard = main_menu_kb(role)
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ افزودن اکانت", callback_data="menu_add")],
            [
                InlineKeyboardButton("🔍 جستجو", callback_data="cmd_search"),
                InlineKeyboardButton("📋 لیست", callback_data="menu_list"),
            ],
            [InlineKeyboardButton("🏠 منوی اصلی", callback_data="home")],
        ])
    
    await update.message.reply_text(help_text, reply_markup=keyboard)
    return MENU

# ==================== USER INQUIRY ====================
async def user_inquiry_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = update.effective_user
    accounts = get_user_accounts(user)
    if not accounts:
        await q.edit_message_text(tr("user_accounts_empty"), reply_markup=main_menu_kb("user"))
        return MENU

    text = f"{tr('user_accounts_title')}\n\n"
    rows = []
    for i, (cid, login, end_date, type_title, _admin_key) in enumerate(accounts, 1):
        rem = remaining_days(end_date)
        status = tr("expired_label") if rem < 0 else (tr("today_label") if rem == 0 else f"{rem}")
        text += f"{i}. `{safe_bt(login)}` - {type_title}\n   ⏳ {status}\n\n"
        rows.append([InlineKeyboardButton(f"{i}. {login[:20]}", callback_data=f"user_info:{cid}")])
    rows.append([InlineKeyboardButton(tr("home"), callback_data="home")])
    await q.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(rows))
    return MENU

async def user_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, cid_s = q.data.split(":", 1)
    cid = int(cid_s)
    msg = get_user_account_detail(cid, update.effective_user)
    if not msg:
        await q.answer("یافت نشد", show_alert=True)
        return MENU
    await q.message.reply_text(
        msg,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(tr("user_inquiry"), callback_data="user_inquiry")],
            [InlineKeyboardButton(tr("home"), callback_data="home")],
        ]),
    )
    return MENU

# ==================== ADMIN REQUESTS ====================
async def admin_request_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not admin_requests_enabled():
        await q.edit_message_text(tr("admin_requests_disabled"), reply_markup=main_menu_kb("user"))
        return MENU
    context.user_data.clear()
    await q.edit_message_text(tr("admin_request_org"))
    return ADMIN_REQUEST_ORG

async def admin_request_org_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["admin_request_org"] = update.message.text.strip()
    await update.message.reply_text(tr("admin_request_text"))
    return ADMIN_REQUEST_TEXT

async def admin_request_text_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    org_name = context.user_data.get("admin_request_org", "").strip()
    request_text = update.message.text.strip()
    user = update.effective_user
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO admin_requests(user_id, username, org_name, request_text, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
        """,
        (user.id, normalize_username(user.username) if user.username else None, org_name, request_text, datetime.now().isoformat()),
    )
    request_id = cur.lastrowid
    conn.commit()
    conn.close()

    message = (
        f"{tr('admin_request_title')}\n\n"
        f"👤 کاربر: {user.id}\n"
        f"🔗 یوزرنیم: @{normalize_username(user.username) if user.username else '-'}\n"
        f"🏢 مجموعه: {org_name}\n\n"
        f"✍️ متن درخواست:\n{request_text}"
    )
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تایید", callback_data=f"admin_req_approve:{request_id}"),
            InlineKeyboardButton("❌ رد", callback_data=f"admin_req_reject:{request_id}"),
        ]
    ])
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, reply_markup=keyboard)
    await update.message.reply_text(tr("admin_request_sent"), reply_markup=main_menu_kb("user"))
    context.user_data.clear()
    return MENU

async def admin_request_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) != "main_admin":
        await q.answer(tr("unknown"), show_alert=True)
        return MENU
    _, req_id_s = q.data.split(":", 1)
    req_id = int(req_id_s)
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username FROM admin_requests WHERE id=? AND status='pending'",
        (req_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        await q.answer("یافت نشد", show_alert=True)
        return MENU
    user_id, username = row
    admin_key = f"id:{user_id}"
    upsert_admin(admin_key, user_id, username, role="admin")
    cur.execute("UPDATE admin_requests SET status='approved' WHERE id=?", (req_id,))
    conn.commit()
    conn.close()
    await context.bot.send_message(chat_id=user_id, text=tr("admin_request_approved"), reply_markup=main_menu_kb("admin"))
    await q.edit_message_text("✅ تایید شد.")
    return MENU

async def admin_request_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) != "main_admin":
        await q.answer(tr("unknown"), show_alert=True)
        return MENU
    _, req_id_s = q.data.split(":", 1)
    context.user_data["reject_request_id"] = int(req_id_s)
    await q.message.reply_text(tr("admin_reject_reason"))
    return ADMIN_REJECT_REASON

async def admin_reject_reason_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req_id = context.user_data.get("reject_request_id")
    if not req_id:
        await update.message.reply_text(tr("unknown"))
        return MENU
    reason = update.message.text.strip()
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id FROM admin_requests WHERE id=? AND status='pending'",
        (req_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        await update.message.reply_text("❌ درخواست پیدا نشد")
        return MENU
    user_id = row[0]
    cur.execute("UPDATE admin_requests SET status='rejected', reason=? WHERE id=?", (reason, req_id))
    conn.commit()
    conn.close()
    await context.bot.send_message(
        chat_id=user_id,
        text=tr("admin_request_rejected").format(reason=reason),
        reply_markup=main_menu_kb("user"),
    )
    context.user_data.clear()
    await update.message.reply_text("✅ رد شد.")
    return MENU

async def admin_management_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) != "main_admin":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb(get_user_role(update.effective_user)))
        return MENU
    await q.edit_message_text(tr("admin_menu_title"), reply_markup=admin_management_kb())
    return MENU

async def admin_toggle_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) != "main_admin":
        await q.answer(tr("unknown"), show_alert=True)
        return MENU
    new_value = "0" if admin_requests_enabled() else "1"
    set_setting("admin_requests_enabled", new_value)
    await q.edit_message_text(tr("admin_menu_title"), reply_markup=admin_management_kb())
    return MENU

async def admin_toggle_share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) != "main_admin":
        await q.answer(tr("unknown"), show_alert=True)
        return MENU
    new_value = "0" if share_admin_data_enabled() else "1"
    set_setting("share_admin_data", new_value)
    await q.edit_message_text(tr("admin_menu_title"), reply_markup=admin_management_kb())
    return MENU

async def admin_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) != "main_admin":
        await q.answer(tr("unknown"), show_alert=True)
        return MENU
    await q.message.reply_text(tr("admin_add_prompt"))
    return ADMIN_ADD_WAIT

async def admin_add_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    username = None
    tg_id = None
    if raw.startswith("@"):
        username = normalize_username(raw)
        admin_key = f"user:{username}"
    elif raw.isdigit():
        tg_id = int(raw)
        admin_key = f"id:{tg_id}"
    else:
        username = normalize_username(raw)
        admin_key = f"user:{username}"
    upsert_admin(admin_key, tg_id, username, role="admin")
    await update.message.reply_text(tr("admin_added"), reply_markup=admin_management_kb())
    return MENU

# ==================== SEARCH ====================
async def cmd_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    context.user_data.clear()
    await q.edit_message_text(
        "🔍 جستجوی اکانت\n\n"
        "یکی از موارد زیر را جستجو کنید:\n"
        "• نام کاربری تلگرام (مثال: @username)\n"
        "• یوزر/ایمیل اکانت\n"
        "• نوع اکانت\n"
        "• توضیحات اکانت\n\n"
        "✍️ متن جستجو را وارد کنید:"
    )
    return WAIT_SEARCH_QUERY

async def receive_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    admin_key = get_admin_key(update.effective_user)
    
    if not query or len(query) < 2:
        await update.message.reply_text("❌ حداقل 2 کاراکتر وارد کنید")
        return WAIT_SEARCH_QUERY
    
    results = search_accounts(query, admin_key)
    
    if not results:
        await update.message.reply_text(
            f"❌ نتیجه‌ای برای '{query}' پیدا نشد",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 جستجوی جدید", callback_data="cmd_search")],
                [InlineKeyboardButton("🏠 منو", callback_data="home")]
            ])
        )
        context.user_data.clear()
        return MENU
    
    text = f"🔍 نتایج: `{safe_bt(query)}`\n\n✅ {len(results)} نتیجه:\n\n"
    buttons = []
    
    for i, (cid, login, type_title, buyer_tg, end_date) in enumerate(results[:10], 1):
        rem = remaining_days(end_date)
        status = "منقضی ❌" if rem < 0 else f"{rem} روز ⏳"
        text += f"{i}. `{safe_bt(login)}` - {type_title}\n   👤 {buyer_tg} | {status}\n\n"
        buttons.append([
            InlineKeyboardButton(f"{i}. {login[:20]}", callback_data=f"info:{cid}:{enc_cb('search')}")
        ])
    
    if len(results) > 10:
        text += f"⚠️ {len(results) - 10} نتیجه دیگر"
    
    buttons.append([InlineKeyboardButton("🔍 جستجوی جدید", callback_data="cmd_search")])
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="home")])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    
    context.user_data.clear()
    return MENU

# ==================== MENU HANDLERS ====================
async def menu_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    context.user_data.clear()
    
    admin_key = get_admin_key(update.effective_user)
    kb = type_pick_kb(admin_key)
    if kb is None:
        await q.edit_message_text(
            tr("no_types"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗂 مدیریت", callback_data="settings_types")],
                [InlineKeyboardButton(tr("home"), callback_data="home")]
            ])
        )
        return MENU
    
    await q.edit_message_text(tr("choose_type"), reply_markup=kb)
    return CHOOSING_TYPE

async def menu_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    context.user_data.clear()
    admin_key = get_admin_key(update.effective_user)
    await q.edit_message_text("📋 انتخاب فیلتر:", reply_markup=list_filter_kb(admin_key))
    return MENU

async def menu_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    context.user_data.clear()
    role = get_user_role(update.effective_user)
    await q.edit_message_text(tr("settings_title"), reply_markup=settings_kb(role))
    return MENU

async def cmd_help_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    help_text = """
📖 راهنما

━━━━━━━━━━━━━━━━━━
/start - شروع
/add - افزودن اکانت
/list - لیست
/search - جستجو
/settings - تنظیمات
/help - راهنما

━━━━━━━━━━━━━━━━━━
📞 @EmadHabibnia
━━━━━━━━━━━━━━━━━━
"""
    
    role = get_user_role(update.effective_user)
    await q.edit_message_text(help_text, reply_markup=main_menu_kb(role))
    return MENU

async def cmd_types_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data.clear()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    admin_key = get_admin_key(update.effective_user)
    types = get_types(data_owner_key(admin_key))
    if not types:
        await q.edit_message_text(
            "❌ هیچ نوع اکانتی وجود ندارد",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ افزودن", callback_data="types_add")],
                [InlineKeyboardButton("🏠 منو", callback_data="home")]
            ])
        )
        return MENU
    
    counts = get_accounts_count_by_type(admin_key)
    text = "🗂 لیست نوع اکانت‌ها\n\n"
    buttons = []
    
    for tid, title in types:
        count = counts.get(tid, 0)
        text += f"• {title} ({count})\n"
        buttons.append([
            InlineKeyboardButton(f"{title} ({count})", callback_data=f"list_type:{tid}:0")
        ])
    
    text += f"\n📊 مجموع: {len(types)} نوع"
    buttons.append([InlineKeyboardButton("➕ افزودن", callback_data="types_add")])
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="home")])
    
    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    return MENU

# ==================== SETTINGS ====================
async def settings_types(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    await q.edit_message_text(tr("types_title"), reply_markup=types_kb())
    return MENU

async def settings_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) != "main_admin":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb(get_user_role(update.effective_user)))
        return MENU
    await q.edit_message_text(tr("db_title"), reply_markup=db_kb())
    return MENU

async def settings_texts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    await q.edit_message_text("✍️ ویرایش متن‌ها", reply_markup=texts_kb())
    return MENU

# ==================== TYPES ====================
async def types_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    context.user_data.clear()
    await q.edit_message_text(tr("types_add_ask"))
    return TYPES_ADD_WAIT

async def types_add_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_key = get_admin_key(update.effective_user)
    title = update.message.text.strip()
    ok, reason = add_type(title, data_owner_key(admin_key))
    if ok:
        await update.message.reply_text(tr("types_added"), reply_markup=types_kb())
    else:
        msg = tr("types_add_exists") if reason == "exists" else "❌ نام نامعتبر"
        await update.message.reply_text(msg, reply_markup=types_kb())
    return MENU

async def types_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    admin_key = get_admin_key(update.effective_user)
    
    page = 0
    if q.data.startswith("types_list:"):
        try:
            page = int(q.data.split(":", 1)[1])
        except:
            page = 0
    
    types = get_types(data_owner_key(admin_key))
    if not types:
        await q.edit_message_text(tr("types_none"), reply_markup=types_kb())
        return MENU
    
    total = len(types)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE or 1
    if page >= total_pages:
        page = total_pages - 1
    
    page_items = types[page * PAGE_SIZE: page * PAGE_SIZE + PAGE_SIZE]
    
    rows = []
    for tid, title in page_items:
        rows.append([
            InlineKeyboardButton(title, callback_data=f"noop_type:{tid}"),
            InlineKeyboardButton("✏️", callback_data=f"types_edit:{tid}:{page}"),
            InlineKeyboardButton("🗑", callback_data=f"types_del:{tid}:{page}"),
        ])
    
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"types_list:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"types_list:{page+1}"))
    if nav:
        rows.append(nav)
    
    rows.append([InlineKeyboardButton("🏠 منو", callback_data="menu_settings")])
    
    await q.edit_message_text(
        f"📋 لیست نوع‌ها\n\nصفحه {page+1} از {total_pages}",
        reply_markup=InlineKeyboardMarkup(rows)
    )
    return MENU

async def types_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    _, tid, page = q.data.split(":")
    context.user_data["types_edit_id"] = int(tid)
    context.user_data["types_edit_page"] = int(page)
    await q.edit_message_text(tr("types_edit_ask"))
    return TYPES_EDIT_WAIT

async def types_edit_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tid = context.user_data.get("types_edit_id")
    page = context.user_data.get("types_edit_page", 0)
    new_title = update.message.text.strip()
    admin_key = get_admin_key(update.effective_user)
    ok = edit_type(int(tid), new_title, data_owner_key(admin_key))
    if ok:
        await update.message.reply_text(tr("types_edited"), reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 بازگشت", callback_data=f"types_list:{page}")],
            [InlineKeyboardButton("🏠 منو", callback_data="menu_settings")]
        ]))
    else:
        await update.message.reply_text("❌ ویرایش ناموفق")
    context.user_data.clear()
    return MENU

async def types_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    _, tid, page = q.data.split(":")
    admin_key = get_admin_key(update.effective_user)
    owner_key = data_owner_key(admin_key)
    ok, reason = delete_type(int(tid), admin_key, owner_key)
    
    if not ok and reason == "blocked":
        await q.answer(tr("types_delete_blocked"), show_alert=True)
        return MENU
    
    await q.message.reply_text(tr("types_deleted"))
    await q.message.reply_text(
        "بازگشت 👇",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 لیست", callback_data=f"types_list:{page}")],
            [InlineKeyboardButton("🏠 منو", callback_data="menu_settings")]
        ])
    )
    return MENU

async def noop_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

# ==================== DB BACKUP/RESTORE ====================
async def db_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) != "main_admin":
        await q.message.reply_text(tr("unknown"))
        return MENU
    
    if not os.path.exists(DB_PATH):
        await q.message.reply_text(tr("db_restore_bad"))
        return MENU
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"ExpiryHub_{ts}.db"
    backup_path = os.path.join(BASE_DIR, backup_name)
    
    try:
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(backup_path)
        src.backup(dst)
        dst.close()
        src.close()
        
        with open(backup_path, "rb") as f:
            await q.message.reply_document(
                document=f,
                filename=backup_name,
                caption=tr("db_backup_caption"),
            )
    finally:
        try:
            if os.path.exists(backup_path):
                os.remove(backup_path)
        except:
            pass
    
    return MENU

async def db_restore_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) != "main_admin":
        await q.edit_message_text(tr("unknown"))
        return MENU
    await q.edit_message_text(tr("db_restore_ask"))
    return WAIT_RESTORE_FILE

async def db_restore_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_user_role(update.effective_user) != "main_admin":
        await update.message.reply_text(tr("unknown"))
        return MENU
    doc = update.message.document
    if not doc:
        await update.message.reply_text(tr("db_restore_bad"))
        return WAIT_RESTORE_FILE
    
    tmp_path = os.path.join(BASE_DIR, "restore_tmp.db")
    
    try:
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(custom_path=tmp_path)
        
        # Validate
        try:
            with open(tmp_path, "rb") as f:
                head = f.read(16)
            if head != b"SQLite format 3\x00":
                raise ValueError("Invalid")
        except:
            os.remove(tmp_path)
            await update.message.reply_text(tr("db_restore_bad"))
            return WAIT_RESTORE_FILE
        
        os.replace(tmp_path, DB_PATH)
        init_db()
        
        await update.message.reply_text(tr("db_restore_done"), reply_markup=main_menu_kb("main_admin"))
        return MENU
    
    except Exception as e:
        await update.message.reply_text("❌ خطا در ریستور")
        return WAIT_RESTORE_FILE
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except:
            pass

# ==================== TEXT EDITING ====================
async def text_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if get_user_role(update.effective_user) == "user":
        await q.edit_message_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    _, key = q.data.split(":", 1)
    context.user_data.clear()
    context.user_data["edit_text_key"] = key
    admin_key = get_admin_key(update.effective_user)
    owner_key = data_owner_key(admin_key)
    context.user_data["edit_text_owner"] = owner_key
    
    current = get_bot_text(key, owner_key)
    await q.edit_message_text(
        f"✏️ ویرایش متن ({key})\n\n"
        f"متن فعلی:\n<pre>{html.escape(current)}</pre>\n\n"
        f"✍️ متن جدید را ارسال کن:",
        parse_mode=ParseMode.HTML
    )
    return WAIT_TEXT_EDIT

async def text_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_user_role(update.effective_user) == "user":
        await update.message.reply_text(tr("unknown"), reply_markup=main_menu_kb("user"))
        return MENU
    key = context.user_data.get("edit_text_key")
    owner_key = context.user_data.get("edit_text_owner")
    if not key:
        await update.message.reply_text(tr("unknown"))
        return MENU
    
    body = update.message.text
    set_bot_text(key, body, owner_key)
    
    await update.message.reply_text("✅ متن ذخیره شد", reply_markup=texts_kb())
    context.user_data.clear()
    return MENU

# ==================== ADD ACCOUNT FLOW ====================
async def type_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    _, tid = q.data.split(":")
    admin_key = get_admin_key(update.effective_user)
    title = type_title_by_id(int(tid), data_owner_key(admin_key))
    if not title:
        role = get_user_role(update.effective_user)
        await q.edit_message_text(tr("no_types"), reply_markup=main_menu_kb(role))
        return MENU
    
    context.user_data["account_type_id"] = int(tid)
    context.user_data["account_type_title"] = title
    context.user_data["admin_key"] = admin_key
    await q.edit_message_text(tr("choose_start"), reply_markup=start_choice_kb())
    return START_CHOICE

async def start_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    is_edit = context.user_data.get("edit_mode") and context.user_data.get("edit_action") == "start"
    admin_key = get_admin_key(update.effective_user)
    
    if q.data == "start_today":
        new_start = date.today().strftime("%Y-%m-%d")
        
        if is_edit:
            cid = int(context.user_data["edit_cid"])
            enc_back = context.user_data["edit_enc_back"]
            
            conn = connect()
            cur = conn.cursor()
            cur.execute("SELECT duration_days FROM accounts WHERE id=? AND admin_key=?", (cid, admin_key))
            row = cur.fetchone()
            if not row:
                conn.close()
                await q.message.reply_text("❌ اکانت پیدا نشد")
                return MENU
            
            duration_days = int(row[0])
            new_end = compute_end_date(new_start, duration_days)
            cur.execute(
                "UPDATE accounts SET start_date=?, end_date=? WHERE id=? AND admin_key=?",
                (new_start, new_end, cid, admin_key),
            )
            conn.commit()
            conn.close()
            
            msg = format_account_update_message(cid, "✅ تاریخ شروع بروزرسانی شد", admin_key)
            if not msg:
                await q.message.reply_text("❌ اکانت پیدا نشد")
                return MENU
            await q.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_config_kb(cid, enc_back))
            context.user_data.clear()
            return MENU
        
        context.user_data["start_date"] = new_start
        await q.edit_message_text(tr("choose_duration"), reply_markup=duration_kb())
        return DURATION_CHOICE
    
    if q.data == "start_greg":
        await q.edit_message_text(tr("ask_greg"))
        return START_GREGORIAN
    
    if q.data == "start_jalali":
        await q.edit_message_text(tr("ask_jalali"))
        return START_JALALI
    
    return START_CHOICE

async def start_gregorian_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except:
        await update.message.reply_text(tr("bad_greg"))
        return START_GREGORIAN
    
    is_edit = context.user_data.get("edit_mode") and context.user_data.get("edit_action") == "start"
    admin_key = get_admin_key(update.effective_user)
    if is_edit:
        cid = int(context.user_data["edit_cid"])
        enc_back = context.user_data["edit_enc_back"]
        
        conn = connect()
        cur = conn.cursor()
        cur.execute("SELECT duration_days FROM accounts WHERE id=? AND admin_key=?", (cid, admin_key))
        row = cur.fetchone()
        if not row:
            conn.close()
            await update.message.reply_text("❌ اکانت پیدا نشد")
            return MENU
        
        duration_days = int(row[0])
        new_end = compute_end_date(text, duration_days)
        cur.execute(
            "UPDATE accounts SET start_date=?, end_date=? WHERE id=? AND admin_key=?",
            (text, new_end, cid, admin_key),
        )
        conn.commit()
        conn.close()
        
        msg = format_account_update_message(cid, "✅ تاریخ شروع بروزرسانی شد", admin_key)
        if not msg:
            await update.message.reply_text("❌ اکانت پیدا نشد")
            return MENU
        await update.message.reply_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_config_kb(cid, enc_back)
        )
        context.user_data.clear()
        return MENU
    
    context.user_data["start_date"] = text
    await update.message.reply_text(tr("choose_duration"), reply_markup=duration_kb())
    return DURATION_CHOICE

async def start_jalali_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        y, m, d = map(int, text.split("-"))
        g_date = jdatetime.date(y, m, d).togregorian()
        new_start = g_date.strftime("%Y-%m-%d")
    except:
        await update.message.reply_text(tr("bad_jalali"))
        return START_JALALI
    
    is_edit = context.user_data.get("edit_mode") and context.user_data.get("edit_action") == "start"
    admin_key = get_admin_key(update.effective_user)
    if is_edit:
        cid = int(context.user_data["edit_cid"])
        enc_back = context.user_data["edit_enc_back"]
        
        conn = connect()
        cur = conn.cursor()
        cur.execute("SELECT duration_days FROM accounts WHERE id=? AND admin_key=?", (cid, admin_key))
        row = cur.fetchone()
        if not row:
            conn.close()
            await update.message.reply_text("❌ اکانت پیدا نشد")
            return MENU
        
        duration_days = int(row[0])
        new_end = compute_end_date(new_start, duration_days)
        cur.execute(
            "UPDATE accounts SET start_date=?, end_date=? WHERE id=? AND admin_key=?",
            (new_start, new_end, cid, admin_key),
        )
        conn.commit()
        conn.close()
        
        msg = format_account_update_message(cid, "✅ تاریخ شروع بروزرسانی شد", admin_key)
        if not msg:
            await update.message.reply_text("❌ اکانت پیدا نشد")
            return MENU
        await update.message.reply_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_config_kb(cid, enc_back)
        )
        context.user_data.clear()
        return MENU
    
    context.user_data["start_date"] = new_start
    await update.message.reply_text(tr("choose_duration"), reply_markup=duration_kb())
    return DURATION_CHOICE

async def duration_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    is_edit = context.user_data.get("edit_mode") and context.user_data.get("edit_action") == "duration"
    mapping = {"dur_30": 30, "dur_90": 90, "dur_180": 180, "dur_365": 365}
    admin_key = get_admin_key(update.effective_user)
    
    if q.data in mapping:
        days = mapping[q.data]
        
        if is_edit:
            cid = int(context.user_data["edit_cid"])
            enc_back = context.user_data["edit_enc_back"]
            
            conn = connect()
            cur = conn.cursor()
            cur.execute("SELECT start_date FROM accounts WHERE id=? AND admin_key=?", (cid, admin_key))
            row = cur.fetchone()
            if not row:
                conn.close()
                await q.edit_message_text("❌ اکانت پیدا نشد")
                return MENU
            
            start_date_s = row[0]
            new_end = compute_end_date(start_date_s, days)
            cur.execute(
                "UPDATE accounts SET duration_days=?, end_date=? WHERE id=? AND admin_key=?",
                (days, new_end, cid, admin_key),
            )
            conn.commit()
            conn.close()
            
            msg = format_account_update_message(cid, "✅ مدت زمان بروزرسانی شد", admin_key)
            if not msg:
                await q.message.reply_text("❌ اکانت پیدا نشد")
                return MENU
            await q.message.reply_text(
                msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_to_config_kb(cid, enc_back)
            )
            context.user_data.clear()
            return MENU
        
        context.user_data["duration_days"] = days
        context.user_data["end_date"] = compute_end_date(context.user_data["start_date"], days)
        await q.edit_message_text(tr("ask_tg"))
        return BUYER_TG
    
    if q.data == "dur_manual":
        await q.edit_message_text(tr("dur_manual_ask"))
        return DURATION_MANUAL
    
    return DURATION_CHOICE

async def duration_manual_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text(tr("bad_number"))
        return DURATION_MANUAL
    
    days = int(text)
    if days <= 0 or days > 3650:
        await update.message.reply_text(tr("bad_range"))
        return DURATION_MANUAL
    
    is_edit = context.user_data.get("edit_mode") and context.user_data.get("edit_action") == "duration"
    admin_key = get_admin_key(update.effective_user)
    if is_edit:
        cid = int(context.user_data["edit_cid"])
        enc_back = context.user_data["edit_enc_back"]
        
        conn = connect()
        cur = conn.cursor()
        cur.execute("SELECT start_date FROM accounts WHERE id=? AND admin_key=?", (cid, admin_key))
        row = cur.fetchone()
        if not row:
            conn.close()
            await update.message.reply_text("❌ اکانت پیدا نشد")
            return MENU
        
        start_date_s = row[0]
        new_end = compute_end_date(start_date_s, days)
        cur.execute(
            "UPDATE accounts SET duration_days=?, end_date=? WHERE id=? AND admin_key=?",
            (days, new_end, cid, admin_key),
        )
        conn.commit()
        conn.close()
        
        msg = format_account_update_message(cid, "✅ مدت زمان بروزرسانی شد", admin_key)
        if not msg:
            await update.message.reply_text("❌ اکانت پیدا نشد")
            return MENU
        await update.message.reply_text(
            msg,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_config_kb(cid, enc_back)
        )
        context.user_data.clear()
        return MENU
    
    context.user_data["duration_days"] = days
    context.user_data["end_date"] = compute_end_date(context.user_data["start_date"], days)
    await update.message.reply_text(tr("ask_tg"))
    return BUYER_TG

async def buyer_tg_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["buyer_tg"] = str(update.message.text).strip()
    await update.message.reply_text(tr("ask_login"))
    return LOGIN

async def login_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["login"] = str(update.message.text).strip()
    await update.message.reply_text(tr("ask_password"))
    return PASSWORD

async def password_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["password"] = str(update.message.text).strip()
    await update.message.reply_text(tr("ask_description"))
    return DESCRIPTION

async def description_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["description"] = str(update.message.text).strip()

    type_title = context.user_data["account_type_title"]
    admin_key = context.user_data["admin_key"]
    start_date_s = context.user_data["start_date"]
    duration_days = int(context.user_data["duration_days"])
    end_date_s = context.user_data["end_date"]
    buyer_tg = context.user_data["buyer_tg"]
    login = context.user_data["login"]
    password = context.user_data["password"]
    description = context.user_data.get("description", "")

    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO accounts
            (account_type_id, admin_key, start_date, end_date, duration_days, buyer_tg, login, password, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(context.user_data["account_type_id"]),
            admin_key, start_date_s, end_date_s, duration_days,
            buyer_tg, login, password, description,
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        await update.message.reply_text("❌ خطا در ذخیره‌سازی")
        return MENU

    end_j = to_jalali_str(end_date_s)
    msg = (
        "✅ اکانت اضافه شد\n\n"
        f"✨ نوع: `{safe_bt(type_title)}`\n"
        f"📅 شروع: `{safe_bt(start_date_s)}`\n"
        f"⏳ مدت: `{safe_bt(duration_days)}`\n"
        f"🧾 پایان میلادی: `{safe_bt(end_date_s)}`\n"
        f"🗓 پایان شمسی: `{safe_bt(end_j)}`\n"
        f"👤 تلگرام: {buyer_tg}\n"
        f"📧 یوزر: `{safe_bt(login)}`\n"
        f"🔑 پسورد: `{safe_bt(password)}`\n"
        f"📝 توضیحات: `{safe_bt(description)}`"
    )
    role = get_user_role(update.effective_user)
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb(role))
    context.user_data.clear()
    return MENU

# ==================== LIST ACCOUNTS ====================
async def list_all_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, page_s = q.data.split(":")
    page = int(page_s)
    return await show_accounts_list(update, context, None, page)

async def list_type_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, tid_s, page_s = q.data.split(":")
    return await show_accounts_list(update, context, int(tid_s), int(page_s))

async def show_accounts_list(update: Update, context: ContextTypes.DEFAULT_TYPE, type_id, page):
    q = update.callback_query
    admin_key = get_admin_key(update.effective_user)
    
    conn = connect()
    cur = conn.cursor()
    if type_id is None:
        cur.execute("""
            SELECT c.id, c.login, c.end_date, t.title
            FROM accounts c
            JOIN account_types t ON t.id = c.account_type_id
            WHERE c.admin_key=?
        """, (admin_key,))
    else:
        cur.execute("""
            SELECT c.id, c.login, c.end_date, t.title
            FROM accounts c
            JOIN account_types t ON t.id = c.account_type_id
            WHERE c.account_type_id=? AND c.admin_key=?
        """, (type_id, admin_key))
    raw = cur.fetchall()
    conn.close()
    
    if not raw:
        await q.edit_message_text(
            tr("list_empty"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(tr("back_filters"), callback_data="menu_list")],
                [InlineKeyboardButton(tr("home"), callback_data="home")]
            ])
        )
        return MENU
    
    active, expired = [], []
    for cid, login, end_date_s, type_title in raw:
        try:
            rem = remaining_days(end_date_s)
        except:
            rem = -999
        (active if rem >= 0 else expired).append((cid, login, rem, type_title))
    
    active.sort(key=lambda x: x[2])
    expired.sort(key=lambda x: x[2])
    items = active + expired
    
    total = len(items)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE or 1
    if page >= total_pages:
        page = total_pages - 1
    
    page_items = items[page * PAGE_SIZE: page * PAGE_SIZE + PAGE_SIZE]
    
    kb_rows = []
    for cid, login, rem, _type_title in page_items:
        label = tr("expired_label") if rem < 0 else (tr("today_label") if rem == 0 else f"{rem}")
        back_cb = f"list_all:{page}" if type_id is None else f"list_type:{type_id}:{page}"
        kb_rows.append([
            InlineKeyboardButton(login, callback_data=f"noop:{cid}"),
            InlineKeyboardButton(label, callback_data=f"noop:{cid}"),
            InlineKeyboardButton(tr("more_info"), callback_data=f"info:{cid}:{enc_cb(back_cb)}"),
        ])
    
    nav_row = []
    if page > 0:
        prev_cb = f"list_all:{page-1}" if type_id is None else f"list_type:{type_id}:{page-1}"
        nav_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=prev_cb))
    if page < total_pages - 1:
        next_cb = f"list_all:{page+1}" if type_id is None else f"list_type:{type_id}:{page+1}"
        nav_row.append(InlineKeyboardButton("➡️ بعدی", callback_data=next_cb))
    if nav_row:
        kb_rows.append(nav_row)
    
    kb_rows.append([InlineKeyboardButton(tr("back_filters"), callback_data="menu_list")])
    kb_rows.append([InlineKeyboardButton(tr("home"), callback_data="home")])
    
    title = "📋 کلیه اکانت‌ها" if type_id is None else f"📋 {type_title_by_id(type_id, data_owner_key(admin_key)) or '-'}"
    header = (
        f"{title}\n\n"
        "اکانت‌ها بر اساس نزدیک‌ترین تاریخ پایان،\n"
        "از بالا به پایین مرتب شده‌اند ⏳\n\n"
        "اکانت‌هایی که تاریخ آن‌ها به پایان رسیده،\n"
        "در انتهای لیست با وضعیت «منقضی» نمایش داده می‌شوند.\n\n"
        "برای مشاهده جزئیات هر اکانت،\n"
        "روی گزینه «ℹ️ اطلاعات بیشتر» کلیک کنید 👇\n\n"
        f"صفحه {page+1} از {total_pages}"
    )
    
    await q.edit_message_text(header, reply_markup=InlineKeyboardMarkup(kb_rows))
    return MENU

# ==================== ACCOUNT INFO/ACTIONS ====================
async def noop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    _, cid_s, enc_back = q.data.split(":", 2)
    cid = int(cid_s)
    back_cb = dec_cb(enc_back)
    admin_key = get_admin_key(update.effective_user)
    
    msg = get_account_full_text(cid, admin_key)
    if not msg:
        await q.answer("یافت نشد", show_alert=True)
        return MENU
    
    await q.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=info_actions_kb(cid, back_cb))
    return MENU

async def renew_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    _, cid_s, enc_back = q.data.split(":", 2)
    cid = int(cid_s)
    back_cb = dec_cb(enc_back)
    admin_key = get_admin_key(update.effective_user)
    
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.account_type_id, c.duration_days, c.buyer_tg, c.login, c.password, c.description
        FROM accounts c WHERE c.id=? AND c.admin_key=?
    """, (cid, admin_key))
    row = cur.fetchone()
    
    if not row:
        conn.close()
        await q.answer("یافت نشد", show_alert=True)
        return MENU
    
    account_type_id, duration_days, buyer_tg, login, password, description = row
    type_title = type_title_by_id(int(account_type_id), data_owner_key(admin_key)) or "نامشخص"
    
    new_start = date.today().strftime("%Y-%m-%d")
    new_end = compute_end_date(new_start, int(duration_days))
    
    cur.execute(
        "UPDATE accounts SET start_date=?, end_date=? WHERE id=? AND admin_key=?",
        (new_start, new_end, cid, admin_key),
    )
    conn.commit()
    conn.close()
    
    end_j = to_jalali_str(new_end)
    msg = (
        "✅ تمدید شد\n\n"
        f"✨ نوع: `{safe_bt(type_title)}`\n"
        f"📅 شروع: `{safe_bt(new_start)}`\n"
        f"⏳ مدت: `{safe_bt(duration_days)}`\n"
        f"🧾 پایان میلادی: `{safe_bt(new_end)}`\n"
        f"🗓 پایان شمسی: `{safe_bt(end_j)}`\n"
        f"👤 تلگرام: {buyer_tg}\n"
        f"📧 یوزر: `{safe_bt(login)}`\n"
        f"🔑 پسورد: `{safe_bt(password)}`\n"
        f"📝 توضیحات: `{safe_bt(description)}`"
    )
    
    await q.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_list_kb(back_cb))
    return MENU

async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    _, cid_s, enc_back = q.data.split(":", 2)
    cid = int(cid_s)
    back_cb = dec_cb(enc_back)
    admin_key = get_admin_key(update.effective_user)
    
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM accounts WHERE id=? AND admin_key=?", (cid, admin_key))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
    except:
        await q.message.reply_text("❌ خطا در حذف")
        return MENU
    
    if deleted == 0:
        await q.message.reply_text("⚠️ اکانت پیدا نشد")
        return MENU
    
    await q.message.reply_text("🗑 حذف شد ✅", reply_markup=back_to_list_kb(back_cb))
    return MENU

async def texts_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    _, cid_s, enc_back = q.data.split(":", 2)
    cid = int(cid_s)
    
    await q.message.reply_text(
        "📨 متن‌های آماده\n\nیکی را انتخاب کن:",
        reply_markup=ready_texts_kb(cid, enc_back)
    )
    return MENU

async def send_ready_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    _, key, cid_s, enc_back = q.data.split(":", 3)
    cid = int(cid_s)
    admin_key = get_admin_key(update.effective_user)
    owner_key = data_owner_key(admin_key)
    
    text = render_template_for_account(key, cid, admin_key, owner_key)
    if not text:
        await q.answer("اکانت پیدا نشد", show_alert=True)
        return MENU
    
    await q.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_config_kb(cid, enc_back))
    return MENU

# ==================== EDIT ACCOUNT ====================
async def edit_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    _, cid_s, enc_back = q.data.split(":", 2)
    cid = int(cid_s)
    admin_key = get_admin_key(update.effective_user)
    
    msg = get_account_full_text(cid, admin_key)
    if not msg:
        await q.answer("یافت نشد", show_alert=True)
        return MENU
    
    await q.message.reply_text(
        msg + "\n\n✏️ یکی از گزینه‌ها را انتخاب کن:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=edit_menu_kb(cid, enc_back)
    )
    return MENU

async def edit_start_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    _, cid_s, enc_back = q.data.split(":", 2)
    context.user_data.clear()
    context.user_data["edit_mode"] = True
    context.user_data["edit_action"] = "start"
    context.user_data["edit_cid"] = int(cid_s)
    context.user_data["edit_enc_back"] = enc_back
    
    await q.message.reply_text("📅 تاریخ شروع جدید:", reply_markup=start_choice_kb())
    return START_CHOICE

async def edit_duration_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    _, cid_s, enc_back = q.data.split(":", 2)
    context.user_data.clear()
    context.user_data["edit_mode"] = True
    context.user_data["edit_action"] = "duration"
    context.user_data["edit_cid"] = int(cid_s)
    context.user_data["edit_enc_back"] = enc_back
    
    await q.message.reply_text("⏳ مدت زمان جدید (روز):", reply_markup=duration_kb())
    return DURATION_CHOICE

async def edit_field_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, field_key: str, title: str):
    q = update.callback_query
    await q.answer()
    
    _, cid_s, enc_back = q.data.split(":", 2)
    context.user_data.clear()
    context.user_data["edit_field"] = field_key
    context.user_data["edit_cid"] = int(cid_s)
    context.user_data["edit_enc_back"] = enc_back
    
    admin_key = get_admin_key(update.effective_user)
    msg = get_account_full_text(int(cid_s), admin_key)
    if msg:
        await q.message.reply_text(
            msg + f"\n\n━━━━━━━━\n{title}\n✍️ متن جدید:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_to_config_kb(int(cid_s), enc_back)
        )
    else:
        await q.message.reply_text(title)
    
    return WAIT_EDIT_FIELD

async def edit_tg_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await edit_field_prompt(update, context, "buyer_tg", "👤 ویرایش تلگرام")

async def edit_login_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await edit_field_prompt(update, context, "login", "📧 ویرایش یوزر/ایمیل")

async def edit_password_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await edit_field_prompt(update, context, "password", "🔑 ویرایش پسورد")

async def edit_description_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await edit_field_prompt(update, context, "description", "📝 ویرایش توضیحات")

async def edit_field_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    field = context.user_data.get("edit_field")
    cid = context.user_data.get("edit_cid")
    enc_back = context.user_data.get("edit_enc_back")
    admin_key = get_admin_key(update.effective_user)
    
    if not field or not cid or not enc_back:
        await update.message.reply_text(tr("unknown"))
        return MENU
    
    new_val = update.message.text.strip()
    
    if field not in ("buyer_tg", "login", "password", "description"):
        await update.message.reply_text("❌ فیلد نامعتبر")
        return MENU
    
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        f"UPDATE accounts SET {field}=? WHERE id=? AND admin_key=?",
        (new_val, int(cid), admin_key),
    )
    conn.commit()
    conn.close()
    
    titles = {
        "buyer_tg": "✅ تلگرام بروزرسانی شد",
        "login": "✅ یوزر/ایمیل بروزرسانی شد",
        "password": "✅ پسورد بروزرسانی شد",
        "description": "✅ توضیحات بروزرسانی شد",
    }
    msg = format_account_update_message(int(cid), titles.get(field, "✅ بروزرسانی شد"), admin_key)
    if not msg:
        await update.message.reply_text("❌ اکانت پیدا نشد")
        return MENU
    
    context.user_data.clear()
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=back_to_config_kb(int(cid), enc_back))
    return MENU

# ==================== REMINDERS ====================
async def check_daily_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = date.today()
    
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT c.id, c.end_date FROM accounts c WHERE c.admin_key=?", (MAIN_ADMIN_KEY,))
    rows = cur.fetchall()
    conn.close()
    
    for cid, end_date_s in rows:
        try:
            end_d = datetime.strptime(end_date_s, "%Y-%m-%d").date()
        except:
            continue
        
        diff = (end_d - today).days
        
        if diff == 2:
            text = render_template_for_account("reminder_2days", int(cid), MAIN_ADMIN_KEY, MAIN_ADMIN_KEY)
            if text:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN
                )
        
        if diff == 0:
            text = render_template_for_account("due_day", int(cid), MAIN_ADMIN_KEY, MAIN_ADMIN_KEY)
            if text:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN
                )

# ==================== MAIN ====================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.post_init = setup_bot_commands
    
    # Command handlers
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CommandHandler("help", cmd_help))
    
    # Conversation handler
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start_cmd)],
        states={
            MENU: [
                CallbackQueryHandler(menu_add, pattern="^menu_add$"),
                CallbackQueryHandler(menu_list, pattern="^menu_list$"),
                CallbackQueryHandler(menu_settings, pattern="^menu_settings$"),
                CallbackQueryHandler(go_home, pattern="^home$"),
                CallbackQueryHandler(user_inquiry_handler, pattern="^user_inquiry$"),
                CallbackQueryHandler(user_info_handler, pattern=r"^user_info:\d+$"),
                CallbackQueryHandler(admin_request_prompt, pattern="^admin_request$"),
                CallbackQueryHandler(admin_request_approve, pattern=r"^admin_req_approve:\d+$"),
                CallbackQueryHandler(admin_request_reject, pattern=r"^admin_req_reject:\d+$"),
                CallbackQueryHandler(admin_management_menu, pattern="^admin_management$"),
                CallbackQueryHandler(admin_toggle_requests, pattern="^admin_toggle_requests$"),
                CallbackQueryHandler(admin_toggle_share, pattern="^admin_toggle_share$"),
                CallbackQueryHandler(admin_add_prompt, pattern="^admin_add$"),
                CallbackQueryHandler(settings_types, pattern="^settings_types$"),
                CallbackQueryHandler(settings_db, pattern="^settings_db$"),
                CallbackQueryHandler(settings_texts, pattern="^settings_texts$"),
                CallbackQueryHandler(db_backup, pattern="^db_backup$"),
                CallbackQueryHandler(db_restore_prompt, pattern="^db_restore$"),
                CallbackQueryHandler(types_add_prompt, pattern="^types_add$"),
                CallbackQueryHandler(types_list, pattern=r"^types_list:\d+$"),
                CallbackQueryHandler(types_edit_prompt, pattern=r"^types_edit:\d+:\d+$"),
                CallbackQueryHandler(types_delete, pattern=r"^types_del:\d+:\d+$"),
                CallbackQueryHandler(noop_type, pattern=r"^noop_type:\d+$"),
                CallbackQueryHandler(list_all_cb, pattern=r"^list_all:\d+$"),
                CallbackQueryHandler(list_type_cb, pattern=r"^list_type:\d+:\d+$"),
                CallbackQueryHandler(info_handler, pattern=r"^info:\d+:.+"),
                CallbackQueryHandler(renew_handler, pattern=r"^renew:\d+:.+"),
                CallbackQueryHandler(delete_handler, pattern=r"^delete:\d+:.+"),
                CallbackQueryHandler(edit_menu_handler, pattern=r"^edit_menu:\d+:.+"),
                CallbackQueryHandler(edit_start_prompt, pattern=r"^edit_start:\d+:.+"),
                CallbackQueryHandler(edit_duration_prompt, pattern=r"^edit_duration:\d+:.+"),
                CallbackQueryHandler(edit_tg_prompt, pattern=r"^edit_tg:\d+:.+"),
                CallbackQueryHandler(edit_login_prompt, pattern=r"^edit_login:\d+:.+"),
                CallbackQueryHandler(edit_password_prompt, pattern=r"^edit_password:\d+:.+"),
                CallbackQueryHandler(edit_description_prompt, pattern=r"^edit_description:\d+:.+"),
                CallbackQueryHandler(texts_ready, pattern=r"^texts_ready:\d+:.+"),
                CallbackQueryHandler(send_ready_text, pattern=r"^send_txt:.+"),
                CallbackQueryHandler(text_edit_prompt, pattern=r"^txt_edit:.+"),
                CallbackQueryHandler(cmd_search_callback, pattern="^cmd_search$"),
                CallbackQueryHandler(cmd_help_inline, pattern="^cmd_help$"),
                CallbackQueryHandler(noop_handler, pattern=r"^noop:\d+$"),
            ],
            CHOOSING_TYPE: [
                CallbackQueryHandler(type_pick, pattern=r"^type_pick:\d+$"),
                CallbackQueryHandler(go_home, pattern="^home$"),
            ],
            START_CHOICE: [
                CallbackQueryHandler(start_choice_cb, pattern=r"^start_"),
            ],
            START_GREGORIAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, start_gregorian_msg),
            ],
            START_JALALI: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, start_jalali_msg),
            ],
            DURATION_CHOICE: [
                CallbackQueryHandler(duration_choice_cb, pattern=r"^dur_"),
            ],
            DURATION_MANUAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, duration_manual_msg),
            ],
            BUYER_TG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, buyer_tg_msg),
            ],
            LOGIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, login_msg),
            ],
            PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, password_msg),
            ],
            DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, description_msg),
            ],
            TYPES_ADD_WAIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, types_add_receive),
            ],
            TYPES_EDIT_WAIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, types_edit_receive),
            ],
            WAIT_RESTORE_FILE: [
                MessageHandler(filters.Document.ALL, db_restore_receive),
            ],
            WAIT_TEXT_EDIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_edit_save),
            ],
            WAIT_EDIT_FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field_save),
            ],
            WAIT_SEARCH_QUERY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_search_query),
            ],
            ADMIN_REQUEST_ORG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_request_org_msg),
            ],
            ADMIN_REQUEST_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_request_text_msg),
            ],
            ADMIN_REJECT_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reject_reason_msg),
            ],
            ADMIN_ADD_WAIT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_receive),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_cmd),
        ],
        allow_reentry=True,
        per_message=False,
    )
    
    app.add_handler(conv)
    
    # Setup reminders
    if app.job_queue:
        app.job_queue.run_daily(
            check_daily_reminders,
            time=dtime(hour=10, minute=0),
            name="daily_reminders"
        )
    
    # Python 3.14 fix
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    
    print("🚀 ExpiryHub Bot Started!")
    app.run_polling()


if __name__ == "__main__":
    main()
