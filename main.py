import asyncio
import logging
import json
import os
import sys
import re
import base64
import hashlib
import shutil
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, FSInputFile, InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from telethon import TelegramClient, events, functions

# ==================== КОНФИГ ====================
BOT_TOKEN = "8975688414:AAGUC6Ag9ADN_p7Tb0R9a8xsLEnsFHFkWZM"
ADMIN_ID = 8543473783
CHANNEL_ID = "-1004311525622"
STORE_CHANNEL_ID = "-1004292126045"
PARTNER_GROUP_ID = -5598258715  # ID группы для уведомлений о заработке партнеров

API_ID = 38387697
API_HASH = "e8fb7f7163498eb28231e45071fe92c0"

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ==================== ПРЕМИУМ ЭМОДЗИ ====================
EMOJI = {
    "star":   ("5438496463044752972", "⭐"),
    "check":  ("5206607081334906820", "✅"),
    "fire":   ("5424972470023104089", "🔥"),
    "money":  ("5287231198098117669", "💰"),
    "cart":   ("5312361253610475399", "🛍"),
    "user":   ("5190872550250405805", "👤"),
    "gift":   ("5278467510604160626", "🎁"),
    "time":   ("5382194935057372936", "⏱"),
    "warn":   ("5274099962655816924", "⚠️"),
    "box":    ("5312361253610475399", "📦"), # Используем иконку корзины для склада
}

def pe(key: str) -> str:
    eid, sym = EMOJI.get(key, (None, ""))
    return f"<tg-emoji emoji-id='{eid}'>{sym}</tg-emoji>" if eid else sym

def eid(key: str):
    return EMOJI.get(key, (None, ""))[0]

def ibtn(builder, text, callback_data=None, url=None, icon_key=None, style=None):
    kw = {"text": text}
    if callback_data is not None: kw["callback_data"] = callback_data
    if url is not None: kw["url"] = url
    if style: kw["style"] = style
    if icon_key and eid(icon_key):
        try: kw["icon_custom_emoji_id"] = eid(icon_key)
        except Exception: pass
    try:
        builder.add(InlineKeyboardButton(**kw))
    except TypeError:
        kw.pop("icon_custom_emoji_id", None)
        kw.pop("style", None)
        builder.add(InlineKeyboardButton(**kw))

# ==================== ФАЙЛЫ ====================
ORDERS_FILE = "orders.json"
REVIEWS_FILE = "reviews.json"
RELAY_FILE = "relay_map.json"
REQUISITES_FILE = "requisites.json"
USERS_FILE = "users.json"
REFERRALS_FILE = "referrals.json"
PROMO_CODES_FILE = "promo_codes.json"
SETTINGS_FILE = "settings.json"
ORDER_COUNTER_FILE = "order_counter.json"
CHAT_HISTORY_FILE = "chat_history.json"
BROADCASTS_FILE = "broadcasts.json"
TRAFFIC_SOURCES_FILE = "traffic_sources.json"
PROMO_EARNINGS_FILE = "promo_earnings.json"

ACCOUNTS_DIR = "accounts"
TEMP_DIR = "temp_sessions"
os.makedirs(ACCOUNTS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ==================== БЭКАПЫ (ENV) ====================
BACKUP_FILES = [
    "orders", "users", "referrals", "promo_codes", "settings",
    "order_counter", "reviews", "relay_map", "requisites",
    "chat_history", "broadcasts", "traffic_sources", "promo_earnings"
]

def get_backup_env_key(name: str) -> str:
    return f"BACKUP_{name.upper()}_B64"

def restore_from_env():
    restored = []
    for name in BACKUP_FILES:
        env_key = get_backup_env_key(name)
        value = os.environ.get(env_key)
        if not value: continue
        path = f"{name}.json"
        if os.path.exists(path) and os.path.getsize(path) > 2: continue
        try:
            data = base64.b64decode(value).decode("utf-8")
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
            restored.append(name)
        except Exception as e:
            logger.error(f"Restore {name} failed: {e}")
    if restored: print(f"[BACKUP] Восстановлено: {', '.join(restored)}")

def auto_backup_note(name: str, data: dict):
    try:
        raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        b64 = base64.b64encode(raw).decode("ascii")
        with open(f"backup_{name}.b64", "w", encoding="utf-8") as f:
            f.write(b64)
    except: pass

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    name = path.replace(".json", "")
    if name in BACKUP_FILES: auto_backup_note(name, data)

def load_orders(): return load_json(ORDERS_FILE)
def save_orders(o): save_json(ORDERS_FILE, o)
def load_reviews(): return load_json(REVIEWS_FILE)
def save_reviews(r): save_json(REVIEWS_FILE, r)
def load_relay(): return load_json(RELAY_FILE)
def save_relay(r): save_json(RELAY_FILE, r)
def load_requisites(): return load_json(REQUISITES_FILE)
def save_requisites(r): save_json(REQUISITES_FILE, r)
def load_users(): return load_json(USERS_FILE)
def save_users(u): save_json(USERS_FILE, u)
def load_referrals(): return load_json(REFERRALS_FILE)
def save_referrals(r): save_json(REFERRALS_FILE, r)
def load_promo_codes(): return load_json(PROMO_CODES_FILE)
def save_promo_codes(p): save_json(PROMO_CODES_FILE, p)
def load_settings(): return load_json(SETTINGS_FILE)
def save_settings(s): save_json(SETTINGS_FILE, s)
def load_order_counter(): return load_json(ORDER_COUNTER_FILE)
def save_order_counter(c): save_json(ORDER_COUNTER_FILE, c)
def load_chat_history(): return load_json(CHAT_HISTORY_FILE)
def save_chat_history(c): save_json(CHAT_HISTORY_FILE, c)
def load_broadcasts(): return load_json(BROADCASTS_FILE)
def save_broadcasts(b): save_json(BROADCASTS_FILE, b)
def load_traffic_sources(): return load_json(TRAFFIC_SOURCES_FILE)
def save_traffic_sources(t): save_json(TRAFFIC_SOURCES_FILE, t)
def load_promo_earnings(): return load_json(PROMO_EARNINGS_FILE)
def save_promo_earnings(e): save_json(PROMO_EARNINGS_FILE, e)

# ==================== СТРАНЫ И СКЛАД ====================
COUNTRY_CODES = {
    "91": ("in", "🇮🇳 Индия"), "95": ("mm", "🇲🇲 Мьянма"),
    "234": ("ng", "🇳🇬 Нигерия"), "62": ("id", "🇮🇩 Индонезия"),
    "1": ("us", "🇺🇸 США"), "57": ("co", "🇨🇴 Колумбия"),
    "880": ("bd", "🇧🇩 Бангладеш"), "998": ("uz", "🇺🇿 Узбекистан"),
    "66": ("th", "🇹🇭 Таиланд"), "44": ("gb", "🇬🇧 Великобритания"),
    "222": ("mr", "🇲🇷 Мавритания"), "380": ("ua", "🇺🇦 Украина"),
    "375": ("by", "🇧🇾 Беларусь"), "77": ("kz", "🇰🇿 Казахстан"),
    "7": ("ru", "🇷🇺 Россия"), "48": ("pl", "🇵🇱 Польша"),
    "49": ("de", "🇩🇪 Германия"), "33": ("fr", "🇫🇷 Франция"),
    "36": ("hu", "🇭🇺 Венгрия"), "299": ("gl", "🇬🇱 Гренландия"),
    "995": ("ge", "🇬🇪 Грузия"), "994": ("az", "🇦🇿 Азербайджан"),
    "996": ("kg", "🇰🇬 Киргизия"), "373": ("md", "🇲🇩 Молдова"),
    "371": ("lv", "🇱🇻 Латвия"), "370": ("lt", "🇱🇹 Литва"),
    "372": ("ee", "🇪🇪 Эстония"), "90": ("tr", "🇹🇷 Турция"),
    "972": ("il", "🇮🇱 Израиль"), "86": ("cn", "🇨🇳 Китай"),
    "81": ("jp", "🇯🇵 Япония"), "82": ("kr", "🇰🇷 Корея"),
    "84": ("vn", "🇻🇳 Вьетнам"), "63": ("ph", "🇵🇭 Филиппины"),
    "60": ("my", "🇲🇾 Малайзия"), "65": ("sg", "🇸🇬 Сингапур"),
    "46": ("se", "🇸🇪 Швеция"), "47": ("no", "🇳🇴 Норвегия"),
    "45": ("dk", "🇩🇰 Дания"), "358": ("fi", "🇫🇮 Финляндия"),
    "351": ("pt", "🇵🇹 Португалия"), "39": ("it", "🇮🇹 Италия"),
    "34": ("es", "🇪🇸 Испания"), "31": ("nl", "🇳🇱 Нидерланды"),
    "32": ("be", "🇧🇪 Бельгия"), "41": ("ch", "🇨🇭 Швейцария"),
    "43": ("at", "🇦🇹 Австрия"), "420": ("cz", "🇨🇿 Чехия"),
    "421": ("sk", "🇸🇰 Словакия"),
}

def detect_country(phone: str) -> tuple:
    if not phone: return ("unknown", "❓ Неизвестно")
    clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    for length in (3, 2, 1):
        prefix = clean[:length]
        if prefix in COUNTRY_CODES: return COUNTRY_CODES[prefix]
    return ("unknown", "❓ Неизвестно")

DEFAULT_PRICES = {
    "in": (30, 40), "mm": (30, 40), "ng": (30, 40), "id": (30, 40),
    "us": (45, 65), "co": (45, 65), "bd": (45, 65),
    "uz": (80, 125), "th": (80, 125),
    "gb": (120, 150), "mr": (120, 150),
    "ua": (150, 200), "by": (150, 200), "kz": (150, 200),
    "pl": (150, 200), "de": (150, 200), "ru": (150, 200),
    "fr": (150, 200), "hu": (200, 300), "gl": (250, 350),
    "tt": (50, 65), "tt_live": (240, 300),
    "dc": (40, 50), "dc_nitro": (150, 200),
}

def country_dir(country: str) -> str: return os.path.join(ACCOUNTS_DIR, country)
def session_path(country: str, name: str) -> str: return os.path.join(country_dir(country), f"{name}.session")
def watcher_path(country: str, name: str) -> str: return os.path.join(country_dir(country), f"{name}_watcher.session")
def meta_path(country: str, name: str) -> str: return os.path.join(country_dir(country), f"{name}.json")

def load_meta(country: str, name: str):
    p = meta_path(country, name)
    if not os.path.exists(p): return None
    with open(p, "r", encoding="utf-8") as f: return json.load(f)

def save_meta(country: str, name: str, meta: dict):
    with open(meta_path(country, name), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

async def analyze_session(session_file: str) -> dict:
    client = TelegramClient(session_file.replace(".session", ""), API_ID, API_HASH)
    result = {"valid": False, "phone": None, "user_id": None, "first_name": None, "has_2fa": False, "password_hint": None}
    try:
        await client.connect()
        if not await client.is_user_authorized():
            result["error"] = "NOT_AUTHORIZED"
            return result
        me = await client.get_me()
        if not me:
            result["error"] = "NO_ME"
            return result
        result.update({
            "valid": True, "phone": me.phone, "user_id": me.id,
            "first_name": me.first_name, "username": me.username,
            "premium": getattr(me, "premium", False),
        })
        try:
            pwd = await client(functions.account.GetPasswordRequest())
            if getattr(pwd, "has_password", False):
                result["has_2fa"] = True
                result["password_hint"] = getattr(pwd, "hint", None)
        except Exception as e:
            logger.warning(f"2FA check failed: {e}")
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:100]}"
    finally:
        try: await client.disconnect()
        except: pass
    return result

def all_available(country: str = None) -> list:
    if not os.path.exists(ACCOUNTS_DIR): return []
    result = []
    countries = [country] if country else os.listdir(ACCOUNTS_DIR)
    for c in countries:
        cd = country_dir(c)
        if not os.path.isdir(cd): continue
        for f in os.listdir(cd):
            if f.endswith(".json"):
                meta = load_meta(c, f.replace(".json", ""))
                if meta and meta.get("status") == "available": result.append(meta)
    return result

def stock_count() -> dict:
    counts = {}
    if not os.path.exists(ACCOUNTS_DIR): return counts
    for c in os.listdir(ACCOUNTS_DIR):
        cd = country_dir(c)
        if not os.path.isdir(cd): continue
        counts[c] = 0
        for f in os.listdir(cd):
            if f.endswith(".json"):
                meta = load_meta(c, f.replace(".json", ""))
                if meta and meta.get("status") == "available": counts[c] += 1
    return counts

def reserve_account(country: str, user_id: int):
    avail = all_available(country)
    if not avail: return None
    acc = avail[0]
    acc["status"] = "reserved"
    acc["reserved_by"] = user_id
    acc["reserved_at"] = datetime.now().isoformat()
    save_meta(country, acc["session_name"], acc)
    return acc

def release_account(country: str, session_name: str):
    meta = load_meta(country, session_name)
    if not meta: return
    meta["status"] = "available"
    meta.pop("reserved_by", None)
    meta.pop("reserved_at", None)
    save_meta(country, session_name, meta)

def mark_sold(country: str, session_name: str, user_id: int):
    meta = load_meta(country, session_name)
    if not meta: return
    meta["status"] = "sold"
    meta["sold_at"] = datetime.now().isoformat()
    meta["sold_to"] = user_id
    save_meta(country, session_name, meta)

def get_user_accounts(user_id: int) -> list:
    result = []
    if not os.path.exists(ACCOUNTS_DIR): return result
    for c in os.listdir(ACCOUNTS_DIR):
        cd = country_dir(c)
        if not os.path.isdir(cd): continue
        for f in os.listdir(cd):
            if f.endswith(".json"):
                meta = load_meta(c, f.replace(".json", ""))
                if meta and meta.get("sold_to") == user_id: result.append(meta)
    return result

# ==================== ПЕРЕХВАТ КОДОВ ====================
active_watchers = {}
watcher_users = {}
watcher_passwords = {}
watcher_orders = {}

async def watch_codes(session_file: str, user_id: int, password: str = None, order_key: str = None):
    session_name = os.path.basename(session_file).replace(".session", "")
    if session_name in active_watchers:
        watcher_users[session_name] = user_id
        if password: watcher_passwords[session_name] = password
        if order_key: watcher_orders[session_name] = order_key
        return

    client = TelegramClient(session_file.replace(".session", ""), API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            try: await bot.send_message(user_id, f"{pe('warn')} Сессия недействительна. Напишите @MaskYoY")
            except: pass
            return

        @client.on(events.NewMessage(from_users=[777000]))
        async def handler(event):
            text = event.message.text or ""
            target = watcher_users.get(session_name)
            if not target: return

            code_match = re.search(r'\b(\d{5})\b', text)
            if code_match:
                code = code_match.group(1)
                pwd = watcher_passwords.get(session_name)
                msg = f"🔑 <b>КОД ПОДТВЕРЖДЕНИЯ</b>\n\n<code>{code}</code>\n\n"
                if pwd: msg += f"🔐 <b>Пароль (2FA):</b> <code>{pwd}</code>\n\n"
                msg += "Введите код в Telegram сейчас же!"
                try: await bot.send_message(target, msg, parse_mode="HTML")
                except Exception as e: logger.error(f"Send code error: {e}")
                return

            low = text.lower()
            login_signals = ["новый вход", "new login", "вы вошли", "you have logged in", "новое устройство", "new device"]
            if any(sig in low for sig in login_signals):
                order_key_local = watcher_orders.get(session_name)
                try:
                    kb = InlineKeyboardBuilder()
                    if order_key_local:
                        ibtn(kb, "Оставить отзыв", callback_data=f"leave_review_{order_key_local}", icon_key="star", style="success")
                    ibtn(kb, "Мои аккаунты", callback_data="my_accounts", icon_key="box")
                    kb.adjust(1)
                    await bot.send_message(target,
                        f"{pe('check')} <b>ВХОД ПОДТВЕРЖДЁН!</b>\n\n"
                        f"📱 Сессия: <code>{session_name}</code>\n"
                        f"🎉 Аккаунт успешно вошёл.\n\n"
                        f"Пожалуйста, оставь отзыв!",
                        reply_markup=kb.as_markup())
                except Exception as e: logger.error(f"Login notify error: {e}")

                try:
                    await bot.send_message(ADMIN_ID,
                        f"{pe('check')} <b>ПОКУПАТЕЛЬ ВОШЁЛ В АККАУНТ</b>\n\n"
                        f"👤 User ID: <code>{target}</code>\n"
                        f"📱 Сессия: <code>{session_name}</code>\n"
                        f"🆔 Заказ: <code>{order_key_local or '—'}</code>")
                except: pass

                if order_key_local:
                    try:
                        orders = load_orders()
                        rk = find_order_key(orders, order_key_local)
                        if rk and orders[rk].get("status") != "completed":
                            orders[rk]["status"] = "completed"
                            orders[rk]["completed_at"] = datetime.now().isoformat()
                            save_orders(orders)
                    except Exception as e: logger.error(f"Auto-complete error: {e}")

        active_watchers[session_name] = client
        watcher_users[session_name] = user_id
        if password: watcher_passwords[session_name] = password
        if order_key: watcher_orders[session_name] = order_key
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Watcher error {session_name}: {e}")
    finally:
        active_watchers.pop(session_name, None)

async def start_code_watcher(country: str, session_name: str, user_id: int, order_key: str = None):
    meta = load_meta(country, session_name)
    pwd = meta.get("password") if meta else None
    sess = watcher_path(country, session_name)
    if not os.path.exists(sess): sess = session_path(country, session_name)
    await watch_codes(sess, user_id, pwd, order_key)

# ==================== НАСТРОЙКИ ====================
DEFAULT_SETTINGS = {
    "referral_bonus_percent": 5.0,
    "partner_commission_percent": 20.0,
    "partner_discount_percent": 10.0,
    "level_bronze_min": 0, "level_bronze_discount": 0,
    "level_silver_min": 500, "level_silver_discount": 3,
    "level_gold_min": 1500, "level_gold_discount": 5,
    "level_platinum_min": 3000, "level_platinum_discount": 7,
    "level_vip_min": 5000, "level_vip_discount": 10,
}
if not os.path.exists(SETTINGS_FILE): save_settings(DEFAULT_SETTINGS)

def get_setting(key, default=None):
    s = load_settings()
    return s.get(key, DEFAULT_SETTINGS.get(key, default))

LEVEL_KEYS = {"bronze": "Бронза", "silver": "Серебро", "gold": "Золото", "platinum": "Платина", "vip": "VIP"}

# ==================== ПОЛЬЗОВАТЕЛИ ====================
async def add_user(user_id, username=None, full_name=None, ref_code=None):
    users = load_users()
    referrals = load_referrals()
    key = str(user_id)
    is_new = key not in users

    if is_new:
        users[key] = {
            "user_id": user_id, "username": username, "full_name": full_name,
            "first_seen": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "referred_by": None, "referral_code": None,
            "total_spent": 0.0, "orders_count": 0, "traffic_source": None,
        }
        if ref_code and ref_code.startswith("ref_"):
            actual = ref_code[4:]
            for rid, rdata in referrals.items():
                if rdata.get("referral_code") == actual:
                    users[key]["referred_by"] = int(rid)
                    rdata.setdefault("referrals_list", []).append({
                        "user_id": user_id, "username": username,
                        "date": datetime.now().isoformat(),
                        "first_purchase_done": False,
                    })
                    break
        if ref_code and not ref_code.startswith("ref_"):
            users[key]["traffic_source"] = ref_code
            sources = load_traffic_sources()
            if ref_code not in sources:
                sources[ref_code] = {"total_visits": 0, "total_registrations": 0, "total_purchases": 0, "total_revenue": 0.0, "created_at": datetime.now().isoformat()}
            sources[ref_code]["total_visits"] += 1
            sources[ref_code]["total_registrations"] += 1
            save_traffic_sources(sources)
        own_code = hashlib.md5(f"{user_id}_ref_salt".encode()).hexdigest()[:8].upper()
        users[key]["referral_code"] = own_code
        referrals.setdefault(key, {"user_id": user_id, "referral_code": own_code, "referrals_list": [], "total_earned": 0.0})
        save_referrals(referrals)
        save_users(users)
        return True

    users[key]["last_active"] = datetime.now().isoformat()
    if username: users[key]["username"] = username
    if full_name: users[key]["full_name"] = full_name
    own_code = users[key].get("referral_code")
    if not own_code:
        own_code = hashlib.md5(f"{user_id}_ref_salt".encode()).hexdigest()[:8].upper()
        users[key]["referral_code"] = own_code
    referrals.setdefault(key, {"user_id": user_id, "referral_code": own_code, "referrals_list": [], "total_earned": 0.0})
    save_referrals(referrals)
    save_users(users)
    return False

DEFAULT_REQUISITES = {
    "uah": f"{pe('money')} Карта Моно: 4874 0700 2513 7454\n\n{pe('gift')} Подарок в ЛС: @MaskYoY",
    "gift": f"{pe('gift')} Подарок в ЛС: @MaskYoY",
}
if not os.path.exists(REQUISITES_FILE): save_requisites(DEFAULT_REQUISITES)

def get_requisites(method):
    req = load_requisites()
    return req.get(method, DEFAULT_REQUISITES.get(method, "Уточните у продавца"))

# ==================== КАТАЛОГ ====================
CATEGORIES = {
    "regular": {
        "name": f"{pe('cart')} ОБЫЧНЫЕ НОМЕРА",
        "products": {
            "🇮🇳 Индия (+91)":          {"uah": 30,  "code": "in"},
            "🇲🇲 Мьянма (+95)":         {"uah": 30,  "code": "mm"},
            "🇳🇬 Нигерия (+234)":       {"uah": 30,  "code": "ng"},
            "🇮🇩 Индонезия (+62)":      {"uah": 30,  "code": "id"},
            "🇺🇸 США (+1)":             {"uah": 45,  "code": "us"},
            "🇨🇴 Колумбия (+57)":       {"uah": 45,  "code": "co"},
            "🇧🇩 Бангладеш (+880)":     {"uah": 45,  "code": "bd"},
            "🇺🇿 Узбекистан (+998)":    {"uah": 80,  "code": "uz"},
            "🇹🇭 Таиланд (+66)":        {"uah": 80,  "code": "th"},
            "🇬🇧 Великобритания (+44)": {"uah": 120, "code": "gb"},
            "🇲🇷 Мавритания (+222)":    {"uah": 120, "code": "mr"},
            "🇺🇦 Украина (+380)":       {"uah": 150, "code": "ua"},
            "🇧🇾 Беларусь (+375)":      {"uah": 150, "code": "by"},
            "🇰🇿 Казахстан (+7)":       {"uah": 150, "code": "kz"},
            "🇵🇱 Польша (+48)":         {"uah": 150, "code": "pl"},
            "🇩🇪 Германия (+49)":       {"uah": 150, "code": "de"},
        },
    },
    "physical": {
        "name": "☎️ ФИЗ НОМЕРА",
        "products": {
            "🇺🇸 США (+1)":            {"uah": 150, "code": "us"},
            "🇺🇦 Украина (+380)":      {"uah": 200, "code": "ua"},
            "🇺🇿 Узбекистан (+998)":   {"uah": 140, "code": "uz"},
            "🇹🇭 Таиланд (+66)":       {"uah": 120, "code": "th"},
            "🇫🇷 Франция (+33)":       {"uah": 150, "code": "fr"},
            "🇰🇿 Казахстан (+77)":     {"uah": 200, "code": "kz"},
            "🇭🇺 Венгрия (+36)":       {"uah": 200, "code": "hu"},
            "🇬🇱 Гренландия (+299)":   {"uah": 250, "code": "gl"},
            "🇵🇱 Польша (+48)":        {"uah": 250, "code": "pl"},
        },
    },
    "tiktok": {
        "name": f"📱 TIKTOK",
        "products": {
            "Обычный TikTok":        {"uah": 50,  "code": "tt"},
            "TikTok с эфирами":      {"uah": 240, "code": "tt_live"},
        },
    },
    "discord": {
        "name": f"💬 DISCORD",
        "products": {
            "Новый Discord":         {"uah": 40,  "code": "dc"},
            "Discord с Nitro":       {"uah": 150, "code": "dc_nitro"},
        },
    },
    "stars": {
        "name": f"{pe('star')} ЗВЁЗДЫ",
        "products": {
            "13 звезд":   {"uah": 7,   "code": "st13"},
            "21 звезда":  {"uah": 15,  "code": "st21"},
            "43 звезды":  {"uah": 35,  "code": "st43"},
            "85 звезд":   {"uah": 60,  "code": "st85"},
            "98 звезд":   {"uah": 70,  "code": "st98"},
            "106 звезд":  {"uah": 75,  "code": "st106"},
            "128 звезд":  {"uah": 80,  "code": "st128"},
            "170 звезд":  {"uah": 130, "code": "st170"},
        },
    }
}

# ==================== FSM ====================
class ReviewStates(StatesGroup):
    waiting_for_stars = State()
    waiting_for_photo_or_skip = State()
    waiting_for_text = State()

class OrderStates(StatesGroup):
    waiting_for_quantity = State()
    waiting_for_promo_input = State()
    waiting_for_payment_method = State()
    waiting_for_confirmation = State()

class AdminStates(StatesGroup):
    waiting_for_requisites_edit = State()
    waiting_for_broadcast = State()

class AdminStockStates(StatesGroup):
    waiting_for_session = State()

class AdminLevelStates(StatesGroup):
    waiting_for_min_spent = State()
    waiting_for_discount = State()

class AdminReferralSettingsStates(StatesGroup):
    waiting_for_bonus_percent = State()

class AdminChatStates(StatesGroup):
    waiting_for_message = State()

class AdminPromoStates(StatesGroup):
    waiting_for_promo_code = State()
    waiting_for_discount_type = State()
    waiting_for_discount_value = State()
    waiting_for_max_uses = State()
    waiting_for_expires_date = State()
    waiting_for_owner_username = State()

class SupportStates(StatesGroup):
    chatting = State()

class PromoStates(StatesGroup):
    waiting_for_promo_code = State()

STATUS_CONFIG = {
    "awaiting_payment": (pe("time"), "Ожидает оплаты"),
    "paid": (pe("money"), "Оплачен"),
    "completed": (pe("check"), "Выполнен"),
    "rejected": (pe("warn"), "Отклонен"),
    "refunded": (pe("money"), "Возврат"),
}

def method_label(m): return {"uah": f"{pe('money')} Гривны", "gift": f"{pe('gift')} Подарок"}.get(m, m)
def method_symbol(m): return {"uah": "₴", "gift": "🎁"}.get(m, "")

def generate_short_order_id():
    counter = load_order_counter()
    current = counter.get("current", 0)
    new_id = current + 1
    counter["current"] = new_id
    save_order_counter(counter)
    return f"#{new_id:06d}"

def find_order_key(orders, order_id):
    if not order_id: return None
    order_id = str(order_id).strip()
    if order_id in orders: return order_id
    clean = order_id.replace("#", "").strip()
    for key, order in orders.items():
        if str(key).replace("#", "").strip() == clean: return key
        if str(order.get("short_id", "")).replace("#", "").strip() == clean: return key
    return None

def get_user_level(user_id):
    users = load_users()
    user = users.get(str(user_id), {})
    total_spent = user.get("total_spent", 0)
    levels = [
        ("VIP", get_setting("level_vip_min", 5000), get_setting("level_vip_discount", 10), "👑"),
        ("Платина", get_setting("level_platinum_min", 3000), get_setting("level_platinum_discount", 7), "💎"),
        ("Золото", get_setting("level_gold_min", 1500), get_setting("level_gold_discount", 5), "🥇"),
        ("Серебро", get_setting("level_silver_min", 500), get_setting("level_silver_discount", 3), "🥈"),
        ("Бронза", get_setting("level_bronze_min", 0), get_setting("level_bronze_discount", 0), "🥉"),
    ]
    for name, min_spent, discount, emoji in levels:
        if total_spent >= min_spent: return {"name": name, "discount": discount, "emoji": emoji, "min_spent": min_spent}
    return {"name": "Бронза", "discount": 0, "emoji": "🥉", "min_spent": 0}

async def process_referral_bonus(referrer_id, referred_id, order_total):
    try: order_total = float(order_total)
    except: return
    if order_total <= 0: return
    referrals = load_referrals()
    rkey = str(referrer_id)
    if rkey not in referrals: return
    rdata = referrals[rkey]
    rdata.setdefault("referrals_list", [])
    users = load_users()
    referred = users.get(str(referred_id), {})
    if referred.get("orders_count", 0) > 1: return
    for ref in rdata["referrals_list"]:
        if ref.get("user_id") == referred_id and ref.get("bonus_promo_code"): return
    bonus_percent = get_setting("referral_bonus_percent", 5.0)
    bonus_amount = round(order_total * (bonus_percent / 100), 2)
    if bonus_amount <= 0: return
    code = "REF" + hashlib.md5(f"{referrer_id}_{referred_id}_{datetime.now().timestamp()}".encode()).hexdigest()[:8].upper()
    promo_codes = load_promo_codes()
    promo_codes[code] = {
        "code": code, "discount_type": "fixed", "discount_value": bonus_amount,
        "max_uses": 1, "current_uses": 0,
        "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
        "is_active": True, "created_at": datetime.now().isoformat(),
        "owner_id": referrer_id,
    }
    save_promo_codes(promo_codes)
    for ref in rdata["referrals_list"]:
        if ref.get("user_id") == referred_id:
            ref["first_purchase_done"] = True
            ref["bonus_amount"] = bonus_amount
            ref["bonus_promo_code"] = code
            break
    rdata["total_earned"] = rdata.get("total_earned", 0) + bonus_amount
    save_referrals(referrals)
    try:
        await bot.send_message(referrer_id, f"{pe('gift')} Реферальный бонус!\nСумма: {bonus_amount:.2f} грн\nПромокод: <code>{code}</code>")
    except: pass

async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(chat_id=STORE_CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

# ==================== КЛАВИАТУРЫ ====================
def get_main_reply_keyboard():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="💬 Отзывы"))
    b.row(KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="📦 Мои аккаунты"))
    b.row(KeyboardButton(text="❓ Частые вопросы"), KeyboardButton(text="📢 Наш Канал"))
    b.row(KeyboardButton(text="👤 Профиль"), KeyboardButton(text="👥 Рефералы"))
    b.row(KeyboardButton(text="🎟 Промокод"))
    return b.as_markup(resize_keyboard=True)

def get_admin_reply_keyboard():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📋 Все заказы"))
    b.row(KeyboardButton(text="⏳ Ожидают оплаты"), KeyboardButton(text="✅ Выполненные"))
    b.row(KeyboardButton(text="📦 Склад"), KeyboardButton(text="💰 Реквизиты"))
    b.row(KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="👤 Пользователи"))
    b.row(KeyboardButton(text="📈 Панель управления"), KeyboardButton(text="🏠 Главное меню"))
    b.row(KeyboardButton(text="🎟 Промокоды"), KeyboardButton(text="⭐ Уровни"))
    b.row(KeyboardButton(text="👥 Рефералы"), KeyboardButton(text="📊 Аналитика"))
    b.row(KeyboardButton(text="🔗 Источники"), KeyboardButton(text="💾 Бэкапы"))
    return b.as_markup(resize_keyboard=True)

def subscribe_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Подписаться", url="http://t.me/owerpass_store", style="primary")
    ibtn(kb, "Я подписался", callback_data="check_sub", icon_key="check", style="success")
    kb.adjust(1)
    return kb.as_markup()

def main_menu_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Каталог", callback_data="menu_catalog", icon_key="cart", style="primary")
    ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
    ibtn(kb, "Мои аккаунты", callback_data="my_accounts", icon_key="box")
    ibtn(kb, "Отзывы", callback_data="menu_reviews", icon_key="star")
    ibtn(kb, "Профиль", callback_data="profile_menu", icon_key="user")
    ibtn(kb, "Рефералы", callback_data="referral_menu", icon_key="gift")
    ibtn(kb, "Промокод", callback_data="promo_menu")
    ibtn(kb, "Наш Канал", url="http://t.me/owerpass_store", style="primary")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup()

def catalog_keyboard():
    kb = InlineKeyboardBuilder()
    for k, v in CATEGORIES.items():
        ibtn(kb, v["name"], callback_data=f"cat_{k}", icon_key="cart")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def category_products_keyboard(category):
    kb = InlineKeyboardBuilder()
    counts = stock_count()
    for product_name, price_data in CATEGORIES[category]["products"].items():
        code = price_data.get("code", "")
        in_stock = counts.get(code, 0) if category not in ("stars", "tiktok", "discord") else 999
        
        if in_stock > 0:
            display = f"{product_name} — {in_stock} шт. | {price_data['uah']}₴"
            cb = f"product_{category}_{code}"
            ibtn(kb, display, callback_data=cb, icon_key="fire" if "stars" in category else None)
        else:
            display = f"❌ {product_name} — НЕТ"
            ibtn(kb, display, callback_data="out_of_stock", style="danger")
    ibtn(kb, "В каталог", callback_data="menu_catalog", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def quantity_keyboard():
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text=f"{i} шт.", callback_data=f"qty_{i}")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(5, 1)
    return kb.as_markup()

def confirm_order_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Подтвердить", callback_data="confirm_order", icon_key="check", style="success")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def awaiting_payment_keyboard(order_id):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Написать продавцу", url="https://t.me/MaskYoY", style="primary")
    ibtn(kb, "Написать в боте", callback_data=f"support_{order_id}", icon_key="warn")
    ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
    kb.adjust(1)
    return kb.as_markup()

def user_order_actions_keyboard(order_id):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Запросить код", callback_data=f"request_code_{order_id}", icon_key="time", style="primary")
    ibtn(kb, "Оставить отзыв", callback_data=f"leave_review_{order_id}", icon_key="star", style="success")
    ibtn(kb, "Запросить замену", callback_data=f"user_replace_{order_id}")
    ibtn(kb, "Запросить возврат", callback_data=f"user_refund_{order_id}", style="danger")
    ibtn(kb, "Все заказы", callback_data="my_orders", icon_key="cart")
    kb.adjust(1)
    return kb.as_markup()

def reviews_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Посмотреть отзывы", url="https://t.me/owerpass_repa", icon_key="star", style="primary")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def stars_keyboard():
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        ibtn(kb, f"{i} ⭐", callback_data=f"stars_{i}", icon_key="star")
    kb.adjust(5)
    return kb.as_markup()

def review_photo_skip_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Пропустить фото", callback_data="skip_photo", icon_key="check", style="primary")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def moderation_keyboard(review_id):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Одобрить", callback_data=f"approve_{review_id}", icon_key="check", style="success")
    ibtn(kb, "Отклонить", callback_data=f"reject_{review_id}", icon_key="warn", style="danger")
    kb.adjust(2)
    return kb.as_markup()

def profile_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Мои аккаунты", callback_data="my_accounts", icon_key="box")
    ibtn(kb, "Рефералы", callback_data="referral_menu", icon_key="gift")
    ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
    ibtn(kb, "Главное меню", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def referral_menu_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Моя статистика", callback_data="referral_stats", icon_key="star")
    ibtn(kb, "Назад", callback_data="profile_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def requisites_edit_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Изменить гривны", callback_data="edit_req_uah", icon_key="money")
    ibtn(kb, "Изменить подарок", callback_data="edit_req_gift", icon_key="gift")
    kb.adjust(1)
    return kb.as_markup()

def admin_stock_menu_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Загрузить .session", callback_data="admin_upload_session", icon_key="box", style="primary")
    ibtn(kb, "Все аккаунты", callback_data="admin_list_accounts", icon_key="cart")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def admin_order_card_keyboard(order_id, status, user_id):
    kb = InlineKeyboardBuilder()
    if status == "awaiting_payment":
        ibtn(kb, "Подтвердить оплату и выдать", callback_data=f"admin_confirm_payment_{order_id}", icon_key="check", style="success")
    elif status == "completed":
        ibtn(kb, "Возврат", callback_data=f"admin_refund_{order_id}", icon_key="money", style="danger")
    ibtn(kb, "Написать покупателю", callback_data=f"admin_chat_with_user_{order_id}", icon_key="user")
    ibtn(kb, "Отменить", callback_data=f"admin_reject_{order_id}", icon_key="warn", style="danger")
    ibtn(kb, "Назад", callback_data="admin_back_to_list", icon_key="warn", style="danger")
    ibtn(kb, "Обновить", callback_data=f"admin_order_detail_{order_id}", icon_key="time")
    kb.adjust(1)
    return kb.as_markup()

def admin_all_orders_keyboard(page=0, per_page=5, status_filter=None):
    kb = InlineKeyboardBuilder()
    orders = load_orders()
    filtered = {k: v for k, v in orders.items() if (not status_filter or v["status"] == status_filter)}
    order_list = sorted(filtered.items(), reverse=True)
    total_pages = (len(order_list) + per_page - 1) // per_page

    if total_pages == 0:
        ibtn(kb, "Обновить", callback_data="admin_page_0", icon_key="time")
        kb.adjust(1)
        return kb.as_markup()

    start = page * per_page
    end = start + per_page
    for oid, order in order_list[start:end]:
        emoji, _ = STATUS_CONFIG.get(order["status"], ("❓", ""))
        symbol = method_symbol(order.get("payment_method", "uah"))
        short_id = order.get("short_id", oid[:8])
        total = order["total"] if isinstance(order["total"], str) else f"{order['total']}{symbol}"
        ibtn(kb, f"{short_id} | {order['product'][:15]} | {total}", callback_data=f"admin_order_detail_{oid}")

    if total_pages > 1:
        if page > 0: kb.button(text="⬅️", callback_data=f"admin_page_{page - 1}")
        if page < total_pages - 1: kb.button(text="➡️", callback_data=f"admin_page_{page + 1}")

    ibtn(kb, "Обновить", callback_data=f"admin_page_{page}", icon_key="time")
    kb.adjust(1)
    return kb.as_markup()

def admin_dashboard_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Заказы", callback_data="admin_orders_dashboard", icon_key="cart")
    ibtn(kb, "Склад", callback_data="admin_stock_menu", icon_key="box")
    ibtn(kb, "Рефералы", callback_data="admin_referrals_dashboard", icon_key="gift")
    ibtn(kb, "Промокоды", callback_data="admin_promo_dashboard")
    ibtn(kb, "Уровни", callback_data="admin_levels_dashboard", icon_key="star")
    ibtn(kb, "Аналитика", callback_data="admin_analytics_dashboard")
    ibtn(kb, "Источники", callback_data="admin_traffic_dashboard")
    ibtn(kb, "Бэкапы", callback_data="admin_backups", icon_key="money")
    ibtn(kb, "Обновить", callback_data="admin_dashboard_refresh", icon_key="time")
    kb.adjust(2, 2, 2, 2, 1)
    return kb.as_markup()

def admin_promo_codes_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Создать промокод", callback_data="admin_create_promo_code", icon_key="gift", style="primary")
    promo_codes = load_promo_codes()
    earnings = load_promo_earnings()
    for code, data in list(promo_codes.items())[:10]:
        status = "🟢" if data.get("is_active", True) else "🔴"
        uses = f"{data.get('current_uses', 0)}/{data.get('max_uses') or '∞'}"
        owner = data.get("owner_username", "Нет")
        earned = earnings.get(code, {}).get("total_earned", 0)
        ibtn(kb, f"{status} {code} ({uses}) 💰{earned:.0f}₴", callback_data=f"admin_promo_code_detail_{code}", icon_key="money")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def admin_levels_keyboard():
    kb = InlineKeyboardBuilder()
    for k, name, e in [("bronze", "Бронза", "🥉"), ("silver", "Серебро", "🥈"), ("gold", "Золото", "🥇"), ("platinum", "Платина", "💎"), ("vip", "VIP", "👑")]:
        ibtn(kb, name, callback_data=f"admin_edit_level_{k}", icon_key="star")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def admin_referrals_settings_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Изменить бонус %", callback_data="admin_edit_referral_bonus", icon_key="money")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

def admin_analytics_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "По дням", callback_data="admin_analytics_by_days", icon_key="time")
    ibtn(kb, "По часам", callback_data="admin_analytics_by_hours", icon_key="time")
    ibtn(kb, "По странам", callback_data="admin_analytics_by_country", icon_key="user")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1)
    return kb.as_markup()

# ==================== ТЕКСТЫ ====================
FAQ_TEXT = f"""
{pe('warn')} <b>КАК КУПИТЬ АККАУНТ?</b>

1️⃣ Выберите категорию и страну
2️⃣ Выберите способ оплаты
3️⃣ Напишите админу @MaskYoY и оплатите
4️⃣ После подтверждения — аккаунт выдастся автоматически

📱 <b>Как войти:</b>
1. Получите .session
2. Войдите в Telegram
3. Нажмите «🔑 Запросить код»
4. Бот автоматически перешлёт код

📞 @MaskYoY
📢 @owerpass_store
"""

# ==================== СТАРТ ====================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    ref_code = None
    if message.text and len(message.text.split()) > 1:
        ref_code = message.text.split()[1]

    is_new = await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name, ref_code=ref_code)

    if message.from_user.id == ADMIN_ID:
        await message.answer(f"{pe('warn')} <b>Админ-панель</b>", reply_markup=get_admin_reply_keyboard())
        return

    if not await check_subscription(message.from_user.id):
        await message.answer(f"{pe('warn')} Подпишитесь на канал!", reply_markup=subscribe_keyboard())
        return

    text = f"{pe('star')} <b>Добро пожаловать в OverPass Store!</b>\n"
    text += "🔹 Продажа номеров Telegram\n"
    text += "🔹 Автоматическая выдача\n"
    if is_new and ref_code and ref_code.startswith("ref_"):
        text += f"{pe('gift')} Вы зарегистрированы по реферальной ссылке!\n"
    text += "Выберите раздел:"
    await message.answer(text, reply_markup=get_main_reply_keyboard())

@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: types.CallbackQuery):
    await callback.answer()
    if await check_subscription(callback.from_user.id):
        try: await callback.message.edit_text(f"{pe('check')} Спасибо!", reply_markup=main_menu_keyboard())
        except: await callback.message.answer(f"{pe('check')} Спасибо!", reply_markup=main_menu_keyboard())
        await callback.message.answer("Навигация:", reply_markup=get_main_reply_keyboard())
    else:
        await callback.answer("❌ Не подписались!", show_alert=True)

# ==================== АДМИН: СКЛАД ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📦 Склад")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_stock_menu")
async def admin_stock_menu(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        msg = event.message
        edit = True
    else:
        msg = event
        edit = False

    counts = stock_count()
    text = f"{pe('box')} <b>СКЛАД</b>\n\n"
    if counts:
        total = sum(counts.values())
        text += f"<b>Всего:</b> {total}\n\n"
        for c, n in sorted(counts.items(), key=lambda x: -x[1]):
            if n > 0: text += f"• {c.upper()}: <b>{n}</b>\n"
    else:
        text += "<i>Пусто</i>\n"

    kb = admin_stock_menu_keyboard()
    if edit:
        try: await msg.edit_text(text, reply_markup=kb)
        except: await msg.answer(text, reply_markup=kb)
    else:
        await msg.answer(text, reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_upload_session")
async def admin_upload_session_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(f"📁 Отправьте файл <code>.session</code>.\n\nБот сам определит страну и проверит 2FA.")
    await state.set_state(AdminStockStates.waiting_for_session)

@dp.message(AdminStockStates.waiting_for_session, F.document)
async def admin_receive_session(message: types.Message, state: FSMContext):
    doc = message.document
    if not doc.file_name.endswith(".session"):
        await message.answer("❌ Нужен .session")
        return

    temp_path = os.path.join(TEMP_DIR, doc.file_name)
    await bot.download(doc, temp_path)

    status_msg = await message.answer(f"{pe('time')} Анализирую сессию...")
    info = await analyze_session(temp_path)

    if not info.get("valid"):
        await status_msg.edit_text(f"❌ <b>Сессия невалидна</b>\n\nПричина: <code>{info.get('error', 'unknown')}</code>")
        try: os.remove(temp_path)
        except: pass
        await state.clear()
        return

    phone = info["phone"]
    country_code, country_name = detect_country(phone)

    if info.get("has_2fa"):
        hint = info.get("password_hint") or "—"
        await status_msg.edit_text(f"⚠️ <b>АККАУНТ С ПАРОЛЕМ!</b>\n\n🌍 {country_name}\n📱 <code>{phone}</code>\n🔐 Хинт: <code>{hint}</code>\n\n<b>НЕ добавлен на склад.</b>")
        try: await bot.send_message(ADMIN_ID, f"⚠️ <b>АККАУНТ С ПАРОЛЕМ — НЕ ДОБАВЛЕН!</b>\n\n🌍 {country_name}\n📱 <code>{phone}</code>\n🔐 Хинт: <code>{hint}</code>\n\nФайл: <code>{doc.file_name}</code>")
        except: pass
        try: os.remove(temp_path)
        except: pass
        await state.clear()
        return

    if country_code not in DEFAULT_PRICES:
        await status_msg.edit_text(f"⚠️ <b>Страна без цены</b>\n\n🌍 {country_name}\n📱 <code>{phone}</code>\n🆔 <code>{country_code}</code>")
        try: os.remove(temp_path)
        except: pass
        await state.clear()
        return

    price_uah, price_stars = DEFAULT_PRICES[country_code]
    name = doc.file_name.replace(".session", "")

    try:
        os.makedirs(country_dir(country_code), exist_ok=True)
        shutil.copy(temp_path, session_path(country_code, name))
        shutil.copy(temp_path, watcher_path(country_code, name))

        meta = {
            "country": country_code, "session_name": name, "phone": phone,
            "user_id": info["user_id"], "first_name": info.get("first_name"),
            "username": info.get("username"), "premium": info.get("premium", False),
            "has_2fa": False, "password": None, "price_uah": price_uah, "price_stars": price_stars,
            "status": "available", "added_at": datetime.now().isoformat(), "sold_at": None, "sold_to": None,
        }
        save_meta(country_code, name, meta)

        try: os.remove(temp_path)
        except: pass

        await status_msg.edit_text(f"{pe('check')} <b>Аккаунт добавлен!</b>\n\n🌍 {country_name}\n📱 <code>{phone}</code>\n👤 {info.get('first_name', '—')}\n⭐ Premium: {'Да' if info.get('premium') else 'Нет'}\n🔐 2FA: Нет\n\n💰 {price_uah}₴")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")

    await state.clear()

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_list_accounts")
async def admin_list_accounts(callback: types.CallbackQuery):
    await callback.answer()
    avail = all_available()
    text = f"📋 <b>ВСЕ АККАУНТЫ ({len(avail)})</b>\n\n"
    for acc in avail[:30]:
        pwd = " 🔐" if acc.get("password") else ""
        text += f"• {acc['country'].upper()} | {acc['phone']} | {acc['price_uah']}₴{pwd}\n"
    if len(avail) > 30: text += f"\n...и ещё {len(avail) - 30}"
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Назад", callback_data="admin_stock_menu", icon_key="warn", style="danger")
    await callback.message.edit_text(text, reply_markup=kb.as_markup())

# ==================== АДМИН: БЭКАПЫ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "💾 Бэкапы")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_backups")
async def admin_backups(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        target = event.message
        edit = True
    else:
        target = event
        edit = False

    text = (f"💾 <b>БЭКАПЫ</b>\n\nRailway стирает файлы при перезапуске.\n\n"
            f"<b>Что делать:</b>\n1. Нажми «📥 Скачать все бэкапы»\n"
            f"2. Скопируй содержимое .b64 файлов\n3. Вставь в Railway → Variables\n"
            f"4. Redeploy — данные восстановятся.\n\n"
            f"<i>Файлы .b64 создаются автоматически после каждого изменения.</i>")

    kb = InlineKeyboardBuilder()
    ibtn(kb, "Скачать все бэкапы", callback_data="admin_download_backups", icon_key="money")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1)

    if edit:
        try: await target.edit_text(text, reply_markup=kb.as_markup())
        except: await target.answer(text, reply_markup=kb.as_markup())
    else:
        await target.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_download_backups")
async def admin_download_backups(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("📥 Собираю бэкапы...")

    all_data = {}
    for name in BACKUP_FILES:
        path = f"{name}.json"
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                all_data[name] = json.load(f)

    combined = json.dumps(all_data, ensure_ascii=False, indent=2)
    b64_all = base64.b64encode(combined.encode("utf-8")).decode("ascii")

    backup_file = "backup_all.b64"
    with open(backup_file, "w", encoding="utf-8") as f:
        f.write(b64_all)

    await callback.message.answer_document(FSInputFile(backup_file), caption=f"💾 <b>BACKUP_ALL_B64</b>\n\nСкопируй в Railway → Variables → BACKUP_ALL_B64")

    for name, data in all_data.items():
        try:
            b64 = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii")
            with open(f"backup_{name}.b64", "w", encoding="utf-8") as f:
                f.write(b64)
        except: pass

# ==================== АДМИН: ПРОМОКОДЫ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "🎟 Промокоды")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_promo_dashboard")
async def admin_promo_menu(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        target = event.message
        edit = True
    else:
        target = event
        edit = False

    text = "🎟 <b>УПРАВЛЕНИЕ ПРОМОКОДАМИ</b>\n\nВыбери промокод или создай новый:"
    kb = admin_promo_codes_keyboard()

    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: await target.answer(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_create_promo_code")
async def admin_start_create_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("🎟 <b>Создание промокода</b>\n\nВведи код (например, <code>SALE2026</code>):")
    await state.set_state(AdminPromoStates.waiting_for_promo_code)

@dp.message(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_promo_code, F.text)
async def admin_promo_code_input(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    promo_codes = load_promo_codes()
    if code in promo_codes:
        await message.answer("❌ Такой промокод уже есть. Введи другой:")
        return
    await state.update_data(promo_code=code)

    kb = InlineKeyboardBuilder()
    ibtn(kb, "Процентная скидка", callback_data="promo_type_percent", style="primary")
    ibtn(kb, "Фиксированная скидка", callback_data="promo_type_fixed", icon_key="money", style="primary")
    kb.adjust(1)

    await message.answer(f"Код: <code>{code}</code>\n\nВыбери тип скидки:", reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_discount_type)

@dp.callback_query(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_discount_type, F.data.startswith("promo_type_"))
async def admin_promo_type(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    discount_type = "percent" if callback.data == "promo_type_percent" else "fixed"
    await state.update_data(discount_type=discount_type)
    label = "процент (например, 10)" if discount_type == "percent" else "сумму в грн (например, 50)"
    await callback.message.edit_text(f"Введи {label}:")
    await state.set_state(AdminPromoStates.waiting_for_discount_value)

@dp.message(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_discount_value, F.text)
async def admin_promo_discount_value(message: types.Message, state: FSMContext):
    try:
        value = float(message.text)
        if value <= 0: raise ValueError
    except:
        await message.answer("❌ Введи положительное число")
        return
    await state.update_data(discount_value=value)

    kb = InlineKeyboardBuilder()
    ibtn(kb, "Без ограничений", callback_data="promo_unlimited")
    for n in [1, 10, 50, 100, 500]:
        kb.button(text=f"{n} использ.", callback_data=f"promo_max_{n}")
    kb.adjust(1)

    await message.answer("Сколько раз можно использовать промокод?", reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_max_uses)

@dp.callback_query(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_max_uses, F.data.startswith("promo_"))
async def admin_promo_max_uses(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    max_uses = None if callback.data == "promo_unlimited" else int(callback.data.split("_")[-1])
    await state.update_data(max_uses=max_uses)

    kb = InlineKeyboardBuilder()
    for days in [1, 7, 30, 90]:
        kb.button(text=f"{days} дней", callback_data=f"promo_expire_{days}")
    ibtn(kb, "Навсегда", callback_data="promo_expire_0", icon_key="check")
    kb.adjust(2)

    await callback.message.edit_text("Срок действия:", reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_expires_date)

@dp.callback_query(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_expires_date, F.data.startswith("promo_expire_"))
async def admin_promo_expires(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    days = int(callback.data.split("_")[-1])
    expires_at = (datetime.now() + timedelta(days=days)).isoformat() if days > 0 else None
    await state.update_data(expires_at=expires_at)
    await callback.message.edit_text("Введите username владельца промокода (без @):")
    await state.set_state(AdminPromoStates.waiting_for_owner_username)

@dp.message(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_owner_username, F.text)
async def admin_promo_owner_username(message: types.Message, state: FSMContext):
    username = message.text.strip().lstrip("@")
    data = await state.get_data()

    promo_codes = load_promo_codes()
    promo_codes[data["promo_code"]] = {
        "code": data["promo_code"], "discount_type": data["discount_type"],
        "discount_value": data["discount_value"], "max_uses": data["max_uses"],
        "current_uses": 0, "expires_at": data.get("expires_at"),
        "is_active": True, "created_at": datetime.now().isoformat(),
        "owner_username": username, "total_earned": 0.0
    }
    save_promo_codes(promo_codes)

    discount_desc = (f"{data['discount_value']}%" if data["discount_type"] == "percent" else f"{data['discount_value']} грн")
    text = (f"{pe('check')} <b>Промокод создан!</b>\n\n"
            f"🎟 Код: <code>{data['promo_code']}</code>\n"
            f"💰 Скидка: {discount_desc}\n"
            f"👤 Владелец: @{username}\n"
            f"🔢 Использований: {data['max_uses'] or '♾'}\n")
    if data.get("expires_at"): text += f"📅 До: {datetime.fromisoformat(data['expires_at']).strftime('%d.%m.%Y')}\n"
    else: text += f"📅 Действует: навсегда\n"

    await message.answer(text, reply_markup=admin_promo_codes_keyboard())
    await state.clear()

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_promo_code_detail_"))
async def admin_promo_code_detail(callback: types.CallbackQuery):
    await callback.answer()
    code = callback.data.replace("admin_promo_code_detail_", "")
    promo_codes = load_promo_codes()
    promo = promo_codes.get(code)
    if not promo:
        await callback.answer("❌ Не найден", show_alert=True)
        return

    status = "🟢 Активен" if promo.get("is_active", True) else "🔴 Выключен"
    discount_desc = (f"{promo['discount_value']}%" if promo["discount_type"] == "percent" else f"{promo['discount_value']} грн")
    uses_text = f"{promo.get('current_uses', 0)}/{promo.get('max_uses') or '∞'}"
    owner = promo.get("owner_username", "Не указан")
    earned = promo.get("total_earned", 0)

    text = (f"🎟 <b>Промокод {code}</b>\n\n"
            f"💰 Скидка: {discount_desc}\n"
            f"👤 Владелец: @{owner}\n"
            f"📌 Статус: {status}\n"
            f"🔢 Использовано: {uses_text}\n"
            f"{pe('money')} Заработано: <b>{earned:.2f} ₴</b>\n")
    if promo.get("expires_at"): text += f"📅 До: {datetime.fromisoformat(promo['expires_at']).strftime('%d.%m.%Y')}\n"
    else: text += f"📅 Действует: навсегда\n"

    kb = InlineKeyboardBuilder()
    if promo.get("is_active", True):
        ibtn(kb, "Выключить", callback_data=f"admin_deactivate_promo_{code}", icon_key="warn", style="danger")
    else:
        ibtn(kb, "Включить", callback_data=f"admin_activate_promo_{code}", icon_key="check", style="success")
    ibtn(kb, "Удалить", callback_data=f"admin_delete_promo_{code}", style="danger")
    ibtn(kb, "Назад", callback_data="admin_promo_dashboard", style="danger")
    kb.adjust(1)

    try: await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except: await callback.message.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_deactivate_promo_"))
async def admin_deactivate_promo(callback: types.CallbackQuery):
    await callback.answer()
    code = callback.data.replace("admin_deactivate_promo_", "")
    promo_codes = load_promo_codes()
    if code in promo_codes:
        promo_codes[code]["is_active"] = False
        save_promo_codes(promo_codes)
    await callback.answer("✅ Выключен", show_alert=True)
    await admin_promo_menu(callback)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_activate_promo_"))
async def admin_activate_promo(callback: types.CallbackQuery):
    await callback.answer()
    code = callback.data.replace("admin_activate_promo_", "")
    promo_codes = load_promo_codes()
    if code in promo_codes:
        promo_codes[code]["is_active"] = True
        save_promo_codes(promo_codes)
    await callback.answer("✅ Включен", show_alert=True)
    await admin_promo_menu(callback)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_delete_promo_"))
async def admin_delete_promo(callback: types.CallbackQuery):
    await callback.answer()
    code = callback.data.replace("admin_delete_promo_", "")
    promo_codes = load_promo_codes()
    if code in promo_codes:
        del promo_codes[code]
        save_promo_codes(promo_codes)
    await callback.answer("🗑 Удалён", show_alert=True)
    await admin_promo_menu(callback)

# ==================== АДМИН: РАССЫЛКА ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📢 Рассылка")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    users = load_users()
    if not users: return await message.answer("❌ Нет пользователей")
    await message.answer(f"📢 <b>РАССЫЛКА</b>\n\n👥 Получателей: <b>{len(users)}</b>\n\nОтправь мне сообщение для рассылки.\nМожно отправить: <b>текст, фото, видео, документ, стикер</b>.\n\nДля отмены: /cancel")
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ Отменено", reply_markup=get_admin_reply_keyboard())
        await state.clear()
        return

    users = load_users()
    total = len(users)
    success, failed, blocked = 0, 0, 0
    status_msg = await message.answer(f"⏳ <b>Рассылка запущена...</b>\n\n👥 Всего: {total}\n📤 Отправлено: 0\n❌ Ошибок: 0")
    last_update = 0

    for i, uid in enumerate(users.keys(), 1):
        try:
            await bot.copy_message(chat_id=int(uid), from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "kicked" in err or "chat not found" in err: blocked += 1
            else: failed += 1
        await asyncio.sleep(0.05)

        if i - last_update >= 20:
            last_update = i
            try: await status_msg.edit_text(f"⏳ <b>Рассылка идёт...</b>\n\n👥 Всего: {total}\n📊 Прогресс: {i}/{total} ({int(i/total*100)}%)\n📤 Доставлено: {success}\n🚫 Заблокировали: {blocked}\n❌ Ошибок: {failed}")
            except: pass

    await status_msg.edit_text(f"✅ <b>РАССЫЛКА ЗАВЕРШЕНА!</b>\n\n👥 Всего: {total}\n📤 Доставлено: <b>{success}</b>\n🚫 Заблокировали бота: <b>{blocked}</b>\n❌ Ошибок: <b>{failed}</b>", reply_markup=get_admin_reply_keyboard())
    await state.clear()

@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    if await state.get_state() is None: return
    await state.clear()
    kb = get_admin_reply_keyboard() if message.from_user.id == ADMIN_ID else get_main_reply_keyboard()
    await message.answer("❌ Отменено", reply_markup=kb)

# ==================== АДМИН: СТАТИСТИКА ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📊 Статистика")
async def admin_statistics(message: types.Message):
    orders = load_orders()
    users = load_users()
    status_counts = {}
    rev_uah = 0
    for order in orders.values():
        s = order["status"]
        status_counts[s] = status_counts.get(s, 0) + 1
        if s == "completed" and not isinstance(order.get("total", 0), str): rev_uah += order.get("total", 0)
    counts = stock_count()
    text = (f"📊 СТАТИСТИКА\n👤 Юзеров: {len(users)}\n📦 Заказов: {len(orders)}\n✅ Выполнено: {status_counts.get('completed', 0)}\n⏳ Ожидают: {status_counts.get('awaiting_payment', 0)}\n💰 UAH: {rev_uah}\n📦 Склад: {sum(counts.values())}")
    await message.answer(text, reply_markup=get_admin_reply_keyboard())

@dp.message(F.from_user.id == ADMIN_ID, F.text == "📋 Все заказы")
async def admin_all_orders(message: types.Message): await show_admin_orders_page(message, 0)
@dp.message(F.from_user.id == ADMIN_ID, F.text == "⏳ Ожидают оплаты")
async def admin_pending_orders(message: types.Message): await show_admin_orders_page(message, 0, "awaiting_payment")
@dp.message(F.from_user.id == ADMIN_ID, F.text == "✅ Выполненные")
async def admin_completed_orders(message: types.Message): await show_admin_orders_page(message, 0, "completed")

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_page_"))
async def admin_page_nav(callback: types.CallbackQuery):
    await callback.answer()
    page = int(callback.data.replace("admin_page_", ""))
    await show_admin_orders_page(callback.message, page, edit=True)

async def show_admin_orders_page(target, page, status_filter=None, edit=False):
    orders = load_orders()
    filtered = {k: v for k, v in orders.items() if (not status_filter or v["status"] == status_filter)}
    order_list = sorted(filtered.items(), reverse=True)
    per_page = 5
    if not order_list:
        kb = admin_all_orders_keyboard(0, per_page, status_filter)
        if edit: await target.edit_text("📋 Нет заказов", reply_markup=kb)
        else: await target.answer("📋 Нет заказов", reply_markup=get_admin_reply_keyboard())
        return

    total_pages = (len(order_list) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    text = f"📋 ЗАКАЗЫ ({page + 1}/{total_pages})\n"
    for oid, order in order_list[page * per_page:(page + 1) * per_page]:
        e, _ = STATUS_CONFIG.get(order["status"], ("❓", ""))
        s = method_symbol(order.get("payment_method", "uah"))
        short = order.get("short_id", oid[:8])
        created = datetime.fromisoformat(order["created_at"]).strftime("%d.%m %H:%M")
        text += f"{e} {short} | {order['product'][:20]}\n  @{order.get('username', '—')} | {order['total']}{s} | {created}\n"

    kb = admin_all_orders_keyboard(page, per_page, status_filter)
    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: pass
    else: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_order_detail_"))
async def admin_order_detail(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("admin_order_detail_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if not rk: return await callback.answer("❌ Не найден", show_alert=True)
    order = orders[rk]
    e, st = STATUS_CONFIG.get(order["status"], ("❓", ""))
    s = method_symbol(order.get("payment_method", "uah"))
    short = order.get("short_id", rk[:8])
    total = order["total"] if isinstance(order["total"], str) else f"{order['total']} {s}"

    text = (f"📦 <b>Заказ {short}</b>\n👤 @{order.get('username', '—')}\n🆔 <code>{order['user_id']}</code>\n📅 {datetime.fromisoformat(order['created_at']).strftime('%d.%m.%Y %H:%M')}\n🌍 {order['product']}\n💰 {total}\n📌 {e} {st}\n")
    if order.get("phone"): text += f"📱 {order['phone']}\n"
    if order.get("used_promo_code"): text += f"🎟 Промокод: <code>{order['used_promo_code']}</code>\n"

    try: await callback.message.edit_text(text, reply_markup=admin_order_card_keyboard(rk, order["status"], order["user_id"]))
    except: await callback.message.answer(text, reply_markup=admin_order_card_keyboard(rk, order["status"], order["user_id"]))

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_back_to_list")
async def admin_back_to_list(callback: types.CallbackQuery):
    await callback.answer()
    await show_admin_orders_page(callback.message, 0, edit=True)

@dp.message(F.from_user.id == ADMIN_ID, F.text == "💰 Реквизиты")
async def admin_requisites(message: types.Message):
    req = load_requisites()
    text = f"💰 РЕКВИЗИТЫ:\n💳 Гривны:\n{req.get('uah', '—')}\n🎁 Подарок:\n{req.get('gift', '—')}\n"
    await message.answer(text, reply_markup=requisites_edit_keyboard())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("edit_req_"))
async def edit_requisite_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    method = callback.data.replace("edit_req_", "")
    labels = {"uah": "Гривны", "gift": "Подарок"}
    await state.update_data(edit_req_method=method)
    await callback.message.answer(f"✏️ Введите новые реквизиты для {labels.get(method, method)}:")
    await state.set_state(AdminStates.waiting_for_requisites_edit)

@dp.message(AdminStates.waiting_for_requisites_edit, F.text)
async def save_requisite(message: types.Message, state: FSMContext):
    data = await state.get_data()
    method = data["edit_req_method"]
    req = load_requisites()
    req[method] = message.text
    save_requisites(req)
    await message.answer(f"✅ Обновлено!", reply_markup=get_admin_reply_keyboard())
    await state.clear()

# ==================== АДМИН: УПРАВЛЕНИЕ ЗАКАЗАМИ ====================
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_confirm_payment_"))
async def admin_confirm_payment(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("admin_confirm_payment_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if not rk: return
    order = orders[rk]
    order["status"] = "paid"
    order["paid_at"] = datetime.now().isoformat()
    save_orders(orders)

    await callback.message.edit_text(f"{pe('check')} Оплата подтверждена. Выдаю аккаунт...")
    await deliver_to_user(order, rk)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_reject_"))
async def admin_reject_order(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("admin_reject_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if not rk: return
    order = orders[rk]
    order["status"] = "rejected"
    save_orders(orders)
    if order.get("country_code") and order.get("session_name"):
        release_account(order["country_code"], order["session_name"])
    try: await bot.send_message(order["user_id"], f"❌ Заказ {order.get('short_id', rk)} отклонён")
    except: pass
    try:
        await callback.message.edit_text(callback.message.text + f"\n❌ <b>ОТКЛОНЁН</b>", reply_markup=admin_order_card_keyboard(rk, "rejected", order["user_id"]))
    except: pass

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_refund_"))
async def admin_refund(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("admin_refund_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if not rk: return
    order = orders[rk]
    order["status"] = "refunded"
    save_orders(orders)
    try: await bot.send_message(order["user_id"], f"💰 Возврат по {order.get('short_id', rk)}.")
    except: pass
    await callback.message.edit_text(callback.message.text + "\n💰 <b>ВОЗВРАТ</b>", reply_markup=admin_order_card_keyboard(rk, "refunded", order["user_id"]))

async def deliver_to_user(order: dict, order_key: str):
    country_code = order["country_code"]
    session_name = order["session_name"]
    phone = order["phone"]
    user_id = order["user_id"]

    sess_file = session_path(country_code, session_name)
    if not os.path.exists(sess_file):
        try: await bot.send_message(user_id, "❌ Файл не найден. @MaskYoY")
        except: pass
        return

    meta = load_meta(country_code, session_name)
    pwd_text = ""
    if meta and meta.get("password"): pwd_text = f"\n🔐 <b>Пароль:</b> <code>{meta['password']}</code>\n"

    _, country_name = detect_country(phone)

    try:
        await bot.send_document(
            chat_id=user_id,
            document=FSInputFile(sess_file, filename=f"{country_code}_{phone}.session"),
            caption=(
                f"🎉 <b>ВАШ АККАУНТ</b>\n\n"
                f"🌍 Страна: {country_name}\n"
                f"📱 Ваш номер: <code>{phone}</code>\n"
                f"{pwd_text}\n"
                f"<b>Как войти:</b>\n"
                f"1. Войдите в новый аккаунт Telegram\n"
                f"2. Используйте номер выше для входа\n"
                f"3. Нажмите кнопку и получите код\n\n"
                f"<b>Код придёт сюда автоматически!</b>"
            ),
            reply_markup=user_order_actions_keyboard(order_key)
        )
        mark_sold(country_code, session_name, user_id)
        order["status"] = "completed"
        order["completed_at"] = datetime.now().isoformat()
        all_orders = load_orders()
        all_orders[order_key] = order
        save_orders(all_orders)

        users = load_users()
        ukey = str(user_id)
        if ukey in users:
            users[ukey]["total_spent"] = users[ukey].get("total_spent", 0) + (order.get("total", 0) if not isinstance(order.get("total", 0), str) else 0)
            users[ukey]["orders_count"] = users[ukey].get("orders_count", 0) + 1
            save_users(users)

        used_promo = order.get("used_promo_code")
        if used_promo: await process_partner_commission(used_promo, order["total"], order_key)

        asyncio.create_task(start_code_watcher(country_code, session_name, user_id, order_key))

        try: await bot.send_message(ADMIN_ID, f"📦 <b>АККАУНТ ВЫДАН</b>\n\n👤 User: <code>{user_id}</code>\n🌍 {country_code.upper()} | 📱 {phone}\n🆔 {order_key}")
        except: pass
    except Exception as e:
        logger.error(f"Deliver error: {e}")

async def process_partner_commission(promo_code, order_total, order_key):
    try: order_total = float(order_total)
    except: return

    promo_codes = load_promo_codes()
    promo = promo_codes.get(promo_code)
    if not promo: return

    owner_username = promo.get("owner_username")
    if not owner_username: return

    users = load_users()
    owner_id = None
    for uid, udata in users.items():
        if udata.get("username") == owner_username:
            owner_id = int(uid)
            break
    if not owner_id: owner_id = promo.get("owner_id")
    if not owner_id: return

    commission_percent = get_setting("partner_commission_percent", 20.0)
    commission_amount = round(order_total * (commission_percent / 100), 2)
    if commission_amount <= 0: return

    promo["current_uses"] = promo.get("current_uses", 0) + 1
    promo["total_earned"] = promo.get("total_earned", 0) + commission_amount
    save_promo_codes(promo_codes)

    referrals = load_referrals()
    owner_key = str(owner_id)
    if owner_key not in referrals:
        referrals[owner_key] = {"user_id": owner_id, "referral_code": "", "referrals_list": [], "total_earned": 0.0}
    referrals[owner_key]["total_earned"] = referrals[owner_key].get("total_earned", 0) + commission_amount
    save_referrals(referrals)

    try:
        notification_text = (f"💰 <b>НОВАЯ ВЫПЛАТА ПАРТНЕРУ!</b>\n\n👤 Партнер: @{owner_username}\n🆔 Заказ: <code>{order_key}</code>\n💵 Сумма заказа: {order_total:.2f} грн\n📈 Комиссия ({commission_percent}%): <b>{commission_amount:.2f} грн</b>\n💎 Всего заработано: {referrals[owner_key]['total_earned']:.2f} грн")
        await bot.send_message(PARTNER_GROUP_ID, notification_text)
    except Exception as e: logger.error(f"Partner notification error: {e}")

    try: await bot.send_message(owner_id, f"🎉 <b>Вы получили комиссию!</b>\n\nЗа заказ <code>{order_key}</code>\nСумма: <b>{commission_amount:.2f} грн</b>\nВсего заработано: {referrals[owner_key]['total_earned']:.2f} грн")
    except: pass

# ==================== ОТЗЫВЫ ====================
@dp.callback_query(F.data.startswith("leave_review_"))
async def start_review(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    oid = callback.data.replace("leave_review_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if not rk:
        await callback.message.answer("Оцените покупку:", reply_markup=stars_keyboard())
        await state.update_data(review_order_id=None)
        await state.set_state(ReviewStates.waiting_for_stars)
        return
    order = orders[rk]
    await state.update_data(review_order_id=rk)
    await callback.message.edit_text(f"Оцените {order.get('short_id', rk)}:", reply_markup=stars_keyboard())
    await state.set_state(ReviewStates.waiting_for_stars)

@dp.callback_query(ReviewStates.waiting_for_stars, F.data.startswith("stars_"))
async def process_stars(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    rating = int(callback.data.split("_")[1])
    await state.update_data(stars=rating)
    await callback.message.edit_text(f"{'⭐' * rating}\n📸 Фото или пропустить:", reply_markup=review_photo_skip_keyboard())
    await state.set_state(ReviewStates.waiting_for_photo_or_skip)

@dp.callback_query(ReviewStates.waiting_for_photo_or_skip, F.data == "skip_photo")
async def skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(photo=None)
    await callback.message.edit_text("✏️ Текст отзыва:")
    await state.set_state(ReviewStates.waiting_for_text)

@dp.message(ReviewStates.waiting_for_photo_or_skip, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("✏️ Текст отзыва:")
    await state.set_state(ReviewStates.waiting_for_text)

@dp.message(ReviewStates.waiting_for_text, F.text)
async def process_review_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    rid = f"rev_{message.from_user.id}_{int(datetime.now().timestamp())}"
    reviews = load_reviews()
    reviews[rid] = {
        "review_id": rid, "user_id": message.from_user.id,
        "username": message.from_user.username, "full_name": message.from_user.full_name,
        "stars": data.get("stars", 5), "text": message.text,
        "photo": data.get("photo"), "order_id": data.get("review_order_id"),
        "status": "pending", "created_at": datetime.now().isoformat(),
    }
    save_reviews(reviews)

    oid = data.get("review_order_id")
    if oid:
        orders = load_orders()
        rk = find_order_key(orders, oid)
        if rk:
            orders[rk]["reviewed"] = True
            save_orders(orders)

    stars_str = "⭐" * data.get("stars", 5)
    caption = (f"НОВЫЙ ОТЗЫВ\nID: {rid}\nОт: {message.from_user.full_name}\n@{message.from_user.username}\nОценка: {stars_str}\nТекст: {message.text}")
    try:
        if data.get("photo"): await bot.send_photo(ADMIN_ID, data["photo"], caption=caption, reply_markup=moderation_keyboard(rid))
        else: await bot.send_message(ADMIN_ID, caption, reply_markup=moderation_keyboard(rid))
        await message.answer("🙏 Спасибо!", reply_markup=get_main_reply_keyboard())
    except Exception as e: logger.error(f"Review error: {e}")
    await state.clear()

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("approve_"))
async def approve_review(callback: types.CallbackQuery):
    await callback.answer()
    rid = callback.data.replace("approve_", "")
    reviews = load_reviews()
    review = reviews.get(rid)
    if not review: return
    text = (f"⭐️ НОВЫЙ ОТЗЫВ\nПокупатель: @{review.get('username', '—')}\nОценка: {'⭐️' * review['stars']}\nОтзыв: {review['text']}\nКупить: @MaskYoY\nКанал: @owerpass_store")
    try:
        if review.get("photo"): await bot.send_photo(CHANNEL_ID, review["photo"], caption=text)
        else: await bot.send_message(CHANNEL_ID, text)
        await bot.send_message(review["user_id"], "🎉 Отзыв опубликован!")
        review["status"] = "approved"
        save_reviews(reviews)
        if callback.message.caption: await callback.message.edit_caption(caption=callback.message.caption + "\n✅ ОПУБЛИКОВАН")
        else: await callback.message.edit_text(callback.message.text + "\n✅ ОПУБЛИКОВАН")
    except Exception as e: logger.error(f"Approve error: {e}")

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("reject_"))
async def reject_review(callback: types.CallbackQuery):
    await callback.answer()
    rid = callback.data.replace("reject_", "")
    reviews = load_reviews()
    review = reviews.get(rid)
    if review:
        review["status"] = "rejected"
        save_reviews(reviews)
        try: await bot.send_message(review["user_id"], "❌ Отзыв отклонён.")
        except: pass

# ==================== ЗАКАЗЫ ПОЛЬЗОВАТЕЛЯ ====================
@dp.callback_query(F.data == "my_orders")
@dp.message(F.from_user.id != ADMIN_ID, F.text == "📋 Мои заказы")
async def show_user_orders(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        user_id = event.from_user.id
        target = event.message
    else:
        user_id = event.from_user.id
        target = event

    orders = load_orders()
    user_orders = {k: v for k, v in orders.items() if v["user_id"] == user_id}
    if not user_orders:
        text = "📋 У вас пока нет заказов"
        kb = main_menu_keyboard()
    else:
        text = f"📋 ВАШИ ЗАКАЗЫ ({len(user_orders)})\n"
        b = InlineKeyboardBuilder()
        for oid, order in sorted(user_orders.items(), reverse=True):
            e, _ = STATUS_CONFIG.get(order["status"], ("❓", ""))
            s = method_symbol(order.get("payment_method", "uah"))
            short = order.get("short_id", oid[:8])
            total = order["total"] if isinstance(order["total"], str) else f"{order['total']} {s}"
            text += f"{e} {short} | {order['product']} | {total}\n"
            ibtn(b, f"{short}", callback_data=f"order_detail_{oid}", icon_key="cart")
        ibtn(b, "Меню", callback_data="main_menu", icon_key="warn", style="danger")
        b.adjust(1)
        kb = b.as_markup()

    try: await target.edit_text(text, reply_markup=kb)
    except: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("order_detail_"))
async def show_order_detail(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("order_detail_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if not rk: return await callback.answer("❌ Не найден", show_alert=True)
    order = orders[rk]
    e, st = STATUS_CONFIG.get(order["status"], ("❓", ""))
    s = method_symbol(order.get("payment_method", "uah"))
    short = order.get("short_id", rk[:8])
    total = order["total"] if isinstance(order["total"], str) else f"{order['total']} {s}"

    text = (f"📋 ЗАКАЗ {short}\nТовар: {order['product']}\nОплата: {method_label(order['payment_method'])}\nСумма: {total}\nСтатус: {e} {st}\n")
    if order.get("phone"): text += f"📱 {order['phone']}\n"

    if order["status"] == "completed": kb = user_order_actions_keyboard(rk)
    elif order["status"] == "awaiting_payment": kb = awaiting_payment_keyboard(rk)
    else:
        b = InlineKeyboardBuilder()
        ibtn(b, "Мои заказы", callback_data="my_orders", icon_key="cart")
        ibtn(b, "Меню", callback_data="main_menu", icon_key="warn", style="danger")
        b.adjust(1)
        kb = b.as_markup()

    try: await callback.message.edit_text(text, reply_markup=kb)
    except: await callback.message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "my_accounts")
@dp.message(F.from_user.id != ADMIN_ID, F.text == "📦 Мои аккаунты")
async def show_my_accounts(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        user_id = event.from_user.id
        target = event.message
    else:
        user_id = event.from_user.id
        target = event

    accounts = get_user_accounts(user_id)
    if not accounts:
        text = "📦 У вас пока нет аккаунтов"
        kb = main_menu_keyboard()
    else:
        text = f"📦 ВАШИ АККАУНТЫ ({len(accounts)})\n\n"
        b = InlineKeyboardBuilder()
        for acc in accounts:
            text += f"🌍 {acc['country'].upper()} | 📱 {acc['phone']}\n"
            ibtn(b, f"Код для {acc['phone']}", callback_data=f"request_code_for_{acc['country']}_{acc['session_name']}", icon_key="time")
        ibtn(b, "Меню", callback_data="main_menu", icon_key="warn", style="danger")
        b.adjust(1)
        kb = b.as_markup()

    try: await target.edit_text(text, reply_markup=kb)
    except: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("request_code_for_"))
async def request_code_for_account(callback: types.CallbackQuery):
    await callback.answer()
    data = callback.data.replace("request_code_for_", "")
    if "_" not in data: return
    country, session_name = data.split("_", 1)

    meta = load_meta(country, session_name)
    phone = meta.get("phone") if meta else "—"

    order_key = None
    orders = load_orders()
    for k, o in orders.items():
        if o.get("session_name") == session_name and o.get("country_code") == country:
            order_key = k
            break

    await callback.message.answer(
        f"🔑 <b>Готово! Входи в Telegram.</b>\n\n"
        f"📱 Номер: <code>{phone}</code>\n"
        f"⏳ Как только Telegram пришлёт код — я сразу перешлю его сюда.\n"
        f"После успешного входа придёт подтверждение + кнопка отзыва.\n\n"
        f"<i>Держи этот чат открытым.</i>",
        reply_markup=user_order_actions_keyboard(order_key) if order_key else None
    )
    asyncio.create_task(start_code_watcher(country, session_name, callback.from_user.id, order_key))

@dp.callback_query(F.data.startswith("user_replace_"))
async def user_replace(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("user_replace_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if rk: await bot.send_message(ADMIN_ID, f"🔄 Замена: {orders[rk].get('short_id', rk)} от @{callback.from_user.username}")
    await callback.message.answer("🔄 Запрос отправлен. @MaskYoY")

@dp.callback_query(F.data.startswith("user_refund_"))
async def user_refund(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("user_refund_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if rk: await bot.send_message(ADMIN_ID, f"💰 Возврат: {orders[rk].get('short_id', rk)} от @{callback.from_user.username}")
    await callback.message.answer("💰 Запрос отправлен. @MaskYoY")

# ==================== ПОДДЕРЖКА ====================
@dp.callback_query(F.data.startswith("support_"))
async def start_support(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    oid = callback.data.replace("support_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if rk: oid = rk
    await state.update_data(support_order_id=oid)
    await state.set_state(SupportStates.chatting)
    close_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Закрыть чат")]], resize_keyboard=True)
    await callback.message.answer("🆘 Напишите сообщение продавцу.", reply_markup=close_kb)

@dp.message(SupportStates.chatting, F.text == "❌ Закрыть чат")
async def close_support(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Закрыто", reply_markup=get_main_reply_keyboard())

@dp.message(SupportStates.chatting)
async def relay_to_admin(message: types.Message, state: FSMContext):
    data = await state.get_data()
    oid = data.get("support_order_id", "—")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    short = orders[rk].get("short_id", oid) if rk else oid
    await bot.send_message(ADMIN_ID, f"🆘 @{message.from_user.username} | Заказ {short}")
    fwd = await bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
    relay = load_relay()
    relay[str(fwd.message_id)] = message.from_user.id
    save_relay(relay)
    await message.answer("✅ Отправлено")

@dp.message(F.from_user.id == ADMIN_ID, F.reply_to_message)
async def relay_admin_to_user(message: types.Message):
    relay = load_relay()
    uid = relay.get(str(message.reply_to_message.message_id))
    if not uid: return
    try:
        await bot.copy_message(uid, message.chat.id, message.message_id)
        await message.answer("✅ Доставлено")
    except Exception as e: await message.answer(f"❌ {e}")

# ==================== ЗАПРОС КОДА ====================
@dp.callback_query(F.data.startswith("request_code_"))
async def request_code_cb(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("request_code_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if not rk: return
    order = orders[rk]
    country, session_name, phone = order["country_code"], order["session_name"], order["phone"]

    sess = watcher_path(country, session_name)
    if not os.path.exists(sess): sess = session_path(country, session_name)
    if not os.path.exists(sess): return await callback.message.answer("❌ Файл сессии не найден. @MaskYoY")

    await callback.message.answer(f"🔑 <b>Готово! Входи в Telegram.</b>\n\n📱 Номер: <code>{phone}</code>\n⏳ Как только Telegram пришлёт код — я сразу перешлю его сюда.\nПосле успешного входа придёт подтверждение + кнопка отзыва.\n\n<i>Держи этот чат открытым.</i>")
    asyncio.create_task(start_code_watcher(country, session_name, callback.from_user.id, rk))

# ==================== ПОЛЬЗОВАТЕЛЬСКИЕ КНОПКИ ====================
@dp.message(F.from_user.id != ADMIN_ID, F.text == "🛍 Каталог")
async def catalog_kb(message: types.Message, state: FSMContext):
    if not await check_subscription(message.from_user.id): return await message.answer("⚠️ Подпишитесь!", reply_markup=subscribe_keyboard())
    await state.clear()
    await message.answer("📂 Категории:", reply_markup=catalog_keyboard())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "💬 Отзывы")
async def reviews_kb(message: types.Message): await message.answer("💬 Отзывы:", reply_markup=reviews_keyboard())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "❓ Частые вопросы")
async def faq_kb(message: types.Message): await message.answer(FAQ_TEXT, reply_markup=get_main_reply_keyboard())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "📢 Наш Канал")
async def channel_kb(message: types.Message):
    b = InlineKeyboardBuilder()
    ibtn(b, "Перейти", url="http://t.me/owerpass_store", style="primary")
    await message.answer("Наш канал:", reply_markup=b.as_markup())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "👤 Профиль")
async def profile_kb(message: types.Message): await show_profile(message)

@dp.callback_query(F.data == "profile_menu")
async def profile_menu_cb(callback: types.CallbackQuery):
    await callback.answer()
    await show_profile(callback.message, callback.from_user)

async def show_profile(target, user_obj=None):
    if user_obj is None: user_obj = target.from_user
    user_id = user_obj.id
    level = get_user_level(user_id)
    orders = load_orders()
    completed = [o for o in orders.values() if o["user_id"] == user_id and o["status"] == "completed"]
    total_spent = sum(o.get("total", 0) for o in completed if not isinstance(o.get("total", 0), str))
    referrals = load_referrals()
    rdata = referrals.get(str(user_id), {})
    total_refs = len(rdata.get("referrals_list", []))

    text = (f"👤 <b>Профиль</b>\n🆔 <code>{user_id}</code>\n👤 {user_obj.full_name}\n⭐ {level['emoji']} {level['name']} (-{level['discount']}%)\n💵 Потрачено: {total_spent:.2f}₴\n📦 Покупок: {len(completed)}\n👥 Рефералов: {total_refs}\n💸 Бонусы: {rdata.get('total_earned', 0):.2f}₴")
    try: await target.edit_text(text, reply_markup=profile_keyboard())
    except: await target.answer(text, reply_markup=profile_keyboard())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "👥 Рефералы")
@dp.callback_query(F.data == "referral_menu")
async def referral_menu(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        user_id = event.from_user.id
        target = event.message
    else:
        user_id = event.from_user.id
        target = event

    referrals = load_referrals()
    rdata = referrals.get(str(user_id), {})
    if not rdata.get("referral_code"):
        code = hashlib.md5(f"{user_id}_ref_salt".encode()).hexdigest()[:8].upper()
        rdata["referral_code"] = code
    rdata.setdefault("referrals_list", [])
    rdata.setdefault("total_earned", 0)
    referrals[str(user_id)] = rdata
    save_referrals(referrals)

    code = rdata["referral_code"]
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{code}"
    bonus = get_setting("referral_bonus_percent", 5.0)

    text = (f"👥 <b>Рефералы</b>\n🎁 Бонус: {bonus}%\n👤 Приглашено: {len(rdata['referrals_list'])}\n💸 Заработано: {rdata['total_earned']:.2f}₴\n\n🔗 <code>{link}</code>")
    kb = referral_menu_keyboard()
    try: await target.edit_text(text, reply_markup=kb)
    except: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "referral_stats")
async def referral_stats(callback: types.CallbackQuery):
    await callback.answer()
    referrals = load_referrals()
    rdata = referrals.get(str(callback.from_user.id), {})
    reflist = rdata.get("referrals_list", [])
    text = "📊 Детали:\n"
    if not reflist: text += "<i>Нет рефералов</i>"
    else:
        for r in reflist[-10:]:
            st = "✅" if r.get("first_purchase_done") else "⏳"
            text += f"{st} @{r.get('username', '—')}\n"
    b = InlineKeyboardBuilder()
    ibtn(b, "Назад", callback_data="referral_menu", icon_key="warn", style="danger")
    await callback.message.edit_text(text, reply_markup=b.as_markup())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "🎟 Промокод")
@dp.callback_query(F.data == "promo_menu")
async def promo_menu(event, state: FSMContext = None):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        target = event.message
    else:
        target = event
    b = InlineKeyboardBuilder()
    ibtn(b, "Назад", callback_data="main_menu", icon_key="warn", style="danger")
    try: await target.edit_text("🎟 <b>Введите промокод</b>", reply_markup=b.as_markup())
    except: await target.answer("🎟 <b>Введите промокод</b>", reply_markup=b.as_markup())
    if state: await state.set_state(PromoStates.waiting_for_promo_code)

@dp.message(PromoStates.waiting_for_promo_code, F.text)
async def process_user_promo(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID: return
    if message.text.startswith("/"):
        await state.clear()
        return
    code = message.text.strip().upper()
    promos = load_promo_codes()
    p = promos.get(code)
    if not p:
        await message.answer("❌ Не найден")
        await state.clear()
        return
    if not p.get("is_active", True) or (p.get("max_uses") and p.get("current_uses", 0) >= p["max_uses"]):
        await message.answer("❌ Неактивен")
        await state.clear()
        return
    if p.get("expires_at") and datetime.now() > datetime.fromisoformat(p["expires_at"]):
        await message.answer("❌ Просрочен")
        await state.clear()
        return
    await message.answer(f"✅ Промокод <code>{code}</code> принят!", reply_markup=main_menu_keyboard())
    await state.clear()

# ==================== КАТАЛОГ И ЗАКАЗ ====================
@dp.callback_query(F.data == "main_menu")
async def go_main(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try: await callback.message.edit_text("👋 Меню:", reply_markup=main_menu_keyboard())
    except: await callback.message.answer("👋 Меню:", reply_markup=main_menu_keyboard())

@dp.callback_query(F.data == "menu_catalog")
async def open_catalog(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    try: await callback.message.edit_text("📂 Категории:", reply_markup=catalog_keyboard())
    except: await callback.message.answer("📂 Категории:", reply_markup=catalog_keyboard())

@dp.callback_query(F.data == "menu_reviews")
async def open_reviews(callback: types.CallbackQuery):
    await callback.answer()
    try: await callback.message.edit_text("💬 Отзывы:", reply_markup=reviews_keyboard())
    except: await callback.message.answer("💬 Отзывы:", reply_markup=reviews_keyboard())

@dp.callback_query(F.data == "out_of_stock")
async def out_of_stock(callback: types.CallbackQuery): await callback.answer("❌ Товар закончился", show_alert=True)

@dp.callback_query(F.data.startswith("cat_"))
async def show_category(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    cat = callback.data.replace("cat_", "")
    if cat not in CATEGORIES: return
    try: await callback.message.edit_text(f"{CATEGORIES[cat]['name']}\nВыберите товар:", reply_markup=category_products_keyboard(cat))
    except: await callback.message.answer(f"{CATEGORIES[cat]['name']}\nВыберите товар:", reply_markup=category_products_keyboard(cat))

@dp.callback_query(F.data.startswith("product_"))
async def product_selected(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    if len(parts) < 3: return
    category = parts[1]
    code = parts[2]

    product_name = None
    for pname, pdata in CATEGORIES[category]["products"].items():
        if pdata.get("code") == code:
            product_name = pname
            break
    if not product_name: return await callback.answer("❌ Не найден", show_alert=True)

    await state.update_data(category=category, product=product_name, code=code)
    try: await callback.message.edit_text(f"✅ {product_name}\n🔢 Количество:", reply_markup=quantity_keyboard())
    except: await callback.message.answer(f"✅ {product_name}\n🔢 Количество:", reply_markup=quantity_keyboard())
    await state.set_state(OrderStates.waiting_for_quantity)

@dp.callback_query(OrderStates.waiting_for_quantity, F.data.startswith("qty_"))
async def process_quantity(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    qty = int(callback.data.split("_")[1])
    await state.update_data(quantity=qty)
    data = await state.get_data()
    code = data["code"]

    avail = all_available(code)
    if not avail and data["category"] not in ("stars", "tiktok", "discord"):
        await callback.message.edit_text("❌ Товар закончился", reply_markup=main_menu_keyboard())
        await state.clear()
        return

    price = avail[0]["price_uah"] if avail else CATEGORIES[data["category"]]["products"][data["product"]]["uah"]
    await state.update_data(price_uah=price)
    await state.update_data(base_price=price)

    text = (f"📦 {data['product']}\n💰 {price}₴\n\nЕсть промокод? Введите его или нажмите 'Пропустить':")
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Пропустить промокод", callback_data="skip_promo", icon_key="check")
    kb.adjust(1)
    try: await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except: await callback.message.answer(text, reply_markup=kb.as_markup())
    await state.set_state(OrderStates.waiting_for_promo_input)

@dp.callback_query(OrderStates.waiting_for_promo_input, F.data == "skip_promo")
async def skip_promo_code(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(used_promo_code=None)
    await state.update_data(discount_amount=0)
    await state.update_data(final_price=await get_final_price(state))
    data = await state.get_data()
    final_price = data.get("final_price")

    text = f"💳 Способ оплаты:\nИтого к оплате: <b>{final_price}₴</b>"
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Оплатить подарком", callback_data="pay_gift", icon_key="gift")
    ibtn(kb, "Оплатить гривнами", callback_data="pay_uah", icon_key="money", style="primary")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    try: await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except: await callback.message.answer(text, reply_markup=kb.as_markup())
    await state.set_state(OrderStates.waiting_for_payment_method)

@dp.message(OrderStates.waiting_for_promo_input, F.text)
async def process_promo_input(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    promos = load_promo_codes()
    p = promos.get(code)

    valid = False
    discount_amount = 0
    if p and p.get("is_active", True):
        max_uses = p.get("max_uses")
        current_uses = p.get("current_uses", 0)
        if not max_uses or current_uses < max_uses:
            if not p.get("expires_at") or datetime.now() < datetime.fromisoformat(p["expires_at"]):
                valid = True
                base_price = (await state.get_data()).get("base_price", 0)
                if p["discount_type"] == "percent": discount_amount = round(base_price * (p["discount_value"] / 100), 2)
                else: discount_amount = min(p["discount_value"], base_price)

    if valid:
        await state.update_data(used_promo_code=code)
        await state.update_data(discount_amount=discount_amount)
        await state.update_data(final_price=await get_final_price(state))
        await message.answer(f"✅ Промокод <code>{code}</code> применен!\nСкидка: -{discount_amount}₴")
        await show_payment_methods_after_promo(message, state)
    else:
        await message.answer("❌ Промокод недействителен, истек или исчерпан. Попробуйте другой или пропустите.")

async def get_final_price(state: FSMContext):
    data = await state.get_data()
    base_price = data.get("base_price", 0)
    discount = data.get("discount_amount", 0)
    return max(0, base_price - discount)

async def show_payment_methods_after_promo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    final_price = data.get("final_price", data.get("price_uah"))

    text = f"💳 Способ оплаты:\nИтого к оплате: <b>{final_price}₴</b>"
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Оплатить подарком", callback_data="pay_gift", icon_key="gift")
    ibtn(kb, "Оплатить гривнами", callback_data="pay_uah", icon_key="money", style="primary")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    await message.answer(text, reply_markup=kb.as_markup())
    await state.set_state(OrderStates.waiting_for_payment_method)

@dp.callback_query(OrderStates.waiting_for_payment_method, F.data.startswith("pay_"))
async def process_payment_method(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    method = callback.data.replace("pay_", "")
    await state.update_data(payment_method=method)
    data = await state.get_data()
    final_price = data.get("final_price", data.get("price_uah"))
    used_promo = data.get("used_promo_code")
    promo_text = f"🎟 Промокод: <code>{used_promo}</code>\n" if used_promo else ""

    text = (f"📋 Подтверждение\nТовар: {data['product']}\nОплата: {'🎁 Подарок' if method == 'gift' else '💳 Гривны'}\n{promo_text}Сумма: {final_price}₴\n\nПодтвердить?")
    try: await callback.message.edit_text(text, reply_markup=confirm_order_keyboard())
    except: await callback.message.answer(text, reply_markup=confirm_order_keyboard())
    await state.set_state(OrderStates.waiting_for_confirmation)

@dp.callback_query(OrderStates.waiting_for_confirmation, F.data == "confirm_order")
async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    category, product, code = data["category"], data["product"], data["code"]
    method, used_promo, final_price = data["payment_method"], data.get("used_promo_code"), data.get("final_price")

    acc = None
    if category not in ("stars", "tiktok", "discord"):
        acc = reserve_account(code, callback.from_user.id)
        if not acc:
            await callback.message.edit_text("❌ Товар закончился!", reply_markup=main_menu_keyboard())
            await state.clear()
            return

    short_id = generate_short_order_id()
    if used_promo:
        promos = load_promo_codes()
        if used_promo in promos: promos[used_promo]["current_uses"] = promos[used_promo].get("current_uses", 0) + 1
        save_promo_codes(promos)

    orders = load_orders()
    orders[short_id] = {
        "order_id": short_id, "short_id": short_id,
        "user_id": callback.from_user.id, "username": callback.from_user.username,
        "full_name": callback.from_user.full_name,
        "category": category, "product": product, "code": code,
        "country_code": acc["country"] if acc else code, "session_name": acc["session_name"] if acc else None,
        "phone": acc["phone"] if acc else None,
        "payment_method": method, "total": final_price,
        "used_promo_code": used_promo,
        "status": "awaiting_payment", "created_at": datetime.now().isoformat(), "reviewed": False,
    }
    save_orders(orders)

    try:
        await bot.send_message(ADMIN_ID,
            f"🆕 <b>НОВЫЙ ЗАКАЗ {short_id}</b>\n\n👤 @{callback.from_user.username} | {callback.from_user.full_name}\n🆔 <code>{callback.from_user.id}</code>\n🌍 {acc['country'].upper() if acc else code} | 📱 {acc['phone'] if acc else '—'}\n💰 {final_price}₴ | {'🎁 Подарок' if method == 'gift' else '💳 Гривны'}\n{'🎟 Промо: ' + used_promo if used_promo else ''}\n\nПодтвердите оплату в <b>📋 Все заказы</b>",
            reply_markup=InlineKeyboardBuilder().button(text="📋 Открыть заказ", callback_data=f"admin_order_detail_{short_id}").as_markup())
    except Exception as e: logger.error(f"Admin notify error: {e}")

    requisites = get_requisites("uah" if method == "uah" else "gift")
    await callback.message.edit_text(
        f"✅ <b>Заказ {short_id} создан!</b>\n\n🌍 {acc['country'].upper() if acc else code}\n📱 {acc['phone'] if acc else '—'}\n💰 <b>{final_price}₴</b>\n💳 Способ: {'🎁 Подарок' if method == 'gift' else '💳 Гривны'}\n\n<b>РЕКВИЗИТЫ:</b>\n{requisites}\n\nПосле оплаты напишите @MaskYoY и пришлите чек.",
        reply_markup=awaiting_payment_keyboard(short_id))
    await state.clear()

# ==================== АДМИН: ПАНЕЛЬ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📈 Панель управления")
async def admin_dashboard_cmd(message: types.Message): await show_dashboard(message)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_dashboard_refresh")
async def dashboard_refresh(callback: types.CallbackQuery):
    await callback.answer()
    await show_dashboard(callback.message, edit=True)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_orders_dashboard")
async def orders_dashboard(callback: types.CallbackQuery):
    await callback.answer()
    await show_admin_orders_page(callback.message, 0, edit=True)

async def show_dashboard(target, edit=False):
    orders = load_orders()
    users = load_users()
    counts = stock_count()
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    rev_today, total_rev, completed = 0, 0, 0
    for o in orders.values():
        if o["status"] == "completed" and not isinstance(o.get("total", 0), str):
            total_rev += o["total"]
            completed += 1
            if o.get("completed_at"):
                try:
                    if datetime.fromisoformat(o["completed_at"]) >= today: rev_today += o["total"]
                except: pass
    new_today = sum(1 for u in users.values() if u.get("first_seen") and datetime.fromisoformat(u["first_seen"]) >= today)
    text = (f"📊 <b>ПАНЕЛЬ</b>\n💰 Сегодня: {rev_today:.2f}₴\n💰 Всего: {total_rev:.2f}₴\n👥 Новых: {new_today}\n📦 Выполнено: {completed}/{len(orders)}\n📦 Склад: {sum(counts.values())} акк.\n👤 Юзеров: {len(users)}")
    kb = admin_dashboard_keyboard()
    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: await target.answer(text, reply_markup=kb)
    else: await target.answer(text, reply_markup=kb)

# ==================== АДМИН: УРОВНИ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "⭐ Уровни")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_levels_dashboard")
async def admin_levels(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        target = event.message
        edit = True
    else:
        target = event
        edit = False
    levels = {
        "Бронза": ("🥉", get_setting("level_bronze_min", 0), get_setting("level_bronze_discount", 0)),
        "Серебро": ("🥈", get_setting("level_silver_min", 500), get_setting("level_silver_discount", 3)),
        "Золото": ("🥇", get_setting("level_gold_min", 1500), get_setting("level_gold_discount", 5)),
        "Платина": ("💎", get_setting("level_platinum_min", 3000), get_setting("level_platinum_discount", 7)),
        "VIP": ("👑", get_setting("level_vip_min", 5000), get_setting("level_vip_discount", 10)),
    }
    text = "⭐ Уровни:\n"
    for n, (e, m, d) in levels.items(): text += f"{e} {n}: от {m}₴ (-{d}%)\n"
    kb = admin_levels_keyboard()
    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: await target.answer(text, reply_markup=kb)
    else: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_edit_level_"))
async def admin_edit_level(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    key = callback.data.replace("admin_edit_level_", "")
    await state.update_data(edit_level=key)
    b = InlineKeyboardBuilder()
    ibtn(b, "Порог", callback_data="edit_level_min", icon_key="money")
    ibtn(b, "Скидка", callback_data="edit_level_discount", icon_key="gift")
    ibtn(b, "Назад", callback_data="admin_levels_dashboard", icon_key="warn", style="danger")
    b.adjust(1)
    await callback.message.edit_text(f"Уровень {LEVEL_KEYS.get(key, key)}:", reply_markup=b.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "edit_level_min")
async def edit_level_min(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="min_spent")
    await callback.message.edit_text("Введите новый порог:")
    await state.set_state(AdminLevelStates.waiting_for_min_spent)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "edit_level_discount")
async def edit_level_discount(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(edit_field="discount")
    await callback.message.edit_text("Введите скидку %:")
    await state.set_state(AdminLevelStates.waiting_for_discount)

@dp.message(AdminLevelStates.waiting_for_min_spent, F.text)
async def save_level_min(message: types.Message, state: FSMContext):
    try: v = float(message.text)
    except:
        await message.answer("❌ Число")
        return
    data = await state.get_data()
    key = data.get("edit_level", "bronze")
    s = load_settings()
    s[f"level_{key}_min"] = v
    save_settings(s)
    await message.answer(f"✅ Порог: {v}₴", reply_markup=get_admin_reply_keyboard())
    await state.clear()

@dp.message(AdminLevelStates.waiting_for_discount, F.text)
async def save_level_disc(message: types.Message, state: FSMContext):
    try:
        v = float(message.text)
        if not (0 <= v <= 100): raise ValueError
    except:
        await message.answer("❌ 0-100")
        return
    data = await state.get_data()
    key = data.get("edit_level", "bronze")
    s = load_settings()
    s[f"level_{key}_discount"] = v
    save_settings(s)
    await message.answer(f"✅ Скидка: {v}%", reply_markup=get_admin_reply_keyboard())
    await state.clear()

# ==================== АДМИН: АНАЛИТИКА ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📊 Аналитика")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_dashboard")
async def admin_analytics(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        target = event.message
        edit = True
    else:
        target = event
        edit = False
    kb = admin_analytics_keyboard()
    if edit:
        try: await target.edit_text("📊 Аналитика:", reply_markup=kb)
        except: await target.answer("📊 Аналитика:", reply_markup=kb)
    else: await target.answer("📊 Аналитика:", reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_by_days")
async def anal_days(callback: types.CallbackQuery):
    await callback.answer()
    orders = load_orders()
    now = datetime.now()
    data = {}
    for i in range(30):
        d = (now - timedelta(days=i)).strftime("%d.%m")
        data[d] = {"rev": 0, "n": 0}
    for o in orders.values():
        if o["status"] == "completed" and o.get("completed_at"):
            try:
                dt = datetime.fromisoformat(o["completed_at"])
                if (now - dt).days < 30 and not isinstance(o.get("total", 0), str):
                    d = dt.strftime("%d.%m")
                    if d in data:
                        data[d]["rev"] += o["total"]
                        data[d]["n"] += 1
            except: pass
    text = "📈 По дням:\n"
    for d in reversed(list(data.keys())):
        if data[d]["rev"] > 0: text += f"📅 {d}: {data[d]['rev']:.2f}₴ ({data[d]['n']})\n"
    b = InlineKeyboardBuilder()
    ibtn(b, "Назад", callback_data="admin_analytics_dashboard", icon_key="warn", style="danger")
    await callback.message.edit_text(text, reply_markup=b.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_by_hours")
async def anal_hours(callback: types.CallbackQuery):
    await callback.answer()
    orders = load_orders()
    h = {i: {"rev": 0, "n": 0} for i in range(24)}
    for o in orders.values():
        if o["status"] == "completed" and o.get("completed_at"):
            try:
                dt = datetime.fromisoformat(o["completed_at"])
                if not isinstance(o.get("total", 0), str):
                    h[dt.hour]["rev"] += o["total"]
                    h[dt.hour]["n"] += 1
            except: pass
    text = "⏰ По часам:\n"
    for i in range(24):
        if h[i]["n"] > 0: text += f"{i:02d}:00 — {h[i]['rev']:.2f}₴ ({h[i]['n']})\n"
    b = InlineKeyboardBuilder()
    ibtn(b, "Назад", callback_data="admin_analytics_dashboard", icon_key="warn", style="danger")
    await callback.message.edit_text(text, reply_markup=b.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_by_country")
async def anal_country(callback: types.CallbackQuery):
    await callback.answer()
    orders = load_orders()
    stats = {}
    for o in orders.values():
        if o["status"] == "completed":
            c = o.get("country_code", "??")
            stats.setdefault(c, {"rev": 0, "n": 0})
            if not isinstance(o.get("total", 0), str): stats[c]["rev"] += o["total"]
            stats[c]["n"] += 1
    text = "🌍 По странам:\n"
    for c, d in sorted(stats.items(), key=lambda x: -x[1]["rev"]): text += f"• {c.upper()}: {d['rev']:.2f}₴ ({d['n']})\n"
    b = InlineKeyboardBuilder()
    ibtn(b, "Назад", callback_data="admin_analytics_dashboard", icon_key="warn", style="danger")
    await callback.message.edit_text(text, reply_markup=b.as_markup())

# ==================== АДМИН: ИСТОЧНИКИ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "🔗 Источники")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_traffic_dashboard")
async def admin_traffic(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        target = event.message
        edit = True
    else:
        target = event
        edit = False
    sources = load_traffic_sources()
    text = "🔗 Источники:\n"
    if not sources: text += "<i>Нет данных</i>"
    else:
        for name, d in sorted(sources.items(), key=lambda x: -x[1].get("total_revenue", 0)): text += f"📍 {name}: {d.get('total_revenue', 0):.2f}₴\n"
    b = InlineKeyboardBuilder()
    ibtn(b, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    if edit:
        try: await target.edit_text(text, reply_markup=b.as_markup())
        except: await target.answer(text, reply_markup=b.as_markup())
    else: await target.answer(text, reply_markup=b.as_markup())

# ==================== АДМИН: РЕФЕРАЛЫ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "👥 Рефералы")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_referrals_dashboard")
async def admin_referrals(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        target = event.message
        edit = True
    else:
        target = event
        edit = False
    referrals = load_referrals()
    bonus = get_setting("referral_bonus_percent", 5.0)
    total = sum(len(r.get("referrals_list", [])) for r in referrals.values())
    earned = sum(r.get("total_earned", 0) for r in referrals.values())
    text = f"👥 Рефералы\n💰 Бонус: {bonus}%\n👥 Всего: {total}\n💸 {earned:.2f}₴\n"
    kb = admin_referrals_settings_keyboard()
    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: await target.answer(text, reply_markup=kb)
    else: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_edit_referral_bonus")
async def admin_edit_bonus(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    cur = get_setting("referral_bonus_percent", 5.0)
    await callback.message.edit_text(f"Текущий: {cur}%\nВведите новый:")
    await state.set_state(AdminReferralSettingsStates.waiting_for_bonus_percent)

@dp.message(AdminReferralSettingsStates.waiting_for_bonus_percent, F.text)
async def save_bonus(message: types.Message, state: FSMContext):
    try:
        v = float(message.text)
        if not (0 <= v <= 100): raise ValueError
    except:
        await message.answer("❌ 0-100")
        return
    s = load_settings()
    s["referral_bonus_percent"] = v
    save_settings(s)
    await message.answer(f"✅ {v}%", reply_markup=get_admin_reply_keyboard())
    await state.clear()

# ==================== АДМИН: ПОЛЬЗОВАТЕЛИ / ЧАТ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "👤 Пользователи")
async def admin_users_list(message: types.Message):
    users = load_users()
    if not users: return await message.answer("📋 Нет", reply_markup=get_admin_reply_keyboard())
    text = f"👤 ВСЕГО: {len(users)}\n"
    for uid, u in sorted(users.items(), key=lambda x: x[1].get("first_seen", ""), reverse=True)[:10]:
        text += f"👤 {u.get('full_name', '—')} (@{u.get('username', '—')})\nID: {uid}\n"
    if len(users) > 10: text += f"...и ещё {len(users) - 10}"
    await message.answer(text, reply_markup=get_admin_reply_keyboard())

@dp.message(F.from_user.id == ADMIN_ID, F.text == "🏠 Главное меню")
async def admin_main_menu(message: types.Message): await message.answer("🏠", reply_markup=get_admin_reply_keyboard())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_chat_with_user_"))
async def admin_chat_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    oid = callback.data.replace("admin_chat_with_user_", "")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if not rk: return
    await state.update_data(admin_chat_order_id=rk)
    await callback.message.answer(f"💬 Введите сообщение покупателю:")
    await state.set_state(AdminChatStates.waiting_for_message)

@dp.message(AdminChatStates.waiting_for_message, F.text)
async def admin_chat_send(message: types.Message, state: FSMContext):
    data = await state.get_data()
    oid = data.get("admin_chat_order_id")
    orders = load_orders()
    rk = find_order_key(orders, oid)
    if not rk:
        await message.answer("❌")
        await state.clear()
        return
    order = orders[rk]
    try:
        await bot.send_message(order["user_id"], f"💬 Админ:\n{message.text}")
        await message.answer("✅", reply_markup=get_admin_reply_keyboard())
    except Exception as e: await message.answer(f"❌ {e}", reply_markup=get_admin_reply_keyboard())
    await state.clear()

# ==================== ОШИБКИ ====================
@dp.errors()
async def error_handler(event):
    logger.error(f"Update error: {event.exception}")
    return True

# ==================== ЗАПУСК ====================
async def main():
    print("=" * 50)
    print("OverPass Store Bot v5")
    print("=" * 50)
    print("[BACKUP] Восстановление из переменных окружения...")
    restore_from_env()

    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(1)

    if os.path.exists(ACCOUNTS_DIR):
        for c in os.listdir(ACCOUNTS_DIR):
            cd = country_dir(c)
            if not os.path.isdir(cd): continue
            for f in os.listdir(cd):
                if f.endswith(".json"):
                    meta = load_meta(c, f.replace(".json", ""))
                    if meta and meta.get("sold_to"):
                        order_key = None
                        orders = load_orders()
                        for k, o in orders.items():
                            if o.get("session_name") == meta["session_name"] and o.get("country_code") == c:
                                order_key = k
                                break
                        asyncio.create_task(start_code_watcher(c, meta["session_name"], meta["sold_to"], order_key))

    print("Бот запущен!")
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Остановлен")
    except Exception as e:
        print(f"Ошибка запуска: {e}")
        sys.exit(1)
