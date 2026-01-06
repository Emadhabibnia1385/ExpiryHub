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
import re
import io
import shutil
import logging
from datetime import datetime, date, timedelta, time as dtime

import jdatetime
import pytz
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
    Document,
)
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
import sys
import subprocess

def ensure_jobqueue_installed() -> bool:
    """
    Ensure python-telegram-bot JobQueue extra deps are installed.
    Returns True if job queue deps are available after this.
    """
    try:
        import apscheduler  # noqa: F401
        return True
    except Exception:
        pass

    try:
        print("⚙️ Installing JobQueue deps (python-telegram-bot[job-queue]) ...")
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-U",
            "python-telegram-bot[job-queue]"
        ])
    except Exception as e:
        print("❌ Auto-install failed:", e)
        return False


    try:
        import apscheduler  # noqa: F401
        return True
    except Exception:
        return False

logger = logging.getLogger(__name__)

# ==================== CONFIG ====================
TOKEN = os.getenv("TOKEN", "YOUR_BOT_TOKEN").strip()
ADMIN_CHAT_ID_RAW = os.getenv("ADMIN_CHAT_ID", "YOUR_ID").strip()

if not TOKEN or TOKEN == "YOUR_BOT_TOKEN":
    raise RuntimeError("TOKEN is not set. Set it in env or code")

try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_RAW)
except Exception:
    raise RuntimeError("ADMIN_CHAT_ID must be a valid integer")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ExpiryHub.db")
PAGE_SIZE = 10

# ==================== DB BACKUP MODULE CONFIG ====================
TZ = pytz.timezone("Asia/Tehran")
CB_DB = "db"
JOB_BACKUP = "expiryhub_auto_backup"

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
    WAIT_TEXT_EDIT,
    WAIT_EDIT_FIELD,
    WAIT_SEARCH_QUERY,
    WAIT_RENEW_DURATION,
    WAIT_USER_INQUIRY_QUERY,  # (unused)
    DB_SET_TARGET_ID,
    DB_SET_INTERVAL,
    DB_RESTORE_WAIT_DOC,
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
    "ask_tg": "👤 آیدی تلگرام را وارد کن (آیدی عددی یا @username):",
    "ask_login": "📧 یوزر/ایمیل را وارد کن:",
    "ask_password": "🔑 پسورد را وارد کن:",
    "ask_description": "📝 توضیحات اکانت را وارد کن (یا بنویس -):",
    "list_empty": "❌ هیچ اکانتی ثبت نشده.",
    "expired_label": "منقضی",
    "today_label": "امروز",
    "more_info": "ℹ️ اطلاعات بیشتر",
    "settings_title": "⚙️ تنظیمات ربات\nیکی از گزینه‌ها را انتخاب کن:",
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
    "home": "🏠 منو",
    "back_filters": "⬅️ تغییر فیلتر",
    "unknown": "⚠️ ورودی نامعتبر است.",
}

def tr(key: str) -> str:
    return STRINGS.get(key, key)

# ==================== HELPERS ====================
def h(x) -> str:
    return html.escape("" if x is None else str(x))

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
    except Exception:
        return -999

def to_jalali_str(gregorian_yyyy_mm_dd: str) -> str:
    g = datetime.strptime(gregorian_yyyy_mm_dd, "%Y-%m-%d").date()
    j = jdatetime.date.fromgregorian(date=g)
    return f"{j.year:04d}-{j.month:02d}-{j.day:02d}"

def is_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid == ADMIN_CHAT_ID

def user_identifier(update: Update) -> str:
    """User can match by numeric id or @username"""
    uid = update.effective_user.id if update.effective_user else None
    uname = update.effective_user.username if update.effective_user else None
    if uname:
        return f"@{uname}"
    return str(uid) if uid is not None else ""

def normalize_buyer_tg(raw: str) -> str:
    """
    Normalize buyer_tg:
      - numeric id stays as-is
      - username -> always '@' + lowercase
    """
    s = (raw or "").strip()
    if not s:
        return ""
    if s.isdigit():
        return s
    s = s.lstrip("@").strip().lower()
    return f"@{s}" if s else ""

def md_backticks_to_html_code(text: str) -> str:
    """
    Convert markdown-style code markers to HTML code blocks so Telegram HTML ParseMode
    shows copyable <code>/<pre>.
      - ```...``` -> <pre>...</pre>
      - `...`     -> <code>...</code>
    """
    if not text:
        return text

    text = re.sub(
        r"```([\s\S]*?)```",
        lambda m: f"<pre>{html.escape(m.group(1))}</pre>",
        text
    )
    text = re.sub(
        r"`([^`\n]+)`",
        lambda m: f"<code>{html.escape(m.group(1))}</code>",
        text
    )
    return text

def start_text_admin() -> str:
    return (
        "سلام 👋\n"
        "به پنل مدیریت ExpiryHub خوش آمدید.\n\n"
        "🛠 این پنل برای مدیریت کامل اکانت‌ها طراحی شده و از طریق آن می‌توانید:\n"
        "• اکانت جدید اضافه کنید\n"
        "• لیست و وضعیت اکانت‌ها را بررسی کنید\n"
        "• اکانت‌ها را ویرایش، تمدید یا حذف نمایید\n"
        "• متن‌های آماده، نوع اکانت و دیتابیس را مدیریت کنید\n\n"
        "از منوی زیر گزینه مورد نظر را انتخاب کنید 👇\n\n"
        "━━━━━━━━━━━━━━\n"
        "🔄 شروع مجدد ربات: /start\n"
        "❓ راهنمای پنل مدیریت: /help\n"
        "━━━━━━━━━━━━━━\n"
        "🛠 توسعه‌دهنده: @emadhabibnia"
    )


def start_text_user() -> str:
    return (
        "سلام 👋\n"
        "به ربات ExpiryHub خوش آمدید.\n\n"
        "📌 ExpiryHub به شما کمک می‌کنه وضعیت اکانت‌هاتون رو به‌سادگی مدیریت کنید "
        "و از زمان باقی‌مونده تا پایان هر اکانت مطلع بشید.\n\n"
        "از طریق دکمه‌های زیر می‌تونید اکانت‌های خودتون رو مشاهده و استعلام کنید.\n"
        "برای دریافت راهنمای کامل‌تر، دستور /help رو بزنید 👇\n\n"
        "━━━━━━━━━━━━━━\n"
        "👨‍💻 Developer: @emadhabibnia"
    )


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
        title TEXT NOT NULL UNIQUE
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS bot_texts (
        key TEXT PRIMARY KEY,
        body TEXT NOT NULL
    )
    """)

    # ✅ settings table for auto-backup module
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings(
        k TEXT PRIMARY KEY,
        v TEXT NOT NULL
    )
    """)

    conn.commit()
    conn.close()

    ensure_accounts_description_column()
    init_default_texts()
    ensure_default_settings()

def ensure_accounts_description_column():
    conn = connect()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(accounts)")
    columns = {row[1] for row in cur.fetchall()}
    if "description" not in columns:
        try:
            cur.execute("ALTER TABLE accounts ADD COLUMN description TEXT NOT NULL DEFAULT ''")
            conn.commit()
        except Exception:
            pass
    conn.close()

def init_default_texts():
    # ✅ HTML templates (copyable fields in <code>)
    defaults = {
        "reminder_2days": (
            "سلام وقت بخیر 👋\n"
            "کاربر عزیز <code>{buyer_tg}</code>\n\n"
            "اکانت <code>{account_type}</code> شما با یوزر/ایمیل <code>{login}</code>\n"
            "تا <code>{days_left}</code> روز دیگر به پایان می‌رسد.\n\n"
            "📝 توضیحات: <code>{description}</code>\n\n"
            "در صورت تمایل به تمدید، لطفاً اقدام کنید ✅"
        ),
        "due_day": (
            "سلام وقت بخیر 👋\n"
            "کاربر عزیز <code>{buyer_tg}</code>\n\n"
            "اکانت <code>{account_type}</code> شما با یوزر/ایمیل <code>{login}</code>\n"
            "امروز به پایان رسیده است.\n\n"
            "📝 توضیحات: <code>{description}</code>\n\n"
            "🏦 نام بانک: <code>{bank_name}</code>\n"
            "💳 شماره کارت: <code>{card_number}</code>\n"
            "👤 به نام: <code>{card_owner}</code>"
        ),
        "inquiry": (
            "سلام 👋\n"
            "اکانت <code>{account_type}</code> شما\n\n"
            "📅 شروع: <code>{start_date}</code>\n"
            "⏳ مدت: <code>{duration_days}</code>\n"
            "🧾 پایان میلادی: <code>{end_date}</code>\n"
            "🗓 پایان شمسی: <code>{end_date_jalali}</code>\n"
            "⌛️ مانده: <code>{days_left}</code> روز\n\n"
            "📝 توضیحات: <code>{description}</code>"
        ),
        "bank_name": "نام بانک",
        "card_number": "0000-0000-0000-0000",
        "card_owner": "نام صاحب کارت",
    }

    conn = connect()
    cur = conn.cursor()
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO bot_texts(key, body) VALUES (?,?)", (k, v))
    conn.commit()
    conn.close()

def ensure_default_settings():
    conn = connect()
    cur = conn.cursor()

    def _ensure_setting(key: str, default: str):
        cur.execute("SELECT 1 FROM settings WHERE k=?", (key,))
        if cur.fetchone() is None:
            cur.execute("INSERT INTO settings(k,v) VALUES(?,?)", (key, default))

    _ensure_setting("backup_enabled", "0")                    # 0/1
    _ensure_setting("backup_target_type", "chat")             # chat/channel (UI)
    _ensure_setting("backup_target_id", str(ADMIN_CHAT_ID))   # default: admin
    _ensure_setting("backup_interval_hours", "24")            # default: 24 hours

    conn.commit()
    conn.close()

def reset_default_texts(force: bool = True):
    defaults = {
        "reminder_2days": (
            "سلام وقت بخیر 👋\n"
            "کاربر عزیز <code>{buyer_tg}</code>\n\n"
            "اکانت <code>{account_type}</code> شما با یوزر/ایمیل <code>{login}</code>\n"
            "تا <code>{days_left}</code> روز دیگر به پایان می‌رسد.\n\n"
            "📝 توضیحات: <code>{description}</code>\n\n"
            "در صورت تمایل به تمدید، لطفاً اقدام کنید ✅"
        ),
        "due_day": (
            "سلام وقت بخیر 👋\n"
            "کاربر عزیز <code>{buyer_tg}</code>\n\n"
            "اکانت <code>{account_type}</code> شما با یوزر/ایمیل <code>{login}</code>\n"
            "امروز به پایان رسیده است.\n\n"
            "📝 توضیحات: <code>{description}</code>\n\n"
            "🏦 نام بانک: <code>{bank_name}</code>\n"
            "💳 شماره کارت: <code>{card_number}</code>\n"
            "👤 به نام: <code>{card_owner}</code>"
        ),
        "inquiry": (
            "سلام 👋\n"
            "اکانت <code>{account_type}</code> شما\n\n"
            "📅 شروع: <code>{start_date}</code>\n"
            "⏳ مدت: <code>{duration_days}</code>\n"
            "🧾 پایان میلادی: <code>{end_date}</code>\n"
            "🗓 پایان شمسی: <code>{end_date_jalali}</code>\n"
            "⌛️ مانده: <code>{days_left}</code> روز\n\n"
            "📝 توضیحات: <code>{description}</code>"
        ),
        "bank_name": "نام بانک",
        "card_number": "0000-0000-0000-0000",
        "card_owner": "نام صاحب کارت",
    }

    conn = connect()
    cur = conn.cursor()
    for k, v in defaults.items():
        if force:
            cur.execute(
                "INSERT INTO bot_texts(key, body) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET body=excluded.body",
                (k, v),
            )
        else:
            cur.execute("INSERT OR IGNORE INTO bot_texts(key, body) VALUES (?, ?)", (k, v))
    conn.commit()
    conn.close()

def get_bot_text(key: str) -> str:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT body FROM bot_texts WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else ""

def set_bot_text(key: str, body: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO bot_texts(key, body) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET body=excluded.body",
        (key, body),
    )
    conn.commit()
    conn.close()

def get_types():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT id, title FROM account_types ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows

def add_type(title: str):
    title = title.strip()
    if not title:
        return False, "empty"
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO account_types(title) VALUES(?)", (title,))
        conn.commit()
        return True, "ok"
    except sqlite3.IntegrityError:
        return False, "exists"
    finally:
        conn.close()

def edit_type(type_id: int, new_title: str):
    new_title = new_title.strip()
    if not new_title:
        return False
    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE account_types SET title=? WHERE id=?", (new_title, type_id))
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_type(type_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM accounts WHERE account_type_id=?", (type_id,))
    used = cur.fetchone()[0]
    if used and used > 0:
        conn.close()
        return False, "blocked"
    cur.execute("DELETE FROM account_types WHERE id=?", (type_id,))
    conn.commit()
    ok = cur.rowcount > 0
    conn.close()
    return ok, "ok"

def type_title_by_id(type_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT title FROM account_types WHERE id=?", (type_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def search_accounts(query: str):
    query_like = f"%{query}%"
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.login, t.title, c.buyer_tg, c.end_date
        FROM accounts c
        JOIN account_types t ON t.id = c.account_type_id
        WHERE c.login LIKE ? OR c.buyer_tg LIKE ? OR t.title LIKE ? OR c.description LIKE ?
        ORDER BY c.end_date DESC
        LIMIT 50
    """, (query_like, query_like, query_like, query_like))
    results = cur.fetchall()
    conn.close()
    return results

def get_account_row(cid: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.title, c.start_date, c.end_date, c.duration_days,
               c.buyer_tg, c.login, c.password, c.description
        FROM accounts c
        JOIN account_types t ON t.id=c.account_type_id
        WHERE c.id=?
    """, (cid,))
    row = cur.fetchone()
    conn.close()
    return row

def get_account_full_html(cid: int):
    row = get_account_row(cid)
    if not row:
        return None

    type_title, start_date_s, end_date_s, duration_days, buyer_tg, login, password, description = row
    end_j = to_jalali_str(end_date_s)
    rem = remaining_days(end_date_s)
    rem_label = tr("expired_label") if rem < 0 else str(rem)

    return (
        f"✨ نوع اکانت: <code>{h(type_title)}</code>\n"
        f"📅 شروع: <code>{h(start_date_s)}</code>\n"
        f"⏳ مدت: <code>{h(duration_days)}</code>\n"
        f"⌛️ مانده: <code>{h(rem_label)}</code>\n"
        f"🧾 پایان میلادی: <code>{h(end_date_s)}</code>\n"
        f"🗓 پایان شمسی: <code>{h(end_j)}</code>\n"
        f"👤 تلگرام: {h(buyer_tg)}\n"
        f"📧 یوزر/ایمیل: <code>{h(login)}</code>\n"
        f"🔑 پسورد: <code>{h(password)}</code>\n"
        f"📝 توضیحات: <code>{h(description)}</code>"
    )

def render_template_for_account(key: str, cid: int):
    row = get_account_row(cid)
    if not row:
        return None

    account_type, start_date_s, end_date_s, duration_days, buyer_tg, login, _password, description = row
    days_left = remaining_days(end_date_s)

    tpl = get_bot_text(key)

    data = dict(
        buyer_tg=h(buyer_tg),
        account_type=h(account_type),
        login=h(login),
        start_date=h(start_date_s),
        end_date=h(end_date_s),
        end_date_jalali=h(to_jalali_str(end_date_s)),
        duration_days=h(duration_days),
        days_left=h(days_left),
        description=h(description),
        bank_name=h(get_bot_text("bank_name")),
        card_number=h(get_bot_text("card_number")),
        card_owner=h(get_bot_text("card_owner")),
    )

    try:
        return tpl.format(**data)
    except Exception:
        return "❌ خطا در قالب متن. لطفاً متن را در تنظیمات اصلاح کنید."

# ==================== KEYBOARDS ====================
def chunk2(items):
    for i in range(0, len(items), 2):
        yield items[i:i + 2]

def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن اکانت جدید", callback_data="menu_add")],
        [
            InlineKeyboardButton("🔍 جستجو", callback_data="cmd_search"),
            InlineKeyboardButton("📋 لیست اکانت‌ها", callback_data="menu_list"),
        ],
        [
            InlineKeyboardButton("⚙️ تنظیمات", callback_data="menu_settings"),
            InlineKeyboardButton("❓ راهنما", callback_data="cmd_help_admin"),
        ],
    ])

def user_menu_kb(is_admin_user: bool = False):
    rows = [
        [InlineKeyboardButton("📌 استعلام اکانت‌های من", callback_data="user_inquiry")],
        [InlineKeyboardButton("❓ راهنما", callback_data="user_help")],
    ]
    if is_admin_user:
        rows.append([InlineKeyboardButton("🔐 ورود به پنل مدیریت", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def settings_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr("settings_types"), callback_data="settings_types")],
        [InlineKeyboardButton("🗄 دیتابیس", callback_data="db:open")],  # ✅ new db module
        [InlineKeyboardButton(tr("settings_texts"), callback_data="settings_texts")],
        [InlineKeyboardButton(tr("home"), callback_data="home")],
    ])

def types_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(tr("types_add"), callback_data="types_add")],
        [InlineKeyboardButton(tr("types_list"), callback_data="types_list:0")],
        [InlineKeyboardButton(tr("home"), callback_data="home")],
    ])

def type_pick_kb():
    types = get_types()
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
        [InlineKeyboardButton("🏠 منو", callback_data="home")],
    ])

def duration_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("30", callback_data="dur_30"),
         InlineKeyboardButton("90", callback_data="dur_90")],
        [InlineKeyboardButton("180", callback_data="dur_180"),
         InlineKeyboardButton("365", callback_data="dur_365")],
        [InlineKeyboardButton(tr("dur_manual_btn"), callback_data="dur_manual")],
        [InlineKeyboardButton("🏠 منو", callback_data="home")],
    ])

def list_filter_kb():
    types = get_types()
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
            InlineKeyboardButton("✅ تمدید", callback_data=f"renew_prompt:{cid}:{b}"),
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
        [InlineKeyboardButton("🏠 منو", callback_data="home")],
    ])

def ready_texts_kb(cid: int, enc_back: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 یادآوری (۲ روز)", callback_data=f"send_txt:reminder_2days:{cid}:{enc_back}")],
        [InlineKeyboardButton("📨 روز سررسید", callback_data=f"send_txt:due_day:{cid}:{enc_back}")],
        [InlineKeyboardButton("📨 استعلام", callback_data=f"send_txt:inquiry:{cid}:{enc_back}")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"info:{cid}:{enc_back}")],
        [InlineKeyboardButton("🏠 منو", callback_data="home")],
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
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"info:{cid}:{enc_back}")],
        [InlineKeyboardButton("🏠 منو", callback_data="home")],
    ])

def back_to_list_kb(back_cb: str):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=back_cb)],
        [InlineKeyboardButton("🏠 منو", callback_data="home")],
    ])

# ==================== COMMANDS & MENUS ====================
async def setup_bot_commands(app):
    public_cmds = [
        BotCommand("start", "شروع ربات"),
        BotCommand("help", "راهنما"),
    ]
    admin_cmds = [
        BotCommand("start", "شروع ربات"),
        BotCommand("add", "افزودن اکانت"),
        BotCommand("list", "لیست اکانت‌ها"),
        BotCommand("search", "جستجوی اکانت"),
        BotCommand("settings", "تنظیمات"),
        BotCommand("help", "راهنما"),
        BotCommand("cancel", "لغو"),
    ]
    await app.bot.set_my_commands(public_cmds, scope=BotCommandScopeDefault())
    await app.bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=ADMIN_CHAT_ID))

def schedule_backup_job(app) -> None:
    """
    Schedule (or re-schedule) auto-backup job using PTB JobQueue.
    If JobQueue is missing, tries to install it automatically.
    """

    # اگر JobQueue وجود ندارد، تلاش برای نصب خودکار
    if not getattr(app, "job_queue", None):
        ok = ensure_jobqueue_installed()
        if not ok:
            print("⚠️ JobQueue is not available; auto-backup disabled.")
            return

    # بعد از نصب ممکن است هنوز job_queue در همین اجرا ساخته نشده باشد
    if not getattr(app, "job_queue", None):
        print("⚠️ JobQueue installed but not initialized in this run. Restart bot once.")
        return

    # حذف jobهای قبلی با همین نام
    try:
        for j in app.job_queue.get_jobs_by_name(JOB_BACKUP):
            j.schedule_removal()
    except Exception:
        pass

    # اگر بکاپ خودکار خاموش است، چیزی زمان‌بندی نکن
    if get_setting("backup_enabled") != "1":
        return

    # خواندن فاصله بکاپ به ساعت (پیش‌فرض 24)
    try:
        hours = int(get_setting("backup_interval_hours") or "24")
        if hours <= 0:
            hours = 1
    except Exception:
        hours = 24

    seconds = hours * 3600

    # زمان‌بندی job تکرارشونده
    app.job_queue.run_repeating(
        callback=send_backup_file,
        interval=seconds,
        first=seconds,
        name=JOB_BACKUP,
    )

    print(f"✅ Auto-backup job scheduled every {hours} hour(s).")


async def post_init(app):
    await setup_bot_commands(app)
    schedule_backup_job(app)
    try:
        schedule_backup_job(app)
    except Exception as e:
        print("⚠️ schedule_backup_job failed:", e)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if is_admin(update):
        await update.message.reply_text(start_text_user(), reply_markup=user_menu_kb(is_admin_user=True))
    else:
        await update.message.reply_text(start_text_user(), reply_markup=user_menu_kb(is_admin_user=False))
    return MENU

async def go_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data.clear()

    if q.from_user.id == ADMIN_CHAT_ID:
        await q.edit_message_text(start_text_user(), reply_markup=user_menu_kb(is_admin_user=True))
    else:
        await q.edit_message_text(start_text_user(), reply_markup=user_menu_kb(is_admin_user=False))
    return MENU

async def admin_panel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await q.answer("⛔️ دسترسی ندارید", show_alert=True)
        return MENU
    context.user_data.clear()
    await q.edit_message_text(start_text_admin(), reply_markup=main_menu_kb())
    return MENU

async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if is_admin(update):
        await update.message.reply_text(start_text_admin(), reply_markup=main_menu_kb())
    else:
        await update.message.reply_text(start_text_user(), reply_markup=user_menu_kb(False))
    return MENU

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if is_admin(update):
        text = (
            "📖 راهنمای کامل پنل مدیریت ExpiryHub\n\n"
            "پنل مدیریت ExpiryHub برای کنترل و مدیریت کامل اکانت‌ها طراحی شده است.\n\n"

            "━━━━━━━━━━━━━━\n"
            "🧩 مدیریت اکانت‌ها\n"
            "• ➕ افزودن اکانت جدید از طریق دکمه «افزودن اکانت جدید» یا دستور /add\n"
            "• 📋 مشاهده لیست اکانت‌ها با /list و امکان فیلتر بر اساس نوع اکانت\n"
            "• 🔍 جستجوی پیشرفته با /search بر اساس:\n"
            "  - یوزر یا ایمیل\n"
            "  - آیدی یا یوزرنیم تلگرام\n"
            "  - نوع اکانت\n"
            "  - توضیحات\n\n"

            "━━━━━━━━━━━━━━\n"
            "📝 مدیریت هر اکانت\n"
            "داخل بخش «اطلاعات بیشتر» هر اکانت می‌توانید:\n"
            "• ✏️ ویرایش تاریخ شروع\n"
            "• ⏳ ویرایش مدت زمان\n"
            "• 👤 ویرایش تلگرام خریدار\n"
            "• 📧 ویرایش یوزر/ایمیل\n"
            "• 🔑 ویرایش پسورد\n"
            "• 📝 ویرایش توضیحات\n"
            "• ✅ تمدید سریع اکانت\n"
            "• 🗑 حذف اکانت\n\n"

            "━━━━━━━━━━━━━━\n"
            "📨 متن‌های آماده\n"
            "برای هر اکانت امکان ارسال پیام‌های آماده وجود دارد:\n"
            "• 📌 استعلام وضعیت اکانت\n"
            "• ⏰ یادآوری ۲ روز مانده به پایان\n"
            "• 📅 پیام روز سررسید\n\n"
            "✍️ متن‌ها کاملاً قابل ویرایش هستند و از متغیرهای پویا پشتیبانی می‌کنند.\n\n"

            "━━━━━━━━━━━━━━\n"
            "🗂 مدیریت نوع اکانت\n"
            "از بخش تنظیمات می‌توانید:\n"
            "• ➕ نوع اکانت جدید اضافه کنید\n"
            "• ✏️ نام نوع اکانت را ویرایش کنید\n"
            "• 🗑 نوع‌های بدون استفاده را حذف نمایید\n\n"

            "━━━━━━━━━━━━━━\n"
            "⚙️ تنظیمات ربات\n"
            "از بخش تنظیمات امکان مدیریت موارد زیر وجود دارد:\n"
            "• ✍️ ویرایش متن‌های سیستمی و پیام‌ها\n"
            "• 🗂 مدیریت نوع اکانت‌ها\n"
            "• 🗄 مدیریت دیتابیس ربات شامل:\n"
            "  - گرفتن بکاپ دستی از دیتابیس\n"
            "  - وارد کردن (ریستور) بکاپ\n"
            "  - فعال یا غیرفعال‌سازی بکاپ خودکار\n\n"

            "━━━━━━━━━━━━━━\n"
            "🔔 سیستم یادآوری خودکار\n"
            "• ارسال پیام یادآوری به ادمین و کاربر:\n"
            "  - ۲ روز قبل از پایان اکانت\n"
            "  - روز سررسید\n\n"

            "━━━━━━━━━━━━━━\n"
            "📌 دستورات مهم\n"
            "• /start شروع یا بازگشت به منو\n"
            "• /help نمایش راهنمای پنل مدیریت\n"
            "• /add افزودن اکانت\n"
            "• /list لیست اکانت‌ها\n"
            "• /search جستجو\n"
            "• /settings تنظیمات\n"
            "• /cancel لغو عملیات جاری\n\n"

            "━━━━━━━━━━━━━━\n"

            "🔒 دسترسی به پنل مدیریت فقط برای ادمین امکان‌پذیر است.\n\n"

            "━━━━━━━━━━━━━━\n"
            "🛠 توسعه‌دهنده: @emadhabibnia"
    )

        await update.message.reply_text(text, reply_markup=main_menu_kb())
    else:
        text = (
            "📖 راهنمای کاربران ExpiryHub\n\n"
            "• برای دیدن اکانت‌های خود: روی «استعلام اکانت‌های من» بزنید.\n"
            "• اگر یوزرنیم دارید، اکانت‌ها می‌توانند با @username هم ثبت شوند.\n"
            "• پیام‌های ۲ روز مانده و روز سررسید (در صورت امکان) برای شما هم ارسال می‌شود.\n"
        )
        await update.message.reply_text(text, reply_markup=user_menu_kb(False))
    return MENU

async def cmd_help_admin_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await q.answer("⛔️ دسترسی ندارید", show_alert=True)
        return MENU
    text = (
            "📖 راهنمای کامل پنل مدیریت ExpiryHub\n\n"
            "پنل مدیریت ExpiryHub برای کنترل و مدیریت کامل اکانت‌ها طراحی شده است.\n\n"

            "━━━━━━━━━━━━━━\n"
            "🧩 مدیریت اکانت‌ها\n"
            "• ➕ افزودن اکانت جدید از طریق دکمه «افزودن اکانت جدید» یا دستور /add\n"
            "• 📋 مشاهده لیست اکانت‌ها با /list و امکان فیلتر بر اساس نوع اکانت\n"
            "• 🔍 جستجوی پیشرفته با /search بر اساس:\n"
            "  - یوزر یا ایمیل\n"
            "  - آیدی یا یوزرنیم تلگرام\n"
            "  - نوع اکانت\n"
            "  - توضیحات\n\n"

            "━━━━━━━━━━━━━━\n"
            "📝 مدیریت هر اکانت\n"
            "داخل بخش «اطلاعات بیشتر» هر اکانت می‌توانید:\n"
            "• ✏️ ویرایش تاریخ شروع\n"
            "• ⏳ ویرایش مدت زمان\n"
            "• 👤 ویرایش تلگرام خریدار\n"
            "• 📧 ویرایش یوزر/ایمیل\n"
            "• 🔑 ویرایش پسورد\n"
            "• 📝 ویرایش توضیحات\n"
            "• ✅ تمدید سریع اکانت\n"
            "• 🗑 حذف اکانت\n\n"

            "━━━━━━━━━━━━━━\n"
            "📨 متن‌های آماده\n"
            "برای هر اکانت امکان ارسال پیام‌های آماده وجود دارد:\n"
            "• 📌 استعلام وضعیت اکانت\n"
            "• ⏰ یادآوری ۲ روز مانده به پایان\n"
            "• 📅 پیام روز سررسید\n\n"
            "✍️ متن‌ها کاملاً قابل ویرایش هستند و از متغیرهای پویا پشتیبانی می‌کنند.\n\n"

            "━━━━━━━━━━━━━━\n"
            "🗂 مدیریت نوع اکانت\n"
            "از بخش تنظیمات می‌توانید:\n"
            "• ➕ نوع اکانت جدید اضافه کنید\n"
            "• ✏️ نام نوع اکانت را ویرایش کنید\n"
            "• 🗑 نوع‌های بدون استفاده را حذف نمایید\n\n"

            "━━━━━━━━━━━━━━\n"
            "⚙️ تنظیمات ربات\n"
            "از بخش تنظیمات امکان مدیریت موارد زیر وجود دارد:\n"
            "• ✍️ ویرایش متن‌های سیستمی و پیام‌ها\n"
            "• 🗂 مدیریت نوع اکانت‌ها\n"
            "• 🗄 مدیریت دیتابیس ربات شامل:\n"
            "  - گرفتن بکاپ دستی از دیتابیس\n"
            "  - وارد کردن (ریستور) بکاپ\n"
            "  - فعال یا غیرفعال‌سازی بکاپ خودکار\n\n"

            "━━━━━━━━━━━━━━\n"
            "🔔 سیستم یادآوری خودکار\n"
            "• ارسال پیام یادآوری به ادمین و کاربر:\n"
            "  - ۲ روز قبل از پایان اکانت\n"
            "  - روز سررسید\n\n"

            "━━━━━━━━━━━━━━\n"
            "📌 دستورات مهم\n"
            "• /start شروع یا بازگشت به منو\n"
            "• /help نمایش راهنمای پنل مدیریت\n"
            "• /add افزودن اکانت\n"
            "• /list لیست اکانت‌ها\n"
            "• /search جستجو\n"
            "• /settings تنظیمات\n"
            "• /cancel لغو عملیات جاری\n\n"

            "━━━━━━━━━━━━━━\n"

            "🔒 دسترسی به پنل مدیریت فقط برای ادمین امکان‌پذیر است.\n\n"

            "━━━━━━━━━━━━━━\n"
            "🛠 توسعه‌دهنده: @emadhabibnia"
    )
    await q.edit_message_text(text, reply_markup=main_menu_kb(), parse_mode=ParseMode.HTML)
    return MENU

async def user_help_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    text = (
        "📖 راهنمای کاربران\n\n"
        "• «استعلام اکانت‌های من» را بزنید تا لیست اکانت‌های ثبت شده به نام شما نمایش داده شود.\n"
        "• اگر اکانت با آیدی عددی یا @username شما ثبت شده باشد، نمایش داده می‌شود.\n"
        "• برای پشتیبانی با ادمین در تماس باشید."
    )
    await q.edit_message_text(text, reply_markup=user_menu_kb(is_admin_user=(q.from_user.id == ADMIN_CHAT_ID)))
    return MENU

# ==================== ADMIN GUARD ====================
async def deny_admin_cb(update: Update, text="⛔️ فقط ادمین دسترسی دارد"):
    q = update.callback_query
    if q:
        await q.answer(text, show_alert=True)

async def deny_admin_msg(update: Update, text="⛔️ فقط ادمین دسترسی دارد"):
    if update.message:
        await update.message.reply_text(text)

# ==================== ADMIN: MENU CALLBACKS ====================
async def menu_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    context.user_data.clear()
    kb = type_pick_kb()
    if kb is None:
        await q.edit_message_text(
            tr("no_types"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗂 مدیریت نوع", callback_data="settings_types")],
                [InlineKeyboardButton(tr("home"), callback_data="home")]
            ])
        )
        return MENU
    await q.edit_message_text(tr("choose_type"), reply_markup=kb)
    return CHOOSING_TYPE

async def menu_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    context.user_data.clear()
    await q.edit_message_text("📋 انتخاب فیلتر:", reply_markup=list_filter_kb())
    return MENU

async def menu_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    context.user_data.clear()
    await q.edit_message_text(tr("settings_title"), reply_markup=settings_kb())
    return MENU

# ==================== ADMIN: COMMANDS ====================
async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    context.user_data.clear()
    kb = type_pick_kb()
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
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    context.user_data.clear()
    await update.message.reply_text("📋 انتخاب فیلتر:", reply_markup=list_filter_kb())
    return MENU

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    context.user_data.clear()
    await update.message.reply_text(tr("settings_title"), reply_markup=settings_kb())
    return MENU

# ==================== SEARCH ====================
async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    context.user_data.clear()
    await update.message.reply_text(
        "🔍 جستجوی اکانت\n\n"
        "جستجو روی:\n"
        "• آیدی عددی یا @username تلگرام\n"
        "• یوزر/ایمیل اکانت\n"
        "• نوع اکانت\n"
        "• توضیحات\n\n"
        "✍️ متن جستجو را وارد کنید:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منو", callback_data="home")]])
    )
    return WAIT_SEARCH_QUERY

async def cmd_search_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    context.user_data.clear()
    await q.edit_message_text(
    "🔍 جستجوی اکانت\n\n"
    "در این بخش می‌توانید اکانت‌ها را با روش‌های مختلف جستجو کنید:\n\n"
    "🔎 موارد قابل جستجو:\n"
    "• 👤 آیدی عددی یا @username تلگرام\n"
    "• 📧 یوزر یا ایمیل اکانت\n"
    "• 🗂 نوع اکانت\n"
    "• 📝 متن موجود در توضیحات\n\n"
    "✍️ لطفاً عبارت مورد نظر برای جستجو را وارد کنید:\n"
    "ℹ️ حداقل ۲ کاراکتر وارد شود.",
    reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 منو", callback_data="home")]
    ])
    )
    return WAIT_SEARCH_QUERY

async def receive_search_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    query = update.message.text.strip()
    if not query or len(query) < 2:
        await update.message.reply_text("❌ حداقل 2 کاراکتر وارد کنید")
        return WAIT_SEARCH_QUERY

    results = search_accounts(query)
    if not results:
        await update.message.reply_text(
            f"❌ نتیجه‌ای برای «{h(query)}» پیدا نشد",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 جستجوی جدید", callback_data="cmd_search")],
                [InlineKeyboardButton("🏠 منو", callback_data="home")]
            ]),
            parse_mode=ParseMode.HTML
        )
        context.user_data.clear()
        return MENU

    text = f"🔍 نتایج برای: <code>{h(query)}</code>\n\n✅ {len(results)} نتیجه:\n\n"
    buttons = []
    for i, (cid, login, type_title, buyer_tg, end_date_s) in enumerate(results[:10], 1):
        rem = remaining_days(end_date_s)
        status = "منقضی ❌" if rem < 0 else f"{rem} روز ⏳"
        text += f"{i}. <code>{h(login)}</code> - {h(type_title)}\n👤 <code>{h(buyer_tg)}</code> | {h(status)}\n\n"
        buttons.append([InlineKeyboardButton(f"{i}. {login[:20]}", callback_data=f"info:{cid}:{enc_cb('search')}")])

    buttons.append([InlineKeyboardButton("🔍 جستجو", callback_data="cmd_search")])
    buttons.append([InlineKeyboardButton("🏠 منو", callback_data="home")])

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    context.user_data.clear()
    return MENU

# ==================== SETTINGS ====================
async def settings_types(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    await q.edit_message_text(tr("types_title"), reply_markup=types_kb())
    return MENU

async def settings_texts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    await q.edit_message_text("✍️ ویرایش متن‌ها", reply_markup=texts_kb())
    return MENU

# ==================== TYPES ====================
async def types_add_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    context.user_data.clear()
    await q.edit_message_text(tr("types_add_ask"))
    return TYPES_ADD_WAIT

async def types_add_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    title = update.message.text.strip()
    ok, reason = add_type(title)
    if ok:
        await update.message.reply_text(tr("types_added"), reply_markup=types_kb())
    else:
        msg = tr("types_add_exists") if reason == "exists" else "❌ نام نامعتبر"
        await update.message.reply_text(msg, reply_markup=types_kb())
    return MENU

async def types_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    page = 0
    if q.data.startswith("types_list:"):
        try:
            page = int(q.data.split(":", 1)[1])
        except Exception:
            page = 0

    types = get_types()
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
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    _, tid, page = q.data.split(":")
    context.user_data["types_edit_id"] = int(tid)
    context.user_data["types_edit_page"] = int(page)
    await q.edit_message_text(tr("types_edit_ask"))
    return TYPES_EDIT_WAIT

async def types_edit_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    tid = context.user_data.get("types_edit_id")
    page = context.user_data.get("types_edit_page", 0)
    new_title = update.message.text.strip()

    ok = edit_type(int(tid), new_title)
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
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    _, tid, page = q.data.split(":")
    ok, reason = delete_type(int(tid))

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

# ==================== TEXT EDITING ====================
async def text_edit_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    _, key = q.data.split(":", 1)
    context.user_data.clear()
    context.user_data["edit_text_key"] = key

    help_vars = (
        "💡 متغیرهای مجاز (کپی کنید و در متن استفاده کنید):\n"
        "• <code>{buyer_tg}</code>\n"
        "• <code>{account_type}</code>\n"
        "• <code>{login}</code>\n"
        "• <code>{start_date}</code>\n"
        "• <code>{end_date}</code>\n"
        "• <code>{end_date_jalali}</code>\n"
        "• <code>{duration_days}</code>\n"
        "• <code>{days_left}</code>\n"
        "• <code>{description}</code>\n"
        "• <code>{bank_name}</code>\n"
        "• <code>{card_number}</code>\n"
        "• <code>{card_owner}</code>\n\n"
        "✅ نکته: متن‌ها HTML هستند و فیلدهای کپی‌پذیر را داخل <code><code>.<code></code> قرار دهید.\n"
    )

    current = get_bot_text(key)

    await q.edit_message_text(
        f"✏️ ویرایش متن (<code>{h(key)}</code>)\n\n"
        f"{help_vars}\n\n"
        f"✍️ متن جدید را ارسال کن:\n\n"
        f"متن فعلی:\n<pre>{html.escape(current)}</pre>",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منو", callback_data="home")]])
    )
    return WAIT_TEXT_EDIT

async def text_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    key = context.user_data.get("edit_text_key")
    if not key:
        await update.message.reply_text(tr("unknown"))
        return MENU

    body = update.message.text
    body = md_backticks_to_html_code(body)
    set_bot_text(key, body)

    await update.message.reply_text("✅ متن ذخیره شد", reply_markup=texts_kb())
    context.user_data.clear()
    return MENU

# ==================== ADD ACCOUNT FLOW ====================
async def type_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    _, tid = q.data.split(":")
    title = type_title_by_id(int(tid))
    if not title:
        await q.edit_message_text(tr("no_types"), reply_markup=main_menu_kb())
        return MENU

    context.user_data["account_type_id"] = int(tid)
    context.user_data["account_type_title"] = title
    await q.edit_message_text(tr("choose_start"), reply_markup=start_choice_kb())
    return START_CHOICE

async def start_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    is_edit = context.user_data.get("edit_mode") and context.user_data.get("edit_action") == "start"

    if q.data == "start_today":
        new_start = date.today().strftime("%Y-%m-%d")

        if is_edit:
            cid = int(context.user_data["edit_cid"])
            enc_back = context.user_data["edit_enc_back"]

            conn = connect()
            cur = conn.cursor()
            cur.execute("SELECT duration_days FROM accounts WHERE id=?", (cid,))
            row = cur.fetchone()
            if not row:
                conn.close()
                await q.message.reply_text("❌ اکانت پیدا نشد")
                return MENU

            duration_days = int(row[0])
            new_end = compute_end_date(new_start, duration_days)
            cur.execute("UPDATE accounts SET start_date=?, end_date=? WHERE id=?", (new_start, new_end, cid))
            conn.commit()
            conn.close()

            msg = get_account_full_html(cid)
            await q.message.reply_text("✅ تاریخ شروع بروزرسانی شد\n\n" + msg, parse_mode=ParseMode.HTML,
                                      reply_markup=back_to_config_kb(cid, enc_back))
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
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    text = update.message.text.strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except Exception:
        await update.message.reply_text(tr("bad_greg"))
        return START_GREGORIAN

    is_edit = context.user_data.get("edit_mode") and context.user_data.get("edit_action") == "start"
    if is_edit:
        cid = int(context.user_data["edit_cid"])
        enc_back = context.user_data["edit_enc_back"]

        conn = connect()
        cur = conn.cursor()
        cur.execute("SELECT duration_days FROM accounts WHERE id=?", (cid,))
        row = cur.fetchone()
        if not row:
            conn.close()
            await update.message.reply_text("❌ اکانت پیدا نشد")
            return MENU

        duration_days = int(row[0])
        new_end = compute_end_date(text, duration_days)
        cur.execute("UPDATE accounts SET start_date=?, end_date=? WHERE id=?", (text, new_end, cid))
        conn.commit()
        conn.close()

        msg = get_account_full_html(cid)
        await update.message.reply_text("✅ تاریخ شروع بروزرسانی شد\n\n" + msg, parse_mode=ParseMode.HTML,
                                        reply_markup=back_to_config_kb(cid, enc_back))
        context.user_data.clear()
        return MENU

    context.user_data["start_date"] = text
    await update.message.reply_text(tr("choose_duration"), reply_markup=duration_kb())
    return DURATION_CHOICE

async def start_jalali_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    text = update.message.text.strip()
    try:
        y, m, d = map(int, text.split("-"))
        g_date = jdatetime.date(y, m, d).togregorian()
        new_start = g_date.strftime("%Y-%m-%d")
    except Exception:
        await update.message.reply_text(tr("bad_jalali"))
        return START_JALALI

    is_edit = context.user_data.get("edit_mode") and context.user_data.get("edit_action") == "start"
    if is_edit:
        cid = int(context.user_data["edit_cid"])
        enc_back = context.user_data["edit_enc_back"]

        conn = connect()
        cur = conn.cursor()
        cur.execute("SELECT duration_days FROM accounts WHERE id=?", (cid,))
        row = cur.fetchone()
        if not row:
            conn.close()
            await update.message.reply_text("❌ اکانت پیدا نشد")
            return MENU

        duration_days = int(row[0])
        new_end = compute_end_date(new_start, duration_days)
        cur.execute("UPDATE accounts SET start_date=?, end_date=? WHERE id=?", (new_start, new_end, cid))
        conn.commit()
        conn.close()

        msg = get_account_full_html(cid)
        await update.message.reply_text("✅ تاریخ شروع بروزرسانی شد\n\n" + msg, parse_mode=ParseMode.HTML,
                                        reply_markup=back_to_config_kb(cid, enc_back))
        context.user_data.clear()
        return MENU

    context.user_data["start_date"] = new_start
    await update.message.reply_text(tr("choose_duration"), reply_markup=duration_kb())
    return DURATION_CHOICE

async def duration_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    is_edit = context.user_data.get("edit_mode") and context.user_data.get("edit_action") == "duration"
    mapping = {"dur_30": 30, "dur_90": 90, "dur_180": 180, "dur_365": 365}

    if q.data in mapping:
        days = mapping[q.data]

        if is_edit:
            cid = int(context.user_data["edit_cid"])
            enc_back = context.user_data["edit_enc_back"]

            conn = connect()
            cur = conn.cursor()
            cur.execute("SELECT start_date FROM accounts WHERE id=?", (cid,))
            row = cur.fetchone()
            if not row:
                conn.close()
                await q.message.reply_text("❌ اکانت پیدا نشد")
                return MENU

            start_date_s = row[0]
            new_end = compute_end_date(start_date_s, days)
            cur.execute("UPDATE accounts SET duration_days=?, end_date=? WHERE id=?", (days, new_end, cid))
            conn.commit()
            conn.close()

            msg = get_account_full_html(cid)
            await q.message.reply_text("✅ مدت زمان بروزرسانی شد\n\n" + msg, parse_mode=ParseMode.HTML,
                                      reply_markup=back_to_config_kb(cid, enc_back))
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
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text(tr("bad_number"))
        return DURATION_MANUAL

    days = int(text)
    if days <= 0 or days > 3650:
        await update.message.reply_text(tr("bad_range"))
        return DURATION_MANUAL

    is_edit = context.user_data.get("edit_mode") and context.user_data.get("edit_action") == "duration"
    if is_edit:
        cid = int(context.user_data["edit_cid"])
        enc_back = context.user_data["edit_enc_back"]

        conn = connect()
        cur = conn.cursor()
        cur.execute("SELECT start_date FROM accounts WHERE id=?", (cid,))
        row = cur.fetchone()
        if not row:
            conn.close()
            await update.message.reply_text("❌ اکانت پیدا نشد")
            return MENU

        start_date_s = row[0]
        new_end = compute_end_date(start_date_s, days)
        cur.execute("UPDATE accounts SET duration_days=?, end_date=? WHERE id=?", (days, new_end, cid))
        conn.commit()
        conn.close()

        msg = get_account_full_html(cid)
        await update.message.reply_text("✅ مدت زمان بروزرسانی شد\n\n" + msg, parse_mode=ParseMode.HTML,
                                        reply_markup=back_to_config_kb(cid, enc_back))
        context.user_data.clear()
        return MENU

    context.user_data["duration_days"] = days
    context.user_data["end_date"] = compute_end_date(context.user_data["start_date"], days)
    await update.message.reply_text(tr("ask_tg"))
    return BUYER_TG

async def buyer_tg_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    context.user_data["buyer_tg"] = normalize_buyer_tg(update.message.text)
    await update.message.reply_text(tr("ask_login"))
    return LOGIN

async def login_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    context.user_data["login"] = str(update.message.text).strip()
    await update.message.reply_text(tr("ask_password"))
    return PASSWORD

async def password_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    context.user_data["password"] = str(update.message.text).strip()
    await update.message.reply_text(tr("ask_description"))
    return DESCRIPTION

async def description_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU

    context.user_data["description"] = str(update.message.text).strip()

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
            (account_type_id, start_date, end_date, duration_days, buyer_tg, login, password, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(context.user_data["account_type_id"]),
            start_date_s, end_date_s, duration_days,
            buyer_tg, login, password, description,
        ))
        conn.commit()
        cid = cur.lastrowid
        conn.close()
    except Exception:
        await update.message.reply_text("❌ خطا در ذخیره‌سازی")
        return MENU

    msg = get_account_full_html(cid)
    await update.message.reply_text("✅ اکانت اضافه شد\n\n" + msg, parse_mode=ParseMode.HTML, reply_markup=main_menu_kb())
    context.user_data.clear()
    return MENU

# ==================== RENEW ====================
async def renew_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    _, cid_s, enc_back = q.data.split(":", 2)
    context.user_data["renew_cid"] = int(cid_s)
    context.user_data["renew_enc_back"] = enc_back

    await q.edit_message_text(
        "⏳ مدت زمان تمدید اکانت را انتخاب کن (روز):\n"
        "تاریخ انقضا از امروز محاسبه خواهد شد.",
        reply_markup=duration_kb()
    )
    return WAIT_RENEW_DURATION

async def renew_duration_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    cid = context.user_data.get("renew_cid")
    enc_back = context.user_data.get("renew_enc_back")
    mapping = {"dur_30": 30, "dur_90": 90, "dur_180": 180, "dur_365": 365}

    if q.data in mapping:
        days = mapping[q.data]
        return await perform_renew(update, context, cid, days, enc_back)

    if q.data == "dur_manual":
        await q.edit_message_text("✍️ مدت زمان تمدید را به روز وارد کن (فقط عدد):")
        return WAIT_RENEW_DURATION

    return WAIT_RENEW_DURATION

async def renew_manual_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text(tr("bad_number"))
        return WAIT_RENEW_DURATION

    days = int(text)
    cid = context.user_data.get("renew_cid")
    enc_back = context.user_data.get("renew_enc_back")
    return await perform_renew(update, context, cid, days, enc_back)

async def perform_renew(update: Update, context: ContextTypes.DEFAULT_TYPE, cid, days, enc_back):
    new_start = date.today().strftime("%Y-%m-%d")
    new_end = compute_end_date(new_start, days)

    conn = connect()
    cur = conn.cursor()
    cur.execute("UPDATE accounts SET start_date=?, end_date=?, duration_days=? WHERE id=?", (new_start, new_end, days, cid))
    conn.commit()
    conn.close()

    msg = get_account_full_html(cid)
    out = "✅ اکانت با موفقیت تمدید شد\n\n" + (msg or "اکانت یافت نشد")

    if update.callback_query:
        await update.callback_query.edit_message_text(out, parse_mode=ParseMode.HTML, reply_markup=back_to_config_kb(cid, enc_back))
    else:
        await update.message.reply_text(out, parse_mode=ParseMode.HTML, reply_markup=back_to_config_kb(cid, enc_back))

    context.user_data.clear()
    return MENU

# ==================== LIST ACCOUNTS ====================
async def list_all_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    _, page_s = q.data.split(":")
    page = int(page_s)
    return await show_accounts_list(update, context, None, page)

async def list_type_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU
    _, tid_s, page_s = q.data.split(":")
    return await show_accounts_list(update, context, int(tid_s), int(page_s))

async def show_accounts_list(update: Update, context: ContextTypes.DEFAULT_TYPE, type_id, page):
    q = update.callback_query

    conn = connect()
    cur = conn.cursor()
    if type_id is None:
        cur.execute("""
            SELECT c.id, c.login, c.end_date, t.title
            FROM accounts c
            JOIN account_types t ON t.id = c.account_type_id
        """)
    else:
        cur.execute("""
            SELECT c.id, c.login, c.end_date, t.title
            FROM accounts c
            JOIN account_types t ON t.id = c.account_type_id
            WHERE c.account_type_id=?
        """, (type_id,))
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
        rem = remaining_days(end_date_s)
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

    title = "📋 کلیه اکانت‌ها" if type_id is None else f"📋 {type_title_by_id(type_id) or '-'}"
    header = (
    f"{title}\n\n"
    "📌 اکانت‌ها بر اساس نزدیک‌ترین تاریخ پایان، از بالا به پایین مرتب شده‌اند ⏳\n"
    "اکانت‌های منقضی‌شده به انتهای لیست منتقل می‌شوند و با برچسب «منقضی» نمایش داده می‌شوند.\n"
    "⏰ اکانت‌های منقضی پس از ۷ روز به‌صورت خودکار حذف خواهند شد.\n\n"
    "📊 جدول شامل ۳ ستون است:\n"
    "• ستون اول: نام اکانت (یوزر یا ایمیل)\n"
    "• ستون دوم: مدت زمان باقی‌مانده\n"
    "• ستون سوم: «اطلاعات بیشتر» برای مشاهده جزئیات، ویرایش، تمدید و متن‌های آماده\n\n"
    f"صفحه {page+1} از {total_pages}"
    )


    await q.edit_message_text(header, reply_markup=InlineKeyboardMarkup(kb_rows))
    return MENU

async def noop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

# ==================== ACCOUNT INFO/ACTIONS ====================
async def info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    _, cid_s, enc_back = q.data.split(":", 2)
    cid = int(cid_s)
    back_cb = dec_cb(enc_back)

    msg = get_account_full_html(cid)
    if not msg:
        await q.answer("یافت نشد", show_alert=True)
        return MENU

    await q.message.reply_text(msg, parse_mode=ParseMode.HTML, reply_markup=info_actions_kb(cid, back_cb))
    return MENU

async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    _, cid_s, enc_back = q.data.split(":", 2)
    cid = int(cid_s)
    back_cb = dec_cb(enc_back)

    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM accounts WHERE id=?", (cid,))
        deleted = cur.rowcount
        conn.commit()
        conn.close()
    except Exception:
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
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

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
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    _, key, cid_s, enc_back = q.data.split(":", 3)
    cid = int(cid_s)

    text = render_template_for_account(key, cid)
    if not text:
        await q.answer("اکانت پیدا نشد", show_alert=True)
        return MENU

    await q.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=back_to_config_kb(cid, enc_back))
    return MENU

# ==================== EDIT ACCOUNT ====================
async def edit_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    _, cid_s, enc_back = q.data.split(":", 2)
    cid = int(cid_s)

    msg = get_account_full_html(cid)
    if not msg:
        await q.answer("یافت نشد", show_alert=True)
        return MENU

    await q.message.reply_text(
        msg + "\n\n✏️ یکی از گزینه‌ها را انتخاب کن:",
        parse_mode=ParseMode.HTML,
        reply_markup=edit_menu_kb(cid, enc_back)
    )
    return MENU

async def edit_start_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

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
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

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
    if q.from_user.id != ADMIN_CHAT_ID:
        await deny_admin_cb(update)
        return MENU

    _, cid_s, enc_back = q.data.split(":", 2)
    context.user_data.clear()
    context.user_data["edit_field"] = field_key
    context.user_data["edit_cid"] = int(cid_s)
    context.user_data["edit_enc_back"] = enc_back

    msg = get_account_full_html(int(cid_s))
    if msg:
        await q.message.reply_text(
            msg + f"\n\n━━━━━━━━\n{title}\n✍️ متن جدید را ارسال کن:",
            parse_mode=ParseMode.HTML,
            reply_markup=back_to_config_kb(int(cid_s), enc_back)
        )
    else:
        await q.message.reply_text(title)

    return WAIT_EDIT_FIELD

async def edit_tg_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await edit_field_prompt(update, context, "buyer_tg", "👤 ویرایش تلگرام (آیدی عددی یا @username)")

async def edit_login_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await edit_field_prompt(update, context, "login", "📧 ویرایش یوزر/ایمیل")

async def edit_password_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await edit_field_prompt(update, context, "password", "🔑 ویرایش پسورد")

async def edit_description_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await edit_field_prompt(update, context, "description", "📝 ویرایش توضیحات")

async def edit_field_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await deny_admin_msg(update)
        return MENU

    field = context.user_data.get("edit_field")
    cid = context.user_data.get("edit_cid")
    enc_back = context.user_data.get("edit_enc_back")

    if not field or not cid or not enc_back:
        await update.message.reply_text(tr("unknown"))
        return MENU

    new_val = update.message.text.strip()
    if field not in ("buyer_tg", "login", "password", "description"):
        await update.message.reply_text("❌ فیلد نامعتبر")
        return MENU

    if field == "buyer_tg":
        new_val = normalize_buyer_tg(new_val)

    conn = connect()
    cur = conn.cursor()
    cur.execute(f"UPDATE accounts SET {field}=? WHERE id=?", (new_val, int(cid)))
    conn.commit()
    conn.close()

    titles = {
        "buyer_tg": "✅ تلگرام بروزرسانی شد",
        "login": "✅ یوزر/ایمیل بروزرسانی شد",
        "password": "✅ پسورد بروزرسانی شد",
        "description": "✅ توضیحات بروزرسانی شد",
    }

    msg = get_account_full_html(int(cid))
    await update.message.reply_text(
        titles.get(field, "✅ بروزرسانی شد") + "\n\n" + (msg or ""),
        parse_mode=ParseMode.HTML,
        reply_markup=back_to_config_kb(int(cid), enc_back)
    )
    context.user_data.clear()
    return MENU

# ==================== USER INQUIRY (LIST OWN ACCOUNTS) ====================
def get_accounts_for_buyer(buyer_keys: list[str]):
    keys = set()
    for k in buyer_keys:
        k = (k or "").strip()
        if not k:
            continue
        if k.isdigit():
            keys.add(k)
        else:
            u = k.lstrip("@").strip().lower()
            if u:
                keys.add(f"@{u}")
                keys.add(u)

    if not keys:
        return []

    conn = connect()
    cur = conn.cursor()
    placeholders = ",".join(["?"] * len(keys))
    cur.execute(f"""
        SELECT c.id, c.login, t.title, c.end_date
        FROM accounts c
        JOIN account_types t ON t.id = c.account_type_id
        WHERE LOWER(c.buyer_tg) IN ({placeholders})
    """, tuple(x.lower() for x in keys))
    rows = cur.fetchall()
    conn.close()
    return rows

async def user_inquiry_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    uid = str(q.from_user.id)
    uname_raw = q.from_user.username or ""
    keys = [uid]
    if uname_raw:
        keys.append(f"@{uname_raw}")
        keys.append(uname_raw)

    rows = get_accounts_for_buyer(keys)
    if not rows:
        await q.edit_message_text(
            "❌ هیچ اکانتی به نام شما ثبت نشده.\n"
            "اگر فکر می‌کنید اشتباه است، از ادمین بخواهید buyer_tg را دقیقاً آیدی عددی یا @username شما ثبت کند.",
            reply_markup=user_menu_kb(is_admin_user=(q.from_user.id == ADMIN_CHAT_ID))
        )
        return MENU

    items = []
    for cid, login, type_title, end_date_s in rows:
        rem = remaining_days(end_date_s)
        items.append((rem, cid, login, type_title, end_date_s))
    items.sort(key=lambda x: x[0])

    text = (
    "📌 اکانت‌های شما\n"
    "🕒 (مرتب‌شده بر اساس نزدیک‌ترین زمان سررسید)\n\n"
    "در لیست زیر، اطلاعات هر اکانت در ۳ ستون نمایش داده می‌شود:\n\n"
    "1️⃣ یوزرنیم / ایمیل اکانت\n"
    "2️⃣ نوع اکانت\n"
    "3️⃣ زمان باقی‌مانده تا پایان\n\n"
    "ℹ️ برای مشاهده اطلاعات کامل هر اکانت،\n"
    "روی یوزرنیم یا ایمیل همان اکانت کلیک کنید 👆"
    )

    kb = []
    for rem, cid, login, type_title, _ in items[:20]:
        label = "منقضی ❌" if rem < 0 else ("امروز ⏳" if rem == 0 else f"{rem} روز")
        kb.append([
            InlineKeyboardButton(login[:24], callback_data=f"user_inquiry_show:{cid}"),
            InlineKeyboardButton(type_title[:18], callback_data="noop_u"),
            InlineKeyboardButton(label[:12], callback_data="noop_u"),
        ])

    kb.append([InlineKeyboardButton("🏠 منو", callback_data="home")])

    await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))
    return MENU

async def user_inquiry_show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    cid = int(q.data.split(":", 1)[1])

    text = render_template_for_account("inquiry", cid)
    if not text:
        await q.edit_message_text(
            "❌ اکانت پیدا نشد.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 منو", callback_data="home")]])
        )
        return MENU

    await q.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data="user_inquiry")]])
    )
    return MENU

async def noop_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()

# ==================== REMINDERS ====================
def parse_buyer_chat_id(buyer_tg: str):
    buyer_tg = (buyer_tg or "").strip()
    if not buyer_tg:
        return None
    if buyer_tg.isdigit():
        return int(buyer_tg)
    return buyer_tg

async def check_daily_reminders(context: ContextTypes.DEFAULT_TYPE):
    today = date.today()

    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT c.id, c.end_date, c.buyer_tg FROM accounts c")
    rows = cur.fetchall()
    conn.close()

    for cid, end_date_s, buyer_tg in rows:
        try:
            end_d = datetime.strptime(end_date_s, "%Y-%m-%d").date()
        except Exception:
            continue

        diff = (end_d - today).days

        if diff == 2:
            text = render_template_for_account("reminder_2days", int(cid))
            if text:
                try:
                    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode=ParseMode.HTML)
                except Exception:
                    pass
                try:
                    chat_id = parse_buyer_chat_id(buyer_tg)
                    if chat_id:
                        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
                except Exception:
                    pass

        if diff == 0:
            text = render_template_for_account("due_day", int(cid))
            if text:
                try:
                    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode=ParseMode.HTML)
                except Exception:
                    pass
                try:
                    chat_id = parse_buyer_chat_id(buyer_tg)
                    if chat_id:
                        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.HTML)
                except Exception:
                    pass

# ==================== DB BACKUP MODULE (ExpiryHub) ====================
def get_setting(k: str) -> str:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT v FROM settings WHERE k=?", (k,))
    row = cur.fetchone()
    conn.close()
    return str(row[0]) if row else ""

def set_setting(k: str, v: str) -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
        (k, v),
    )
    conn.commit()
    conn.close()

def rtl(text: str) -> str:
    RLM = "\u200f"
    return "\n".join([RLM + ln for ln in (text or "").splitlines()])

def _deny_if_not_admin(update: Update) -> bool:
    uid = update.effective_user.id if update.effective_user else None
    return uid != ADMIN_CHAT_ID

def backup_filename(prefix: str = "ExpiryHub_backup") -> str:
    ts = datetime.now(TZ).strftime("%Y-%m-%d_%H-%M-%S")
    return f"{prefix}_{ts}.db"

def make_backup_bytes() -> bytes:
    tmp_path = f"/tmp/{backup_filename(prefix='ExpiryHub_sqlite_backup')}"
    src = sqlite3.connect(DB_PATH)
    try:
        dst = sqlite3.connect(tmp_path)
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
    finally:
        src.close()

    with open(tmp_path, "rb") as f:
        data = f.read()

    try:
        os.remove(tmp_path)
    except Exception:
        pass

    return data

def db_menu_text() -> str:
    enabled = get_setting("backup_enabled") == "1"
    ttype = get_setting("backup_target_type") or "chat"
    tid = get_setting("backup_target_id") or str(ADMIN_CHAT_ID)
    try:
        hours = int(get_setting("backup_interval_hours") or "24")
    except Exception:
        hours = 24

    dest = "آیدی" if ttype == "chat" else "کانال"
    onoff = "روشن ✅" if enabled else "خاموش ❌"

    return (
        "🗄 دیتابیس ExpiryHub\n\n"
        f"🕒 بکاپ خودکار: {onoff}\n"
        f"📍 مقصد بکاپ: {dest}\n"
        f"🆔 مقصد فعلی: {tid}\n"
        f"⏱ هر چند ساعت: {hours}\n"
    )

def db_menu_kb() -> InlineKeyboardMarkup:
    enabled = get_setting("backup_enabled") == "1"
    onoff = "روشن ✅" if enabled else "خاموش ❌"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 گرفتن بکاپ (الان)", callback_data=f"{CB_DB}:backup_now")],
        [InlineKeyboardButton("📤 وارد کردن بکاپ", callback_data=f"{CB_DB}:restore")],
        [InlineKeyboardButton(f"🕒 بکاپ خودکار: {onoff}", callback_data=f"{CB_DB}:toggle")],
        [InlineKeyboardButton("📍 مقصد بکاپ", callback_data=f"{CB_DB}:target")],
        [InlineKeyboardButton("⏱ هر چند ساعت", callback_data=f"{CB_DB}:interval")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data="menu_settings")],
    ])

def db_target_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 ارسال بکاپ به یک آیدی", callback_data=f"{CB_DB}:target:chat")],
        [InlineKeyboardButton("📣 ارسال بکاپ به کانال", callback_data=f"{CB_DB}:target:channel")],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"{CB_DB}:open")],
    ])

async def send_backup_file(context: ContextTypes.DEFAULT_TYPE) -> None:
    if get_setting("backup_enabled") != "1":
        return

    tid = get_setting("backup_target_id") or str(ADMIN_CHAT_ID)
    try:
        target_id = int(tid)
    except Exception:
        target_id = ADMIN_CHAT_ID

    fname = backup_filename(prefix="ExpiryHub_backup")
    data = make_backup_bytes()

    bio = io.BytesIO(data)
    bio.name = fname

    caption = rtl(f"🗄 بکاپ دیتابیس ExpiryHub\n\n📦 {fname}")

    try:
        await context.bot.send_document(
            chat_id=target_id,
            document=bio,
            filename=fname,
            caption=caption,
        )
    except Exception as e:
        logger.warning("Auto-backup send failed: %s", e)

async def db_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    if _deny_if_not_admin(update):
        await q.answer("⛔️ فقط ادمین دسترسی دارد", show_alert=True)
        return MENU

    parts = (q.data or "").split(":")
    act = parts[1] if len(parts) > 1 else ""

    if act == "open":
        await q.edit_message_text(rtl(db_menu_text()), reply_markup=db_menu_kb())
        return MENU

    if act == "backup_now":
        fname = backup_filename(prefix="ExpiryHub_backup")
        data = make_backup_bytes()
        bio = io.BytesIO(data)
        bio.name = fname

        await q.edit_message_text(rtl("در حال ارسال بکاپ..."), reply_markup=db_menu_kb())
        await context.bot.send_document(
            chat_id=update.effective_user.id,
            document=bio,
            filename=fname,
            caption=rtl(f"🗄 بکاپ دیتابیس ExpiryHub\n\n📦 {fname}"),
        )
        await q.edit_message_text(rtl(db_menu_text()), reply_markup=db_menu_kb())
        return MENU

    if act == "toggle":
        cur = get_setting("backup_enabled") or "0"
        set_setting("backup_enabled", "0" if cur == "1" else "1")
        schedule_backup_job(context.application)
        await q.edit_message_text(rtl(db_menu_text()), reply_markup=db_menu_kb())
        return MENU

    if act == "target":
        await q.edit_message_text(
            rtl(
                "📍 مقصد بکاپ\n\n"
                "یکی از گزینه‌ها را انتخاب کنید:\n"
                "• ارسال به آیدی: آیدی عددی چت/گروه\n"
                "• ارسال به کانال: آیدی عددی کانال (مثل -100...)\n\n"
                "ℹ️ اگر کانال انتخاب می‌کنی، ربات باید داخل کانال اجازه ارسال داشته باشد."
            ),
            reply_markup=db_target_kb(),
        )
        return MENU

    await q.edit_message_text(rtl("دستور ناشناخته."), reply_markup=db_menu_kb())
    return MENU

async def db_target_choice_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    if _deny_if_not_admin(update):
        await q.answer("⛔️ فقط ادمین دسترسی دارد", show_alert=True)
        return MENU

    parts = (q.data or "").split(":")
    target_type = parts[2] if len(parts) > 2 else ""

    if target_type == "chat":
        set_setting("backup_target_type", "chat")
        await q.edit_message_text(
            rtl(
                "👤 ارسال بکاپ به آیدی\n\n"
                f"آیدی عددی مقصد را وارد کنید.\n"
                f"اگر /skip بزنید → پیش‌فرض: {ADMIN_CHAT_ID}"
            )
        )
        return DB_SET_TARGET_ID

    if target_type == "channel":
        set_setting("backup_target_type", "channel")
        await q.edit_message_text(
            rtl(
                "📣 ارسال بکاپ به کانال\n\n"
                "آیدی عددی کانال را وارد کنید (مثل -1001234567890).\n\n"
                "⚠️ ربات باید در کانال اجازه ارسال داشته باشد."
            )
        )
        return DB_SET_TARGET_ID

    await q.edit_message_text(rtl("گزینه نامعتبر."), reply_markup=db_menu_kb())
    return MENU

async def db_set_target_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _deny_if_not_admin(update):
        await update.message.reply_text("⛔️ فقط ادمین دسترسی دارد")
        return MENU

    text = (update.message.text or "").strip()

    if text.startswith("/skip"):
        set_setting("backup_target_id", str(ADMIN_CHAT_ID))
        await update.effective_chat.send_message(rtl("✅ مقصد روی آیدی پیش‌فرض ادمین تنظیم شد."))
    else:
        if not re.fullmatch(r"-?\d+", text):
            await update.effective_chat.send_message(rtl("❌ فقط آیدی عددی وارد کنید (مثلاً 123 یا -100...)."))
            return DB_SET_TARGET_ID
        set_setting("backup_target_id", text)
        await update.effective_chat.send_message(rtl("✅ مقصد بکاپ ثبت شد."))

    schedule_backup_job(context.application)
    await update.effective_chat.send_message(rtl(db_menu_text()), reply_markup=db_menu_kb())
    return MENU

async def db_interval_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    if _deny_if_not_admin(update):
        await q.answer("⛔️ فقط ادمین دسترسی دارد", show_alert=True)
        return MENU

    await q.edit_message_text(rtl("⏱ عدد فاصله بکاپ خودکار را به ساعت وارد کنید (مثلاً 24):"))
    return DB_SET_INTERVAL

async def db_set_interval_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _deny_if_not_admin(update):
        await update.message.reply_text("⛔️ فقط ادمین دسترسی دارد")
        return MENU

    t = (update.message.text or "").strip()
    if not re.fullmatch(r"\d+", t):
        await update.effective_chat.send_message(rtl("❌ فقط عدد وارد کنید (ساعت):"))
        return DB_SET_INTERVAL

    hours = max(1, int(t))
    set_setting("backup_interval_hours", str(hours))
    schedule_backup_job(context.application)

    await update.effective_chat.send_message(rtl("✅ فاصله بکاپ خودکار ثبت شد."))
    await update.effective_chat.send_message(rtl(db_menu_text()), reply_markup=db_menu_kb())
    return MENU

async def db_restore_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    q = update.callback_query
    await q.answer()

    if _deny_if_not_admin(update):
        await q.answer("⛔️ فقط ادمین دسترسی دارد", show_alert=True)
        return MENU

    await q.edit_message_text(rtl("📤 لطفاً فایل بکاپ با پسوند .db را ارسال کنید:"))
    return DB_RESTORE_WAIT_DOC

async def db_restore_wait_doc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if _deny_if_not_admin(update):
        await update.message.reply_text("⛔️ فقط ادمین دسترسی دارد")
        return MENU

    msg = update.message
    if not msg or not msg.document:
        await update.effective_chat.send_message(rtl("❌ لطفاً یک فایل .db ارسال کنید."))
        return DB_RESTORE_WAIT_DOC

    doc: Document = msg.document
    fname = (doc.file_name or "").lower()
    if not fname.endswith(".db"):
        await update.effective_chat.send_message(rtl("❌ فقط فایل با پسوند .db قابل قبول است."))
        return DB_RESTORE_WAIT_DOC

    file = await context.bot.get_file(doc.file_id)
    tmp_in = f"/tmp/restore_{datetime.now(TZ).strftime('%Y%m%d_%H%M%S')}.db"
    await file.download_to_drive(custom_path=tmp_in)

    # emergency backup before restore
    try:
        emergency_name = backup_filename(prefix="ExpiryHub_emergency_before_restore")
        data = make_backup_bytes()
        bio = io.BytesIO(data)
        bio.name = emergency_name

        await update.effective_chat.send_message(rtl("🧯 بکاپ اضطراری از دیتابیس فعلی گرفته شد."))
        await context.bot.send_document(
            chat_id=update.effective_user.id,
            document=bio,
            filename=emergency_name,
            caption=rtl(f"🧯 بکاپ اضطراری قبل از ریستور\n\n📦 {emergency_name}"),
        )
    except Exception as e:
        logger.warning("Failed to send emergency backup: %s", e)

    try:
        shutil.move(tmp_in, DB_PATH)
        init_db()
        await update.effective_chat.send_message(rtl("✅ بکاپ با موفقیت وارد شد."))
    except Exception as e:
        logger.exception("Restore failed: %s", e)
        await update.effective_chat.send_message(rtl("❌ خطا در ریستور بکاپ."))
        return MENU

    schedule_backup_job(context.application)
    await update.effective_chat.send_message(rtl(db_menu_text()), reply_markup=db_menu_kb())
    return MENU

# ==================== MAIN ====================
def main():
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.post_init = post_init

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start_cmd),
            CommandHandler("help", cmd_help),
            CommandHandler("add", cmd_add),
            CommandHandler("list", cmd_list),
            CommandHandler("search", cmd_search),
            CommandHandler("settings", cmd_settings),
        ],
        states={
            MENU: [
                # user
                CallbackQueryHandler(user_inquiry_cb, pattern="^user_inquiry$"),
                CallbackQueryHandler(user_inquiry_show, pattern=r"^user_inquiry_show:\d+$"),
                CallbackQueryHandler(noop_user, pattern=r"^noop_u$"),
                CallbackQueryHandler(user_help_cb, pattern="^user_help$"),
                CallbackQueryHandler(admin_panel_cb, pattern="^admin_panel$"),

                # admin panel
                CallbackQueryHandler(menu_add, pattern="^menu_add$"),
                CallbackQueryHandler(menu_list, pattern="^menu_list$"),
                CallbackQueryHandler(menu_settings, pattern="^menu_settings$"),
                CallbackQueryHandler(settings_types, pattern="^settings_types$"),
                CallbackQueryHandler(settings_texts, pattern="^settings_texts$"),

                # ✅ new DB module callbacks
                CallbackQueryHandler(db_cb, pattern=rf"^{CB_DB}:(open|backup_now|toggle|target)$"),
                CallbackQueryHandler(db_target_choice_cb, pattern=rf"^{CB_DB}:target:(chat|channel)$"),
                CallbackQueryHandler(db_interval_entry, pattern=rf"^{CB_DB}:interval$"),
                CallbackQueryHandler(db_restore_entry, pattern=rf"^{CB_DB}:restore$"),

                CallbackQueryHandler(types_add_prompt, pattern="^types_add$"),
                CallbackQueryHandler(types_list, pattern=r"^types_list:\d+$"),
                CallbackQueryHandler(types_edit_prompt, pattern=r"^types_edit:\d+:\d+$"),
                CallbackQueryHandler(types_delete, pattern=r"^types_del:\d+:\d+$"),
                CallbackQueryHandler(noop_type, pattern=r"^noop_type:\d+$"),
                CallbackQueryHandler(list_all_cb, pattern=r"^list_all:\d+$"),
                CallbackQueryHandler(list_type_cb, pattern=r"^list_type:\d+:\d+$"),
                CallbackQueryHandler(info_handler, pattern=r"^info:\d+:.+"),
                CallbackQueryHandler(renew_prompt, pattern=r"^renew_prompt:\d+:.+"),
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
                CallbackQueryHandler(cmd_help_admin_inline, pattern="^cmd_help_admin$"),
                CallbackQueryHandler(noop_handler, pattern=r"^noop:\d+$"),
                CallbackQueryHandler(go_home, pattern="^home$"),
            ],
            CHOOSING_TYPE: [
                CallbackQueryHandler(type_pick, pattern=r"^type_pick:\d+$"),
                CallbackQueryHandler(go_home, pattern="^home$"),
            ],
            START_CHOICE: [
                CallbackQueryHandler(start_choice_cb, pattern=r"^start_"),
                CallbackQueryHandler(go_home, pattern="^home$"),
            ],
            START_GREGORIAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, start_gregorian_msg)
            ],
            START_JALALI: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, start_jalali_msg),
            ],
            DURATION_CHOICE: [
                CallbackQueryHandler(duration_choice_cb, pattern=r"^dur_"),
                CallbackQueryHandler(go_home, pattern="^home$"),
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
            WAIT_TEXT_EDIT: [
                CallbackQueryHandler(go_home, pattern="^home$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, text_edit_save),
            ],
            WAIT_EDIT_FIELD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_field_save),
            ],
            WAIT_SEARCH_QUERY: [
                CallbackQueryHandler(go_home, pattern="^home$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_search_query),
            ],
            WAIT_RENEW_DURATION: [
                CallbackQueryHandler(renew_duration_choice_cb, pattern=r"^dur_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, renew_manual_msg),
            ],

            # ✅ DB module states
            DB_SET_TARGET_ID: [
                CommandHandler("skip", db_set_target_id_input),
                MessageHandler(filters.TEXT & ~filters.COMMAND, db_set_target_id_input),
            ],
            DB_SET_INTERVAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, db_set_interval_input),
            ],
            DB_RESTORE_WAIT_DOC: [
                MessageHandler(filters.Document.ALL, db_restore_wait_doc),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_cmd)],
        allow_reentry=True,
        per_message=False,
    )

    app.add_handler(conv)

    if app.job_queue:
        app.job_queue.run_daily(check_daily_reminders, time=dtime(hour=10, minute=0), name="daily_reminders")

    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    print("🚀 ExpiryHub Bot Started!")
    app.run_polling()

if __name__ == "__main__":
    main()

