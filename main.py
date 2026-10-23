# -*- coding: utf-8 -*-
"""OverPass Store Bot v9 — все кнопки рабочие, устойчив к перезапускам."""
import asyncio
import logging
import json
import os
import sys
import re
import base64
import hashlib
import shutil
import html
import time
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, FSInputFile, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter
from telethon import TelegramClient, events, functions

# ==================== КОНФИГ ====================
# Рекомендуется задать значения в переменных окружения (Railway -> Variables)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8975688414:AAGUC6Ag9ADN_p7Tb0R9a8xsLEnsFHFkWZM")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8543473783"))
CHANNEL_ID = os.environ.get("CHANNEL_ID", "-1004311525622")
STORE_CHANNEL_ID = os.environ.get("STORE_CHANNEL_ID", "-1004292126045")
PARTNER_GROUP_ID = int(os.environ.get("PARTNER_GROUP_ID", "-5598258715"))
API_ID = int(os.environ.get("API_ID", "38387697"))
API_HASH = os.environ.get("API_HASH", "e8fb7f7163498eb28231e45071fe92c0")
SELLER = "@MaskYoY"

# Если на хостинге подключён Volume — укажите DATA_DIR, и все данные переживут перезапуск
DATA_DIR = os.environ.get("DATA_DIR")
if DATA_DIR:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.chdir(DATA_DIR)

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("shop")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ==================== ПРЕМИУМ ЭМОДЗИ ====================
EMOJI = {
    "star": ("5438496463044752972", "⭐"), "check": ("5206607081334906820", "✅"),
    "fire": ("5424972470023104089", "🔥"), "money": ("5287231198098117669", "💰"),
    "cart": ("5312361253610475399", "🛍"), "user": ("5190872550250405805", "👤"),
    "gift": ("5278467510604160626", "🎁"), "time": ("5382194935057372936", "⏱"),
    "warn": ("5447644880824181073", "⚠️"), "box": ("5472335930549347896", "📦"),
    "card": ("5445353829304387411", "💳"), "key": ("5413395871008058098", "🔑"),
    "phone": ("5407025283456835913", "📱"), "lock": ("5197288647275071607", "🔐"),
    "trash": ("5445267414562389170", "🗑"), "chart": ("5231200819986047254", "📊"),
    "chart_up": ("5397892696926860982", "📈"), "gear": ("5341715473882955310", "⚙️"),
    "megaphone": ("5424818078833715060", "📢"), "link": ("5271604874419647061", "🔗"),
    "save": ("5462956611033117422", "💾"), "calendar": ("5274055917766202507", "📅"),
    "rocket": ("5188481279963715781", "🚀"), "heart": ("4996980495100150380", "❤️"),
    "cross": ("5210952531676504517", "❌"), "question": ("5436113877181941026", "❓"),
    "plus": ("5397916757333654639", "➕"), "refresh": ("5346269127059196142", "🔄"),
    "back": ("5258236805890710909", "⬅️"), "next": ("5877468380125990242", "➡️"),
    "trophy": ("5188344996356448758", "🏆"), "crown": ("5217822164362739968", "👑"),
    "diamond": ("5427168083074628963", "💎"), "medal1": ("5440539497383087970", "🥇"),
    "medal2": ("5447203607294265305", "🥈"), "medal3": ("5453902265922376865", "🥉"),
    "ticket": ("5377599075237502153", "🎟"), "chat": ("5443038326535759644", "💬"),
    "globe": ("5224450179368767019", "🌍"), "pin": ("5938027397524754858", "📌"),
    "sparkle": ("5325547803936572038", "✨"),
}


def pe(key):
    e, sym = EMOJI.get(key, (None, ""))
    return '<tg-emoji emoji-id="%s">%s</tg-emoji>' % (e, sym) if e else sym


def eid(key):
    return EMOJI.get(key, (None, ""))[0]


_BTN_FIELDS = getattr(InlineKeyboardButton, "model_fields", {}) or {}
_HAS_STYLE = "style" in _BTN_FIELDS
_HAS_ICON = "icon_custom_emoji_id" in _BTN_FIELDS


def ibtn(builder, text, callback_data=None, url=None, icon_key=None, style=None):
    kw = {"text": text}
    if callback_data is not None:
        kw["callback_data"] = callback_data
    if url is not None:
        kw["url"] = url
    if style and _HAS_STYLE:
        kw["style"] = style
    if icon_key and eid(icon_key) and _HAS_ICON:
        kw["icon_custom_emoji_id"] = eid(icon_key)
    builder.add(InlineKeyboardButton(**kw))


# ==================== УТИЛИТЫ ====================
def esc(s):
    return html.escape(str(s)) if s is not None else ""


def uname(u):
    return "@" + esc(u) if u else "—"


def money(x):
    try:
        x = float(x)
    except Exception:
        return "0"
    return str(int(x)) if x == int(x) else "%.2f" % x


def otot(o):
    try:
        return float(o.get("total", 0))
    except Exception:
        return 0.0


_clicks = {}


def throttle(uid, key, sec=3.0):
    """False — если то же действие уже выполнялось менее sec секунд назад."""
    now = time.time()
    k = (uid, key)
    if now - _clicks.get(k, 0) < sec:
        return False
    _clicks[k] = now
    if len(_clicks) > 5000:
        _clicks.clear()
    return True


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
TRAFFIC_SOURCES_FILE = "traffic_sources.json"
PROMO_EARNINGS_FILE = "promo_earnings.json"

ACCOUNTS_DIR = "accounts"
TEMP_DIR = "temp_sessions"
os.makedirs(ACCOUNTS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

BACKUP_FILES = ["orders", "users", "referrals", "promo_codes", "settings", "order_counter",
                "reviews", "relay_map", "requisites", "traffic_sources", "promo_earnings"]


def restore_from_env():
    """Восстановление из переменных окружения (BACKUP_ALL_B64 или BACKUP_<NAME>_B64)."""
    allv = os.environ.get("BACKUP_ALL_B64")
    if allv:
        try:
            data = json.loads(base64.b64decode(allv).decode("utf-8"))
            for name, content in data.items():
                p = "%s.json" % name
                if os.path.exists(p) and os.path.getsize(p) > 2:
                    continue
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(content, f, ensure_ascii=False, indent=2)
                print("[BACKUP] %s восстановлен" % name)
        except Exception as e:
            logger.error("Restore ALL: %s", e)
    for name in BACKUP_FILES:
        v = os.environ.get("BACKUP_%s_B64" % name.upper())
        if not v:
            continue
        p = "%s.json" % name
        if os.path.exists(p) and os.path.getsize(p) > 2:
            continue
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(base64.b64decode(v).decode("utf-8"))
            print("[BACKUP] %s восстановлен" % name)
        except Exception as e:
            logger.error("Restore %s: %s", name, e)


def load_json(p):
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error("load_json %s: %s", p, e)
    return {}


def save_json(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def load_orders(): return load_json(ORDERS_FILE)
def save_orders(x): save_json(ORDERS_FILE, x)
def load_reviews(): return load_json(REVIEWS_FILE)
def save_reviews(x): save_json(REVIEWS_FILE, x)
def load_relay(): return load_json(RELAY_FILE)
def save_relay(x): save_json(RELAY_FILE, x)
def load_requisites(): return load_json(REQUISITES_FILE)
def save_requisites(x): save_json(REQUISITES_FILE, x)
def load_users(): return load_json(USERS_FILE)
def save_users(x): save_json(USERS_FILE, x)
def load_referrals(): return load_json(REFERRALS_FILE)
def save_referrals(x): save_json(REFERRALS_FILE, x)
def load_promo_codes(): return load_json(PROMO_CODES_FILE)
def save_promo_codes(x): save_json(PROMO_CODES_FILE, x)
def load_settings(): return load_json(SETTINGS_FILE)
def save_settings(x): save_json(SETTINGS_FILE, x)
def load_order_counter(): return load_json(ORDER_COUNTER_FILE)
def save_order_counter(x): save_json(ORDER_COUNTER_FILE, x)
def load_traffic_sources(): return load_json(TRAFFIC_SOURCES_FILE)
def save_traffic_sources(x): save_json(TRAFFIC_SOURCES_FILE, x)
def load_promo_earnings(): return load_json(PROMO_EARNINGS_FILE)
def save_promo_earnings(x): save_json(PROMO_EARNINGS_FILE, x)


# Сначала восстановление, потом дефолты (иначе дефолты «перекрывают» бэкап)
restore_from_env()

# ==================== СТРАНЫ ====================
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
    "90": ("tr", "🇹🇷 Турция"), "86": ("cn", "🇨🇳 Китай"),
    "81": ("jp", "🇯🇵 Япония"), "82": ("kr", "🇰🇷 Корея"),
    "84": ("vn", "🇻🇳 Вьетнам"), "63": ("ph", "🇵🇭 Филиппины"),
    "60": ("my", "🇲🇾 Малайзия"), "65": ("sg", "🇸🇬 Сингапур"),
}
COUNTRY_NAME = {v[0]: v[1] for v in COUNTRY_CODES.values()}


def country_name(code):
    return COUNTRY_NAME.get(code, (code or "?").upper())


def detect_country(phone):
    if not phone:
        return ("unknown", "❓ Неизвестно")
    clean = str(phone).replace("+", "").replace(" ", "").replace("-", "")
    for length in (3, 2, 1):
        p = clean[:length]
        if p in COUNTRY_CODES:
            return COUNTRY_CODES[p]
    return ("unknown", "❓ Неизвестно")


# ==================== СКЛАД ====================
def country_dir(c): return os.path.join(ACCOUNTS_DIR, c)
def session_path(c, n): return os.path.join(country_dir(c), "%s.session" % n)
def watcher_path(c, n): return os.path.join(country_dir(c), "%s_watcher.session" % n)
def meta_path(c, n): return os.path.join(country_dir(c), "%s.json" % n)


def load_meta(c, n):
    p = meta_path(c, n)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_meta(c, n, meta):
    os.makedirs(country_dir(c), exist_ok=True)
    save_json(meta_path(c, n), meta)


def list_metas():
    res = []
    if not os.path.isdir(ACCOUNTS_DIR):
        return res
    for c in sorted(os.listdir(ACCOUNTS_DIR)):
        cd = country_dir(c)
        if not os.path.isdir(cd):
            continue
        for f in sorted(os.listdir(cd)):
            if f.endswith(".json"):
                m = load_meta(c, f[:-5])
                if m:
                    res.append(m)
    return res


def all_available(country=None, stock_type=None):
    res = []
    for m in list_metas():
        if m.get("status") != "available":
            continue
        if country and m.get("country") != country:
            continue
        if stock_type and m.get("stock_type") != stock_type:
            continue
        res.append(m)
    return res


def stock_count(stock_type=None):
    counts = {}
    for m in all_available(stock_type=stock_type):
        counts[m["country"]] = counts.get(m["country"], 0) + 1
    return counts


def reserve_accounts(country, uid, stock_type, qty):
    avail = all_available(country, stock_type)
    if len(avail) < qty:
        return None
    taken = avail[:qty]
    for acc in taken:
        acc["status"] = "reserved"
        acc["reserved_by"] = uid
        acc["reserved_at"] = datetime.now().isoformat()
        save_meta(acc["country"], acc["session_name"], acc)
    return taken


def release_account(country, n):
    meta = load_meta(country, n)
    if not meta or meta.get("status") != "reserved":
        return
    meta["status"] = "available"
    meta.pop("reserved_by", None)
    meta.pop("reserved_at", None)
    save_meta(country, n, meta)


def mark_sold(country, n, uid):
    meta = load_meta(country, n)
    if not meta:
        return
    meta["status"] = "sold"
    meta["sold_at"] = datetime.now().isoformat()
    meta["sold_to"] = uid
    save_meta(country, n, meta)


async def analyze_session(session_file):
    client = TelegramClient(session_file.replace(".session", ""), API_ID, API_HASH)
    res = {"valid": False, "phone": None, "user_id": None, "first_name": None,
           "has_2fa": False, "password_hint": None}
    try:
        await client.connect()
        if not await client.is_user_authorized():
            res["error"] = "NOT_AUTHORIZED"
            return res
        me = await client.get_me()
        if not me:
            res["error"] = "NO_ME"
            return res
        res.update({"valid": True, "phone": me.phone, "user_id": me.id, "first_name": me.first_name,
                    "username": me.username, "premium": getattr(me, "premium", False)})
        try:
            pwd = await client(functions.account.GetPasswordRequest())
            if getattr(pwd, "has_password", False):
                res["has_2fa"] = True
                res["password_hint"] = getattr(pwd, "hint", None)
        except Exception as e:
            logger.warning("2FA check: %s", e)
    except Exception as e:
        res["error"] = "%s: %s" % (type(e).__name__, str(e)[:100])
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
    return res


# ==================== НАСТРОЙКИ ====================
DEFAULT_SETTINGS = {
    "referral_bonus_percent": 5.0,
    "partner_commission_percent": 20.0,
    "stars_enabled": True,
    "order_ttl_minutes": 60,
    "price_override": {},
    "level_bronze_min": 0, "level_bronze_discount": 0,
    "level_silver_min": 500, "level_silver_discount": 3,
    "level_gold_min": 1500, "level_gold_discount": 5,
    "level_platinum_min": 3000, "level_platinum_discount": 7,
    "level_vip_min": 5000, "level_vip_discount": 10,
}
if not os.path.exists(SETTINGS_FILE):
    save_settings(DEFAULT_SETTINGS)


def get_setting(k, d=None):
    return load_settings().get(k, DEFAULT_SETTINGS.get(k, d))


def stars_enabled():
    return bool(get_setting("stars_enabled", True))


LEVEL_KEYS = {"bronze": "Бронза", "silver": "Серебро", "gold": "Золото", "platinum": "Платина", "vip": "VIP"}

DEFAULT_REQUISITES = {
    "uah": "%s <b>Карта Моно:</b> <code>4874 0700 2513 7454</code>\n\n%s <b>Подарок в ЛС:</b> %s" % (pe("money"), pe("gift"), SELLER),
    "gift": "%s <b>Подарок в ЛС:</b> %s" % (pe("gift"), SELLER),
}
if not os.path.exists(REQUISITES_FILE):
    save_requisites(DEFAULT_REQUISITES)


def get_requisites(m):
    return load_requisites().get(m, DEFAULT_REQUISITES.get(m, "Уточните у продавца"))


# ==================== КАТАЛОГ ====================
CATEGORIES = {
    "virtual": {
        "name": "%s ВИРТУАЛЬНЫЕ НОМЕРА" % pe("phone"), "stock_type": "virtual",
        "products": {
            "🇮🇳 Индия (+91)": {"uah": 30, "code": "in"},
            "🇲🇲 Мьянма (+95)": {"uah": 30, "code": "mm"},
            "🇳🇬 Нигерия (+234)": {"uah": 30, "code": "ng"},
            "🇮🇩 Индонезия (+62)": {"uah": 30, "code": "id"},
            "🇺🇸 США (+1)": {"uah": 45, "code": "us"},
            "🇨🇴 Колумбия (+57)": {"uah": 45, "code": "co"},
            "🇧🇩 Бангладеш (+880)": {"uah": 45, "code": "bd"},
            "🇺🇿 Узбекистан (+998)": {"uah": 80, "code": "uz"},
            "🇹🇭 Таиланд (+66)": {"uah": 80, "code": "th"},
            "🇬🇧 Великобритания (+44)": {"uah": 120, "code": "gb"},
            "🇲🇷 Мавритания (+222)": {"uah": 120, "code": "mr"},
            "🇺🇦 Украина (+380)": {"uah": 150, "code": "ua"},
            "🇧🇾 Беларусь (+375)": {"uah": 150, "code": "by"},
            "🇰🇿 Казахстан (+7)": {"uah": 150, "code": "kz"},
            "🇵🇱 Польша (+48)": {"uah": 150, "code": "pl"},
            "🇩🇪 Германия (+49)": {"uah": 150, "code": "de"},
        },
    },
    "physical": {
        "name": "☎️ ФИЗИЧЕСКИЕ НОМЕРА", "stock_type": "physical",
        "products": {
            "🇺🇸 США (+1)": {"uah": 150, "code": "us"},
            "🇺🇦 Украина (+380)": {"uah": 200, "code": "ua"},
            "🇺🇿 Узбекистан (+998)": {"uah": 140, "code": "uz"},
            "🇹🇭 Таиланд (+66)": {"uah": 120, "code": "th"},
            "🇫🇷 Франция (+33)": {"uah": 150, "code": "fr"},
            "🇰🇿 Казахстан (+77)": {"uah": 200, "code": "kz"},
            "🇭🇺 Венгрия (+36)": {"uah": 200, "code": "hu"},
            "🇬🇱 Гренландия (+299)": {"uah": 250, "code": "gl"},
            "🇵🇱 Польша (+48)": {"uah": 250, "code": "pl"},
        },
    },
    "tiktok": {
        "name": "%s TIKTOK" % pe("fire"), "stock_type": "none",
        "products": {
            "Обычный TikTok": {"uah": 50, "code": "tt"},
            "TikTok с эфирами": {"uah": 240, "code": "tt_live"},
        },
    },
    "discord": {
        "name": "%s DISCORD" % pe("chat"), "stock_type": "none",
        "products": {
            "Новый Discord": {"uah": 40, "code": "dc"},
            "Discord с Nitro": {"uah": 150, "code": "dc_nitro"},
        },
    },
    "stars": {"name": "%s TELEGRAM STARS" % pe("star"), "stock_type": "none", "products": {}},
}

STAR_PACKAGES = [
    {"count": 13, "price": 7}, {"count": 21, "price": 15}, {"count": 43, "price": 35},
    {"count": 85, "price": 60}, {"count": 98, "price": 70}, {"count": 106, "price": 75},
    {"count": 128, "price": 80}, {"count": 170, "price": 130},
]


def find_product(category, code):
    cat = CATEGORIES.get(category)
    if not cat:
        return None, None
    for pname, pdata in cat["products"].items():
        if pdata.get("code") == code:
            return pname, pdata
    return None, None


def get_price(category, code):
    """Единый источник цены: каталог + ручные переопределения (/setprice)."""
    ov = load_settings().get("price_override", {}) or {}
    key = "%s:%s" % (category, code)
    if key in ov:
        try:
            return float(ov[key])
        except Exception:
            pass
    _, pd = find_product(category, code)
    return float(pd["uah"]) if pd else 0.0


# ==================== ПОЛЬЗОВАТЕЛИ ====================
def own_ref_code(user_id):
    return hashlib.md5(("%s_ref_salt" % user_id).encode()).hexdigest()[:8].upper()


async def add_user(user_id, username=None, full_name=None, ref_code=None):
    users = load_users()
    referrals = load_referrals()
    key = str(user_id)
    is_new = key not in users
    if is_new:
        users[key] = {"user_id": user_id, "username": username, "full_name": full_name,
                      "first_seen": datetime.now().isoformat(), "last_active": datetime.now().isoformat(),
                      "referred_by": None, "referral_code": None, "total_spent": 0.0, "orders_count": 0,
                      "traffic_source": None, "balance": 0.0, "saved_promo": None}
        if ref_code and ref_code.startswith("ref_"):
            actual = ref_code[4:]
            if actual != own_ref_code(user_id):
                for rid, rdata in referrals.items():
                    if rdata.get("referral_code") == actual:
                        users[key]["referred_by"] = int(rid)
                        rdata.setdefault("referrals_list", []).append(
                            {"user_id": user_id, "username": username, "date": datetime.now().isoformat(),
                             "first_purchase_done": False})
                        break
        elif ref_code:
            users[key]["traffic_source"] = ref_code
            sources = load_traffic_sources()
            if ref_code not in sources:
                sources[ref_code] = {"total_visits": 0, "total_registrations": 0, "total_purchases": 0,
                                     "total_revenue": 0.0, "created_at": datetime.now().isoformat()}
            sources[ref_code]["total_visits"] += 1
            sources[ref_code]["total_registrations"] += 1
            save_traffic_sources(sources)
    else:
        users[key]["last_active"] = datetime.now().isoformat()
        if username:
            users[key]["username"] = username
        if full_name:
            users[key]["full_name"] = full_name
        users[key].setdefault("balance", 0.0)
    code = own_ref_code(user_id)
    users[key]["referral_code"] = code
    referrals.setdefault(key, {"user_id": user_id, "referral_code": code, "referrals_list": [], "total_earned": 0.0})
    referrals[key]["referral_code"] = code
    save_referrals(referrals)
    save_users(users)
    return is_new


def get_balance(uid):
    try:
        return float(load_users().get(str(uid), {}).get("balance", 0) or 0)
    except Exception:
        return 0.0


def add_balance(uid, amount):
    users = load_users()
    k = str(uid)
    if k not in users:
        return False
    users[k]["balance"] = round(float(users[k].get("balance", 0) or 0) + float(amount), 2)
    save_users(users)
    return True


def spend_balance(uid, amount):
    if get_balance(uid) + 1e-9 < amount:
        return False
    return add_balance(uid, -amount)


def get_user_level(uid):
    u = load_users().get(str(uid), {})
    spent = u.get("total_spent", 0) or 0
    levels = [
        ("VIP", get_setting("level_vip_min", 5000), get_setting("level_vip_discount", 10), "crown"),
        ("Платина", get_setting("level_platinum_min", 3000), get_setting("level_platinum_discount", 7), "diamond"),
        ("Золото", get_setting("level_gold_min", 1500), get_setting("level_gold_discount", 5), "medal1"),
        ("Серебро", get_setting("level_silver_min", 500), get_setting("level_silver_discount", 3), "medal2"),
        ("Бронза", get_setting("level_bronze_min", 0), get_setting("level_bronze_discount", 0), "medal3"),
    ]
    for name, mn, d, ek in levels:
        if spent >= mn:
            return {"name": name, "discount": d, "emoji": pe(ek), "min_spent": mn}
    return {"name": "Бронза", "discount": 0, "emoji": pe("medal3"), "min_spent": 0}


# ==================== ПРОМОКОДЫ ====================
def validate_promo(code):
    code = (code or "").strip().upper()
    p = load_promo_codes().get(code)
    if not p:
        return False, None, "Промокод не найден"
    if not p.get("is_active", True):
        return False, None, "Промокод отключён"
    mu = p.get("max_uses")
    if mu and p.get("current_uses", 0) >= mu:
        return False, None, "Лимит использований исчерпан"
    if p.get("expires_at"):
        try:
            if datetime.now() > datetime.fromisoformat(p["expires_at"]):
                return False, None, "Срок действия истёк"
        except Exception:
            pass
    return True, p, ""


def compute_price(uid, category, code, qty, promo_code):
    unit = get_price(category, code)
    base = round(unit * qty, 2)
    lvl = get_user_level(uid)
    lvl_disc = round(base * float(lvl["discount"]) / 100, 2)
    after = base - lvl_disc
    promo_disc = 0.0
    used = None
    if promo_code:
        ok, p, _ = validate_promo(promo_code)
        if ok:
            used = promo_code.strip().upper()
            if p["discount_type"] == "percent":
                promo_disc = round(after * float(p["discount_value"]) / 100, 2)
            else:
                promo_disc = min(float(p["discount_value"]), after)
    total = max(round(after - promo_disc, 2), 0.0)
    return {"unit": unit, "base": base, "level": lvl, "level_disc": lvl_disc,
            "promo": used, "promo_disc": promo_disc, "total": total}


# ==================== ЗАКАЗЫ ====================
STATUS_CONFIG = {
    "awaiting_payment": (pe("time"), "Ожидает оплаты"),
    "paid": (pe("money"), "Оплачен"),
    "completed": (pe("check"), "Выполнен"),
    "rejected": (pe("warn"), "Отклонён"),
    "cancelled": (pe("cross"), "Отменён"),
    "expired": (pe("time"), "Истёк"),
    "refunded": (pe("money"), "Возврат"),
}


def method_label(m):
    return {"uah": "💳 Гривны", "gift": "🎁 Подарок", "balance": "👛 Баланс"}.get(m, str(m))


def generate_short_order_id():
    c = load_order_counter()
    cur = c.get("current", 0) + 1
    c["current"] = cur
    save_order_counter(c)
    return "#%06d" % cur


def find_order_key(orders, oid):
    if not oid:
        return None
    oid = str(oid).strip()
    if oid in orders:
        return oid
    clean = oid.replace("#", "").strip()
    for k, o in orders.items():
        if str(k).replace("#", "").strip() == clean:
            return k
        if str(o.get("short_id", "")).replace("#", "").strip() == clean:
            return k
    return None


def get_order(raw):
    orders = load_orders()
    rk = find_order_key(orders, raw)
    return rk, (orders.get(rk) if rk else None)


def update_order(rk, **fields):
    orders = load_orders()
    o = orders.get(rk)
    if not o:
        return None
    o.update(fields)
    save_orders(orders)
    return o


def order_items(o):
    if o.get("items") is not None:
        return o["items"]
    if o.get("session_name") and o.get("country_code"):
        return [{"country": o["country_code"], "session_name": o["session_name"], "phone": o.get("phone"),
                 "delivered": o.get("status") == "completed"}]
    return []


def cancel_order(rk, status):
    """Снять заказ: освободить аккаунты, вернуть использование промокода."""
    orders = load_orders()
    o = orders.get(rk)
    if not o:
        return None
    for it in order_items(o):
        if not it.get("delivered"):
            release_account(it["country"], it["session_name"])
    promo = o.get("used_promo_code")
    if promo and o.get("promo_counted"):
        promos = load_promo_codes()
        if promo in promos:
            promos[promo]["current_uses"] = max(0, promos[promo].get("current_uses", 0) - 1)
            save_promo_codes(promos)
        o["promo_counted"] = False
    if o.get("paid_by_balance") and not o.get("balance_refunded") and status in ("rejected", "cancelled", "expired"):
        add_balance(o["user_id"], otot(o))
        o["balance_refunded"] = True
    o["status"] = status
    o["closed_at"] = datetime.now().isoformat()
    save_orders(orders)
    return o


# ==================== ПЕРЕХВАТ КОДОВ ====================
active_watchers = {}
watcher_users = {}
watcher_orders = {}
login_notified = set()


async def watch_codes(c, n, user_id, order_key=None):
    key = "%s:%s" % (c, n)
    watcher_users[key] = user_id
    if order_key:
        watcher_orders[key] = order_key
    if key in active_watchers:
        return
    active_watchers[key] = None
    sess = watcher_path(c, n)
    if not os.path.exists(sess):
        sess = session_path(c, n)
    if not os.path.exists(sess):
        active_watchers.pop(key, None)
        return
    client = TelegramClient(sess.replace(".session", ""), API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            try:
                await bot.send_message(user_id, "%s Сессия недействительна. %s" % (pe("warn"), SELLER))
            except Exception:
                pass
            return
        meta = load_meta(c, n) or {}

        @client.on(events.NewMessage(from_users=[777000]))
        async def handler(event):
            text = event.message.text or ""
            target = watcher_users.get(key)
            if not target:
                return
            m = re.search(r"\b(\d{5})\b", text)
            if m:
                msg = "%s <b>КОД ПОДТВЕРЖДЕНИЯ</b>\n\n<code>%s</code>\n\n" % (pe("key"), m.group(1))
                if meta.get("password"):
                    msg += "%s <b>Пароль (2FA):</b> <code>%s</code>\n\n" % (pe("lock"), esc(meta["password"]))
                msg += "Введите код в Telegram сейчас же!"
                try:
                    await bot.send_message(target, msg)
                except Exception as e:
                    logger.error("Send code: %s", e)
                return
            low = text.lower()
            if any(s in low for s in ["новый вход", "new login", "вы вошли", "you have logged in",
                                      "новое устройство", "new device", "новый вхід"]):
                nk = (key, target)
                if nk in login_notified:
                    return
                login_notified.add(nk)
                ok_key = watcher_orders.get(key)
                reviewed = False
                if ok_key:
                    _, oo = get_order(ok_key)
                    reviewed = bool(oo and oo.get("reviewed"))
                try:
                    kb = InlineKeyboardBuilder()
                    if ok_key and not reviewed:
                        ibtn(kb, "Оставить отзыв", callback_data="leave_review_%s" % ok_key, icon_key="star", style="success")
                    ibtn(kb, "Мои аккаунты", callback_data="my_accounts", icon_key="box")
                    kb.adjust(1)
                    await bot.send_message(
                        target,
                        "%s <b>ВХОД ПОДТВЕРЖДЁН!</b>\n\n%s Сессия: <code>%s</code>\n%s Аккаунт успешно вошёл.\n\n"
                        "Пожалуйста, оставь отзыв!" % (pe("check"), pe("phone"), esc(n), pe("sparkle")),
                        reply_markup=kb.as_markup())
                except Exception as e:
                    logger.error("Login notify: %s", e)
                try:
                    await bot.send_message(
                        ADMIN_ID, "%s <b>ПОКУПАТЕЛЬ ВОШЁЛ</b>\n\n%s ID: <code>%s</code>\n%s Сессия: <code>%s</code>\n🆔 Заказ: <code>%s</code>"
                        % (pe("check"), pe("user"), target, pe("phone"), esc(n), esc(ok_key or "—")))
                except Exception:
                    pass

        active_watchers[key] = client
        await client.run_until_disconnected()
    except Exception as e:
        logger.error("Watcher %s: %s", key, e)
    finally:
        active_watchers.pop(key, None)
        try:
            await client.disconnect()
        except Exception:
            pass


async def start_code_watcher(c, n, uid, order_key=None):
    await watch_codes(c, n, uid, order_key)


async def ensure_recent_watchers(days=3):
    """Поднять наблюдателей для недавно проданных аккаунтов (остальные — по кнопке «Запросить код»)."""
    limit = datetime.now() - timedelta(days=days)
    for rk, o in load_orders().items():
        if o.get("status") != "completed":
            continue
        try:
            done = datetime.fromisoformat(o.get("completed_at") or o["created_at"])
        except Exception:
            continue
        if done < limit:
            continue
        for it in order_items(o):
            if it.get("delivered", True):
                key = "%s:%s" % (it["country"], it["session_name"])
                if key not in active_watchers:
                    asyncio.create_task(start_code_watcher(it["country"], it["session_name"], o["user_id"], rk))
                    await asyncio.sleep(0.5)


# ==================== FSM ====================
class ReviewStates(StatesGroup):
    waiting_for_stars = State()
    waiting_for_photo_or_skip = State()
    waiting_for_text = State()


class OrderStates(StatesGroup):
    checkout = State()
    waiting_for_promo = State()


class ReceiptStates(StatesGroup):
    waiting = State()


class AdminStates(StatesGroup):
    waiting_for_requisites_edit = State()
    waiting_for_broadcast = State()
    confirm_broadcast = State()


class AdminStockStates(StatesGroup):
    waiting_for_session = State()


class AdminLevelStates(StatesGroup):
    waiting_for_min_spent = State()
    waiting_for_discount = State()


class AdminReferralSettingsStates(StatesGroup):
    waiting_for_bonus_percent = State()
    waiting_for_partner_percent = State()


class AdminChatStates(StatesGroup):
    waiting_for_message = State()


class AdminSettingsStates(StatesGroup):
    waiting_for_ttl = State()


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


# ==================== ОБЩИЕ ХЕЛПЕРЫ UI ====================
IS_ADMIN = F.from_user.id == ADMIN_ID
NOT_ADMIN = F.from_user.id != ADMIN_ID


def MENU(word):
    """Кнопка обычной клавиатуры: ищем ключевое слово, но только в коротких сообщениях."""
    return F.text.contains(word) & (F.text.len() <= 30)


async def show(target, text, kb=None):
    """Отредактировать сообщение, а если нельзя — отправить новое."""
    try:
        await target.edit_text(text, reply_markup=kb)
    except Exception as e:
        if "not modified" in str(e).lower():
            return
        try:
            await target.answer(text, reply_markup=kb)
        except Exception as e2:
            logger.error("show: %s", e2)


async def out(event, text, kb=None):
    if isinstance(event, types.CallbackQuery):
        await show(event.message, text, kb)
    else:
        await event.answer(text, reply_markup=kb)


async def ack(event):
    if isinstance(event, types.CallbackQuery):
        try:
            await event.answer()
        except Exception:
            pass


async def alert(cb, text):
    await cb.answer(text, show_alert=True)


async def stale(cb):
    await cb.answer("⚠️ Кнопка устарела — откройте меню заново", show_alert=True)


def back_kb(cb_data, text="Назад"):
    kb = InlineKeyboardBuilder()
    ibtn(kb, text, callback_data=cb_data, icon_key="back", style="danger")
    return kb.as_markup()


# ==================== КЛАВИАТУРЫ ====================
def get_main_reply_keyboard():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="⭐ Купить звёзды"))
    b.row(KeyboardButton(text="📋 Мои заказы"), KeyboardButton(text="📦 Мои аккаунты"))
    b.row(KeyboardButton(text="💬 Отзывы"), KeyboardButton(text="❓ FAQ"))
    b.row(KeyboardButton(text="👤 Профиль"), KeyboardButton(text="🎁 Рефералы"))
    b.row(KeyboardButton(text="🎟 Промокод"), KeyboardButton(text="📢 Канал"))
    return b.as_markup(resize_keyboard=True)


def get_admin_reply_keyboard():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📊 Статистика"), KeyboardButton(text="🛍 Все заказы"))
    b.row(KeyboardButton(text="⏱ Ожидают"), KeyboardButton(text="✅ Выполненные"))
    b.row(KeyboardButton(text="📦 Склад"), KeyboardButton(text="💰 Реквизиты"))
    b.row(KeyboardButton(text="📢 Рассылка"), KeyboardButton(text="👥 Пользователи"))
    b.row(KeyboardButton(text="📈 Панель"), KeyboardButton(text="🏠 Главное меню"))
    b.row(KeyboardButton(text="🎟 Промокоды"), KeyboardButton(text="⭐ Уровни"))
    b.row(KeyboardButton(text="🎁 Рефералы"), KeyboardButton(text="📉 Аналитика"))
    b.row(KeyboardButton(text="🔗 Источники"), KeyboardButton(text="💾 Бэкапы"))
    b.row(KeyboardButton(text="⚙️ Настройки"))
    return b.as_markup(resize_keyboard=True)


def subscribe_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Подписаться", url="https://t.me/owerpass_store", icon_key="megaphone", style="primary")
    ibtn(kb, "Я подписался", callback_data="check_sub", icon_key="check", style="success")
    kb.adjust(1)
    return kb.as_markup()


def main_menu_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Каталог", callback_data="menu_catalog", icon_key="cart", style="primary")
    ibtn(kb, "Купить звёзды", callback_data="menu_stars", icon_key="star", style="primary")
    ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
    ibtn(kb, "Мои аккаунты", callback_data="my_accounts", icon_key="box")
    ibtn(kb, "Отзывы", callback_data="menu_reviews", icon_key="chat")
    ibtn(kb, "Профиль", callback_data="profile_menu", icon_key="user")
    ibtn(kb, "Рефералы", callback_data="referral_menu", icon_key="gift")
    ibtn(kb, "Промокод", callback_data="promo_menu", icon_key="ticket")
    kb.adjust(2, 2, 2, 2)
    return kb.as_markup()


def catalog_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Виртуальные номера", callback_data="cat_virtual", icon_key="phone", style="primary")
    ibtn(kb, "Физические номера", callback_data="cat_physical", icon_key="card", style="primary")
    ibtn(kb, "TikTok", callback_data="cat_tiktok", icon_key="fire", style="primary")
    ibtn(kb, "Discord", callback_data="cat_discord", icon_key="chat", style="primary")
    if stars_enabled():
        ibtn(kb, "Telegram Stars", callback_data="cat_stars", icon_key="star", style="primary")
    else:
        ibtn(kb, "Звёзды недоступны", callback_data="stars_off", icon_key="cross", style="danger")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="back", style="danger")
    kb.adjust(1)
    return kb.as_markup()


def category_products_keyboard(category):
    kb = InlineKeyboardBuilder()
    cat = CATEGORIES[category]
    st = cat.get("stock_type", "none")
    counts = stock_count(st) if st != "none" else {}
    for pname, pdata in cat["products"].items():
        code = pdata["code"]
        price = money(get_price(category, code))
        if st == "none":
            ibtn(kb, "%s — %s₴" % (pname, price), callback_data="product_%s_%s" % (category, code))
        else:
            n = counts.get(code, 0)
            if n > 0:
                ibtn(kb, "%s — %s шт. | %s₴" % (pname, n, price), callback_data="product_%s_%s" % (category, code),
                     icon_key="fire" if n < 5 else None)
            else:
                ibtn(kb, "❌ %s — НЕТ" % pname, callback_data="out_of_stock", style="danger")
    ibtn(kb, "В каталог", callback_data="menu_catalog", icon_key="back", style="danger")
    kb.adjust(1)
    return kb.as_markup()


def quantity_keyboard(maxq):
    kb = InlineKeyboardBuilder()
    for i in range(1, maxq + 1):
        kb.button(text="%d шт." % i, callback_data="qty_%d" % i)
    kb.adjust(5)
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="cross", style="danger")
    kb.adjust(5, 1)
    return kb.as_markup()


def awaiting_payment_keyboard(rk):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Я оплатил — отправить чек", callback_data="paid_%s" % rk, icon_key="check", style="success")
    ibtn(kb, "Написать продавцу", url="https://t.me/MaskYoY", icon_key="chat", style="primary")
    ibtn(kb, "Написать в боте", callback_data="support_%s" % rk, icon_key="warn")
    ibtn(kb, "Отменить заказ", callback_data="ucancel_%s" % rk, icon_key="cross", style="danger")
    ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
    kb.adjust(1)
    return kb.as_markup()


def user_order_actions_keyboard(rk, o=None, idx=None):
    if o is None:
        _, o = get_order(rk)
    items = order_items(o) if o else []
    kb = InlineKeyboardBuilder()
    if items:
        if idx is not None:
            ibtn(kb, "Запросить код", callback_data="code_%s_%d" % (rk, idx), icon_key="key", style="primary")
        else:
            for i, it in enumerate(items):
                label = "Запросить код" if len(items) == 1 else "Код: %s" % it.get("phone")
                ibtn(kb, label, callback_data="code_%s_%d" % (rk, i), icon_key="key", style="primary")
    if not (o and o.get("reviewed")):
        ibtn(kb, "Оставить отзыв", callback_data="leave_review_%s" % rk, icon_key="star", style="success")
    if items:
        ibtn(kb, "Запросить замену", callback_data="user_replace_%s" % rk, icon_key="refresh")
    ibtn(kb, "Запросить возврат", callback_data="user_refund_%s" % rk, icon_key="money", style="danger")
    ibtn(kb, "Все заказы", callback_data="my_orders", icon_key="cart")
    kb.adjust(1)
    return kb.as_markup()


def reviews_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Посмотреть отзывы", url="https://t.me/owerpass_repa", icon_key="star", style="primary")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="back", style="danger")
    kb.adjust(1)
    return kb.as_markup()


def rating_keyboard():
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        ibtn(kb, "%d ⭐" % i, callback_data="rate_%d" % i)
    kb.adjust(5)
    return kb.as_markup()


def review_photo_skip_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Пропустить фото", callback_data="skip_photo", icon_key="check", style="primary")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="cross", style="danger")
    kb.adjust(1)
    return kb.as_markup()


def moderation_keyboard(rid):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Одобрить", callback_data="approve_%s" % rid, icon_key="check", style="success")
    ibtn(kb, "Отклонить", callback_data="reject_%s" % rid, icon_key="cross", style="danger")
    kb.adjust(2)
    return kb.as_markup()


def profile_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Мои аккаунты", callback_data="my_accounts", icon_key="box")
    ibtn(kb, "Рефералы", callback_data="referral_menu", icon_key="gift")
    ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
    ibtn(kb, "Промокод", callback_data="promo_menu", icon_key="ticket")
    ibtn(kb, "Главное меню", callback_data="main_menu", icon_key="back", style="danger")
    kb.adjust(1)
    return kb.as_markup()


def admin_dashboard_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Заказы", callback_data="aol_all_0", icon_key="cart")
    ibtn(kb, "Склад", callback_data="admin_stock_menu", icon_key="box")
    ibtn(kb, "Рефералы", callback_data="admin_referrals_dashboard", icon_key="gift")
    ibtn(kb, "Промокоды", callback_data="admin_promo_dashboard", icon_key="ticket")
    ibtn(kb, "Уровни", callback_data="admin_levels_dashboard", icon_key="star")
    ibtn(kb, "Аналитика", callback_data="admin_analytics_dashboard", icon_key="chart_up")
    ibtn(kb, "Источники", callback_data="admin_traffic_dashboard", icon_key="link")
    ibtn(kb, "Бэкапы", callback_data="admin_backups", icon_key="save")
    ibtn(kb, "Настройки", callback_data="admin_settings", icon_key="gear")
    ibtn(kb, "Обновить", callback_data="admin_dashboard_refresh", icon_key="refresh")
    kb.adjust(2, 2, 2, 2, 2)
    return kb.as_markup()


FAQ_TEXT = (
    "%s <b>КАК КУПИТЬ?</b>\n\n"
    "%s <b>Аккаунты:</b>\n1. Выберите категорию и страну\n2. Выберите количество\n"
    "3. Примените промокод (по желанию)\n4. Оплатите и нажмите «Я оплатил», отправьте чек\n"
    "5. После проверки аккаунт придёт автоматически\n\n"
    "%s <b>Звёзды:</b>\n1. Выберите пакет\n2. Оплатите — подарок придёт в ЛС от продавца\n\n"
    "%s <b>Как войти в аккаунт:</b>\n1. Получите .session файл\n2. Войдите в Telegram по номеру\n"
    "3. Нажмите «Запросить код» (Мои аккаунты)\n4. Бот перешлёт код автоматически\n\n"
    "%s <b>Баланс:</b> бонусы за рефералов зачисляются на баланс и списываются при оплате.\n\n"
    "%s %s\n%s @owerpass_store"
) % (pe("warn"), pe("cart"), pe("star"), pe("key"), pe("gift"), pe("chat"), SELLER, pe("megaphone"))


# ==================== ПОДПИСКА (MIDDLEWARE) ====================
_sub_cache = {}
_sub_warned = False


async def check_subscription(uid):
    global _sub_warned
    now = time.time()
    c = _sub_cache.get(uid)
    if c and now - c < 300:
        return True
    try:
        m = await bot.get_chat_member(chat_id=int(STORE_CHANNEL_ID), user_id=uid)
        ok = str(getattr(m.status, "value", m.status)) in ("member", "administrator", "creator") or \
            bool(getattr(m, "is_member", False))
        if ok:
            _sub_cache[uid] = now
        return ok
    except Exception as e:
        # Бот не админ в канале / канал недоступен — не блокируем магазин, предупреждаем админа
        logger.warning("check_subscription: %s", e)
        if not _sub_warned:
            _sub_warned = True
            try:
                await bot.send_message(ADMIN_ID, "%s Проверка подписки не работает: <code>%s</code>\n"
                                       "Добавьте бота админом в канал. Пока подписка не проверяется."
                                       % (pe("warn"), esc(str(e)[:200])))
            except Exception:
                pass
        return True


class SubscriptionMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if not user or user.id == ADMIN_ID:
            return await handler(event, data)
        if isinstance(event, types.Message) and event.text and event.text.startswith("/start"):
            return await handler(event, data)
        if isinstance(event, types.CallbackQuery) and event.data == "check_sub":
            return await handler(event, data)
        if await check_subscription(user.id):
            return await handler(event, data)
        text = "%s Для использования магазина подпишитесь на канал!" % pe("warn")
        try:
            if isinstance(event, types.CallbackQuery):
                await event.answer()
                await event.message.answer(text, reply_markup=subscribe_keyboard())
            else:
                await event.answer(text, reply_markup=subscribe_keyboard())
        except Exception:
            pass
        return None


dp.message.outer_middleware(SubscriptionMiddleware())
dp.callback_query.outer_middleware(SubscriptionMiddleware())


# ==================== КОМАНДЫ / СТАРТ ====================
@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    kb = get_admin_reply_keyboard() if message.from_user.id == ADMIN_ID else get_main_reply_keyboard()
    await message.answer("%s Отменено" % pe("cross"), reply_markup=kb)


@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    ref_code = None
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1:
        ref_code = parts[1].strip()
    is_new = await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name, ref_code=ref_code)
    if message.from_user.id == ADMIN_ID:
        await message.answer("%s <b>Админ-панель</b>" % pe("warn"), reply_markup=get_admin_reply_keyboard())
        return
    if not await check_subscription(message.from_user.id):
        await message.answer("%s Подпишитесь на канал!" % pe("warn"), reply_markup=subscribe_keyboard())
        return
    text = ("%s <b>Добро пожаловать в OverPass Store!</b>\n\n%s Виртуальные и физические номера\n"
            "%s Telegram Stars\n%s TikTok и Discord аккаунты\n\n"
            % (pe("sparkle"), pe("rocket"), pe("star"), pe("fire")))
    if is_new and ref_code and ref_code.startswith("ref_"):
        text += "%s Вы зарегистрированы по реферальной ссылке!\n\n" % pe("gift")
    text += "Выберите раздел:"
    await message.answer(text, reply_markup=get_main_reply_keyboard())


@dp.message(Command("menu"), NOT_ADMIN)
async def cmd_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("%s <b>Меню</b>" % pe("sparkle"), reply_markup=main_menu_keyboard())


@dp.message(Command("admin"), IS_ADMIN)
async def cmd_admin(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("%s <b>Админ-панель</b>" % pe("warn"), reply_markup=get_admin_reply_keyboard())


@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: types.CallbackQuery):
    if await check_subscription(callback.from_user.id):
        await callback.answer()
        await show(callback.message, "%s Спасибо! Подписка подтверждена." % pe("check"), main_menu_keyboard())
        await callback.message.answer("Навигация доступна внизу ⬇️", reply_markup=get_main_reply_keyboard())
    else:
        await callback.answer("❌ Вы ещё не подписались!", show_alert=True)


@dp.callback_query(F.data == "main_menu")
async def go_main(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await show(callback.message, "%s <b>Меню</b>" % pe("sparkle"), main_menu_keyboard())


# ==================== КНОПКИ ОБЫЧНОЙ КЛАВИАТУРЫ (ПОЛЬЗОВАТЕЛЬ) ====================
@dp.message(NOT_ADMIN, MENU("Каталог"))
@dp.callback_query(F.data == "menu_catalog")
async def open_catalog(event, state: FSMContext):
    await ack(event)
    await state.clear()
    await out(event, "%s Категории:" % pe("cart"), catalog_keyboard())


@dp.message(NOT_ADMIN, MENU("Купить звёзды"))
@dp.callback_query(F.data == "menu_stars")
async def stars_menu(event, state: FSMContext):
    if not stars_enabled():
        if isinstance(event, types.CallbackQuery):
            await event.answer("❌ Звёзды временно недоступны", show_alert=True)
        else:
            await event.answer("❌ Звёзды временно недоступны")
        return
    await ack(event)
    await state.clear()
    kb = InlineKeyboardBuilder()
    for pkg in STAR_PACKAGES:
        ibtn(kb, "%d ⭐ — %s ₴" % (pkg["count"], money(pkg["price"])), callback_data="starpkg_%d" % pkg["count"],
             icon_key="star", style="primary")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="back", style="danger")
    kb.adjust(2)
    await out(event, "%s <b>ПОКУПКА TELEGRAM STARS</b>\n\n%s Выберите пакет:\n\n<i>Звёзды приходят в ЛС от продавца после оплаты</i>"
              % (pe("star"), pe("sparkle")), kb.as_markup())


@dp.callback_query(F.data == "stars_off")
async def stars_off(callback: types.CallbackQuery):
    await callback.answer("❌ Звёзды временно недоступны", show_alert=True)


@dp.message(NOT_ADMIN, MENU("Отзывы"))
@dp.callback_query(F.data == "menu_reviews")
async def open_reviews(event, state: FSMContext):
    await ack(event)
    await state.clear()
    await out(event, "%s Отзывы наших клиентов:" % pe("chat"), reviews_keyboard())


@dp.message(NOT_ADMIN, MENU("FAQ"))
async def faq(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(FAQ_TEXT, reply_markup=get_main_reply_keyboard())


@dp.message(NOT_ADMIN, MENU("Канал"))
async def channel(message: types.Message, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Перейти", url="https://t.me/owerpass_store", icon_key="megaphone", style="primary")
    await message.answer("%s Наш канал:" % pe("megaphone"), reply_markup=kb.as_markup())


@dp.callback_query(F.data == "out_of_stock")
async def out_of_stock(callback: types.CallbackQuery):
    await callback.answer("❌ Товар закончился", show_alert=True)


# ==================== КАТАЛОГ / ОФОРМЛЕНИЕ ЗАКАЗА ====================
@dp.callback_query(F.data.startswith("cat_"))
async def show_category(callback: types.CallbackQuery, state: FSMContext):
    cat = callback.data[4:]
    if cat not in CATEGORIES:
        return await stale(callback)
    if cat == "stars":
        return await stars_menu(callback, state)
    await callback.answer()
    await state.clear()
    await show(callback.message, "%s\n\nВыберите товар:" % CATEGORIES[cat]["name"], category_products_keyboard(cat))


@dp.callback_query(F.data.startswith("product_"))
async def product_selected(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_", 2)
    if len(parts) < 3 or parts[1] not in CATEGORIES:
        return await stale(callback)
    category, code = parts[1], parts[2]
    pname, _ = find_product(category, code)
    if not pname:
        return await stale(callback)
    st = CATEGORIES[category].get("stock_type", "none")
    maxq = 5
    if st != "none":
        n = len(all_available(code, st))
        if n <= 0:
            return await alert(callback, "❌ Нет в наличии")
        maxq = min(5, n)
    await callback.answer()
    saved = load_users().get(str(callback.from_user.id), {}).get("saved_promo")
    await state.set_data({"category": category, "code": code, "product": pname, "stock_type": st,
                          "qty": 1, "promo": saved})
    await state.set_state(OrderStates.checkout)
    await show(callback.message, "%s <b>%s</b>\n%s Цена: %s ₴ за шт.\n\n🔢 Выберите количество:"
               % (pe("check"), esc(pname), pe("money"), money(get_price(category, code))), quantity_keyboard(maxq))


def checkout_view(uid, data):
    pr = compute_price(uid, data["category"], data["code"], data["qty"], data.get("promo"))
    lines = ["%s <b>ОФОРМЛЕНИЕ</b>\n" % pe("cart"),
             "%s %s × %d" % (pe("box"), esc(data["product"]), data["qty"]),
             "%s Цена: %s ₴" % (pe("money"), money(pr["base"]))]
    if pr["level_disc"] > 0:
        lines.append("%s Скидка уровня %s %s: −%s ₴" % (pe("star"), pr["level"]["emoji"], pr["level"]["name"], money(pr["level_disc"])))
    if pr["promo"]:
        lines.append("%s Промокод <code>%s</code>: −%s ₴" % (pe("ticket"), esc(pr["promo"]), money(pr["promo_disc"])))
    lines.append("\n%s <b>Итого: %s ₴</b>" % (pe("money"), money(pr["total"])))
    bal = get_balance(uid)
    if bal > 0:
        lines.append("%s Ваш баланс: %s ₴" % (pe("diamond"), money(bal)))
    lines.append("\nВыберите способ оплаты:")
    kb = InlineKeyboardBuilder()
    if pr["promo"]:
        ibtn(kb, "Убрать промокод", callback_data="promo_remove", icon_key="cross")
    else:
        ibtn(kb, "Ввести промокод", callback_data="promo_enter", icon_key="ticket")
    ibtn(kb, "Оплатить гривнами", callback_data="pay_uah", icon_key="money", style="primary")
    ibtn(kb, "Оплатить подарком", callback_data="pay_gift", icon_key="gift")
    if bal + 1e-9 >= pr["total"] > 0:
        ibtn(kb, "Оплатить с баланса", callback_data="pay_balance", icon_key="diamond", style="success")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="cross", style="danger")
    kb.adjust(1)
    return "\n".join(lines), kb.as_markup(), pr


async def render_checkout(event, state, uid):
    data = await state.get_data()
    if "category" not in data:
        return False
    text, kb, pr = checkout_view(uid, data)
    if data.get("promo") and not pr["promo"]:
        await state.update_data(promo=None)
    await state.set_state(OrderStates.checkout)
    await out(event, text, kb)
    return True


@dp.callback_query(F.data.startswith("qty_"))
async def process_quantity(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "category" not in data:
        return await stale(callback)
    try:
        qty = int(callback.data[4:])
    except ValueError:
        return await stale(callback)
    if data["stock_type"] != "none" and len(all_available(data["code"], data["stock_type"])) < qty:
        return await alert(callback, "❌ Столько нет в наличии")
    await callback.answer()
    await state.update_data(qty=qty)
    await render_checkout(callback, state, callback.from_user.id)


@dp.callback_query(F.data == "promo_enter")
async def promo_enter(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "category" not in data:
        return await stale(callback)
    await callback.answer()
    await state.set_state(OrderStates.waiting_for_promo)
    await show(callback.message, "%s Отправьте промокод сообщением:" % pe("ticket"), back_kb("promo_back", "Назад к оплате"))


@dp.callback_query(F.data == "promo_back")
async def promo_back(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if not await render_checkout(callback, state, callback.from_user.id):
        await show(callback.message, "%s <b>Меню</b>" % pe("sparkle"), main_menu_keyboard())


@dp.callback_query(F.data == "promo_remove")
async def promo_remove(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(promo=None)
    if not await render_checkout(callback, state, callback.from_user.id):
        await stale(callback)


@dp.message(OrderStates.waiting_for_promo, F.text)
async def order_promo_input(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    ok, p, reason = validate_promo(code)
    if not ok:
        await message.answer("%s %s. Введите другой промокод:" % (pe("cross"), reason), reply_markup=back_kb("promo_back", "Назад к оплате"))
        return
    await state.update_data(promo=code)
    await message.answer("%s Промокод <code>%s</code> применён!" % (pe("check"), esc(code)))
    await render_checkout(message, state, message.from_user.id)


@dp.callback_query(F.data.startswith("pay_"))
async def process_payment(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    method = callback.data[4:]
    if "category" not in data or method not in ("uah", "gift", "balance"):
        return await stale(callback)
    _, _, pr = checkout_view(callback.from_user.id, data)
    if method == "balance" and get_balance(callback.from_user.id) + 1e-9 < pr["total"]:
        return await alert(callback, "❌ Недостаточно средств на балансе")
    await callback.answer()
    await state.update_data(method=method)
    text = ("%s <b>Подтверждение</b>\n\nТовар: %s × %d\nОплата: %s\n%sСумма: <b>%s ₴</b>\n\nПодтвердить?"
            % (pe("cart"), esc(data["product"]), data["qty"], method_label(method),
               ("%s Промокод: <code>%s</code>\n" % (pe("ticket"), esc(pr["promo"]))) if pr["promo"] else "",
               money(pr["total"])))
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Подтвердить", callback_data="confirm_order", icon_key="check", style="success")
    ibtn(kb, "Назад", callback_data="promo_back", icon_key="back")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="cross", style="danger")
    kb.adjust(1)
    await show(callback.message, text, kb.as_markup())


def admin_order_notice(rk, o, title):
    items = order_items(o)
    ph = ", ".join(str(i.get("phone")) for i in items) if items else "—"
    return ("%s <b>%s %s</b>\n\n%s %s | %s\n🆔 <code>%s</code>\n%s %s\n%s Номера: %s\n%s %s ₴ | %s\n%s"
            % (pe("sparkle"), title, rk, pe("user"), uname(o.get("username")), esc(o.get("full_name")), o["user_id"],
               pe("cart"), esc(o["product"]), pe("phone"), esc(ph), pe("money"), money(otot(o)),
               method_label(o.get("payment_method")),
               ("\n%s Промо: %s" % (pe("ticket"), esc(o["used_promo_code"]))) if o.get("used_promo_code") else ""))


def open_order_kb(rk):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Открыть заказ", callback_data="ao_view_%s" % rk, icon_key="cart", style="primary")
    return kb.as_markup()


async def place_order(callback, *, category, product, code, items, qty, total, method, promo=None, is_stars=False):
    u = callback.from_user
    rk = generate_short_order_id()
    if method == "balance":
        if not spend_balance(u.id, total):
            for it in items:
                release_account(it["country"], it["session_name"])
            await callback.message.answer("%s Недостаточно средств на балансе" % pe("cross"))
            return None
    first = items[0] if items else {}
    order = {
        "order_id": rk, "short_id": rk, "user_id": u.id, "username": u.username, "full_name": u.full_name,
        "category": category, "product": product, "code": code, "qty": qty, "items": items,
        "country_code": first.get("country"), "session_name": first.get("session_name"), "phone": first.get("phone"),
        "payment_method": method, "total": total, "used_promo_code": promo, "promo_counted": bool(promo),
        "status": "awaiting_payment", "created_at": datetime.now().isoformat(), "reviewed": False,
        "is_stars": is_stars, "paid_by_balance": method == "balance",
    }
    orders = load_orders()
    orders[rk] = order
    save_orders(orders)
    if promo:
        promos = load_promo_codes()
        if promo in promos:
            promos[promo]["current_uses"] = promos[promo].get("current_uses", 0) + 1
            save_promo_codes(promos)

    title = "ЗАКАЗ НА ЗВЁЗДЫ" if is_stars else "НОВЫЙ ЗАКАЗ"
    try:
        await bot.send_message(ADMIN_ID, admin_order_notice(rk, order, title), reply_markup=open_order_kb(rk))
    except Exception as e:
        logger.error("Admin notify: %s", e)

    if method == "balance":
        update_order(rk, status="paid", paid_at=datetime.now().isoformat())
        if items:
            await show(callback.message, "%s <b>Заказ %s оплачен с баланса!</b>\nОтправляю аккаунт…" % (pe("check"), rk))
            await deliver_order(rk)
        else:
            await show(callback.message, "%s <b>Заказ %s оплачен с баланса!</b>\n\nПродавец %s выдаст товар в ближайшее время."
                       % (pe("check"), rk, SELLER), back_kb("my_orders", "Мои заказы"))
        return rk

    req = get_requisites("uah" if method == "uah" else "gift")
    ttl = int(get_setting("order_ttl_minutes", 60))
    await show(callback.message,
               "%s <b>Заказ %s создан!</b>\n\n%s %s\n%s <b>%s ₴</b>\n\n<b>РЕКВИЗИТЫ:</b>\n%s\n\n"
               "%s После оплаты нажмите «Я оплатил» и отправьте чек.\n%s Заказ без оплаты отменится через %d мин."
               % (pe("check"), rk, pe("cart"), esc(product) + (" × %d" % qty if qty > 1 else ""),
                  pe("money"), money(total), req, pe("warn"), pe("time"), ttl),
               awaiting_payment_keyboard(rk))
    return rk


@dp.callback_query(F.data == "confirm_order")
async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if "category" not in data or "method" not in data:
        return await stale(callback)
    if not throttle(callback.from_user.id, "confirm_order"):
        return await callback.answer()
    await callback.answer()
    uid = callback.from_user.id
    category, code, qty, method = data["category"], data["code"], data["qty"], data["method"]
    st = data["stock_type"]
    pr = compute_price(uid, category, code, qty, data.get("promo"))
    if method == "balance" and get_balance(uid) + 1e-9 < pr["total"]:
        await state.clear()
        await show(callback.message, "%s Недостаточно средств на балансе" % pe("cross"), main_menu_keyboard())
        return
    items = []
    if st != "none":
        accs = reserve_accounts(code, uid, st, qty)
        if not accs:
            await state.clear()
            await show(callback.message, "%s Товар закончился!" % pe("cross"), main_menu_keyboard())
            return
        items = [{"country": a["country"], "session_name": a["session_name"], "phone": a["phone"], "delivered": False}
                 for a in accs]
    await state.clear()
    await place_order(callback, category=category, product=data["product"], code=code, items=items, qty=qty,
                      total=pr["total"], method=method, promo=pr["promo"])


# ==================== ЗВЁЗДЫ ====================
@dp.callback_query(F.data.startswith("starpkg_"))
async def star_pkg_selected(callback: types.CallbackQuery):
    if not stars_enabled():
        return await alert(callback, "❌ Звёзды временно недоступны")
    try:
        count = int(callback.data[8:])
    except ValueError:
        return await stale(callback)
    pkg = next((p for p in STAR_PACKAGES if p["count"] == count), None)
    if not pkg:
        return await alert(callback, "❌ Пакет не найден")
    await callback.answer()
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Оплатить гривнами", callback_data="starbuy_%d_uah" % count, icon_key="money", style="primary")
    if get_balance(callback.from_user.id) + 1e-9 >= pkg["price"]:
        ibtn(kb, "Оплатить с баланса", callback_data="starbuy_%d_balance" % count, icon_key="diamond", style="success")
    ibtn(kb, "Назад", callback_data="menu_stars", icon_key="back", style="danger")
    kb.adjust(1)
    await show(callback.message, "%s <b>Пакет: %d ⭐</b>\n\n%s Сумма к оплате: <b>%s ₴</b>\n\nВыберите способ оплаты:"
               % (pe("star"), count, pe("money"), money(pkg["price"])), kb.as_markup())


@dp.callback_query(F.data.startswith("starbuy_"))
async def star_buy(callback: types.CallbackQuery):
    if not stars_enabled():
        return await alert(callback, "❌ Звёзды временно недоступны")
    try:
        _, cnt, method = callback.data.split("_")
        count = int(cnt)
    except ValueError:
        return await stale(callback)
    pkg = next((p for p in STAR_PACKAGES if p["count"] == count), None)
    if not pkg or method not in ("uah", "balance"):
        return await stale(callback)
    if not throttle(callback.from_user.id, callback.data):
        return await callback.answer()
    await callback.answer()
    await place_order(callback, category="stars", product="%d ⭐" % count, code="stars", items=[], qty=1,
                      total=float(pkg["price"]), method=method, is_stars=True)


# ==================== ОПЛАТА: ЧЕК / ОТМЕНА ====================
@dp.callback_query(F.data.startswith("paid_"))
async def user_paid(callback: types.CallbackQuery, state: FSMContext):
    rk, o = get_order(callback.data[5:])
    if not o or o["user_id"] != callback.from_user.id:
        return await stale(callback)
    if o["status"] != "awaiting_payment":
        return await alert(callback, "Заказ уже в статусе: %s" % STATUS_CONFIG.get(o["status"], ("", o["status"]))[1])
    await callback.answer()
    await state.set_state(ReceiptStates.waiting)
    await state.update_data(receipt_order=rk)
    await callback.message.answer("%s Отправьте чек об оплате (скриншот, файл или текст). Для отмены — /cancel" % pe("card"))


@dp.message(ReceiptStates.waiting)
async def receive_receipt(message: types.Message, state: FSMContext):
    d = await state.get_data()
    rk, o = get_order(d.get("receipt_order"))
    if not o:
        await state.clear()
        return await message.answer("%s Заказ не найден" % pe("cross"))
    if not (message.photo or message.document or message.text):
        return await message.answer("%s Отправьте фото, файл или текст чека" % pe("warn"))
    try:
        await bot.send_message(ADMIN_ID, "%s <b>ЧЕК по заказу %s</b>\n%s %s | %s ₴" % (
            pe("card"), rk, pe("user"), uname(message.from_user.username), money(otot(o))), reply_markup=
            _admin_card_kb(rk, o))
        await bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
    except Exception as e:
        logger.error("receipt: %s", e)
        return await message.answer("%s Не удалось отправить чек, напишите %s" % (pe("cross"), SELLER))
    update_order(rk, receipt_sent=True, receipt_at=datetime.now().isoformat())
    await state.clear()
    await message.answer("%s Чек отправлен продавцу! Оплата проверяется, обычно это занимает несколько минут." % pe("check"),
                         reply_markup=get_main_reply_keyboard())


@dp.callback_query(F.data.startswith("ucancel_"))
async def user_cancel_order(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[8:])
    if not o or o["user_id"] != callback.from_user.id:
        return await stale(callback)
    if o["status"] != "awaiting_payment":
        return await alert(callback, "Этот заказ уже нельзя отменить")
    await callback.answer()
    cancel_order(rk, "cancelled")
    try:
        await bot.send_message(ADMIN_ID, "%s Покупатель %s отменил заказ %s" % (pe("cross"), uname(callback.from_user.username), rk))
    except Exception:
        pass
    await show(callback.message, "%s Заказ %s отменён" % (pe("cross"), rk), main_menu_keyboard())


# ==================== ВЫДАЧА / ЗАВЕРШЕНИЕ ====================
async def deliver_order(rk):
    _, o = get_order(rk)
    if not o:
        return False
    uid = o["user_id"]
    items = order_items(o)
    all_ok = True
    for i, it in enumerate(items):
        if it.get("delivered"):
            continue
        c, n, phone = it["country"], it["session_name"], it.get("phone")
        sess = session_path(c, n)
        if not os.path.exists(sess):
            all_ok = False
            try:
                await bot.send_message(ADMIN_ID, "%s Файл сессии не найден: %s/%s (заказ %s)" % (pe("cross"), c, esc(n), rk))
                await bot.send_message(uid, "%s Файл не найден, продавец уже уведомлён. %s" % (pe("cross"), SELLER))
            except Exception:
                pass
            continue
        meta = load_meta(c, n) or {}
        pwd = ("\n%s <b>Пароль:</b> <code>%s</code>\n" % (pe("lock"), esc(meta["password"]))) if meta.get("password") else ""
        try:
            await bot.send_document(
                chat_id=uid, document=FSInputFile(sess, filename="%s_%s.session" % (c, phone)),
                caption=("%s <b>ВАШ АККАУНТ</b>\n\n%s Страна: %s\n%s Номер: <code>%s</code>\n%s\n<b>Как войти:</b>\n"
                         "1. Войдите в Telegram по номеру выше\n2. Нажмите «Запросить код»\n\n<b>%s Код придёт сюда!</b>"
                         % (pe("sparkle"), pe("globe"), country_name(c), pe("phone"), esc(phone), pwd, pe("key"))),
                reply_markup=user_order_actions_keyboard(rk, o, idx=i))
        except Exception as e:
            all_ok = False
            logger.error("Deliver %s: %s", rk, e)
            try:
                await bot.send_message(ADMIN_ID, "%s Не удалось отправить аккаунт по заказу %s: <code>%s</code>" % (pe("cross"), rk, esc(str(e)[:200])))
            except Exception:
                pass
            continue
        mark_sold(c, n, uid)
        it["delivered"] = True
        asyncio.create_task(start_code_watcher(c, n, uid, rk))
    orders = load_orders()
    if rk in orders:
        # сохраняем флаги delivered, не затирая другие поля
        orders[rk]["items"] = items
        save_orders(orders)
    if all_ok and items:
        await complete_order(rk)
        try:
            await bot.send_message(ADMIN_ID, "%s <b>АККАУНТ ВЫДАН</b> (%s)\n%s <code>%s</code>" % (pe("check"), rk, pe("user"), uid))
        except Exception:
            pass
    return all_ok


async def complete_order(rk):
    update_order(rk, status="completed", completed_at=datetime.now().isoformat())
    await on_completed(rk)


async def on_completed(rk):
    """Учёт покупки: траты, уровни, источники, рефералка, комиссия партнёра — ровно один раз."""
    orders = load_orders()
    o = orders.get(rk)
    if not o or o.get("accounted"):
        return
    o["accounted"] = True
    save_orders(orders)
    uid = o["user_id"]
    total = otot(o)
    users = load_users()
    k = str(uid)
    if k in users:
        users[k]["total_spent"] = round(float(users[k].get("total_spent", 0) or 0) + total, 2)
        users[k]["orders_count"] = users[k].get("orders_count", 0) + 1
        src = users[k].get("traffic_source")
        ref_by = users[k].get("referred_by")
        save_users(users)
    else:
        src = ref_by = None
    if src:
        s = load_traffic_sources()
        if src in s:
            s[src]["total_purchases"] = s[src].get("total_purchases", 0) + 1
            s[src]["total_revenue"] = s[src].get("total_revenue", 0) + total
            save_traffic_sources(s)
    if ref_by:
        try:
            refs = load_referrals()
            rr = refs.get(str(ref_by))
            if rr:
                entry = next((x for x in rr.get("referrals_list", []) if x.get("user_id") == uid and not x.get("first_purchase_done")), None)
                if entry:
                    entry["first_purchase_done"] = True
                    bonus = round(total * float(get_setting("referral_bonus_percent", 5.0)) / 100, 2)
                    if bonus > 0:
                        rr["total_earned"] = round(rr.get("total_earned", 0) + bonus, 2)
                        save_referrals(refs)
                        add_balance(ref_by, bonus)
                        try:
                            await bot.send_message(ref_by, "%s <b>Реферальный бонус!</b>\n\n%s +%s ₴ зачислено на баланс\nВаш баланс: %s ₴"
                                                   % (pe("gift"), pe("money"), money(bonus), money(get_balance(ref_by))))
                        except Exception:
                            pass
                    else:
                        save_referrals(refs)
        except Exception as e:
            logger.error("ref bonus: %s", e)
    if o.get("used_promo_code"):
        await process_partner_commission(o["used_promo_code"], total, rk)


async def process_partner_commission(promo_code, order_total, rk):
    promos = load_promo_codes()
    promo = promos.get(promo_code)
    if not promo or not promo.get("owner_username"):
        return
    owner_username = promo["owner_username"]
    owner_id = promo.get("owner_id")
    for uid, u in load_users().items():
        if (u.get("username") or "").lower() == owner_username.lower():
            owner_id = int(uid)
            break
    percent = float(get_setting("partner_commission_percent", 20.0))
    amount = round(float(order_total) * percent / 100, 2)
    if amount <= 0:
        return
    promo["total_earned"] = round(promo.get("total_earned", 0) + amount, 2)
    save_promo_codes(promos)
    pe_ = load_promo_earnings()
    pe_.setdefault(promo_code, {"total_earned": 0.0, "orders": 0})
    pe_[promo_code]["total_earned"] = round(pe_[promo_code]["total_earned"] + amount, 2)
    pe_[promo_code]["orders"] += 1
    save_promo_earnings(pe_)
    try:
        await bot.send_message(PARTNER_GROUP_ID, "%s <b>ВЫПЛАТА ПАРТНЁРУ</b>\n\n%s @%s\n%s %.2f₴ (%s%%)\n🆔 %s"
                               % (pe("money"), pe("user"), esc(owner_username), pe("money"), amount, percent, rk))
    except Exception:
        pass
    if owner_id:
        try:
            await bot.send_message(owner_id, "%s <b>Вы получили комиссию!</b>\n\n%s %.2f₴ по промокоду <code>%s</code>"
                                   % (pe("sparkle"), pe("money"), amount, esc(promo_code)))
        except Exception:
            pass


# ==================== МОИ ЗАКАЗЫ / АККАУНТЫ ====================
@dp.message(NOT_ADMIN, MENU("Мои заказы"))
@dp.callback_query(F.data == "my_orders")
async def my_orders(event, state: FSMContext):
    await ack(event)
    await state.clear()
    uid = event.from_user.id
    mine = [(k, v) for k, v in load_orders().items() if v.get("user_id") == uid]
    if not mine:
        return await out(event, "%s У вас пока нет заказов" % pe("cart"), main_menu_keyboard())
    mine.sort(key=lambda x: x[1].get("created_at", ""), reverse=True)
    text = "%s <b>ВАШИ ЗАКАЗЫ (%d)</b>\n\n" % (pe("cart"), len(mine))
    b = InlineKeyboardBuilder()
    for rk, o in mine[:10]:
        e, st = STATUS_CONFIG.get(o["status"], (pe("warn"), o["status"]))
        text += "%s %s | %s | %s ₴\n" % (e, rk, esc(o["product"]), money(otot(o)))
        ibtn(b, "%s — %s" % (rk, o["product"][:20]), callback_data="order_detail_%s" % rk, icon_key="cart")
    if len(mine) > 10:
        text += "\n<i>Показаны последние 10</i>"
    ibtn(b, "Меню", callback_data="main_menu", icon_key="back", style="danger")
    b.adjust(1)
    await out(event, text, b.as_markup())


@dp.callback_query(F.data.startswith("order_detail_"))
async def order_detail(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[13:])
    if not o or o["user_id"] != callback.from_user.id:
        return await alert(callback, "❌ Заказ не найден")
    await callback.answer()
    e, st = STATUS_CONFIG.get(o["status"], (pe("warn"), o["status"]))
    text = ("%s <b>ЗАКАЗ %s</b>\n\nТовар: %s%s\nОплата: %s\nСумма: %s ₴\nСтатус: %s %s\n"
            % (pe("cart"), rk, esc(o["product"]), (" × %d" % o["qty"]) if o.get("qty", 1) > 1 else "",
               method_label(o.get("payment_method")), money(otot(o)), e, st))
    for it in order_items(o):
        text += "%s %s\n" % (pe("phone"), esc(it.get("phone")))
    if o["status"] == "completed":
        kb = user_order_actions_keyboard(rk, o)
    elif o["status"] == "awaiting_payment":
        kb = awaiting_payment_keyboard(rk)
    else:
        b = InlineKeyboardBuilder()
        ibtn(b, "Мои заказы", callback_data="my_orders", icon_key="cart")
        ibtn(b, "Меню", callback_data="main_menu", icon_key="back", style="danger")
        b.adjust(1)
        kb = b.as_markup()
    await show(callback.message, text, kb)


@dp.message(NOT_ADMIN, MENU("Мои аккаунты"))
@dp.callback_query(F.data == "my_accounts")
async def my_accounts(event, state: FSMContext):
    await ack(event)
    await state.clear()
    uid = event.from_user.id
    rows = []
    for rk, o in sorted(load_orders().items(), key=lambda x: x[1].get("created_at", ""), reverse=True):
        if o.get("user_id") == uid and o.get("status") == "completed":
            for i, it in enumerate(order_items(o)):
                if it.get("delivered", True):
                    rows.append((rk, i, it))
    if not rows:
        return await out(event, "%s У вас пока нет аккаунтов" % pe("box"), main_menu_keyboard())
    text = "%s <b>ВАШИ АККАУНТЫ (%d)</b>\n\n" % (pe("box"), len(rows))
    b = InlineKeyboardBuilder()
    for rk, i, it in rows[:20]:
        text += "%s %s | %s %s\n" % (pe("globe"), country_name(it["country"]), pe("phone"), esc(it.get("phone")))
        ibtn(b, "Код для %s" % it.get("phone"), callback_data="code_%s_%d" % (rk, i), icon_key="key")
    ibtn(b, "Меню", callback_data="main_menu", icon_key="back", style="danger")
    b.adjust(1)
    await out(event, text, b.as_markup())


@dp.callback_query(F.data.startswith("code_"))
async def request_code(callback: types.CallbackQuery):
    try:
        raw, idx = callback.data[5:].rsplit("_", 1)
        idx = int(idx)
    except ValueError:
        return await stale(callback)
    rk, o = get_order(raw)
    if not o or o["user_id"] != callback.from_user.id or o["status"] != "completed":
        return await alert(callback, "❌ Заказ не найден или не выполнен")
    items = order_items(o)
    if idx >= len(items):
        return await stale(callback)
    it = items[idx]
    c, n = it["country"], it["session_name"]
    if not (os.path.exists(watcher_path(c, n)) or os.path.exists(session_path(c, n))):
        return await alert(callback, "❌ Файл сессии не найден. Напишите %s" % SELLER)
    await callback.answer("Ожидаю код…")
    await callback.message.answer(
        "%s <b>Готово!</b>\n\n%s Номер: <code>%s</code>\n%s Как только Telegram пришлёт код — перешлю сюда.\n"
        "Теперь запросите код входа в Telegram."
        % (pe("key"), pe("phone"), esc(it.get("phone")), pe("time")))
    asyncio.create_task(start_code_watcher(c, n, callback.from_user.id, rk))


@dp.callback_query(F.data.startswith("user_replace_"))
async def user_replace(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[13:])
    if not o or o["user_id"] != callback.from_user.id:
        return await stale(callback)
    if not throttle(callback.from_user.id, callback.data, 30):
        return await alert(callback, "Запрос уже отправлен")
    await callback.answer()
    try:
        await bot.send_message(ADMIN_ID, "%s Запрос замены: %s %s" % (pe("refresh"), rk, uname(callback.from_user.username)), reply_markup=open_order_kb(rk))
    except Exception:
        pass
    await callback.message.answer("%s Запрос отправлен продавцу. %s" % (pe("refresh"), SELLER))


@dp.callback_query(F.data.startswith("user_refund_"))
async def user_refund(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[12:])
    if not o or o["user_id"] != callback.from_user.id:
        return await stale(callback)
    if not throttle(callback.from_user.id, callback.data, 30):
        return await alert(callback, "Запрос уже отправлен")
    await callback.answer()
    try:
        await bot.send_message(ADMIN_ID, "%s Запрос возврата: %s %s" % (pe("money"), rk, uname(callback.from_user.username)), reply_markup=open_order_kb(rk))
    except Exception:
        pass
    await callback.message.answer("%s Запрос отправлен продавцу. %s" % (pe("money"), SELLER))


# ==================== ПРОФИЛЬ / РЕФЕРАЛЫ / ПРОМОКОД ====================
@dp.message(NOT_ADMIN, MENU("Профиль"))
@dp.callback_query(F.data == "profile_menu")
async def show_profile(event, state: FSMContext):
    await ack(event)
    await state.clear()
    u = event.from_user
    lvl = get_user_level(u.id)
    comp = [o for o in load_orders().values() if o.get("user_id") == u.id and o.get("status") == "completed"]
    spent = sum(otot(o) for o in comp)
    r = load_referrals().get(str(u.id), {})
    saved = load_users().get(str(u.id), {}).get("saved_promo")
    text = ("%s <b>Профиль</b>\n\n🆔 <code>%s</code>\n%s %s\n%s %s %s (−%s%%)\n\n%s Потрачено: %.2f ₴\n%s Покупок: %d\n"
            "%s Рефералов: %d\n%s Баланс: <b>%.2f ₴</b>%s"
            % (pe("user"), u.id, pe("user"), esc(u.full_name), pe("star"), lvl["emoji"], lvl["name"], money(lvl["discount"]),
               pe("money"), spent, pe("cart"), len(comp), pe("gift"), len(r.get("referrals_list", [])),
               pe("diamond"), get_balance(u.id),
               ("\n%s Промокод: <code>%s</code>" % (pe("ticket"), esc(saved))) if saved else ""))
    await out(event, text, profile_keyboard())


@dp.message(NOT_ADMIN, MENU("Рефералы"))
@dp.callback_query(F.data == "referral_menu")
async def ref_menu(event, state: FSMContext):
    await ack(event)
    await state.clear()
    uid = event.from_user.id
    await add_user(uid, event.from_user.username, event.from_user.full_name)
    r = load_referrals().get(str(uid), {})
    bot_info = await bot.get_me()
    link = "https://t.me/%s?start=ref_%s" % (bot_info.username, r.get("referral_code") or own_ref_code(uid))
    text = ("%s <b>Рефералы</b>\n\n%s Бонус: %s%% с первой покупки друга\n%s Приглашено: %d\n%s Заработано: %.2f ₴\n"
            "%s Баланс: <b>%.2f ₴</b> (тратится при оплате)\n\n%s <code>%s</code>"
            % (pe("gift"), pe("money"), money(get_setting("referral_bonus_percent", 5.0)), pe("user"),
               len(r.get("referrals_list", [])), pe("money"), r.get("total_earned", 0), pe("diamond"), get_balance(uid),
               pe("link"), link))
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Моя статистика", callback_data="referral_stats", icon_key="chart")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="back", style="danger")
    kb.adjust(1)
    await out(event, text, kb.as_markup())


@dp.callback_query(F.data == "referral_stats")
async def ref_stats(callback: types.CallbackQuery):
    await callback.answer()
    r = load_referrals().get(str(callback.from_user.id), {})
    lst = r.get("referrals_list", [])
    text = "%s <b>Мои рефералы</b>\n\n" % pe("chart")
    if not lst:
        text += "<i>Пока никого нет</i>"
    for x in lst[-15:]:
        st = pe("check") if x.get("first_purchase_done") else pe("time")
        text += "%s %s\n" % (st, uname(x.get("username")))
    text += "\n%s — купил, %s — ещё нет" % (pe("check"), pe("time"))
    await show(callback.message, text, back_kb("referral_menu"))


@dp.message(NOT_ADMIN, MENU("Промокод"))
@dp.callback_query(F.data == "promo_menu")
async def promo_menu_ev(event, state: FSMContext):
    await ack(event)
    saved = load_users().get(str(event.from_user.id), {}).get("saved_promo")
    await state.set_state(PromoStates.waiting_for_promo_code)
    kb = InlineKeyboardBuilder()
    if saved:
        ibtn(kb, "Удалить сохранённый", callback_data="promo_forget", icon_key="trash")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="back", style="danger")
    kb.adjust(1)
    text = "%s <b>Введите промокод</b>\n\nОн сохранится и применится при оформлении заказа." % pe("ticket")
    if saved:
        text += "\n\nСейчас сохранён: <code>%s</code>" % esc(saved)
    await out(event, text, kb.as_markup())


@dp.callback_query(F.data == "promo_forget")
async def promo_forget(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Удалено")
    users = load_users()
    k = str(callback.from_user.id)
    if k in users:
        users[k]["saved_promo"] = None
        save_users(users)
    await state.clear()
    await show(callback.message, "%s Сохранённый промокод удалён" % pe("check"), main_menu_keyboard())


@dp.message(PromoStates.waiting_for_promo_code, F.text)
async def check_promo(message: types.Message, state: FSMContext):
    ok, p, reason = validate_promo(message.text)
    if not ok:
        await message.answer("%s %s. Введите другой промокод или /cancel" % (pe("cross"), reason))
        return
    code = message.text.strip().upper()
    users = load_users()
    k = str(message.from_user.id)
    if k in users:
        users[k]["saved_promo"] = code
        save_users(users)
    d = ("%s%%" % money(p["discount_value"])) if p["discount_type"] == "percent" else ("%s ₴" % money(p["discount_value"]))
    await message.answer("%s Промокод <code>%s</code> принят! Скидка %s применится при оформлении." % (pe("check"), esc(code), d),
                         reply_markup=get_main_reply_keyboard())
    await state.clear()


# ==================== ОТЗЫВЫ ====================
@dp.callback_query(F.data.startswith("leave_review_"))
async def start_review(callback: types.CallbackQuery, state: FSMContext):
    rk, o = get_order(callback.data[13:])
    if o:
        if o["user_id"] != callback.from_user.id:
            return await stale(callback)
        if o.get("reviewed"):
            return await alert(callback, "Вы уже оставили отзыв по этому заказу. Спасибо!")
    await callback.answer()
    await state.set_state(ReviewStates.waiting_for_stars)
    await state.update_data(review_order_id=rk if o else None)
    await callback.message.answer("%s Оцените %s:" % (pe("star"), rk if o else "магазин"), reply_markup=rating_keyboard())


@dp.callback_query(ReviewStates.waiting_for_stars, F.data.startswith("rate_"))
async def process_stars(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    r = int(callback.data[5:])
    await state.update_data(stars=r)
    await state.set_state(ReviewStates.waiting_for_photo_or_skip)
    await show(callback.message, "%s\nОтправьте фото к отзыву, напишите текст или нажмите «Пропустить»:" % ("⭐" * r), review_photo_skip_keyboard())


@dp.callback_query(ReviewStates.waiting_for_photo_or_skip, F.data == "skip_photo")
async def skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(photo=None)
    await state.set_state(ReviewStates.waiting_for_text)
    await show(callback.message, "%s Напишите текст отзыва:" % pe("chat"))


@dp.message(ReviewStates.waiting_for_photo_or_skip, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await state.set_state(ReviewStates.waiting_for_text)
    await message.answer("%s Напишите текст отзыва:" % pe("chat"))


@dp.message(ReviewStates.waiting_for_photo_or_skip, F.text)
async def review_text_instead_of_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=None)
    await process_review(message, state)


@dp.message(ReviewStates.waiting_for_text, F.text)
async def process_review(message: types.Message, state: FSMContext):
    d = await state.get_data()
    rid = "rev_%s_%d" % (message.from_user.id, int(datetime.now().timestamp()))
    reviews = load_reviews()
    reviews[rid] = {"review_id": rid, "user_id": message.from_user.id, "username": message.from_user.username,
                    "full_name": message.from_user.full_name, "stars": d.get("stars", 5), "text": message.text,
                    "photo": d.get("photo"), "order_id": d.get("review_order_id"), "status": "pending",
                    "created_at": datetime.now().isoformat()}
    save_reviews(reviews)
    if d.get("review_order_id"):
        update_order(d["review_order_id"], reviewed=True)
    cap = ("%s НОВЫЙ ОТЗЫВ\nОт: %s\n%s\n%s\n%s" % (pe("star"), esc(message.from_user.full_name),
                                                  uname(message.from_user.username), "⭐" * d.get("stars", 5), esc(message.text)))
    try:
        if d.get("photo"):
            await bot.send_photo(ADMIN_ID, d["photo"], caption=cap[:1000], reply_markup=moderation_keyboard(rid))
        else:
            await bot.send_message(ADMIN_ID, cap, reply_markup=moderation_keyboard(rid))
    except Exception as e:
        logger.error("Review: %s", e)
    await message.answer("%s Спасибо за отзыв! Он появится в канале после проверки." % pe("heart"), reply_markup=get_main_reply_keyboard())
    await state.clear()


@dp.callback_query(IS_ADMIN, F.data.startswith("approve_"))
async def approve_review(callback: types.CallbackQuery):
    rid = callback.data[8:]
    rr = load_reviews()
    r = rr.get(rid)
    if not r:
        return await alert(callback, "Отзыв не найден")
    if r.get("status") != "pending":
        return await alert(callback, "Уже обработан: %s" % r.get("status"))
    text = "%s ОТЗЫВ\n%s\n%s\n%s\n\n%s" % (pe("star"), uname(r.get("username")), "⭐" * r["stars"], esc(r["text"]), SELLER)
    try:
        if r.get("photo"):
            await bot.send_photo(int(CHANNEL_ID), r["photo"], caption=text[:1000])
        else:
            await bot.send_message(int(CHANNEL_ID), text)
    except Exception as e:
        return await alert(callback, "Не удалось опубликовать: %s" % str(e)[:150])
    r["status"] = "approved"
    save_reviews(rr)
    await callback.answer("✅ Опубликовано")
    try:
        await bot.send_message(r["user_id"], "%s Ваш отзыв опубликован!" % pe("sparkle"))
    except Exception:
        pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@dp.callback_query(IS_ADMIN, F.data.startswith("reject_"))
async def reject_review(callback: types.CallbackQuery):
    rid = callback.data[7:]
    rr = load_reviews()
    r = rr.get(rid)
    if not r:
        return await alert(callback, "Отзыв не найден")
    if r.get("status") != "pending":
        return await alert(callback, "Уже обработан: %s" % r.get("status"))
    r["status"] = "rejected"
    save_reviews(rr)
    await callback.answer("Отклонено")
    try:
        await bot.send_message(r["user_id"], "%s Отзыв не прошёл модерацию." % pe("cross"))
    except Exception:
        pass
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


# ==================== ПОДДЕРЖКА ====================
@dp.callback_query(F.data.startswith("support_"))
async def start_support(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    rk, o = get_order(callback.data[8:])
    await state.set_state(SupportStates.chatting)
    await state.update_data(support_order_id=rk or callback.data[8:])
    close_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Закрыть чат")]], resize_keyboard=True)
    await callback.message.answer("%s Напишите сообщение продавцу — я передам. Чтобы выйти, нажмите «Закрыть чат»." % pe("warn"),
                                  reply_markup=close_kb)


@dp.message(SupportStates.chatting, F.text == "❌ Закрыть чат")
async def close_support(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("%s Чат закрыт" % pe("cross"), reply_markup=get_main_reply_keyboard())


@dp.message(SupportStates.chatting)
async def relay_user(message: types.Message, state: FSMContext):
    d = await state.get_data()
    oid = d.get("support_order_id", "—")
    try:
        head = await bot.send_message(ADMIN_ID, "%s %s | %s | ID <code>%s</code>\n<i>Ответьте реплаем на это сообщение</i>"
                                      % (pe("warn"), uname(message.from_user.username), esc(oid), message.from_user.id))
        fwd = await bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
        rel = load_relay()
        rel[str(fwd.message_id)] = message.from_user.id
        rel[str(head.message_id)] = message.from_user.id
        if len(rel) > 3000:
            for key in list(rel.keys())[:1000]:
                rel.pop(key, None)
        save_relay(rel)
        await message.answer("%s Отправлено" % pe("check"))
    except Exception as e:
        logger.error("relay_user: %s", e)
        await message.answer("%s Не удалось отправить, напишите напрямую %s" % (pe("cross"), SELLER))


# ==================== АДМИН: ЗАКАЗЫ ====================
FILTERS = {"all": None, "wait": "awaiting_payment", "paid": "paid", "done": "completed"}
FILTER_TITLES = {"all": "Все заказы", "wait": "Ожидают оплаты", "paid": "Оплачены (ждут выдачи)", "done": "Выполненные"}


async def show_admin_orders(event, flt="all", page=0):
    sf = FILTERS.get(flt)
    orders = load_orders()
    lst = sorted([(k, v) for k, v in orders.items() if not sf or v.get("status") == sf],
                 key=lambda x: x[1].get("created_at", ""), reverse=True)
    per = 6
    pages = max(1, (len(lst) + per - 1) // per)
    page = max(0, min(page, pages - 1))
    kb = InlineKeyboardBuilder()
    if not lst:
        text = "%s <b>%s</b>\n\nНет заказов" % (pe("cart"), FILTER_TITLES[flt])
    else:
        text = "%s <b>%s</b> (%d/%d)\n\n" % (pe("cart"), FILTER_TITLES[flt], page + 1, pages)
        for rk, o in lst[page * per:(page + 1) * per]:
            e, _ = STATUS_CONFIG.get(o["status"], (pe("warn"), ""))
            try:
                created = datetime.fromisoformat(o["created_at"]).strftime("%d.%m %H:%M")
            except Exception:
                created = ""
            text += "%s %s | %s\n  %s | %s ₴ | %s%s\n" % (e, rk, esc(o["product"][:20]), uname(o.get("username")), money(otot(o)), created,
                                                       " 🧾" if o.get("receipt_sent") and o["status"] == "awaiting_payment" else "")
            ibtn(kb, "%s | %s | %s₴" % (rk, o["product"][:14], money(otot(o))), callback_data="ao_view_%s" % rk)
        text += "\n🧾 — покупатель прислал чек"
    nav = 0
    if page > 0:
        ibtn(kb, "Назад", callback_data="aol_%s_%d" % (flt, page - 1), icon_key="back")
        nav += 1
    if page < pages - 1:
        ibtn(kb, "Вперёд", callback_data="aol_%s_%d" % (flt, page + 1), icon_key="next")
        nav += 1
    ibtn(kb, "Обновить", callback_data="aol_%s_%d" % (flt, page), icon_key="refresh")
    ibtn(kb, "Панель", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    sizes = [1] * len(lst[page * per:(page + 1) * per])
    if nav:
        sizes.append(nav)
    sizes += [2]
    kb.adjust(*sizes)
    await out(event, text, kb.as_markup())


@dp.message(IS_ADMIN, MENU("Все заказы"))
async def admin_all_orders(message: types.Message, state: FSMContext):
    await state.clear()
    await show_admin_orders(message, "all", 0)


@dp.message(IS_ADMIN, MENU("Ожидают"))
async def admin_pending(message: types.Message, state: FSMContext):
    await state.clear()
    await show_admin_orders(message, "wait", 0)


@dp.message(IS_ADMIN, MENU("Выполненные"))
async def admin_completed(message: types.Message, state: FSMContext):
    await state.clear()
    await show_admin_orders(message, "done", 0)


@dp.callback_query(IS_ADMIN, F.data.startswith("aol_"))
async def admin_orders_nav(callback: types.CallbackQuery):
    await callback.answer()
    try:
        _, flt, page = callback.data.split("_")
        await show_admin_orders(callback, flt if flt in FILTERS else "all", int(page))
    except ValueError:
        await show_admin_orders(callback, "all", 0)


def _admin_card_kb(rk, o):
    st = o["status"]
    items = order_items(o)
    kb = InlineKeyboardBuilder()
    if st == "awaiting_payment":
        ibtn(kb, "Подтвердить оплату", callback_data="ao_pay_%s" % rk, icon_key="check", style="success")
    elif st == "paid":
        if items:
            ibtn(kb, "Выдать аккаунты", callback_data="ao_deliver_%s" % rk, icon_key="box", style="success")
        else:
            ibtn(kb, "Завершить заказ", callback_data="ao_done_%s" % rk, icon_key="check", style="success")
    elif st == "completed":
        if items:
            ibtn(kb, "Выдать замену", callback_data="ao_repl_%s" % rk, icon_key="refresh")
        ibtn(kb, "Возврат", callback_data="ao_askref_%s" % rk, icon_key="money", style="danger")
    if st in ("awaiting_payment", "paid"):
        ibtn(kb, "Отменить заказ", callback_data="ao_askrej_%s" % rk, icon_key="cross", style="danger")
    ibtn(kb, "Написать покупателю", callback_data="ao_chat_%s" % rk, icon_key="chat")
    ibtn(kb, "Обновить", callback_data="ao_view_%s" % rk, icon_key="refresh")
    ibtn(kb, "К списку", callback_data="aol_all_0", icon_key="back", style="danger")
    kb.adjust(1)
    return kb.as_markup()


def admin_order_text(rk, o):
    e, st = STATUS_CONFIG.get(o["status"], (pe("warn"), o["status"]))
    try:
        created = datetime.fromisoformat(o["created_at"]).strftime("%d.%m.%Y %H:%M")
    except Exception:
        created = "—"
    text = ("%s <b>Заказ %s</b>\n\n%s %s\n🆔 <code>%s</code>\n%s %s\n%s %s%s\n%s %s ₴ (%s)\n%s %s %s\n"
            % (pe("box"), rk, pe("user"), uname(o.get("username")), o["user_id"], pe("calendar"), created,
               pe("cart"), esc(o["product"]), (" × %d" % o["qty"]) if o.get("qty", 1) > 1 else "",
               pe("money"), money(otot(o)), method_label(o.get("payment_method")), pe("pin"), e, st))
    for it in order_items(o):
        text += "%s %s %s%s\n" % (pe("phone"), esc(it.get("phone")), country_name(it.get("country")), "" if it.get("delivered") else " (не выдан)")
    if o.get("used_promo_code"):
        text += "%s Промокод: <code>%s</code>\n" % (pe("ticket"), esc(o["used_promo_code"]))
    if o.get("receipt_sent") and o["status"] == "awaiting_payment":
        text += "🧾 <b>Чек отправлен покупателем</b>\n"
    if not order_items(o) and o["status"] in ("awaiting_payment", "paid"):
        text += "\n%s <b>Ручная выдача:</b> отправьте товар %s и нажмите «Завершить».\n" % (
            pe("star") if o.get("is_stars") else pe("pin"), "подарком в ЛС" if o.get("is_stars") else "покупателю (кнопка «Написать»)")
    return text


async def show_admin_order(target, rk):
    _, o = get_order(rk)
    if not o:
        return await show(target, "%s Заказ не найден" % pe("cross"))
    await show(target, admin_order_text(rk, o), _admin_card_kb(rk, o))


@dp.callback_query(IS_ADMIN, F.data.startswith("ao_view_"))
async def ao_view(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[8:])
    if not o:
        return await alert(callback, "❌ Заказ не найден")
    await callback.answer()
    await show_admin_order(callback.message, rk)


@dp.callback_query(IS_ADMIN, F.data.startswith("ao_pay_"))
async def ao_pay(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[7:])
    if not o:
        return await alert(callback, "❌ Заказ не найден")
    if o["status"] != "awaiting_payment":
        return await alert(callback, "Статус уже: %s" % STATUS_CONFIG.get(o["status"], ("", o["status"]))[1])
    await callback.answer()
    update_order(rk, status="paid", paid_at=datetime.now().isoformat())
    if order_items(o):
        await show(callback.message, "%s Оплата подтверждена. Выдаю аккаунт…" % pe("check"))
        await deliver_order(rk)
    else:
        txt = ("%s <b>Оплата по заказу %s подтверждена!</b>\n\n" % (pe("check"), rk) +
               ("Звёзды будут отправлены подарком в ЛС в ближайшее время." if o.get("is_stars")
                else "Продавец %s свяжется с вами для выдачи товара." % SELLER))
        try:
            await bot.send_message(o["user_id"], txt)
        except Exception:
            pass
    await show_admin_order(callback.message, rk)


@dp.callback_query(IS_ADMIN, F.data.startswith("ao_deliver_"))
async def ao_deliver(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[11:])
    if not o:
        return await alert(callback, "❌ Заказ не найден")
    await callback.answer("Выдаю…")
    ok = await deliver_order(rk)
    if not ok:
        await callback.message.answer("%s Выдача по %s не удалась полностью — см. сообщения выше" % (pe("warn"), rk))
    await show_admin_order(callback.message, rk)


@dp.callback_query(IS_ADMIN, F.data.startswith("ao_done_"))
async def ao_done(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[8:])
    if not o:
        return await alert(callback, "❌ Заказ не найден")
    if o["status"] not in ("paid", "awaiting_payment"):
        return await alert(callback, "Заказ уже в другом статусе")
    await callback.answer()
    await complete_order(rk)
    _, o = get_order(rk)
    try:
        kb = InlineKeyboardBuilder()
        ibtn(kb, "Оставить отзыв", callback_data="leave_review_%s" % rk, icon_key="star", style="success")
        kb.adjust(1)
        await bot.send_message(o["user_id"], "%s <b>Заказ %s выполнен!</b>\n\n%s %s\n\nСпасибо за покупку!"
                               % (pe("check"), rk, pe("cart"), esc(o["product"])), reply_markup=kb.as_markup())
    except Exception as e:
        logger.error("ao_done notify: %s", e)
    await show_admin_order(callback.message, rk)


@dp.callback_query(IS_ADMIN, F.data.startswith("ao_askrej_"))
async def ao_askrej(callback: types.CallbackQuery):
    rk = callback.data[10:]
    await callback.answer()
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Да, отменить", callback_data="ao_dorej_%s" % rk, icon_key="check", style="danger")
    ibtn(kb, "Нет", callback_data="ao_view_%s" % rk, icon_key="back")
    kb.adjust(2)
    await show(callback.message, "%s Отменить заказ %s? Аккаунты вернутся на склад." % (pe("warn"), rk), kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data.startswith("ao_dorej_"))
async def ao_dorej(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[9:])
    if not o:
        return await alert(callback, "❌ Заказ не найден")
    if o["status"] not in ("awaiting_payment", "paid"):
        return await alert(callback, "Заказ уже в другом статусе")
    await callback.answer()
    cancel_order(rk, "rejected")
    try:
        await bot.send_message(o["user_id"], "%s Заказ %s отклонён. Вопросы: %s" % (pe("cross"), rk, SELLER))
    except Exception:
        pass
    await show_admin_order(callback.message, rk)


@dp.callback_query(IS_ADMIN, F.data.startswith("ao_askref_"))
async def ao_askref(callback: types.CallbackQuery):
    rk = callback.data[10:]
    await callback.answer()
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Да, оформить возврат", callback_data="ao_doref_%s" % rk, icon_key="check", style="danger")
    ibtn(kb, "Нет", callback_data="ao_view_%s" % rk, icon_key="back")
    kb.adjust(2)
    await show(callback.message, "%s Оформить возврат по заказу %s? Если платили с баланса — сумма вернётся на баланс." % (pe("warn"), rk), kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data.startswith("ao_doref_"))
async def ao_doref(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[9:])
    if not o:
        return await alert(callback, "❌ Заказ не найден")
    if o["status"] != "completed":
        return await alert(callback, "Возврат возможен только для выполненных заказов")
    await callback.answer()
    total = otot(o)
    update_order(rk, status="refunded", refunded_at=datetime.now().isoformat())
    users = load_users()
    k = str(o["user_id"])
    if k in users and o.get("accounted"):
        users[k]["total_spent"] = max(0, round(float(users[k].get("total_spent", 0) or 0) - total, 2))
        users[k]["orders_count"] = max(0, users[k].get("orders_count", 0) - 1)
        save_users(users)
    if o.get("paid_by_balance"):
        add_balance(o["user_id"], total)
    try:
        await bot.send_message(o["user_id"], "%s Возврат по заказу %s оформлен.%s" % (
            pe("money"), rk, " Сумма зачислена на баланс." if o.get("paid_by_balance") else " Продавец вернёт средства."))
    except Exception:
        pass
    await show_admin_order(callback.message, rk)


@dp.callback_query(IS_ADMIN, F.data.startswith("ao_repl_"))
async def ao_replace(callback: types.CallbackQuery):
    rk, o = get_order(callback.data[8:])
    if not o:
        return await alert(callback, "❌ Заказ не найден")
    items = order_items(o)
    if not items:
        return await alert(callback, "У заказа нет аккаунтов")
    code = items[0]["country"]
    st = (load_meta(code, items[0]["session_name"]) or {}).get("stock_type") or CATEGORIES.get(o.get("category"), {}).get("stock_type")
    accs = reserve_accounts(code, o["user_id"], st, 1)
    if not accs:
        return await alert(callback, "❌ На складе нет замены для %s" % country_name(code))
    await callback.answer("Выдаю замену…")
    a = accs[0]
    items = items + [{"country": a["country"], "session_name": a["session_name"], "phone": a["phone"], "delivered": False, "replacement": True}]
    update_order(rk, items=items)
    await deliver_order(rk)
    await show_admin_order(callback.message, rk)


@dp.callback_query(IS_ADMIN, F.data.startswith("ao_chat_"))
async def ao_chat(callback: types.CallbackQuery, state: FSMContext):
    rk, o = get_order(callback.data[8:])
    if not o:
        return await alert(callback, "❌ Заказ не найден")
    await callback.answer()
    await state.set_state(AdminChatStates.waiting_for_message)
    await state.update_data(chat_uid=o["user_id"], chat_order=rk)
    await callback.message.answer("%s Напишите сообщение для %s (заказ %s). Любой тип сообщения. /cancel — отмена."
                                  % (pe("chat"), uname(o.get("username")), rk))


@dp.message(IS_ADMIN, AdminChatStates.waiting_for_message)
async def ao_chat_send(message: types.Message, state: FSMContext):
    d = await state.get_data()
    uid, rk = d.get("chat_uid"), d.get("chat_order")
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Ответить", callback_data="support_%s" % rk, icon_key="chat", style="primary")
    try:
        await bot.send_message(uid, "%s <b>Сообщение от продавца</b> (заказ %s):" % (pe("chat"), rk))
        await bot.copy_message(uid, message.chat.id, message.message_id, reply_markup=kb.as_markup())
        await message.answer("%s Доставлено" % pe("check"), reply_markup=get_admin_reply_keyboard())
    except Exception as e:
        await message.answer("%s Не доставлено: %s" % (pe("cross"), esc(str(e)[:150])))
    await state.clear()


@dp.message(IS_ADMIN, F.reply_to_message)
async def relay_admin(message: types.Message):
    uid = load_relay().get(str(message.reply_to_message.message_id))
    if not uid:
        return
    try:
        await bot.copy_message(uid, message.chat.id, message.message_id)
        await message.answer("%s Доставлено" % pe("check"))
    except Exception as e:
        await message.answer("%s %s" % (pe("cross"), esc(str(e)[:150])))


# ==================== АДМИН: ПАНЕЛЬ / СТАТИСТИКА ====================
@dp.message(IS_ADMIN, F.text == "🏠 Главное меню")
async def admin_main(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Админ-меню", reply_markup=get_admin_reply_keyboard())


@dp.message(IS_ADMIN, MENU("Статистика"))
async def admin_stats(message: types.Message, state: FSMContext):
    await state.clear()
    orders = load_orders()
    users = load_users()
    sc = {}
    rev = 0.0
    for o in orders.values():
        sc[o["status"]] = sc.get(o["status"], 0) + 1
        if o["status"] == "completed":
            rev += otot(o)
    await message.answer(
        "%s <b>СТАТИСТИКА</b>\n\n%s Пользователей: %d\n%s Заказов: %d\n%s Выполнено: %d\n%s Ожидают: %d\n"
        "%s Оплачены/ждут выдачи: %d\n%s Оборот: %s₴\n%s Склад: %d"
        % (pe("chart"), pe("user"), len(users), pe("cart"), len(orders), pe("check"), sc.get("completed", 0),
           pe("time"), sc.get("awaiting_payment", 0), pe("money"), sc.get("paid", 0), pe("money"), money(rev),
           pe("box"), sum(stock_count().values())), reply_markup=get_admin_reply_keyboard())


@dp.message(IS_ADMIN, MENU("Панель"))
@dp.callback_query(IS_ADMIN, F.data == "admin_dashboard_refresh")
async def show_dashboard(event, state: FSMContext):
    await ack(event)
    await state.clear()
    orders = load_orders()
    users = load_users()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    rt = tr = 0.0
    completed = 0
    waiting = 0
    for o in orders.values():
        if o["status"] == "awaiting_payment":
            waiting += 1
        if o["status"] == "completed":
            tr += otot(o)
            completed += 1
            try:
                if datetime.fromisoformat(o.get("completed_at") or o["created_at"]) >= today:
                    rt += otot(o)
            except Exception:
                pass
    nt = 0
    for u in users.values():
        try:
            if u.get("first_seen") and datetime.fromisoformat(u["first_seen"]) >= today:
                nt += 1
        except Exception:
            pass
    v = stock_count("virtual")
    p = stock_count("physical")
    text = ("%s <b>ПАНЕЛЬ</b>\n\n%s Сегодня: <b>%.2f₴</b>\n%s Всего: <b>%.2f₴</b>\n\n%s Новых сегодня: %d\n"
            "%s Выполнено: %d/%d\n%s Ожидают оплаты: %d\n%s Вирт. склад: %d\n%s Физ. склад: %d\n%s Звёзды: <b>%s</b>\n%s Юзеров: %d"
            % (pe("chart"), pe("money"), rt, pe("money"), tr, pe("user"), nt, pe("cart"), completed, len(orders),
               pe("time"), waiting, pe("phone"), sum(v.values()), pe("card"), sum(p.values()), pe("star"),
               "ВКЛ" if stars_enabled() else "ВЫКЛ", pe("user"), len(users)))
    await out(event, text, admin_dashboard_keyboard())


# ==================== АДМИН: НАСТРОЙКИ ====================
def settings_view():
    s = stars_enabled()
    ttl = int(get_setting("order_ttl_minutes", 60))
    ov = load_settings().get("price_override", {}) or {}
    text = ("%s <b>НАСТРОЙКИ</b>\n\n%s Звёзды: <b>%s</b>\n%s Автоотмена неоплаченных: <b>%d мин</b>\n"
            "%s Цен переопределено: %d\n\n<b>Команды:</b>\n"
            "<code>/setprice virtual in 35</code> — цена товара\n<code>/setprice list</code> — список цен\n"
            "<code>/addbalance ID сумма</code> — начислить баланс\n<code>/user ID</code> — карточка пользователя"
            % (pe("gear"), pe("star"), "ВКЛ" if s else "ВЫКЛ", pe("time"), ttl, pe("money"), len(ov)))
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Звёзды: %s" % ("ВКЛ" if s else "ВЫКЛ"), callback_data="admin_toggle_stars", icon_key="star", style="success" if s else "danger")
    ibtn(kb, "Время автоотмены", callback_data="admin_edit_ttl", icon_key="time")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1)
    return text, kb.as_markup()


@dp.message(IS_ADMIN, MENU("Настройки"))
@dp.callback_query(IS_ADMIN, F.data == "admin_settings")
async def admin_settings_menu(event, state: FSMContext):
    await ack(event)
    await state.clear()
    t, kb = settings_view()
    await out(event, t, kb)


@dp.callback_query(IS_ADMIN, F.data == "admin_toggle_stars")
async def admin_toggle_stars(callback: types.CallbackQuery):
    s = load_settings()
    new = not bool(s.get("stars_enabled", True))
    s["stars_enabled"] = new
    save_settings(s)
    await callback.answer("Звёзды %s" % ("включены ✅" if new else "выключены ❌"))
    t, kb = settings_view()
    await show(callback.message, t, kb)


@dp.callback_query(IS_ADMIN, F.data == "admin_edit_ttl")
async def admin_edit_ttl(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminSettingsStates.waiting_for_ttl)
    await callback.message.answer("Через сколько минут отменять неоплаченные заказы? (число, 0 — не отменять)")


@dp.message(IS_ADMIN, AdminSettingsStates.waiting_for_ttl, F.text)
async def admin_save_ttl(message: types.Message, state: FSMContext):
    try:
        v = int(message.text.strip())
        if v < 0:
            raise ValueError
    except ValueError:
        return await message.answer("%s Нужно целое число ≥ 0" % pe("cross"))
    s = load_settings()
    s["order_ttl_minutes"] = v
    save_settings(s)
    await state.clear()
    await message.answer("%s Сохранено: %d мин" % (pe("check")), reply_markup=get_admin_reply_keyboard()) if False else \
        await message.answer("%s Сохранено: %d мин" % (pe("check"), v), reply_markup=get_admin_reply_keyboard())


@dp.message(Command("setprice"), IS_ADMIN)
async def cmd_setprice(message: types.Message):
    args = (message.text or "").split()[1:]
    s = load_settings()
    ov = s.setdefault("price_override", {})
    if args and args[0] == "list":
        txt = "%s <b>Цены</b>\n\n" % pe("money")
        for cat, cd in CATEGORIES.items():
            for pname, pd in cd["products"].items():
                key = "%s:%s" % (cat, pd["code"])
                txt += "<code>%s %s</code> — %s₴%s\n" % (cat, pd["code"], money(get_price(cat, pd["code"])), " ✏️" if key in ov else "")
        return await message.answer(txt[:4000])
    if len(args) == 3 and args[0] == "reset":
        ov.pop("%s:%s" % (args[1], args[2]), None)
        save_settings(s)
        return await message.answer("%s Цена сброшена" % pe("check"))
    if len(args) != 3:
        return await message.answer("Формат: <code>/setprice категория код цена</code>\nСброс: <code>/setprice reset категория код</code>\nСписок: <code>/setprice list</code>")
    cat, code, val = args
    name, _ = find_product(cat, code)
    if not name:
        return await message.answer("%s Товар не найден. Смотрите <code>/setprice list</code>" % pe("cross"))
    try:
        v = float(val)
        if v <= 0:
            raise ValueError
    except ValueError:
        return await message.answer("%s Цена должна быть числом > 0" % pe("cross"))
    ov["%s:%s" % (cat, code)] = v
    save_settings(s)
    await message.answer("%s %s = %s₴" % (pe("check"), esc(name), money(v)))


@dp.message(Command("addbalance"), IS_ADMIN)
async def cmd_addbalance(message: types.Message):
    args = (message.text or "").split()[1:]
    try:
        uid = int(args[0])
        amount = float(args[1])
    except Exception:
        return await message.answer("Формат: <code>/addbalance ID сумма</code>")
    if not add_balance(uid, amount):
        return await message.answer("%s Пользователь не найден" % pe("cross"))
    await message.answer("%s Баланс %s: %s ₴" % (pe("check"), uid, money(get_balance(uid))))
    try:
        await bot.send_message(uid, "%s Вам начислено %s ₴. Баланс: %s ₴" % (pe("money"), money(amount), money(get_balance(uid))))
    except Exception:
        pass


@dp.message(Command("user"), IS_ADMIN)
async def cmd_user(message: types.Message):
    args = (message.text or "").split()[1:]
    if not args:
        return await message.answer("Формат: <code>/user ID</code> или <code>/user username</code>")
    users = load_users()
    u = users.get(args[0]) or next((x for x in users.values() if (x.get("username") or "").lower() == args[0].lstrip("@").lower()), None)
    if not u:
        return await message.answer("%s Не найден" % pe("cross"))
    orders = [o for o in load_orders().values() if o.get("user_id") == u["user_id"]]
    await message.answer("%s <b>%s</b> %s\n🆔 <code>%s</code>\n%s Потрачено: %.2f ₴ (%d зак.)\n%s Баланс: %.2f ₴\n%s Источник: %s\nРеферер: %s"
                         % (pe("user"), esc(u.get("full_name")), uname(u.get("username")), u["user_id"], pe("money"),
                            u.get("total_spent", 0), len(orders), pe("diamond"), get_balance(u["user_id"]), pe("link"),
                            esc(u.get("traffic_source") or "—"), u.get("referred_by") or "—"))


# ==================== АДМИН: СКЛАД ====================
@dp.message(IS_ADMIN, MENU("Склад"))
@dp.callback_query(IS_ADMIN, F.data == "admin_stock_menu")
async def admin_stock_menu(event, state: FSMContext):
    await ack(event)
    await state.clear()
    v = stock_count("virtual")
    p = stock_count("physical")
    reserved = sum(1 for m in list_metas() if m.get("status") == "reserved")
    text = "%s <b>СКЛАД</b>\n\n%s Виртуальных: <b>%d</b>\n%s Физических: <b>%d</b>\n⏳ В резерве: %d" % (
        pe("box"), pe("phone"), sum(v.values()), pe("card"), sum(p.values()), reserved)
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Виртуальные номера", callback_data="admin_stock_virtual", icon_key="phone", style="primary")
    ibtn(kb, "Физические номера", callback_data="admin_stock_physical", icon_key="card", style="primary")
    ibtn(kb, "Все аккаунты", callback_data="admin_lp_all_0", icon_key="cart")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1)
    await out(event, text, kb.as_markup())


async def stock_type_screen(callback, stock_type):
    await callback.answer()
    counts = stock_count(stock_type)
    title = "ВИРТУАЛЬНЫЕ НОМЕРА" if stock_type == "virtual" else "ФИЗИЧЕСКИЕ НОМЕРА"
    text = "%s <b>%s</b>\n\n" % (pe("phone") if stock_type == "virtual" else pe("card"), title)
    if counts:
        for c, n in sorted(counts.items(), key=lambda x: -x[1]):
            text += "• %s: <b>%d</b>\n" % (country_name(c), n)
    else:
        text += "<i>Пусто</i>"
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Загрузить .session", callback_data="admin_upload_%s" % stock_type, icon_key="plus", style="primary")
    ibtn(kb, "Список аккаунтов", callback_data="admin_lp_%s_0" % stock_type, icon_key="cart")
    ibtn(kb, "Назад", callback_data="admin_stock_menu", icon_key="back", style="danger")
    kb.adjust(1)
    await show(callback.message, text, kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data == "admin_stock_virtual")
async def admin_stock_virtual(callback: types.CallbackQuery):
    await stock_type_screen(callback, "virtual")


@dp.callback_query(IS_ADMIN, F.data == "admin_stock_physical")
async def admin_stock_physical(callback: types.CallbackQuery):
    await stock_type_screen(callback, "physical")


@dp.callback_query(IS_ADMIN, F.data.startswith("admin_upload_"))
async def admin_upload_start(callback: types.CallbackQuery, state: FSMContext):
    stock_type = callback.data[13:]
    if stock_type not in ("virtual", "physical"):
        return await stale(callback)
    await callback.answer()
    await state.set_state(AdminStockStates.waiting_for_session)
    await state.update_data(stock_type=stock_type, uploaded=0)
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Готово", callback_data="admin_upload_done", icon_key="check", style="success")
    await show(callback.message, "%s Отправляйте файлы <code>.session</code> (%s). Можно сразу много — по одному сообщению.\n"
               "Страна и 2FA определяются автоматически. Когда закончите — «Готово»."
               % (pe("plus"), "виртуальные" if stock_type == "virtual" else "физические"), kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data == "admin_upload_done")
async def admin_upload_done(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    d = await state.get_data()
    await state.clear()
    await callback.message.answer("%s Загрузка завершена. Добавлено: %d" % (pe("check"), d.get("uploaded", 0)), reply_markup=get_admin_reply_keyboard())


@dp.message(IS_ADMIN, AdminStockStates.waiting_for_session, F.document)
async def admin_receive_session(message: types.Message, state: FSMContext):
    d = await state.get_data()
    stock_type = d.get("stock_type", "virtual")
    doc = message.document
    fname = os.path.basename(doc.file_name or "")
    if not fname.endswith(".session"):
        return await message.answer("%s Нужен файл .session (получен: %s)" % (pe("cross"), esc(fname)))
    name = re.sub(r"[^\w\-.+]", "_", fname[:-8])
    temp_path = os.path.join(TEMP_DIR, "%s.session" % name)
    await bot.download(doc, temp_path)
    status = await message.answer("%s Анализирую %s…" % (pe("time"), esc(name)))

    async def cleanup():
        for suffix in (".session", ".session-journal"):
            try:
                os.remove(os.path.join(TEMP_DIR, name + suffix))
            except Exception:
                pass

    info = await analyze_session(temp_path)
    if not info.get("valid"):
        await cleanup()
        return await status.edit_text("%s <b>%s — сессия невалидна</b>\n<code>%s</code>" % (pe("cross"), esc(name), esc(info.get("error", "unknown"))))
    phone = info["phone"]
    cc, cn = detect_country(phone)
    if info.get("has_2fa"):
        await cleanup()
        return await status.edit_text("%s <b>%s — аккаунт с паролем (2FA), не добавлен</b>\n%s\n%s <code>%s</code>\nХинт: <code>%s</code>"
                                      % (pe("warn"), esc(name), cn, pe("phone"), esc(phone), esc(info.get("password_hint") or "—")))
    known = {pd["code"] for pd in CATEGORIES[stock_type]["products"].values()}
    if cc not in known:
        await cleanup()
        return await status.edit_text("%s <b>%s — страна не продаётся в этой категории</b>\n%s (<code>%s</code>)" % (pe("warn"), esc(name), cn, cc))
    for m in list_metas():
        if str(m.get("phone")) == str(phone) or (m["country"] == cc and m["session_name"] == name):
            await cleanup()
            return await status.edit_text("%s <b>%s — уже есть на складе</b> (%s, статус: %s)" % (pe("warn"), esc(phone), m["country"].upper(), m.get("status")))
    try:
        os.makedirs(country_dir(cc), exist_ok=True)
        shutil.copy(temp_path, session_path(cc, name))
        shutil.copy(temp_path, watcher_path(cc, name))
        meta = {"country": cc, "session_name": name, "phone": phone, "user_id": info["user_id"],
                "first_name": info.get("first_name"), "username": info.get("username"),
                "premium": info.get("premium", False), "has_2fa": False, "password": None,
                "price_uah": get_price(stock_type, cc), "stock_type": stock_type, "status": "available",
                "added_at": datetime.now().isoformat(), "sold_at": None, "sold_to": None}
        save_meta(cc, name, meta)
        await cleanup()
        await state.update_data(uploaded=d.get("uploaded", 0) + 1)
        kb = InlineKeyboardBuilder()
        ibtn(kb, "Готово", callback_data="admin_upload_done", icon_key="check", style="success")
        await status.edit_text("%s <b>Добавлен</b> (%s)\n%s %s\n%s <code>%s</code> | %s\n%s %s ₴\n\nОтправьте ещё или нажмите «Готово»."
                               % (pe("check"), "виртуальный" if stock_type == "virtual" else "физический", pe("globe"), cn,
                                  pe("phone"), esc(phone), esc(info.get("first_name") or "—"), pe("money"),
                                  money(get_price(stock_type, cc))), reply_markup=kb.as_markup())
    except Exception as e:
        await cleanup()
        await status.edit_text("%s Ошибка: %s" % (pe("cross"), esc(str(e)[:200])))


@dp.message(IS_ADMIN, AdminStockStates.waiting_for_session, Command("done"))
async def admin_upload_done_cmd(message: types.Message, state: FSMContext):
    d = await state.get_data()
    await state.clear()
    await message.answer("%s Загрузка завершена. Добавлено: %d" % (pe("check"), d.get("uploaded", 0)), reply_markup=get_admin_reply_keyboard())


@dp.callback_query(IS_ADMIN, F.data.startswith("admin_lp_"))
async def admin_list_accounts(callback: types.CallbackQuery):
    await callback.answer()
    try:
        _, _, stype, page = callback.data.split("_")
        page = int(page)
    except ValueError:
        return await stale(callback)
    avail = all_available(stock_type=None if stype == "all" else stype)
    per = 8
    pages = max(1, (len(avail) + per - 1) // per)
    page = max(0, min(page, pages - 1))
    text = "%s <b>АККАУНТЫ В НАЛИЧИИ (%d)</b> — стр. %d/%d\n\n" % (pe("box"), len(avail), page + 1, pages)
    kb = InlineKeyboardBuilder()
    chunk = avail[page * per:(page + 1) * per]
    for acc in chunk:
        t = "📱" if acc.get("stock_type") == "virtual" else "☎️"
        text += "%s %s | %s | %s₴\n" % (t, acc["country"].upper(), esc(acc["phone"]), money(get_price(acc.get("stock_type", "virtual"), acc["country"])))
        cd = "accaskdel_%s:%s" % (acc["country"], acc["session_name"])
        if len(cd.encode()) <= 64:
            ibtn(kb, "🗑 %s" % acc["phone"], callback_data=cd)
    nav = 0
    if page > 0:
        ibtn(kb, "Назад", callback_data="admin_lp_%s_%d" % (stype, page - 1), icon_key="back")
        nav += 1
    if page < pages - 1:
        ibtn(kb, "Вперёд", callback_data="admin_lp_%s_%d" % (stype, page + 1), icon_key="next")
        nav += 1
    ibtn(kb, "К складу", callback_data="admin_stock_menu", icon_key="back", style="danger")
    sizes = [1] * len([1 for a in chunk if len(("accaskdel_%s:%s" % (a["country"], a["session_name"])).encode()) <= 64])
    if nav:
        sizes.append(nav)
    sizes.append(1)
    kb.adjust(*sizes)
    await show(callback.message, text, kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data.startswith("accaskdel_"))
async def acc_ask_delete(callback: types.CallbackQuery):
    await callback.answer()
    key = callback.data[10:]
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Да, удалить", callback_data="accdodel_%s" % key, icon_key="trash", style="danger")
    ibtn(kb, "Нет", callback_data="admin_lp_all_0", icon_key="back")
    kb.adjust(2)
    await show(callback.message, "%s Удалить аккаунт <code>%s</code> со склада? Это необратимо." % (pe("warn"), esc(key)), kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data.startswith("accdodel_"))
async def acc_do_delete(callback: types.CallbackQuery):
    key = callback.data[9:]
    try:
        c, n = key.split(":", 1)
    except ValueError:
        return await stale(callback)
    meta = load_meta(c, n)
    if not meta or meta.get("status") != "available":
        return await alert(callback, "Аккаунт недоступен для удаления (продан/в резерве)")
    for p in (session_path(c, n), watcher_path(c, n), meta_path(c, n)):
        try:
            os.remove(p)
        except Exception:
            pass
    await callback.answer("🗑 Удалён")
    await admin_list_accounts_refresh(callback)


async def admin_list_accounts_refresh(callback):
    callback.data = "admin_lp_all_0"
    await admin_list_accounts(callback)


# ==================== АДМИН: РЕКВИЗИТЫ / РАССЫЛКА ====================
@dp.message(IS_ADMIN, MENU("Реквизиты"))
async def admin_requisites(message: types.Message, state: FSMContext):
    await state.clear()
    r = load_requisites()
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Изменить гривны", callback_data="edit_req_uah", icon_key="money")
    ibtn(kb, "Изменить подарок", callback_data="edit_req_gift", icon_key="gift")
    kb.adjust(1)
    await message.answer("%s <b>РЕКВИЗИТЫ:</b>\n\n%s Гривны:\n%s\n\n%s Подарок:\n%s" % (pe("money"), pe("card"), r.get("uah", "—"), pe("gift"), r.get("gift", "—")),
                         reply_markup=kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data.startswith("edit_req_"))
async def edit_req(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    m = callback.data[9:]
    await state.update_data(edit_req_method=m)
    await callback.message.answer("%s Введите новые реквизиты для «%s» (можно HTML: &lt;b&gt;, &lt;code&gt;). /cancel — отмена:" % (pe("warn"), {"uah": "Гривны", "gift": "Подарок"}.get(m, m)))
    await state.set_state(AdminStates.waiting_for_requisites_edit)


@dp.message(IS_ADMIN, AdminStates.waiting_for_requisites_edit, F.text)
async def save_req(message: types.Message, state: FSMContext):
    d = await state.get_data()
    try:
        await bot.send_message(ADMIN_ID, "Предпросмотр:\n\n" + message.text)
    except Exception as e:
        return await message.answer("%s Некорректная HTML-разметка: %s\nПопробуйте ещё раз." % (pe("cross"), esc(str(e)[:150])))
    r = load_requisites()
    r[d["edit_req_method"]] = message.text
    save_requisites(r)
    await message.answer("%s Обновлено!" % pe("check"), reply_markup=get_admin_reply_keyboard())
    await state.clear()


@dp.message(IS_ADMIN, MENU("Рассылка"))
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    n = len(load_users())
    if not n:
        return await message.answer("%s Нет пользователей" % pe("cross"))
    await state.clear()
    await message.answer("%s <b>РАССЫЛКА</b>\n\n%s Получателей: <b>%d</b>\n\nОтправьте сообщение (текст/фото/видео). /cancel — отмена." % (pe("megaphone"), pe("user"), n))
    await state.set_state(AdminStates.waiting_for_broadcast)


@dp.message(IS_ADMIN, AdminStates.waiting_for_broadcast)
async def bc_receive(message: types.Message, state: FSMContext):
    await state.update_data(bc_chat=message.chat.id, bc_msg=message.message_id)
    await state.set_state(AdminStates.confirm_broadcast)
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Отправить всем", callback_data="bc_go", icon_key="check", style="success")
    ibtn(kb, "Отмена", callback_data="bc_cancel", icon_key="cross", style="danger")
    kb.adjust(2)
    await message.answer("%s Отправить это сообщение %d пользователям?" % (pe("warn"), len(load_users())), reply_markup=kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data == "bc_cancel")
async def bc_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await show(callback.message, "%s Рассылка отменена" % pe("cross"))


@dp.callback_query(IS_ADMIN, F.data == "bc_go")
async def bc_go(callback: types.CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if "bc_msg" not in d:
        return await stale(callback)
    await callback.answer()
    await state.clear()
    users = [u for u in load_users().keys() if int(u) != ADMIN_ID]
    status = await callback.message.edit_text("%s <b>Рассылка…</b>" % pe("time"))
    ok = fail = blocked = 0
    for i, uid in enumerate(users, 1):
        for attempt in range(2):
            try:
                await bot.copy_message(int(uid), d["bc_chat"], d["bc_msg"])
                ok += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except Exception as e:
                err = str(e).lower()
                if any(x in err for x in ("blocked", "kicked", "chat not found", "deactivated")):
                    blocked += 1
                else:
                    fail += 1
                break
        await asyncio.sleep(0.05)
        if i % 25 == 0:
            try:
                await status.edit_text("%s %d/%d | %s %d | %s %d" % (pe("time"), i, len(users), pe("check"), ok, pe("cross"), fail))
            except Exception:
                pass
    await status.edit_text("%s <b>Готово!</b>\n\n%s Доставлено: %d\n%s Ошибок: %d\n🚫 Заблокировали бота: %d" % (pe("check"), pe("check"), ok, pe("cross"), fail, blocked))


# ==================== АДМИН: УРОВНИ ====================
@dp.message(IS_ADMIN, MENU("Уровни"))
@dp.callback_query(IS_ADMIN, F.data == "admin_levels_dashboard")
async def admin_levels(event, state: FSMContext):
    await ack(event)
    await state.clear()
    emo = {"bronze": "medal3", "silver": "medal2", "gold": "medal1", "platinum": "diamond", "vip": "crown"}
    text = "%s <b>Уровни</b>\n\n" % pe("star")
    kb = InlineKeyboardBuilder()
    for k, label in LEVEL_KEYS.items():
        text += "%s <b>%s</b> — от %s₴ (−%s%%)\n" % (pe(emo[k]), label, money(get_setting("level_%s_min" % k, 0)), money(get_setting("level_%s_discount" % k, 0)))
        ibtn(kb, label, callback_data="admin_edit_level_%s" % k, icon_key=emo[k])
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1)
    await out(event, text, kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data.startswith("admin_edit_level_"))
async def edit_level(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    k = callback.data[17:]
    if k not in LEVEL_KEYS:
        return await stale(callback)
    await state.update_data(edit_level=k)
    b = InlineKeyboardBuilder()
    ibtn(b, "Порог", callback_data="edit_level_min", icon_key="money")
    ibtn(b, "Скидка", callback_data="edit_level_discount", icon_key="gift")
    ibtn(b, "Назад", callback_data="admin_levels_dashboard", icon_key="back", style="danger")
    b.adjust(1)
    await show(callback.message, "Уровень <b>%s</b>:" % LEVEL_KEYS[k], b.as_markup())


@dp.callback_query(IS_ADMIN, F.data == "edit_level_min")
async def edit_level_min(callback: types.CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if "edit_level" not in d:
        return await stale(callback)
    await callback.answer()
    await show(callback.message, "Введите порог трат (₴):")
    await state.set_state(AdminLevelStates.waiting_for_min_spent)


@dp.callback_query(IS_ADMIN, F.data == "edit_level_discount")
async def edit_level_discount(callback: types.CallbackQuery, state: FSMContext):
    d = await state.get_data()
    if "edit_level" not in d:
        return await stale(callback)
    await callback.answer()
    await show(callback.message, "Введите скидку (%):")
    await state.set_state(AdminLevelStates.waiting_for_discount)


@dp.message(IS_ADMIN, AdminLevelStates.waiting_for_min_spent, F.text)
async def save_lvl_min(message: types.Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if v < 0:
            raise ValueError
    except ValueError:
        return await message.answer("%s Введите число ≥ 0" % pe("cross"))
    k = (await state.get_data()).get("edit_level", "bronze")
    s = load_settings()
    s["level_%s_min" % k] = v
    save_settings(s)
    await message.answer("%s Порог: %s₴" % (pe("check"), money(v)), reply_markup=get_admin_reply_keyboard())
    await state.clear()


@dp.message(IS_ADMIN, AdminLevelStates.waiting_for_discount, F.text)
async def save_lvl_disc(message: types.Message, state: FSMContext):
    try:
        v = float(message.text.replace(",", "."))
        if not (0 <= v <= 100):
            raise ValueError
    except ValueError:
        return await message.answer("%s Введите число 0–100" % pe("cross"))
    k = (await state.get_data()).get("edit_level", "bronze")
    s = load_settings()
    s["level_%s_discount" % k] = v
    save_settings(s)
    await message.answer("%s Скидка: %s%%" % (pe("check"), money(v)), reply_markup=get_admin_reply_keyboard())
    await state.clear()


# ==================== АДМИН: АНАЛИТИКА / ИСТОЧНИКИ ====================
@dp.message(IS_ADMIN, MENU("Аналитика"))
@dp.callback_query(IS_ADMIN, F.data == "admin_analytics_dashboard")
async def admin_analytics(event, state: FSMContext):
    await ack(event)
    await state.clear()
    kb = InlineKeyboardBuilder()
    ibtn(kb, "По дням", callback_data="admin_analytics_by_days", icon_key="calendar")
    ibtn(kb, "По часам", callback_data="admin_analytics_by_hours", icon_key="time")
    ibtn(kb, "По странам", callback_data="admin_analytics_by_country", icon_key="globe")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1)
    await out(event, "%s <b>Аналитика</b>" % pe("chart"), kb.as_markup())


def completed_orders():
    return [o for o in load_orders().values() if o.get("status") == "completed"]


def completed_dt(o):
    try:
        return datetime.fromisoformat(o.get("completed_at") or o["created_at"])
    except Exception:
        return None


@dp.callback_query(IS_ADMIN, F.data == "admin_analytics_by_days")
async def an_days(callback: types.CallbackQuery):
    await callback.answer()
    now = datetime.now()
    d = {}
    for o in completed_orders():
        dt = completed_dt(o)
        if dt and (now - dt).days < 30:
            x = d.setdefault(dt.strftime("%d.%m"), [0.0, 0, dt])
            x[0] += otot(o)
            x[1] += 1
    text = "%s <b>Выручка по дням (30 дн.)</b>\n\n" % pe("chart_up")
    for k, (r, n, _) in sorted(d.items(), key=lambda x: x[1][2], reverse=True):
        text += "%s %s: %s₴ (%d)\n" % (pe("calendar"), k, money(r), n)
    if not d:
        text += "<i>Нет данных</i>"
    await show(callback.message, text, back_kb("admin_analytics_dashboard"))


@dp.callback_query(IS_ADMIN, F.data == "admin_analytics_by_hours")
async def an_hours(callback: types.CallbackQuery):
    await callback.answer()
    h = {}
    for o in completed_orders():
        dt = completed_dt(o)
        if dt:
            x = h.setdefault(dt.hour, [0.0, 0])
            x[0] += otot(o)
            x[1] += 1
    text = "%s <b>Выручка по часам</b>\n\n" % pe("time")
    for hr in sorted(h):
        text += "%02d:00 — %s₴ (%d)\n" % (hr, money(h[hr][0]), h[hr][1])
    if not h:
        text += "<i>Нет данных</i>"
    await show(callback.message, text, back_kb("admin_analytics_dashboard"))


@dp.callback_query(IS_ADMIN, F.data == "admin_analytics_by_country")
async def an_country(callback: types.CallbackQuery):
    await callback.answer()
    s = {}
    for o in completed_orders():
        c = o.get("country_code") or o.get("code") or "??"
        x = s.setdefault(c, [0.0, 0])
        x[0] += otot(o)
        x[1] += 1
    text = "%s <b>По странам/товарам</b>\n\n" % pe("globe")
    for c, (r, n) in sorted(s.items(), key=lambda y: -y[1][0]):
        text += "%s: %s₴ (%d)\n" % (country_name(c) if c in COUNTRY_NAME else c.upper(), money(r), n)
    if not s:
        text += "<i>Нет данных</i>"
    await show(callback.message, text, back_kb("admin_analytics_dashboard"))


@dp.message(IS_ADMIN, MENU("Источники"))
@dp.callback_query(IS_ADMIN, F.data == "admin_traffic_dashboard")
async def admin_traffic(event, state: FSMContext):
    await ack(event)
    await state.clear()
    s = load_traffic_sources()
    text = "%s <b>Источники трафика</b>\n\nСсылка вида <code>t.me/бот?start=НАЗВАНИЕ</code>\n\n" % pe("link")
    if not s:
        text += "<i>Нет данных</i>"
    for n, x in sorted(s.items(), key=lambda y: -y[1].get("total_revenue", 0)):
        text += "%s <b>%s</b>: %d визитов, %d покупок, %s₴\n" % (pe("pin"), esc(n), x.get("total_visits", 0), x.get("total_purchases", 0), money(x.get("total_revenue", 0)))
    await out(event, text, back_kb("admin_dashboard_refresh"))


# ==================== АДМИН: РЕФЕРАЛЫ / ПОЛЬЗОВАТЕЛИ ====================
@dp.message(IS_ADMIN, MENU("Рефералы"))
@dp.callback_query(IS_ADMIN, F.data == "admin_referrals_dashboard")
async def admin_refs(event, state: FSMContext):
    await ack(event)
    await state.clear()
    r = load_referrals()
    tot = sum(len(x.get("referrals_list", [])) for x in r.values())
    earned = sum(x.get("total_earned", 0) for x in r.values())
    text = "%s <b>Рефералы</b>\n\n%s Бонус рефереру: %s%%\n%s Комиссия партнёрам: %s%%\n%s Приглашено всего: %d\n%s Начислено: %.0f₴" % (
        pe("gift"), pe("money"), money(get_setting("referral_bonus_percent", 5.0)), pe("ticket"),
        money(get_setting("partner_commission_percent", 20.0)), pe("user"), tot, pe("money"), earned)
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Изменить бонус %", callback_data="admin_edit_referral_bonus", icon_key="money")
    ibtn(kb, "Изменить комиссию партнёров %", callback_data="admin_edit_partner_percent", icon_key="ticket")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1)
    await out(event, text, kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data == "admin_edit_referral_bonus")
async def edit_ref_bonus(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await show(callback.message, "Введите новый реферальный бонус (%):")
    await state.set_state(AdminReferralSettingsStates.waiting_for_bonus_percent)


@dp.callback_query(IS_ADMIN, F.data == "admin_edit_partner_percent")
async def edit_partner_percent(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await show(callback.message, "Введите новую комиссию партнёров (%):")
    await state.set_state(AdminReferralSettingsStates.waiting_for_partner_percent)


async def _save_percent(message, state, key):
    try:
        v = float(message.text.replace(",", "."))
        if not (0 <= v <= 100):
            raise ValueError
    except ValueError:
        return await message.answer("%s Введите число 0–100" % pe("cross"))
    s = load_settings()
    s[key] = v
    save_settings(s)
    await message.answer("%s Сохранено: %s%%" % (pe("check"), money(v)), reply_markup=get_admin_reply_keyboard())
    await state.clear()


@dp.message(IS_ADMIN, AdminReferralSettingsStates.waiting_for_bonus_percent, F.text)
async def save_ref_bonus(message: types.Message, state: FSMContext):
    await _save_percent(message, state, "referral_bonus_percent")


@dp.message(IS_ADMIN, AdminReferralSettingsStates.waiting_for_partner_percent, F.text)
async def save_partner_percent(message: types.Message, state: FSMContext):
    await _save_percent(message, state, "partner_commission_percent")


@dp.message(IS_ADMIN, MENU("Пользователи"))
async def admin_users(message: types.Message, state: FSMContext):
    await state.clear()
    u = load_users()
    if not u:
        return await message.answer("%s Нет пользователей" % pe("cart"), reply_markup=get_admin_reply_keyboard())
    text = "%s <b>ПОЛЬЗОВАТЕЛЕЙ: %d</b>\n\n" % (pe("user"), len(u))
    for uid, x in sorted(u.items(), key=lambda y: y[1].get("first_seen", ""), reverse=True)[:10]:
        text += "%s %s (%s)\nID: <code>%s</code> | %s₴\n" % (pe("user"), esc(x.get("full_name", "—")), uname(x.get("username")), uid, money(x.get("total_spent", 0)))
    text += "\nКарточка: <code>/user ID</code>"
    await message.answer(text, reply_markup=get_admin_reply_keyboard())


# ==================== АДМИН: БЭКАПЫ ====================
@dp.message(IS_ADMIN, MENU("Бэкапы"))
@dp.callback_query(IS_ADMIN, F.data == "admin_backups")
async def admin_backups(event, state: FSMContext):
    await ack(event)
    await state.clear()
    text = ("%s <b>БЭКАПЫ</b>\n\nНа Railway файлы стираются при пересборке. Решения:\n"
            "1) подключите Volume и задайте переменную <code>DATA_DIR</code>;\n"
            "2) либо скачайте бэкап и вставьте в Variables как <code>BACKUP_ALL_B64</code>.\n\n"
            "Склад (.session) в переменные не помещается — скачивайте архивом." % pe("save"))
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Скачать данные (BACKUP_ALL_B64)", callback_data="admin_download_backups", icon_key="save")
    ibtn(kb, "Скачать склад (zip)", callback_data="admin_download_accounts", icon_key="box")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1)
    await out(event, text, kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data == "admin_download_backups")
async def download_backups(callback: types.CallbackQuery):
    await callback.answer()
    data = {}
    for n in BACKUP_FILES:
        p = "%s.json" % n
        if os.path.exists(p):
            data[n] = load_json(p)
    b64 = base64.b64encode(json.dumps(data, ensure_ascii=False).encode()).decode()
    with open("backup_all.b64", "w") as f:
        f.write(b64)
    await callback.message.answer_document(FSInputFile("backup_all.b64"), caption="%s Содержимое файла вставьте в переменную BACKUP_ALL_B64" % pe("save"))


@dp.callback_query(IS_ADMIN, F.data == "admin_download_accounts")
async def download_accounts(callback: types.CallbackQuery):
    await callback.answer("Собираю архив…")
    try:
        path = shutil.make_archive("accounts_backup", "zip", ACCOUNTS_DIR)
        if os.path.getsize(path) > 49 * 1024 * 1024:
            return await callback.message.answer("%s Архив больше 50 МБ — скачайте папку accounts с сервера напрямую" % pe("warn"))
        await callback.message.answer_document(FSInputFile(path), caption="%s Склад аккаунтов" % pe("box"))
    except Exception as e:
        await callback.message.answer("%s Ошибка: %s" % (pe("cross"), esc(str(e)[:150])))


# ==================== АДМИН: ПРОМОКОДЫ ====================
@dp.message(IS_ADMIN, MENU("Промокоды"))
@dp.callback_query(IS_ADMIN, F.data == "admin_promo_dashboard")
async def admin_promo(event, state: FSMContext):
    await ack(event)
    await state.clear()
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Создать промокод", callback_data="admin_create_promo_code", icon_key="plus", style="primary")
    earnings = load_promo_earnings()
    for code, data in list(load_promo_codes().items())[:20]:
        uses = "%d/%s" % (data.get("current_uses", 0), data.get("max_uses") or "∞")
        mark = "" if data.get("is_active", True) else "⛔ "
        ibtn(kb, "%s%s (%s) %s %.0f₴" % (mark, code, uses, ("@" + data["owner_username"]) if data.get("owner_username") else "", earnings.get(code, {}).get("total_earned", 0)),
             callback_data="admin_promo_code_detail_%s" % code, icon_key="ticket")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1)
    await out(event, "%s <b>ПРОМОКОДЫ</b>" % pe("ticket"), kb.as_markup())


@dp.callback_query(IS_ADMIN, F.data == "admin_create_promo_code")
async def create_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await show(callback.message, "%s Введите код промокода (латиница/цифры):" % pe("ticket"))
    await state.set_state(AdminPromoStates.waiting_for_promo_code)


@dp.message(IS_ADMIN, AdminPromoStates.waiting_for_promo_code, F.text)
async def promo_code_input(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_\-]{2,20}", code):
        return await message.answer("%s Только латиница, цифры, _ и - (2–20 символов)" % pe("cross"))
    if code in load_promo_codes():
        return await message.answer("%s Такой код уже есть" % pe("cross"))
    await state.update_data(promo_code=code)
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Процент", callback_data="promo_type_percent", style="primary")
    ibtn(kb, "Фикс ₴", callback_data="promo_type_fixed", icon_key="money", style="primary")
    kb.adjust(2)
    await message.answer("Код: <code>%s</code>\nТип скидки:" % esc(code), reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_discount_type)


@dp.callback_query(IS_ADMIN, AdminPromoStates.waiting_for_discount_type, F.data.startswith("promo_type_"))
async def promo_type(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    t = "percent" if callback.data == "promo_type_percent" else "fixed"
    await state.update_data(discount_type=t)
    await show(callback.message, "Введите %s:" % ("процент (1–100)" if t == "percent" else "сумму в ₴"))
    await state.set_state(AdminPromoStates.waiting_for_discount_value)


@dp.message(IS_ADMIN, AdminPromoStates.waiting_for_discount_value, F.text)
async def promo_value(message: types.Message, state: FSMContext):
    d = await state.get_data()
    try:
        v = float(message.text.replace(",", "."))
        if v <= 0 or (d.get("discount_type") == "percent" and v > 100):
            raise ValueError
    except ValueError:
        return await message.answer("%s Некорректное число" % pe("cross"))
    await state.update_data(discount_value=v)
    kb = InlineKeyboardBuilder()
    ibtn(kb, "∞ без лимита", callback_data="promo_unlimited")
    for n in (1, 10, 50, 100, 500):
        kb.button(text=str(n), callback_data="promo_max_%d" % n)
    kb.adjust(1, 5)
    await message.answer("Максимум использований:", reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_max_uses)


@dp.callback_query(IS_ADMIN, AdminPromoStates.waiting_for_max_uses, F.data.startswith("promo_"))
async def promo_max(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    mu = None if callback.data == "promo_unlimited" else int(callback.data.split("_")[-1])
    await state.update_data(max_uses=mu)
    kb = InlineKeyboardBuilder()
    for dd in (1, 7, 30, 90):
        ibtn(kb, "%d дн." % dd, callback_data="promo_expire_%d" % dd, icon_key="calendar")
    ibtn(kb, "Бессрочно", callback_data="promo_expire_0", icon_key="check")
    kb.adjust(2)
    await show(callback.message, "Срок действия:", kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_expires_date)


@dp.callback_query(IS_ADMIN, AdminPromoStates.waiting_for_expires_date, F.data.startswith("promo_expire_"))
async def promo_exp(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    days = int(callback.data.split("_")[-1])
    await state.update_data(expires_at=(datetime.now() + timedelta(days=days)).isoformat() if days > 0 else None)
    await show(callback.message, "%s Username партнёра-владельца (без @) или «-» если без партнёра:" % pe("user"))
    await state.set_state(AdminPromoStates.waiting_for_owner_username)


@dp.message(IS_ADMIN, AdminPromoStates.waiting_for_owner_username, F.text)
async def promo_owner(message: types.Message, state: FSMContext):
    user = message.text.strip().lstrip("@")
    if user == "-":
        user = None
    d = await state.get_data()
    p = load_promo_codes()
    p[d["promo_code"]] = {"code": d["promo_code"], "discount_type": d["discount_type"], "discount_value": d["discount_value"],
                          "max_uses": d["max_uses"], "current_uses": 0, "expires_at": d.get("expires_at"), "is_active": True,
                          "created_at": datetime.now().isoformat(), "owner_username": user, "total_earned": 0.0}
    save_promo_codes(p)
    desc = ("%s%%" % money(d["discount_value"])) if d["discount_type"] == "percent" else ("%s₴" % money(d["discount_value"]))
    await message.answer("%s <b>Создан!</b>\n\n%s <code>%s</code>\n%s %s\n%s %s" % (pe("check"), pe("ticket"), esc(d["promo_code"]), pe("money"), desc, pe("user"), uname(user)),
                         reply_markup=get_admin_reply_keyboard())
    await state.clear()


@dp.callback_query(IS_ADMIN, F.data.startswith("admin_promo_code_detail_"))
async def promo_detail(callback: types.CallbackQuery):
    code = callback.data[24:]
    p = load_promo_codes().get(code)
    if not p:
        return await alert(callback, "❌ Не найден")
    await callback.answer()
    desc = ("%s%%" % money(p["discount_value"])) if p["discount_type"] == "percent" else ("%s₴" % money(p["discount_value"]))
    exp = p.get("expires_at")
    text = ("%s <b>%s</b>\n\n%s Скидка: %s\n%s Партнёр: %s\n%s Статус: %s\n%s Использований: %d/%s\n%s Срок: %s\n%s Заработано партнёром: %.0f₴"
            % (pe("ticket"), esc(code), pe("money"), desc, pe("user"), uname(p.get("owner_username")), pe("pin"),
               "активен" if p.get("is_active", True) else "выключен", pe("chart"), p.get("current_uses", 0), p.get("max_uses") or "∞",
               pe("calendar"), exp[:10] if exp else "бессрочно", pe("money"), p.get("total_earned", 0)))
    kb = InlineKeyboardBuilder()
    if p.get("is_active", True):
        ibtn(kb, "Выключить", callback_data="admin_deactivate_promo_%s" % code, icon_key="cross", style="danger")
    else:
        ibtn(kb, "Включить", callback_data="admin_activate_promo_%s" % code, icon_key="check", style="success")
    ibtn(kb, "Удалить", callback_data="admin_delete_promo_%s" % code, icon_key="trash", style="danger")
    ibtn(kb, "Назад", callback_data="admin_promo_dashboard", icon_key="back", style="danger")
    kb.adjust(1)
    await show(callback.message, text, kb.as_markup())


async def _promo_toggle(callback, code, active):
    p = load_promo_codes()
    if code in p:
        p[code]["is_active"] = active
        save_promo_codes(p)
    await callback.answer("Включён ✅" if active else "Выключен ⛔")
    callback.data = "admin_promo_code_detail_%s" % code
    await promo_detail(callback)


@dp.callback_query(IS_ADMIN, F.data.startswith("admin_deactivate_promo_"))
async def deact(callback: types.CallbackQuery):
    await _promo_toggle(callback, callback.data[23:], False)


@dp.callback_query(IS_ADMIN, F.data.startswith("admin_activate_promo_"))
async def act(callback: types.CallbackQuery):
    await _promo_toggle(callback, callback.data[21:], True)


@dp.callback_query(IS_ADMIN, F.data.startswith("admin_delete_promo_"))
async def delp(callback: types.CallbackQuery, state: FSMContext):
    code = callback.data[19:]
    p = load_promo_codes()
    if code in p:
        del p[code]
        save_promo_codes(p)
    await callback.answer("🗑 Удалён")
    await admin_promo(callback, state)


# ==================== ФОНОВЫЕ ЗАДАЧИ ====================
async def expire_orders():
    ttl = int(get_setting("order_ttl_minutes", 60))
    if ttl <= 0:
        return
    limit = datetime.now() - timedelta(minutes=ttl)
    for rk, o in list(load_orders().items()):
        if o.get("status") != "awaiting_payment" or o.get("receipt_sent"):
            continue
        try:
            if datetime.fromisoformat(o["created_at"]) > limit:
                continue
        except Exception:
            continue
        cancel_order(rk, "expired")
        try:
            await bot.send_message(o["user_id"], "%s Заказ %s отменён: не оплачен вовремя. Оформите заново в каталоге." % (pe("time"), rk))
        except Exception:
            pass


async def maintenance_loop():
    while True:
        await asyncio.sleep(300)
        try:
            await expire_orders()
            await ensure_recent_watchers()
        except Exception as e:
            logger.error("maintenance: %s", e)


# ==================== ЗАПАСНЫЕ ОБРАБОТЧИКИ (В КОНЦЕ!) ====================
@dp.message(IS_ADMIN, StateFilter_none := None) if False else dp.message(IS_ADMIN, F.text)
async def admin_unknown(message: types.Message, state: FSMContext):
    if await state.get_state() is not None:
        return
    await message.answer("Используйте кнопки меню или /admin", reply_markup=get_admin_reply_keyboard())


@dp.message(NOT_ADMIN, F.text)
async def user_unknown(message: types.Message, state: FSMContext):
    if await state.get_state() is not None:
        return
    await message.answer("Используйте кнопки меню ниже или /menu", reply_markup=get_main_reply_keyboard())


@dp.callback_query()
async def stale_callback(callback: types.CallbackQuery):
    await callback.answer("⚠️ Кнопка устарела — откройте меню заново (/start)", show_alert=True)


@dp.errors()
async def on_err(event):
    logger.error("Handler error: %s", event.exception, exc_info=event.exception)
    try:
        cb = event.update.callback_query
        if cb:
            await cb.answer("⚠️ Произошла ошибка, попробуйте ещё раз", show_alert=True)
    except Exception:
        pass
    return True


async def main():
    print("=" * 50)
    print("OverPass Store Bot v9")
    print("=" * 50)
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(maintenance_loop())
    asyncio.create_task(ensure_recent_watchers())
    print("Бот запущен!")
    try:
        await dp.start_polling(bot, drop_pending_updates=True, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Остановлен")
    except Exception as e:
        print("Ошибка: %s" % e)
        sys.exit(1)
