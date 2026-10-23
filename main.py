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
PARTNER_GROUP_ID = -5598258715

API_ID = 38387697
API_HASH = "e8fb7f7163498eb28231e45071fe92c0"

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ==================== ПРЕМИУМ ЭМОДЗИ ====================
EMOJI = {
    "star":     ("5438496463044752972", "⭐"),
    "check":    ("5206607081334906820", "✅"),
    "fire":     ("5424972470023104089", "🔥"),
    "money":    ("5287231198098117669", "💰"),
    "cart":     ("5312361253610475399", "🛍"),
    "user":     ("5190872550250405805", "👤"),
    "gift":     ("5278467510604160626", "🎁"),
    "time":     ("5382194935057372936", "⏱"),
    "warn":     ("5447644880824181073", "⚠️"),
    "box":      ("5472335930549347896", "📦"),
    "card":     ("5445353829304387411", "💳"),
    "key":      ("5413395871008058098", "🔑"),
    "phone":    ("5407025283456835913", "📱"),
    "lock":     ("5197288647275071607", "🔐"),
    "trash":    ("5445267414562389170", "🗑"),
    "chart":    ("5231200819986047254", "📊"),
    "chart_up": ("5397892696926860982", "📈"),
    "gear":     ("5341715473882955310", "⚙️"),
    "megaphone":("5424818078833715060", "📢"),
    "link":     ("5271604874419647061", "🔗"),
    "save":     ("5462956611033117422", "💾"),
    "calendar": ("5274055917766202507", "📅"),
    "rocket":   ("5188481279963715781", "🚀"),
    "heart":    ("4996980495100150380", "❤️"),
    "cross":    ("5210952531676504517", "❌"),
    "question": ("5436113877181941026", "❓"),
    "plus":     ("5397916757333654639", "➕"),
    "refresh":  ("5346269127059196142", "🔄"),
    "back":     ("5258236805890710909", "⬅️"),
    "next":     ("5877468380125990242", "➡️"),
    "trophy":   ("5188344996356448758", "🏆"),
    "crown":    ("5217822164362739968", "👑"),
    "diamond":  ("5427168083074628963", "💎"),
    "medal1":   ("5440539497383087970", "🥇"),
    "medal2":   ("5447203607294265305", "🥈"),
    "medal3":   ("5453902265922376865", "🥉"),
    "ticket":   ("5377599075237502153", "🎟"),
    "chat":     ("5443038326535759644", "💬"),
    "globe":    ("5224450179368767019", "🌍"),
    "pin":      ("5938027397524754858", "📌"),
    "sparkle":  ("5325547803936572038", "✨"),
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
    try: builder.add(InlineKeyboardButton(**kw))
    except TypeError:
        kw.pop("icon_custom_emoji_id", None); kw.pop("style", None)
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

BACKUP_FILES = ["orders","users","referrals","promo_codes","settings","order_counter","reviews","relay_map","requisites","chat_history","broadcasts","traffic_sources","promo_earnings"]

def restore_from_env():
    for name in BACKUP_FILES:
        v = os.environ.get(f"BACKUP_{name.upper()}_B64")
        if not v: continue
        p = f"{name}.json"
        if os.path.exists(p) and os.path.getsize(p) > 2: continue
        try:
            with open(p, "w", encoding="utf-8") as f: f.write(base64.b64decode(v).decode("utf-8"))
            print(f"[BACKUP] {name} восстановлен")
        except Exception as e: logger.error(f"Restore {name}: {e}")

def auto_backup_note(name, data):
    try:
        raw = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        with open(f"backup_{name}.b64", "w", encoding="utf-8") as f: f.write(base64.b64encode(raw).decode())
    except: pass

def load_json(p):
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f: return json.load(f)
    return {}

def save_json(p, d):
    with open(p, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False, indent=2)
    n = p.replace(".json","")
    if n in BACKUP_FILES: auto_backup_note(n, d)

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
def load_chat_history(): return load_json(CHAT_HISTORY_FILE)
def save_chat_history(x): save_json(CHAT_HISTORY_FILE, x)
def load_broadcasts(): return load_json(BROADCASTS_FILE)
def save_broadcasts(x): save_json(BROADCASTS_FILE, x)
def load_traffic_sources(): return load_json(TRAFFIC_SOURCES_FILE)
def save_traffic_sources(x): save_json(TRAFFIC_SOURCES_FILE, x)
def load_promo_earnings(): return load_json(PROMO_EARNINGS_FILE)
def save_promo_earnings(x): save_json(PROMO_EARNINGS_FILE, x)

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

def detect_country(phone):
    if not phone: return ("unknown", "❓ Неизвестно")
    clean = phone.replace("+", "").replace(" ", "").replace("-", "")
    for length in (3, 2, 1):
        p = clean[:length]
        if p in COUNTRY_CODES: return COUNTRY_CODES[p]
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

# ==================== СКЛАД ====================
def country_dir(c): return os.path.join(ACCOUNTS_DIR, c)
def session_path(c, n): return os.path.join(country_dir(c), f"{n}.session")
def watcher_path(c, n): return os.path.join(country_dir(c), f"{n}_watcher.session")
def meta_path(c, n): return os.path.join(country_dir(c), f"{n}.json")

def load_meta(c, n):
    p = meta_path(c, n)
    if not os.path.exists(p): return None
    with open(p, "r", encoding="utf-8") as f: return json.load(f)

def save_meta(c, n, meta):
    with open(meta_path(c, n), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

async def analyze_session(session_file):
    client = TelegramClient(session_file.replace(".session", ""), API_ID, API_HASH)
    res = {"valid": False, "phone": None, "user_id": None, "first_name": None, "has_2fa": False, "password_hint": None}
    try:
        await client.connect()
        if not await client.is_user_authorized():
            res["error"] = "NOT_AUTHORIZED"; return res
        me = await client.get_me()
        if not me:
            res["error"] = "NO_ME"; return res
        res.update({"valid": True, "phone": me.phone, "user_id": me.id, "first_name": me.first_name, "username": me.username, "premium": getattr(me, "premium", False)})
        try:
            pwd = await client(functions.account.GetPasswordRequest())
            if getattr(pwd, "has_password", False):
                res["has_2fa"] = True
                res["password_hint"] = getattr(pwd, "hint", None)
        except Exception as e: logger.warning(f"2FA check: {e}")
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {str(e)[:100]}"
    finally:
        try: await client.disconnect()
        except: pass
    return res

def all_available(country=None, stock_type=None):
    if not os.path.exists(ACCOUNTS_DIR): return []
    result = []
    countries = [country] if country else os.listdir(ACCOUNTS_DIR)
    for c in countries:
        cd = country_dir(c)
        if not os.path.isdir(cd): continue
        for f in os.listdir(cd):
            if f.endswith(".json"):
                meta = load_meta(c, f.replace(".json",""))
                if meta and meta.get("status") == "available":
                    if stock_type and meta.get("stock_type") != stock_type: continue
                    result.append(meta)
    return result

def stock_count(stock_type=None):
    counts = {}
    if not os.path.exists(ACCOUNTS_DIR): return counts
    for c in os.listdir(ACCOUNTS_DIR):
        cd = country_dir(c)
        if not os.path.isdir(cd): continue
        counts[c] = 0
        for f in os.listdir(cd):
            if f.endswith(".json"):
                meta = load_meta(c, f.replace(".json",""))
                if meta and meta.get("status") == "available":
                    if stock_type and meta.get("stock_type") != stock_type: continue
                    counts[c] += 1
    return {k:v for k,v in counts.items() if v>0}

def reserve_account(country, uid, stock_type=None):
    avail = all_available(country, stock_type)
    if not avail: return None
    acc = avail[0]
    acc["status"] = "reserved"; acc["reserved_by"] = uid; acc["reserved_at"] = datetime.now().isoformat()
    save_meta(country, acc["session_name"], acc)
    return acc

def release_account(country, n):
    meta = load_meta(country, n)
    if not meta: return
    meta["status"] = "available"; meta.pop("reserved_by", None); meta.pop("reserved_at", None)
    save_meta(country, n, meta)

def mark_sold(country, n, uid):
    meta = load_meta(country, n)
    if not meta: return
    meta["status"] = "sold"; meta["sold_at"] = datetime.now().isoformat(); meta["sold_to"] = uid
    save_meta(country, n, meta)

def get_user_accounts(uid):
    result = []
    if not os.path.exists(ACCOUNTS_DIR): return result
    for c in os.listdir(ACCOUNTS_DIR):
        cd = country_dir(c)
        if not os.path.isdir(cd): continue
        for f in os.listdir(cd):
            if f.endswith(".json"):
                meta = load_meta(c, f.replace(".json",""))
                if meta and meta.get("sold_to") == uid: result.append(meta)
    return result

# ==================== ПЕРЕХВАТ КОДОВ ====================
active_watchers, watcher_users, watcher_passwords, watcher_orders = {}, {}, {}, {}

async def watch_codes(session_file, user_id, password=None, order_key=None):
    session_name = os.path.basename(session_file).replace(".session","")
    if session_name in active_watchers:
        watcher_users[session_name] = user_id
        if password: watcher_passwords[session_name] = password
        if order_key: watcher_orders[session_name] = order_key
        return
    client = TelegramClient(session_file.replace(".session",""), API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            try: await bot.send_message(user_id, f"{pe('warn')} Сессия недействительна. @MaskYoY")
            except: pass
            return
        @client.on(events.NewMessage(from_users=[777000]))
        async def handler(event):
            text = event.message.text or ""
            target = watcher_users.get(session_name)
            if not target: return
            m = re.search(r'\b(\d{5})\b', text)
            if m:
                code = m.group(1); pwd = watcher_passwords.get(session_name)
                msg = f"{pe('key')} <b>КОД ПОДТВЕРЖДЕНИЯ</b>\n\n<code>{code}</code>\n\n"
                if pwd: msg += f"{pe('lock')} <b>Пароль (2FA):</b> <code>{pwd}</code>\n\n"
                msg += "Введите код в Telegram сейчас же!"
                try: await bot.send_message(target, msg)
                except Exception as e: logger.error(f"Send code: {e}")
                return
            low = text.lower()
            if any(s in low for s in ["новый вход", "new login", "вы вошли", "you have logged in", "новое устройство", "new device"]):
                order_key_local = watcher_orders.get(session_name)
                try:
                    kb = InlineKeyboardBuilder()
                    if order_key_local: ibtn(kb, "Оставить отзыв", callback_data=f"leave_review_{order_key_local}", icon_key="star", style="success")
                    ibtn(kb, "Мои аккаунты", callback_data="my_accounts", icon_key="box")
                    kb.adjust(1)
                    await bot.send_message(target,
                        f"{pe('check')} <b>ВХОД ПОДТВЕРЖДЁН!</b>\n\n"
                        f"{pe('phone')} Сессия: <code>{session_name}</code>\n"
                        f"{pe('sparkle')} Аккаунт успешно вошёл.\n\n"
                        f"Пожалуйста, оставь отзыв!",
                        reply_markup=kb.as_markup())
                except Exception as e: logger.error(f"Login notify: {e}")
                try:
                    await bot.send_message(ADMIN_ID,
                        f"{pe('check')} <b>ПОКУПАТЕЛЬ ВОШЁЛ</b>\n\n"
                        f"{pe('user')} ID: <code>{target}</code>\n"
                        f"{pe('phone')} Сессия: <code>{session_name}</code>\n"
                        f"🆔 Заказ: <code>{order_key_local or '—'}</code>")
                except: pass
                if order_key_local:
                    try:
                        orders = load_orders(); rk = find_order_key(orders, order_key_local)
                        if rk and orders[rk].get("status") != "completed":
                            orders[rk]["status"] = "completed"
                            orders[rk]["completed_at"] = datetime.now().isoformat()
                            save_orders(orders)
                    except Exception as e: logger.error(f"Auto-complete: {e}")
        active_watchers[session_name] = client
        watcher_users[session_name] = user_id
        if password: watcher_passwords[session_name] = password
        if order_key: watcher_orders[session_name] = order_key
        await client.run_until_disconnected()
    except Exception as e: logger.error(f"Watcher {session_name}: {e}")
    finally: active_watchers.pop(session_name, None)

async def start_code_watcher(c, n, uid, order_key=None):
    meta = load_meta(c, n)
    pwd = meta.get("password") if meta else None
    sess = watcher_path(c, n)
    if not os.path.exists(sess): sess = session_path(c, n)
    await watch_codes(sess, uid, pwd, order_key)

# ==================== НАСТРОЙКИ ====================
DEFAULT_SETTINGS = {
    "referral_bonus_percent": 5.0, "partner_commission_percent": 20.0,
    "level_bronze_min": 0, "level_bronze_discount": 0,
    "level_silver_min": 500, "level_silver_discount": 3,
    "level_gold_min": 1500, "level_gold_discount": 5,
    "level_platinum_min": 3000, "level_platinum_discount": 7,
    "level_vip_min": 5000, "level_vip_discount": 10,
}
if not os.path.exists(SETTINGS_FILE): save_settings(DEFAULT_SETTINGS)
def get_setting(k, d=None): return load_settings().get(k, DEFAULT_SETTINGS.get(k, d))
LEVEL_KEYS = {"bronze": "Бронза", "silver": "Серебро", "gold": "Золото", "platinum": "Платина", "vip": "VIP"}

# ==================== ПОЛЬЗОВАТЕЛИ ====================
async def add_user(user_id, username=None, full_name=None, ref_code=None):
    users = load_users(); referrals = load_referrals(); key = str(user_id); is_new = key not in users
    if is_new:
        users[key] = {"user_id": user_id, "username": username, "full_name": full_name,
                      "first_seen": datetime.now().isoformat(), "last_active": datetime.now().isoformat(),
                      "referred_by": None, "referral_code": None, "total_spent": 0.0, "orders_count": 0, "traffic_source": None}
        if ref_code and ref_code.startswith("ref_"):
            actual = ref_code[4:]
            for rid, rdata in referrals.items():
                if rdata.get("referral_code") == actual:
                    users[key]["referred_by"] = int(rid)
                    rdata.setdefault("referrals_list", []).append({"user_id": user_id, "username": username, "date": datetime.now().isoformat(), "first_purchase_done": False})
                    break
        if ref_code and not ref_code.startswith("ref_"):
            users[key]["traffic_source"] = ref_code
            sources = load_traffic_sources()
            if ref_code not in sources: sources[ref_code] = {"total_visits":0,"total_registrations":0,"total_purchases":0,"total_revenue":0.0,"created_at":datetime.now().isoformat()}
            sources[ref_code]["total_visits"] += 1; sources[ref_code]["total_registrations"] += 1
            save_traffic_sources(sources)
        code = hashlib.md5(f"{user_id}_ref_salt".encode()).hexdigest()[:8].upper()
        users[key]["referral_code"] = code
        referrals.setdefault(key, {"user_id": user_id, "referral_code": code, "referrals_list": [], "total_earned": 0.0})
        save_referrals(referrals); save_users(users); return True
    users[key]["last_active"] = datetime.now().isoformat()
    if username: users[key]["username"] = username
    if full_name: users[key]["full_name"] = full_name
    own = users[key].get("referral_code")
    if not own:
        own = hashlib.md5(f"{user_id}_ref_salt".encode()).hexdigest()[:8].upper()
        users[key]["referral_code"] = own
    referrals.setdefault(key, {"user_id": user_id, "referral_code": own, "referrals_list": [], "total_earned": 0.0})
    save_referrals(referrals); save_users(users); return False

DEFAULT_REQUISITES = {
    "uah": f"{pe('money')} <b>Карта Моно:</b> <code>4874 0700 2513 7454</code>\n\n{pe('gift')} <b>Подарок в ЛС:</b> @MaskYoY",
    "gift": f"{pe('gift')} <b>Подарок в ЛС:</b> @MaskYoY",
}
if not os.path.exists(REQUISITES_FILE): save_requisites(DEFAULT_REQUISITES)
def get_requisites(m): return load_requisites().get(m, DEFAULT_REQUISITES.get(m, "Уточните у продавца"))

# ==================== КАТАЛОГ ====================
# stock_type: "virtual" | "physical" | "none"
CATEGORIES = {
    "virtual": {
        "name": f"{pe('phone')} ВИРТУАЛЬНЫЕ НОМЕРА",
        "stock_type": "virtual",
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
        "name": "☎️ ФИЗИЧЕСКИЕ НОМЕРА",
        "stock_type": "physical",
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
        "name": f"{pe('fire')} TIKTOK",
        "stock_type": "none",
        "products": {
            "Обычный TikTok":   {"uah": 50,  "code": "tt"},
            "TikTok с эфирами": {"uah": 240, "code": "tt_live"},
        },
    },
    "discord": {
        "name": f"{pe('chat')} DISCORD",
        "stock_type": "none",
        "products": {
            "Новый Discord":   {"uah": 40,  "code": "dc"},
            "Discord с Nitro": {"uah": 150, "code": "dc_nitro"},
        },
    },
    "stars": {
        "name": f"{pe('star')} TELEGRAM STARS",
        "stock_type": "none",
        "products": {},
    },
}

# Пакеты звёзд
STAR_PACKAGES = [
    {"count": 13,  "price": 7},
    {"count": 21,  "price": 15},
    {"count": 43,  "price": 35},
    {"count": 85,  "price": 60},
    {"count": 98,  "price": 70},
    {"count": 106, "price": 75},
    {"count": 128, "price": 80},
    {"count": 170, "price": 130},
]

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

class StarStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment = State()
    waiting_for_confirm = State()

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
    c = load_order_counter(); cur = c.get("current", 0) + 1
    c["current"] = cur; save_order_counter(c)
    return f"#{cur:06d}"

def find_order_key(orders, oid):
    if not oid: return None
    oid = str(oid).strip()
    if oid in orders: return oid
    clean = oid.replace("#","").strip()
    for k, o in orders.items():
        if str(k).replace("#","").strip() == clean: return k
        if str(o.get("short_id","")).replace("#","").strip() == clean: return k
    return None

def get_user_level(uid):
    users = load_users(); u = users.get(str(uid), {}); spent = u.get("total_spent", 0)
    levels = [
        ("VIP", get_setting("level_vip_min",5000), get_setting("level_vip_discount",10), "crown"),
        ("Платина", get_setting("level_platinum_min",3000), get_setting("level_platinum_discount",7), "diamond"),
        ("Золото", get_setting("level_gold_min",1500), get_setting("level_gold_discount",5), "medal1"),
        ("Серебро", get_setting("level_silver_min",500), get_setting("level_silver_discount",3), "medal2"),
        ("Бронза", get_setting("level_bronze_min",0), get_setting("level_bronze_discount",0), "medal3"),
    ]
    for name, mn, d, ek in levels:
        if spent >= mn: return {"name": name, "discount": d, "emoji": pe(ek), "min_spent": mn}
    return {"name": "Бронза", "discount": 0, "emoji": pe("medal3"), "min_spent": 0}

async def check_subscription(uid):
    try:
        m = await bot.get_chat_member(chat_id=STORE_CHANNEL_ID, user_id=uid)
        return m.status in ["member", "administrator", "creator"]
    except: return False

# ==================== КЛАВИАТУРЫ ====================
def get_main_reply_keyboard():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=f"{EMOJI['cart'][1]} Каталог"), KeyboardButton(text=f"{EMOJI['star'][1]} Купить звёзды"))
    b.row(KeyboardButton(text=f"{EMOJI['cart'][1]} Мои заказы"), KeyboardButton(text=f"{EMOJI['box'][1]} Мои аккаунты"))
    b.row(KeyboardButton(text=f"{EMOJI['chat'][1]} Отзывы"), KeyboardButton(text=f"{EMOJI['question'][1]} FAQ"))
    b.row(KeyboardButton(text=f"{EMOJI['user'][1]} Профиль"), KeyboardButton(text=f"{EMOJI['gift'][1]} Рефералы"))
    b.row(KeyboardButton(text=f"{EMOJI['ticket'][1]} Промокод"), KeyboardButton(text=f"{EMOJI['megaphone'][1]} Канал"))
    return b.as_markup(resize_keyboard=True)

def get_admin_reply_keyboard():
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text=f"{EMOJI['chart'][1]} Статистика"), KeyboardButton(text=f"{EMOJI['cart'][1]} Все заказы"))
    b.row(KeyboardButton(text=f"{EMOJI['time'][1]} Ожидают"), KeyboardButton(text=f"{EMOJI['check'][1]} Выполненные"))
    b.row(KeyboardButton(text=f"{EMOJI['box'][1]} Склад"), KeyboardButton(text=f"{EMOJI['money'][1]} Реквизиты"))
    b.row(KeyboardButton(text=f"{EMOJI['megaphone'][1]} Рассылка"), KeyboardButton(text=f"{EMOJI['user'][1]} Пользователи"))
    b.row(KeyboardButton(text=f"{EMOJI['chart_up'][1]} Панель"), KeyboardButton(text="🏠 Главное меню"))
    b.row(KeyboardButton(text=f"{EMOJI['ticket'][1]} Промокоды"), KeyboardButton(text=f"{EMOJI['star'][1]} Уровни"))
    b.row(KeyboardButton(text=f"{EMOJI['gift'][1]} Рефералы"), KeyboardButton(text=f"{EMOJI['chart'][1]} Аналитика"))
    b.row(KeyboardButton(text=f"{EMOJI['link'][1]} Источники"), KeyboardButton(text=f"{EMOJI['save'][1]} Бэкапы"))
    return b.as_markup(resize_keyboard=True)

def subscribe_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Подписаться", url="http://t.me/owerpass_store", icon_key="megaphone", style="primary")
    ibtn(kb, "Я подписался", callback_data="check_sub", icon_key="check", style="success")
    kb.adjust(1); return kb.as_markup()

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
    kb.adjust(2,2,2,2); return kb.as_markup()

def catalog_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Виртуальные номера", callback_data="cat_virtual", icon_key="phone", style="primary")
    ibtn(kb, "Физические номера", callback_data="cat_physical", icon_key="card", style="primary")
    ibtn(kb, "TikTok", callback_data="cat_tiktok", icon_key="fire", style="primary")
    ibtn(kb, "Discord", callback_data="cat_discord", icon_key="chat", style="primary")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def category_products_keyboard(category):
    kb = InlineKeyboardBuilder()
    cat = CATEGORIES[category]
    stock_type = cat.get("stock_type", "none")
    counts = stock_count(stock_type) if stock_type != "none" else {}
    for pname, pdata in cat["products"].items():
        code = pdata.get("code", "")
        in_stock = counts.get(code, 0) if stock_type != "none" else 999
        if in_stock > 0:
            ibtn(kb, f"{pname} — {in_stock} шт. | {pdata['uah']}₴", callback_data=f"product_{category}_{code}", icon_key="fire" if in_stock < 5 else None)
        else:
            ibtn(kb, f"❌ {pname} — НЕТ", callback_data="out_of_stock", icon_key="cross", style="danger")
    ibtn(kb, "В каталог", callback_data="menu_catalog", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def quantity_keyboard():
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text=f"{i} шт.", callback_data=f"qty_{i}")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="cross", style="danger")
    kb.adjust(5,1); return kb.as_markup()

def confirm_order_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Подтвердить", callback_data="confirm_order", icon_key="check", style="success")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="cross", style="danger")
    kb.adjust(1); return kb.as_markup()

def awaiting_payment_keyboard(order_id):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Написать продавцу", url="https://t.me/MaskYoY", icon_key="chat", style="primary")
    ibtn(kb, "Написать в боте", callback_data=f"support_{order_id}", icon_key="warn")
    ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
    kb.adjust(1); return kb.as_markup()

def user_order_actions_keyboard(order_id):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Запросить код", callback_data=f"request_code_{order_id}", icon_key="key", style="primary")
    ibtn(kb, "Оставить отзыв", callback_data=f"leave_review_{order_id}", icon_key="star", style="success")
    ibtn(kb, "Запросить замену", callback_data=f"user_replace_{order_id}", icon_key="refresh")
    ibtn(kb, "Запросить возврат", callback_data=f"user_refund_{order_id}", icon_key="money", style="danger")
    ibtn(kb, "Все заказы", callback_data="my_orders", icon_key="cart")
    kb.adjust(1); return kb.as_markup()

def reviews_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Посмотреть отзывы", url="https://t.me/owerpass_repa", icon_key="star", style="primary")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def stars_keyboard():
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        ibtn(kb, f"{i} ⭐", callback_data=f"stars_{i}", icon_key="star")
    kb.adjust(5); return kb.as_markup()

def review_photo_skip_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Пропустить фото", callback_data="skip_photo", icon_key="check", style="primary")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="cross", style="danger")
    kb.adjust(1); return kb.as_markup()

def moderation_keyboard(review_id):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Одобрить", callback_data=f"approve_{review_id}", icon_key="check", style="success")
    ibtn(kb, "Отклонить", callback_data=f"reject_{review_id}", icon_key="cross", style="danger")
    kb.adjust(2); return kb.as_markup()

def profile_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Мои аккаунты", callback_data="my_accounts", icon_key="box")
    ibtn(kb, "Рефералы", callback_data="referral_menu", icon_key="gift")
    ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
    ibtn(kb, "Главное меню", callback_data="main_menu", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def referral_menu_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Моя статистика", callback_data="referral_stats", icon_key="chart")
    ibtn(kb, "Назад", callback_data="profile_menu", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def requisites_edit_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Изменить гривны", callback_data="edit_req_uah", icon_key="money")
    ibtn(kb, "Изменить подарок", callback_data="edit_req_gift", icon_key="gift")
    kb.adjust(1); return kb.as_markup()

def admin_stock_menu_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Виртуальные номера", callback_data="admin_stock_virtual", icon_key="phone", style="primary")
    ibtn(kb, "Физические номера", callback_data="admin_stock_physical", icon_key="card", style="primary")
    ibtn(kb, "Все аккаунты", callback_data="admin_list_accounts", icon_key="cart")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_stock_type_keyboard(stock_type):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Загрузить .session", callback_data=f"admin_upload_{stock_type}", icon_key="plus", style="primary")
    ibtn(kb, "Список аккаунтов", callback_data=f"admin_list_{stock_type}", icon_key="cart")
    ibtn(kb, "Назад", callback_data="admin_stock_menu", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_order_card_keyboard(order_id, status, user_id):
    kb = InlineKeyboardBuilder()
    if status == "awaiting_payment":
        ibtn(kb, "Подтвердить оплату", callback_data=f"admin_confirm_payment_{order_id}", icon_key="check", style="success")
    elif status == "completed":
        ibtn(kb, "Возврат", callback_data=f"admin_refund_{order_id}", icon_key="money", style="danger")
    ibtn(kb, "Написать покупателю", callback_data=f"admin_chat_with_user_{order_id}", icon_key="chat")
    ibtn(kb, "Отменить", callback_data=f"admin_reject_{order_id}", icon_key="cross", style="danger")
    ibtn(kb, "Назад", callback_data="admin_back_to_list", icon_key="back", style="danger")
    ibtn(kb, "Обновить", callback_data=f"admin_order_detail_{order_id}", icon_key="refresh")
    kb.adjust(1); return kb.as_markup()

def admin_all_orders_keyboard(page=0, per_page=5, status_filter=None):
    kb = InlineKeyboardBuilder()
    orders = load_orders()
    filtered = {k:v for k,v in orders.items() if (not status_filter or v["status"] == status_filter)}
    order_list = sorted(filtered.items(), reverse=True)
    total_pages = (len(order_list) + per_page - 1) // per_page
    if total_pages == 0:
        ibtn(kb, "Обновить", callback_data="admin_page_0", icon_key="refresh")
        kb.adjust(1); return kb.as_markup()
    start = page * per_page; end = start + per_page
    for oid, order in order_list[start:end]:
        sym = method_symbol(order.get("payment_method", "uah"))
        short_id = order.get("short_id", oid[:8])
        total = order["total"] if isinstance(order["total"], str) else f"{order['total']}{sym}"
        ibtn(kb, f"{short_id} | {order['product'][:15]} | {total}", callback_data=f"admin_order_detail_{oid}")
    if total_pages > 1:
        if page > 0: ibtn(kb, "Назад", callback_data=f"admin_page_{page - 1}", icon_key="back")
        if page < total_pages - 1: ibtn(kb, "Вперёд", callback_data=f"admin_page_{page + 1}", icon_key="next")
    ibtn(kb, "Обновить", callback_data=f"admin_page_{page}", icon_key="refresh")
    kb.adjust(1); return kb.as_markup()

def admin_dashboard_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Заказы", callback_data="admin_orders_dashboard", icon_key="cart")
    ibtn(kb, "Склад", callback_data="admin_stock_menu", icon_key="box")
    ibtn(kb, "Рефералы", callback_data="admin_referrals_dashboard", icon_key="gift")
    ibtn(kb, "Промокоды", callback_data="admin_promo_dashboard", icon_key="ticket")
    ibtn(kb, "Уровни", callback_data="admin_levels_dashboard", icon_key="star")
    ibtn(kb, "Аналитика", callback_data="admin_analytics_dashboard", icon_key="chart_up")
    ibtn(kb, "Источники", callback_data="admin_traffic_dashboard", icon_key="link")
    ibtn(kb, "Бэкапы", callback_data="admin_backups", icon_key="save")
    ibtn(kb, "Обновить", callback_data="admin_dashboard_refresh", icon_key="refresh")
    kb.adjust(2,2,2,2,1); return kb.as_markup()

def admin_promo_codes_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Создать промокод", callback_data="admin_create_promo_code", icon_key="plus", style="primary")
    earnings = load_promo_earnings()
    for code, data in list(load_promo_codes().items())[:10]:
        uses = f"{data.get('current_uses', 0)}/{data.get('max_uses') or '∞'}"
        owner = data.get("owner_username", "Нет")
        earned = earnings.get(code, {}).get("total_earned", 0)
        ibtn(kb, f"{code} ({uses}) @{owner} {earned:.0f}₴", callback_data=f"admin_promo_code_detail_{code}", icon_key="ticket")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_levels_keyboard():
    kb = InlineKeyboardBuilder()
    for k, ek in [("bronze","medal3"),("silver","medal2"),("gold","medal1"),("platinum","diamond"),("vip","crown")]:
        ibtn(kb, LEVEL_KEYS[k], callback_data=f"admin_edit_level_{k}", icon_key=ek)
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_referrals_settings_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Изменить бонус %", callback_data="admin_edit_referral_bonus", icon_key="money")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_analytics_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "По дням", callback_data="admin_analytics_by_days", icon_key="calendar")
    ibtn(kb, "По часам", callback_data="admin_analytics_by_hours", icon_key="time")
    ibtn(kb, "По странам", callback_data="admin_analytics_by_country", icon_key="globe")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def stars_packages_keyboard():
    kb = InlineKeyboardBuilder()
    for pkg in STAR_PACKAGES:
        ibtn(kb, f"{pkg['count']} ⭐ — {pkg['price']} ₴", callback_data=f"starpkg_{pkg['count']}", icon_key="star", style="primary")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="back", style="danger")
    kb.adjust(2); return kb.as_markup()

def stars_payment_keyboard(amount, price):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Оплатить гривнами", callback_data=f"starpay_uah", icon_key="money", style="primary")
    ibtn(kb, "Назад", callback_data="menu_stars", icon_key="back", style="danger")
    kb.adjust(1); return kb.as_markup()

def stars_confirm_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Подтвердить", callback_data="star_confirm", icon_key="check", style="success")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="cross", style="danger")
    kb.adjust(1); return kb.as_markup()

# ==================== ТЕКСТЫ ====================
FAQ_TEXT = f"""
{pe('warn')} <b>КАК КУПИТЬ?</b>

{pe('cart')} <b>Аккаунты:</b>
1. Выберите категорию и страну
2. Выберите количество
3. Примените промокод (по желанию)
4. Оплатите — аккаунт выдастся автоматически

{pe('star')} <b>Звёзды:</b>
1. Выберите пакет (13, 21, 43...)
2. Оплатите — подарок придёт в ЛС от админа

{pe('key')} <b>Как войти в аккаунт:</b>
1. Получите .session файл
2. Войдите в Telegram
3. Нажмите «Запросить код»
4. Бот перешлёт код автоматически

{pe('chat')} @MaskYoY
{pe('megaphone')} @owerpass_store
"""

# ==================== СТАРТ ====================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    ref_code = None
    if message.text and len(message.text.split()) > 1: ref_code = message.text.split()[1]
    is_new = await add_user(message.from_user.id, message.from_user.username, message.from_user.full_name, ref_code=ref_code)
    if message.from_user.id == ADMIN_ID:
        await message.answer(f"{pe('warn')} <b>Админ-панель</b>", reply_markup=get_admin_reply_keyboard()); return
    if not await check_subscription(message.from_user.id):
        await message.answer(f"{pe('warn')} Подпишитесь на канал!", reply_markup=subscribe_keyboard()); return
    text = f"{pe('sparkle')} <b>Добро пожаловать в OverPass Store!</b>\n\n{pe('rocket')} Виртуальные и физические номера\n{pe('star')} Telegram Stars\n{pe('fire')} TikTok и Discord аккаунты\n\n"
    if is_new and ref_code and ref_code.startswith("ref_"):
        text += f"{pe('gift')} Вы зарегистрированы по реферальной ссылке!\n\n"
    text += "Выберите раздел:"
    await message.answer(text, reply_markup=get_main_reply_keyboard())

@dp.callback_query(F.data == "check_sub")
async def process_check_sub(callback: types.CallbackQuery):
    await callback.answer()
    if await check_subscription(callback.from_user.id):
        try: await callback.message.edit_text(f"{pe('check')} Спасибо!", reply_markup=main_menu_keyboard())
        except: await callback.message.answer(f"{pe('check')} Спасибо!", reply_markup=main_menu_keyboard())
        await callback.message.answer("Навигация:", reply_markup=get_main_reply_keyboard())
    else: await callback.answer(f"{pe('cross')} Не подписались!", show_alert=True)

# ==================== ЗВЁЗДЫ ====================
@dp.message(F.from_user.id != ADMIN_ID, F.text == "⭐ Купить звёзды")
@dp.callback_query(F.data == "menu_stars")
async def stars_menu(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); target = event.message
    else: target = event
    text = (
        f"{pe('star')} <b>ПОКУПКА TELEGRAM STARS</b>\n\n"
        f"{pe('sparkle')} Выберите пакет:\n\n"
        f"<i>Звёзды приходят в ЛС от админа после оплаты</i>"
    )
    try: await target.edit_text(text, reply_markup=stars_packages_keyboard())
    except: await target.answer(text, reply_markup=stars_packages_keyboard())

@dp.callback_query(F.data.startswith("starpkg_"))
async def star_pkg_selected(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    try:
        count = int(callback.data.replace("starpkg_", ""))
    except: return
    pkg = next((p for p in STAR_PACKAGES if p["count"] == count), None)
    if not pkg: return await callback.answer(f"{pe('cross')} Не найдено", show_alert=True)
    await state.update_data(star_count=count, star_price=pkg["price"])
    text = (
        f"{pe('star')} <b>Пакет: {count} ⭐</b>\n\n"
        f"{pe('money')} Сумма к оплате: <b>{pkg['price']} ₴</b>\n\n"
        f"Выберите способ оплаты:"
    )
    try: await callback.message.edit_text(text, reply_markup=stars_payment_keyboard(count, pkg["price"]))
    except: await callback.message.answer(text, reply_markup=stars_payment_keyboard(count, pkg["price"]))
    await state.set_state(StarStates.waiting_for_payment)

@dp.callback_query(StarStates.waiting_for_payment, F.data == "starpay_uah")
async def star_pay_uah(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    count = data.get("star_count"); price = data.get("star_price")
    text = (
        f"{pe('card')} <b>Подтверждение</b>\n\n"
        f"{pe('star')} Звёзды: <b>{count} ⭐</b>\n"
        f"{pe('money')} Сумма: <b>{price} ₴</b>\n\n"
        f"Подтвердить заказ?"
    )
    try: await callback.message.edit_text(text, reply_markup=stars_confirm_keyboard())
    except: await callback.message.answer(text, reply_markup=stars_confirm_keyboard())
    await state.set_state(StarStates.waiting_for_confirm)

@dp.callback_query(StarStates.waiting_for_confirm, F.data == "star_confirm")
async def star_confirm(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    count = data.get("star_count"); price = data.get("star_price")
    short_id = generate_short_order_id()
    orders = load_orders()
    orders[short_id] = {
        "order_id": short_id, "short_id": short_id,
        "user_id": callback.from_user.id,
        "username": callback.from_user.username,
        "full_name": callback.from_user.full_name,
        "category": "stars", "product": f"{count} ⭐",
        "code": "stars",
        "country_code": None, "session_name": None, "phone": None,
        "payment_method": "uah", "total": price,
        "used_promo_code": None,
        "status": "awaiting_payment",
        "created_at": datetime.now().isoformat(),
        "reviewed": False, "is_stars": True,
    }
    save_orders(orders)
    try:
        await bot.send_message(ADMIN_ID,
            f"{pe('star')} <b>ЗАКАЗ НА ЗВЁЗДЫ {short_id}</b>\n\n"
            f"{pe('user')} @{callback.from_user.username} | {callback.from_user.full_name}\n"
            f"🆔 <code>{callback.from_user.id}</code>\n"
            f"{pe('star')} Звёзды: <b>{count} ⭐</b>\n"
            f"{pe('money')} Сумма: <b>{price} ₴</b>\n\n"
            f"Подтвердите оплату — потом отправьте звёзды подарком в ЛС",
            reply_markup=InlineKeyboardBuilder().button(
                text="📋 Открыть заказ", callback_data=f"admin_order_detail_{short_id}").as_markup())
    except Exception as e: logger.error(f"Star admin notify: {e}")
    req = get_requisites("uah")
    await callback.message.edit_text(
        f"{pe('check')} <b>Заказ {short_id} создан!</b>\n\n"
        f"{pe('star')} {count} ⭐\n"
        f"{pe('money')} <b>{price} ₴</b>\n\n"
        f"<b>РЕКВИЗИТЫ:</b>\n{req}\n\n"
        f"{pe('warn')} После оплаты напишите @MaskYoY и пришлите чек.",
        reply_markup=awaiting_payment_keyboard(short_id))
    await state.clear()

# ==================== АДМИН: СКЛАД ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📦 Склад")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_stock_menu")
async def admin_stock_menu(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); target = event.message; edit = True
    else: target = event; edit = False
    v = stock_count("virtual"); p = stock_count("physical")
    text = (
        f"{pe('box')} <b>СКЛАД</b>\n\n"
        f"{pe('phone')} Виртуальных: <b>{sum(v.values())}</b>\n"
        f"{pe('card')} Физических: <b>{sum(p.values())}</b>"
    )
    kb = admin_stock_menu_keyboard()
    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: await target.answer(text, reply_markup=kb)
    else: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_stock_virtual")
async def admin_stock_virtual(callback: types.CallbackQuery):
    await callback.answer()
    counts = stock_count("virtual")
    text = f"{pe('phone')} <b>ВИРТУАЛЬНЫЕ НОМЕРА</b>\n\n"
    if counts:
        for c, n in sorted(counts.items(), key=lambda x: -x[1]):
            text += f"• {c.upper()}: <b>{n}</b>\n"
    else: text += "<i>Пусто</i>"
    await callback.message.edit_text(text, reply_markup=admin_stock_type_keyboard("virtual"))

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_stock_physical")
async def admin_stock_physical(callback: types.CallbackQuery):
    await callback.answer()
    counts = stock_count("physical")
    text = f"{pe('card')} <b>ФИЗИЧЕСКИЕ НОМЕРА</b>\n\n"
    if counts:
        for c, n in sorted(counts.items(), key=lambda x: -x[1]):
            text += f"• {c.upper()}: <b>{n}</b>\n"
    else: text += "<i>Пусто</i>"
    await callback.message.edit_text(text, reply_markup=admin_stock_type_keyboard("physical"))

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_upload_"))
async def admin_upload_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    stock_type = callback.data.replace("admin_upload_", "")
    await state.update_data(stock_type=stock_type)
    label = "виртуального" if stock_type == "virtual" else "физического"
    await callback.message.edit_text(
        f"{pe('plus')} Отправьте файл <code>.session</code> ({label} аккаунта).\n\n"
        f"Бот сам определит страну и проверит 2FA.")
    await state.set_state(AdminStockStates.waiting_for_session)

@dp.message(AdminStockStates.waiting_for_session, F.document)
async def admin_receive_session(message: types.Message, state: FSMContext):
    data = await state.get_data(); stock_type = data.get("stock_type", "virtual")
    doc = message.document
    if not doc.file_name.endswith(".session"):
        await message.answer(f"{pe('cross')} Нужен .session"); return
    temp_path = os.path.join(TEMP_DIR, doc.file_name)
    await bot.download(doc, temp_path)
    status_msg = await message.answer(f"{pe('time')} Анализирую сессию...")
    info = await analyze_session(temp_path)
    if not info.get("valid"):
        await status_msg.edit_text(f"{pe('cross')} <b>Сессия невалидна</b>\n\n<code>{info.get('error','unknown')}</code>")
        try: os.remove(temp_path)
        except: pass
        await state.clear(); return
    phone = info["phone"]; cc, cn = detect_country(phone)
    if info.get("has_2fa"):
        hint = info.get("password_hint") or "—"
        await status_msg.edit_text(f"{pe('warn')} <b>АККАУНТ С ПАРОЛЕМ!</b>\n\n{pe('globe')} {cn}\n{pe('phone')} <code>{phone}</code>\n{pe('lock')} Хинт: <code>{hint}</code>\n\n<b>НЕ добавлен.</b>")
        try: os.remove(temp_path)
        except: pass
        await state.clear(); return
    if cc not in DEFAULT_PRICES:
        await status_msg.edit_text(f"{pe('warn')} <b>Страна без цены</b>\n\n{pe('globe')} {cn}\nID: <code>{cc}</code>")
        try: os.remove(temp_path)
        except: pass
        await state.clear(); return
    price_uah, price_stars = DEFAULT_PRICES[cc]
    name = doc.file_name.replace(".session","")
    try:
        os.makedirs(country_dir(cc), exist_ok=True)
        shutil.copy(temp_path, session_path(cc, name))
        shutil.copy(temp_path, watcher_path(cc, name))
        meta = {
            "country": cc, "session_name": name, "phone": phone,
            "user_id": info["user_id"], "first_name": info.get("first_name"),
            "username": info.get("username"), "premium": info.get("premium", False),
            "has_2fa": False, "password": None,
            "price_uah": price_uah, "price_stars": price_stars,
            "stock_type": stock_type,
            "status": "available",
            "added_at": datetime.now().isoformat(), "sold_at": None, "sold_to": None,
        }
        save_meta(cc, name, meta)
        try: os.remove(temp_path)
        except: pass
        label = "виртуальный" if stock_type == "virtual" else "физический"
        await status_msg.edit_text(
            f"{pe('check')} <b>Аккаунт добавлен!</b> ({label})\n\n"
            f"{pe('globe')} {cn}\n{pe('phone')} <code>{phone}</code>\n"
            f"{pe('user')} {info.get('first_name','—')}\n"
            f"{pe('money')} {price_uah}₴")
    except Exception as e:
        await status_msg.edit_text(f"{pe('cross')} Ошибка: {e}")
    await state.clear()

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_list_"))
async def admin_list_by_type(callback: types.CallbackQuery):
    await callback.answer()
    stock_type = callback.data.replace("admin_list_", "")
    if stock_type == "accounts":
        stock_type = None
    avail = all_available(stock_type=stock_type) if stock_type else all_available()
    text = f"{pe('box')} <b>АККАУНТЫ ({len(avail)})</b>\n\n"
    for acc in avail[:30]:
        t = "📱" if acc.get("stock_type") == "virtual" else "☎️"
        text += f"{t} {acc['country'].upper()} | {acc['phone']} | {acc['price_uah']}₴\n"
    if len(avail) > 30: text += f"\n...и ещё {len(avail) - 30}"
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Назад", callback_data="admin_stock_menu" if stock_type else "admin_dashboard_refresh", icon_key="back", style="danger")
    try: await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except: await callback.message.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_list_accounts")
async def admin_list_accounts(callback: types.CallbackQuery):
    await admin_list_by_type(callback)

# ==================== КАТАЛОГ / ЗАКАЗ АККАУНТОВ ====================
@dp.message(F.from_user.id != ADMIN_ID, F.text == "🛍 Каталог")
async def catalog_kb(message: types.Message, state: FSMContext):
    if not await check_subscription(message.from_user.id):
        return await message.answer(f"{pe('warn')} Подпишитесь!", reply_markup=subscribe_keyboard())
    await state.clear()
    await message.answer(f"{pe('cart')} Категории:", reply_markup=catalog_keyboard())

@dp.callback_query(F.data == "menu_catalog")
async def open_catalog(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer(); await state.clear()
    try: await callback.message.edit_text(f"{pe('cart')} Категории:", reply_markup=catalog_keyboard())
    except: await callback.message.answer(f"{pe('cart')} Категории:", reply_markup=catalog_keyboard())

@dp.callback_query(F.data == "menu_reviews")
async def open_reviews(callback: types.CallbackQuery):
    await callback.answer()
    try: await callback.message.edit_text(f"{pe('chat')} Отзывы:", reply_markup=reviews_keyboard())
    except: await callback.message.answer(f"{pe('chat')} Отзывы:", reply_markup=reviews_keyboard())

@dp.callback_query(F.data == "out_of_stock")
async def out_of_stock(callback: types.CallbackQuery): await callback.answer(f"{pe('cross')} Товар закончился", show_alert=True)

@dp.callback_query(F.data.startswith("cat_"))
async def show_category(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    cat = callback.data.replace("cat_", "")
    if cat not in CATEGORIES: return
    if cat == "stars":
        await stars_menu(callback); return
    try: await callback.message.edit_text(f"{CATEGORIES[cat]['name']}\n\nВыберите товар:", reply_markup=category_products_keyboard(cat))
    except: await callback.message.answer(f"{CATEGORIES[cat]['name']}\n\nВыберите товар:", reply_markup=category_products_keyboard(cat))

@dp.callback_query(F.data.startswith("product_"))
async def product_selected(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    if len(parts) < 3: return
    category = parts[1]; code = parts[2]
    product_name = None
    for pname, pdata in CATEGORIES[category]["products"].items():
        if pdata.get("code") == code: product_name = pname; break
    if not product_name: return await callback.answer(f"{pe('cross')} Не найден", show_alert=True)
    stock_type = CATEGORIES[category].get("stock_type", "none")
    avail = all_available(code, stock_type) if stock_type != "none" else None
    if stock_type != "none" and not avail:
        return await callback.answer(f"{pe('cross')} Нет в наличии", show_alert=True)
    await state.update_data(category=category, product=product_name, code=code, stock_type=stock_type)
    try: await callback.message.edit_text(f"{pe('check')} {product_name}\n\n🔢 Выберите количество:", reply_markup=quantity_keyboard())
    except: await callback.message.answer(f"{pe('check')} {product_name}\n\n🔢 Выберите количество:", reply_markup=quantity_keyboard())
    await state.set_state(OrderStates.waiting_for_quantity)

@dp.callback_query(OrderStates.waiting_for_quantity, F.data.startswith("qty_"))
async def process_quantity(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    qty = int(callback.data.split("_")[1])
    await state.update_data(quantity=qty)
    data = await state.get_data()
    code = data["code"]; stock_type = data.get("stock_type", "none")
    avail = all_available(code, stock_type) if stock_type != "none" else None
    if stock_type != "none" and not avail:
        await callback.message.edit_text(f"{pe('cross')} Товар закончился", reply_markup=main_menu_keyboard())
        await state.clear(); return
    price = avail[0]["price_uah"] if avail else CATEGORIES[data["category"]]["products"][data["product"]]["uah"]
    await state.update_data(price_uah=price, base_price=price)
    text = (f"{pe('box')} {data['product']}\n{pe('money')} {price} ₴\n\n"
            f"Есть промокод? Введите его или нажмите «Пропустить»:")
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Пропустить", callback_data="skip_promo", icon_key="check")
    kb.adjust(1)
    try: await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except: await callback.message.answer(text, reply_markup=kb.as_markup())
    await state.set_state(OrderStates.waiting_for_promo_input)

@dp.callback_query(OrderStates.waiting_for_promo_input, F.data == "skip_promo")
async def skip_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(used_promo_code=None, discount_amount=0, final_price=await get_final_price(state))
    data = await state.get_data()
    text = f"{pe('card')} Способ оплаты:\n{pe('money')} Итого: <b>{data['final_price']} ₴</b>"
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Оплатить подарком", callback_data="pay_gift", icon_key="gift")
    ibtn(kb, "Оплатить гривнами", callback_data="pay_uah", icon_key="money", style="primary")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="cross", style="danger")
    kb.adjust(1)
    try: await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except: await callback.message.answer(text, reply_markup=kb.as_markup())
    await state.set_state(OrderStates.waiting_for_payment_method)

@dp.message(OrderStates.waiting_for_promo_input, F.text)
async def process_promo(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    p = load_promo_codes().get(code)
    valid = False; disc = 0
    if p and p.get("is_active", True):
        mu = p.get("max_uses"); cu = p.get("current_uses", 0)
        if (not mu or cu < mu) and (not p.get("expires_at") or datetime.now() < datetime.fromisoformat(p["expires_at"])):
            valid = True
            base = (await state.get_data()).get("base_price", 0)
            if p["discount_type"] == "percent": disc = round(base * (p["discount_value"] / 100), 2)
            else: disc = min(p["discount_value"], base)
    if valid:
        await state.update_data(used_promo_code=code, discount_amount=disc, final_price=await get_final_price(state))
        await message.answer(f"{pe('check')} Промокод <code>{code}</code> применён! Скидка: -{disc}₴")
        data = await state.get_data()
        kb = InlineKeyboardBuilder()
        ibtn(kb, "Оплатить подарком", callback_data="pay_gift", icon_key="gift")
        ibtn(kb, "Оплатить гривнами", callback_data="pay_uah", icon_key="money", style="primary")
        ibtn(kb, "Отмена", callback_data="main_menu", icon_key="cross", style="danger")
        kb.adjust(1)
        await message.answer(f"{pe('card')} Итого: <b>{data['final_price']} ₴</b>", reply_markup=kb.as_markup())
        await state.set_state(OrderStates.waiting_for_payment_method)
    else:
        await message.answer(f"{pe('cross')} Промокод недействителен. Введите другой или «Пропустить».")

async def get_final_price(state: FSMContext):
    data = await state.get_data()
    return max(0, data.get("base_price", 0) - data.get("discount_amount", 0))

@dp.callback_query(OrderStates.waiting_for_payment_method, F.data.startswith("pay_"))
async def process_payment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    method = callback.data.replace("pay_", "")
    await state.update_data(payment_method=method)
    data = await state.get_data()
    fp = data.get("final_price", data.get("price_uah"))
    used = data.get("used_promo_code")
    promo_line = f"{pe('ticket')} Промокод: <code>{used}</code>\n" if used else ""
    text = (f"{pe('cart')} <b>Подтверждение</b>\n\n"
            f"Товар: {data['product']}\n"
            f"Оплата: {'🎁 Подарок' if method == 'gift' else '💳 Гривны'}\n"
            f"{promo_line}"
            f"Сумма: <b>{fp} ₴</b>\n\nПодтвердить?")
    try: await callback.message.edit_text(text, reply_markup=confirm_order_keyboard())
    except: await callback.message.answer(text, reply_markup=confirm_order_keyboard())
    await state.set_state(OrderStates.waiting_for_confirmation)

@dp.callback_query(OrderStates.waiting_for_confirmation, F.data == "confirm_order")
async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    category, product, code = data["category"], data["product"], data["code"]
    stock_type = data.get("stock_type", "none")
    method = data["payment_method"]
    used = data.get("used_promo_code")
    fp = data.get("final_price", data.get("price_uah"))

    acc = None
    if stock_type != "none":
        acc = reserve_account(code, callback.from_user.id, stock_type)
        if not acc:
            await callback.message.edit_text(f"{pe('cross')} Товар закончился!", reply_markup=main_menu_keyboard())
            await state.clear(); return

    short_id = generate_short_order_id()
    if used:
        promos = load_promo_codes()
        if used in promos: promos[used]["current_uses"] = promos[used].get("current_uses", 0) + 1
        save_promo_codes(promos)

    orders = load_orders()
    orders[short_id] = {
        "order_id": short_id, "short_id": short_id,
        "user_id": callback.from_user.id, "username": callback.from_user.username,
        "full_name": callback.from_user.full_name,
        "category": category, "product": product, "code": code,
        "country_code": acc["country"] if acc else None,
        "session_name": acc["session_name"] if acc else None,
        "phone": acc["phone"] if acc else None,
        "payment_method": method, "total": fp,
        "used_promo_code": used,
        "status": "awaiting_payment", "created_at": datetime.now().isoformat(),
        "reviewed": False,
    }
    save_orders(orders)

    try:
        await bot.send_message(ADMIN_ID,
            f"{pe('sparkle')} <b>НОВЫЙ ЗАКАЗ {short_id}</b>\n\n"
            f"{pe('user')} @{callback.from_user.username} | {callback.from_user.full_name}\n"
            f"🆔 <code>{callback.from_user.id}</code>\n"
            f"{pe('globe')} {acc['country'].upper() if acc else code} | {pe('phone')} {acc['phone'] if acc else '—'}\n"
            f"{pe('money')} {fp}₴ | {'🎁 Подарок' if method == 'gift' else '💳 Гривны'}\n"
            f"{pe('ticket') + ' Промо: ' + used if used else ''}",
            reply_markup=InlineKeyboardBuilder().button(
                text="📋 Открыть заказ", callback_data=f"admin_order_detail_{short_id}").as_markup())
    except Exception as e: logger.error(f"Admin notify: {e}")

    req = get_requisites("uah" if method == "uah" else "gift")
    await callback.message.edit_text(
        f"{pe('check')} <b>Заказ {short_id} создан!</b>\n\n"
        f"{pe('globe')} {acc['country'].upper() if acc else code}\n"
        f"{pe('phone')} {acc['phone'] if acc else '—'}\n"
        f"{pe('money')} <b>{fp} ₴</b>\n\n"
        f"<b>РЕКВИЗИТЫ:</b>\n{req}\n\n"
        f"{pe('warn')} После оплаты напишите @MaskYoY с чеком.",
        reply_markup=awaiting_payment_keyboard(short_id))
    await state.clear()

# ==================== АДМИН: ЗАКАЗЫ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📋 Все заказы")
async def admin_all_orders(message: types.Message): await show_admin_orders_page(message, 0)
@dp.message(F.from_user.id == ADMIN_ID, F.text == "⏳ Ожидают")
async def admin_pending(message: types.Message): await show_admin_orders_page(message, 0, "awaiting_payment")
@dp.message(F.from_user.id == ADMIN_ID, F.text == "✅ Выполненные")
async def admin_completed(message: types.Message): await show_admin_orders_page(message, 0, "completed")

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_page_"))
async def admin_page_nav(callback: types.CallbackQuery):
    await callback.answer()
    page = int(callback.data.replace("admin_page_", ""))
    await show_admin_orders_page(callback.message, page, edit=True)

async def show_admin_orders_page(target, page, status_filter=None, edit=False):
    orders = load_orders()
    filtered = {k:v for k,v in orders.items() if (not status_filter or v["status"] == status_filter)}
    order_list = sorted(filtered.items(), reverse=True); per_page = 5
    if not order_list:
        kb = admin_all_orders_keyboard(0, per_page, status_filter)
        if edit: await target.edit_text(f"{pe('cart')} Нет заказов", reply_markup=kb)
        else: await target.answer(f"{pe('cart')} Нет заказов", reply_markup=get_admin_reply_keyboard())
        return
    total_pages = (len(order_list) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    text = f"{pe('cart')} <b>ЗАКАЗЫ</b> ({page + 1}/{total_pages})\n\n"
    for oid, order in order_list[page * per_page:(page + 1) * per_page]:
        e, _ = STATUS_CONFIG.get(order["status"], (pe("warn"), ""))
        s = method_symbol(order.get("payment_method", "uah"))
        short = order.get("short_id", oid[:8])
        created = datetime.fromisoformat(order["created_at"]).strftime("%d.%m %H:%M")
        text += f"{e} {short} | {order['product'][:20]}\n  @{order.get('username','—')} | {order['total']}{s} | {created}\n"
    kb = admin_all_orders_keyboard(page, per_page, status_filter)
    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: pass
    else: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_order_detail_"))
async def admin_order_detail(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("admin_order_detail_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk: return await callback.answer(f"{pe('cross')} Не найден", show_alert=True)
    order = orders[rk]
    e, st = STATUS_CONFIG.get(order["status"], (pe("warn"), ""))
    s = method_symbol(order.get("payment_method", "uah"))
    short = order.get("short_id", rk[:8])
    total = order["total"] if isinstance(order["total"], str) else f"{order['total']} {s}"
    text = (f"{pe('box')} <b>Заказ {short}</b>\n\n"
            f"{pe('user')} @{order.get('username','—')}\n"
            f"🆔 <code>{order['user_id']}</code>\n"
            f"{pe('calendar')} {datetime.fromisoformat(order['created_at']).strftime('%d.%m.%Y %H:%M')}\n"
            f"{pe('cart')} {order['product']}\n"
            f"{pe('money')} {total}\n"
            f"{pe('pin')} {e} {st}\n")
    if order.get("phone"): text += f"{pe('phone')} {order['phone']}\n"
    if order.get("used_promo_code"): text += f"{pe('ticket')} Промокод: <code>{order['used_promo_code']}</code>\n"
    if order.get("is_stars"): text += f"\n{pe('star')} <b>Это заказ на звёзды</b>\nПосле подтверждения оплаты отправьте звёзды подарком в ЛС."
    try: await callback.message.edit_text(text, reply_markup=admin_order_card_keyboard(rk, order["status"], order["user_id"]))
    except: await callback.message.answer(text, reply_markup=admin_order_card_keyboard(rk, order["status"], order["user_id"]))

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_back_to_list")
async def admin_back_to_list(callback: types.CallbackQuery):
    await callback.answer()
    await show_admin_orders_page(callback.message, 0, edit=True)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_confirm_payment_"))
async def admin_confirm_payment(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("admin_confirm_payment_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk: return
    order = orders[rk]
    order["status"] = "paid"; order["paid_at"] = datetime.now().isoformat(); save_orders(orders)

    if order.get("is_stars"):
        await callback.message.edit_text(
            f"{pe('check')} Оплата подтверждена!\n\n"
            f"{pe('star')} Это заказ на звёзды.\n"
            f"Отправьте {order['product']} подарком в ЛС @{order.get('username')}\n"
            f"Затем нажмите «Завершить».",
            reply_markup=admin_order_card_keyboard(rk, "paid", order["user_id"]))
    else:
        await callback.message.edit_text(f"{pe('check')} Оплата подтверждена. Выдаю аккаунт...")
        await deliver_to_user(order, rk)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_reject_"))
async def admin_reject(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("admin_reject_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk: return
    order = orders[rk]; order["status"] = "rejected"; save_orders(orders)
    if order.get("country_code") and order.get("session_name"):
        release_account(order["country_code"], order["session_name"])
    try: await bot.send_message(order["user_id"], f"{pe('cross')} Заказ {order.get('short_id', rk)} отклонён")
    except: pass
    try: await callback.message.edit_text(callback.message.text + f"\n{pe('cross')} <b>ОТКЛОНЁН</b>", reply_markup=admin_order_card_keyboard(rk, "rejected", order["user_id"]))
    except: pass

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_refund_"))
async def admin_refund(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("admin_refund_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk: return
    order = orders[rk]; order["status"] = "refunded"; save_orders(orders)
    try: await bot.send_message(order["user_id"], f"{pe('money')} Возврат по {order.get('short_id', rk)}.")
    except: pass
    await callback.message.edit_text(callback.message.text + f"\n{pe('money')} <b>ВОЗВРАТ</b>", reply_markup=admin_order_card_keyboard(rk, "refunded", order["user_id"]))

async def deliver_to_user(order, order_key):
    cc = order["country_code"]; sn = order["session_name"]; phone = order["phone"]; uid = order["user_id"]
    sess = session_path(cc, sn)
    if not os.path.exists(sess):
        try: await bot.send_message(uid, f"{pe('cross')} Файл не найден. @MaskYoY")
        except: pass
        return
    meta = load_meta(cc, sn)
    pwd = ""
    if meta and meta.get("password"): pwd = f"\n{pe('lock')} <b>Пароль:</b> <code>{meta['password']}</code>\n"
    _, cn = detect_country(phone)
    try:
        await bot.send_document(
            chat_id=uid,
            document=FSInputFile(sess, filename=f"{cc}_{phone}.session"),
            caption=(f"{pe('sparkle')} <b>ВАШ АККАУНТ</b>\n\n"
                     f"{pe('globe')} Страна: {cn}\n"
                     f"{pe('phone')} Номер: <code>{phone}</code>\n{pwd}\n"
                     f"<b>Как войти:</b>\n"
                     f"1. Войдите в аккаунт Telegram\n"
                     f"2. Используйте номер выше\n"
                     f"3. Нажмите «Запросить код»\n\n"
                     f"<b>{pe('key')} Код придёт сюда!</b>"),
            reply_markup=user_order_actions_keyboard(order_key))
        mark_sold(cc, sn, uid)
        order["status"] = "completed"; order["completed_at"] = datetime.now().isoformat()
        all_orders = load_orders(); all_orders[order_key] = order; save_orders(all_orders)
        users = load_users(); uk = str(uid)
        if uk in users:
            users[uk]["total_spent"] = users[uk].get("total_spent", 0) + (order.get("total", 0) if not isinstance(order.get("total", 0), str) else 0)
            users[uk]["orders_count"] = users[uk].get("orders_count", 0) + 1
            save_users(users)
        used = order.get("used_promo_code")
        if used: await process_partner_commission(used, order["total"], order_key)
        asyncio.create_task(start_code_watcher(cc, sn, uid, order_key))
        try: await bot.send_message(ADMIN_ID, f"{pe('check')} <b>АККАУНТ ВЫДАН</b>\n\n{pe('user')} <code>{uid}</code>\n{pe('globe')} {cc.upper()} | {phone}")
        except: pass
    except Exception as e: logger.error(f"Deliver: {e}")

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_complete_stars_"))
async def admin_complete_stars(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("admin_complete_stars_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk: return
    order = orders[rk]; order["status"] = "completed"; order["completed_at"] = datetime.now().isoformat()
    save_orders(orders)
    try:
        await bot.send_message(order["user_id"], f"{pe('check')} <b>Звёзды отправлены!</b>\n\n{pe('star')} {order['product']}\n\nСпасибо за покупку!", reply_markup=user_order_actions_keyboard(rk))
    except: pass
    await admin_order_detail(callback)

async def process_partner_commission(promo_code, order_total, order_key):
    try: order_total = float(order_total)
    except: return
    promos = load_promo_codes(); promo = promos.get(promo_code)
    if not promo: return
    owner_username = promo.get("owner_username")
    if not owner_username: return
    users = load_users(); owner_id = None
    for uid, u in users.items():
        if u.get("username") == owner_username: owner_id = int(uid); break
    if not owner_id: owner_id = promo.get("owner_id")
    if not owner_id: return
    percent = get_setting("partner_commission_percent", 20.0)
    amount = round(order_total * (percent / 100), 2)
    if amount <= 0: return
    promo["current_uses"] = promo.get("current_uses", 0) + 1
    promo["total_earned"] = promo.get("total_earned", 0) + amount
    save_promo_codes(promos)
    referrals = load_referrals(); ok = str(owner_id)
    if ok not in referrals: referrals[ok] = {"user_id": owner_id, "referral_code": "", "referrals_list": [], "total_earned": 0.0}
    referrals[ok]["total_earned"] = referrals[ok].get("total_earned", 0) + amount
    save_referrals(referrals)
    try: await bot.send_message(PARTNER_GROUP_ID, f"{pe('money')} <b>ВЫПЛАТА ПАРТНЁРУ</b>\n\n{pe('user')} @{owner_username}\n{pe('money')} {amount:.2f}₴ ({percent}%)\n🆔 {order_key}")
    except: pass
    try: await bot.send_message(owner_id, f"{pe('sparkle')} <b>Вы получили комиссию!</b>\n\n{pe('money')} {amount:.2f}₴\nВсего: {referrals[ok]['total_earned']:.2f}₴")
    except: pass

# ==================== РЕКВИЗИТЫ / РАССЫЛКА ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "💰 Реквизиты")
async def admin_requisites(message: types.Message):
    r = load_requisites()
    text = f"{pe('money')} <b>РЕКВИЗИТЫ:</b>\n\n{pe('card')} Гривны:\n{r.get('uah','—')}\n\n{pe('gift')} Подарок:\n{r.get('gift','—')}"
    await message.answer(text, reply_markup=requisites_edit_keyboard())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("edit_req_"))
async def edit_req(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    m = callback.data.replace("edit_req_", "")
    await state.update_data(edit_req_method=m)
    labels = {"uah": "Гривны", "gift": "Подарок"}
    await callback.message.answer(f"{pe('warn')} Введите новые реквизиты для {labels.get(m, m)}:")
    await state.set_state(AdminStates.waiting_for_requisites_edit)

@dp.message(AdminStates.waiting_for_requisites_edit, F.text)
async def save_req(message: types.Message, state: FSMContext):
    d = await state.get_data()
    r = load_requisites(); r[d["edit_req_method"]] = message.text; save_requisites(r)
    await message.answer(f"{pe('check')} Обновлено!", reply_markup=get_admin_reply_keyboard())
    await state.clear()

@dp.message(F.from_user.id == ADMIN_ID, F.text == "📢 Рассылка")
async def admin_broadcast_start(message: types.Message, state: FSMContext):
    users = load_users()
    if not users: return await message.answer(f"{pe('cross')} Нет пользователей")
    await message.answer(f"{pe('megaphone')} <b>РАССЫЛКА</b>\n\n{pe('user')} Получателей: <b>{len(users)}</b>\n\nОтправьте сообщение. /cancel — отмена.")
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer(f"{pe('cross')} Отменено", reply_markup=get_admin_reply_keyboard()); await state.clear(); return
    users = load_users(); total = len(users); ok = fail = blocked = 0
    st = await message.answer(f"{pe('time')} <b>Рассылка...</b>")
    for i, uid in enumerate(users.keys(), 1):
        try: await bot.copy_message(int(uid), message.chat.id, message.message_id); ok += 1
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ["blocked","kicked","chat not found"]): blocked += 1
            else: fail += 1
        await asyncio.sleep(0.05)
        if i % 20 == 0:
            try: await st.edit_text(f"{pe('time')} {i}/{total} | {pe('check')} {ok} | {pe('cross')} {fail}")
            except: pass
    await st.edit_text(f"{pe('check')} <b>Готово!</b>\n\n{pe('check')} Доставлено: {ok}\n{pe('cross')} Ошибок: {fail}\n🚫 Блок: {blocked}", reply_markup=get_admin_reply_keyboard())
    await state.clear()

@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    if await state.get_state() is None: return
    await state.clear()
    kb = get_admin_reply_keyboard() if message.from_user.id == ADMIN_ID else get_main_reply_keyboard()
    await message.answer(f"{pe('cross')} Отменено", reply_markup=kb)

# ==================== СТАТИСТИКА / ПАНЕЛЬ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📊 Статистика")
async def admin_stats(message: types.Message):
    orders = load_orders(); users = load_users(); sc = {}; rev = 0
    for o in orders.values():
        sc[o["status"]] = sc.get(o["status"], 0) + 1
        if o["status"] == "completed" and not isinstance(o.get("total", 0), str): rev += o["total"]
    text = (f"{pe('chart')} <b>СТАТИСТИКА</b>\n\n"
            f"{pe('user')} Пользователей: {len(users)}\n"
            f"{pe('cart')} Заказов: {len(orders)}\n"
            f"{pe('check')} Выполнено: {sc.get('completed', 0)}\n"
            f"{pe('time')} Ожидают: {sc.get('awaiting_payment', 0)}\n"
            f"{pe('money')} Оборот: {rev}₴\n"
            f"{pe('box')} Склад: {sum(stock_count().values())}")
    await message.answer(text, reply_markup=get_admin_reply_keyboard())

@dp.message(F.from_user.id == ADMIN_ID, F.text == "📈 Панель")
async def admin_panel(message: types.Message): await show_dashboard(message)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_dashboard_refresh")
async def dash_refresh(callback: types.CallbackQuery):
    await callback.answer(); await show_dashboard(callback.message, edit=True)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_orders_dashboard")
async def orders_dash(callback: types.CallbackQuery):
    await callback.answer(); await show_admin_orders_page(callback.message, 0, edit=True)

async def show_dashboard(target, edit=False):
    orders = load_orders(); users = load_users()
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    rt = tr = completed = 0
    for o in orders.values():
        if o["status"] == "completed" and not isinstance(o.get("total", 0), str):
            tr += o["total"]; completed += 1
            if o.get("completed_at"):
                try:
                    if datetime.fromisoformat(o["completed_at"]) >= today: rt += o["total"]
                except: pass
    nt = sum(1 for u in users.values() if u.get("first_seen") and datetime.fromisoformat(u["first_seen"]) >= today)
    v = stock_count("virtual"); p = stock_count("physical")
    text = (f"{pe('chart')} <b>ПАНЕЛЬ</b>\n\n"
            f"{pe('money')} Сегодня: <b>{rt:.2f}₴</b>\n"
            f"{pe('money')} Всего: <b>{tr:.2f}₴</b>\n\n"
            f"{pe('user')} Новых: {nt}\n"
            f"{pe('cart')} Выполнено: {completed}/{len(orders)}\n"
            f"{pe('phone')} Вирт. склад: {sum(v.values())}\n"
            f"{pe('card')} Физ. склад: {sum(p.values())}\n"
            f"{pe('user')} Юзеров: {len(users)}")
    kb = admin_dashboard_keyboard()
    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: await target.answer(text, reply_markup=kb)
    else: await target.answer(text, reply_markup=kb)

# ==================== УРОВНИ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "⭐ Уровни")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_levels_dashboard")
async def admin_levels(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); target = event.message; edit = True
    else: target = event; edit = False
    levels = {
        "Бронза": (pe("medal3"), get_setting("level_bronze_min",0), get_setting("level_bronze_discount",0)),
        "Серебро": (pe("medal2"), get_setting("level_silver_min",500), get_setting("level_silver_discount",3)),
        "Золото": (pe("medal1"), get_setting("level_gold_min",1500), get_setting("level_gold_discount",5)),
        "Платина": (pe("diamond"), get_setting("level_platinum_min",3000), get_setting("level_platinum_discount",7)),
        "VIP": (pe("crown"), get_setting("level_vip_min",5000), get_setting("level_vip_discount",10)),
    }
    text = f"{pe('star')} <b>Уровни</b>\n\n"
    for n, (e,m,d) in levels.items(): text += f"{e} <b>{n}</b> — от {m}₴ (-{d}%)\n"
    kb = admin_levels_keyboard()
    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: await target.answer(text, reply_markup=kb)
    else: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_edit_level_"))
async def edit_level(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    k = callback.data.replace("admin_edit_level_", "")
    await state.update_data(edit_level=k)
    b = InlineKeyboardBuilder()
    ibtn(b, "Порог", callback_data="edit_level_min", icon_key="money")
    ibtn(b, "Скидка", callback_data="edit_level_discount", icon_key="gift")
    ibtn(b, "Назад", callback_data="admin_levels_dashboard", icon_key="back", style="danger")
    b.adjust(1)
    await callback.message.edit_text(f"Уровень {LEVEL_KEYS.get(k,k)}:", reply_markup=b.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "edit_level_min")
async def edit_level_min(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer(); await state.update_data(edit_field="min_spent")
    await callback.message.edit_text("Введите порог:")
    await state.set_state(AdminLevelStates.waiting_for_min_spent)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "edit_level_discount")
async def edit_level_discount(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer(); await state.update_data(edit_field="discount")
    await callback.message.edit_text("Введите скидку %:")
    await state.set_state(AdminLevelStates.waiting_for_discount)

@dp.message(AdminLevelStates.waiting_for_min_spent, F.text)
async def save_lvl_min(message: types.Message, state: FSMContext):
    try: v = float(message.text)
    except: return await message.answer(f"{pe('cross')} Число")
    d = await state.get_data(); k = d.get("edit_level","bronze")
    s = load_settings(); s[f"level_{k}_min"] = v; save_settings(s)
    await message.answer(f"{pe('check')} {v}₴", reply_markup=get_admin_reply_keyboard()); await state.clear()

@dp.message(AdminLevelStates.waiting_for_discount, F.text)
async def save_lvl_disc(message: types.Message, state: FSMContext):
    try:
        v = float(message.text)
        if not (0<=v<=100): raise ValueError
    except: return await message.answer(f"{pe('cross')} 0-100")
    d = await state.get_data(); k = d.get("edit_level","bronze")
    s = load_settings(); s[f"level_{k}_discount"] = v; save_settings(s)
    await message.answer(f"{pe('check')} {v}%", reply_markup=get_admin_reply_keyboard()); await state.clear()

# ==================== АНАЛИТИКА / ИСТОЧНИКИ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📊 Аналитика")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_dashboard")
async def admin_analytics(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); target = event.message; edit = True
    else: target = event; edit = False
    kb = admin_analytics_keyboard()
    if edit:
        try: await target.edit_text(f"{pe('chart')} Аналитика:", reply_markup=kb)
        except: await target.answer(f"{pe('chart')} Аналитика:", reply_markup=kb)
    else: await target.answer(f"{pe('chart')} Аналитика:", reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_by_days")
async def an_days(callback: types.CallbackQuery):
    await callback.answer()
    orders = load_orders(); now = datetime.now(); d = {}
    for i in range(30):
        d[(now - timedelta(days=i)).strftime("%d.%m")] = {"r":0,"n":0}
    for o in orders.values():
        if o["status"] == "completed" and o.get("completed_at"):
            try:
                dt = datetime.fromisoformat(o["completed_at"])
                if (now-dt).days < 30 and not isinstance(o.get("total",0), str):
                    k = dt.strftime("%d.%m")
                    if k in d: d[k]["r"] += o["total"]; d[k]["n"] += 1
            except: pass
    text = f"{pe('chart_up')} <b>По дням</b>\n\n"
    for k in reversed(list(d.keys())):
        if d[k]["r"] > 0: text += f"{pe('calendar')} {k}: {d[k]['r']:.0f}₴ ({d[k]['n']})\n"
    b = InlineKeyboardBuilder(); ibtn(b, "Назад", callback_data="admin_analytics_dashboard", icon_key="back", style="danger")
    await callback.message.edit_text(text, reply_markup=b.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_by_hours")
async def an_hours(callback: types.CallbackQuery):
    await callback.answer()
    orders = load_orders(); h = {i:{"r":0,"n":0} for i in range(24)}
    for o in orders.values():
        if o["status"] == "completed" and o.get("completed_at"):
            try:
                dt = datetime.fromisoformat(o["completed_at"])
                if not isinstance(o.get("total",0), str): h[dt.hour]["r"] += o["total"]; h[dt.hour]["n"] += 1
            except: pass
    text = f"{pe('time')} <b>По часам</b>\n\n"
    for i in range(24):
        if h[i]["n"] > 0: text += f"{pe('time')} {i:02d}:00 — {h[i]['r']:.0f}₴ ({h[i]['n']})\n"
    b = InlineKeyboardBuilder(); ibtn(b, "Назад", callback_data="admin_analytics_dashboard", icon_key="back", style="danger")
    await callback.message.edit_text(text, reply_markup=b.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_by_country")
async def an_country(callback: types.CallbackQuery):
    await callback.answer()
    orders = load_orders(); s = {}
    for o in orders.values():
        if o["status"] == "completed":
            c = o.get("country_code","??"); s.setdefault(c, {"r":0,"n":0})
            if not isinstance(o.get("total",0), str): s[c]["r"] += o["total"]
            s[c]["n"] += 1
    text = f"{pe('globe')} <b>По странам</b>\n\n"
    for c, x in sorted(s.items(), key=lambda y: -y[1]["r"]): text += f"{pe('globe')} {c.upper()}: {x['r']:.0f}₴ ({x['n']})\n"
    b = InlineKeyboardBuilder(); ibtn(b, "Назад", callback_data="admin_analytics_dashboard", icon_key="back", style="danger")
    await callback.message.edit_text(text, reply_markup=b.as_markup())

@dp.message(F.from_user.id == ADMIN_ID, F.text == "🔗 Источники")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_traffic_dashboard")
async def admin_traffic(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); target = event.message; edit = True
    else: target = event; edit = False
    s = load_traffic_sources(); text = f"{pe('link')} <b>Источники</b>\n\n"
    if not s: text += "<i>Нет данных</i>"
    else:
        for n, x in sorted(s.items(), key=lambda y: -y[1].get("total_revenue",0)): text += f"{pe('pin')} {n}: {x.get('total_revenue',0):.0f}₴\n"
    b = InlineKeyboardBuilder(); ibtn(b, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    if edit:
        try: await target.edit_text(text, reply_markup=b.as_markup())
        except: await target.answer(text, reply_markup=b.as_markup())
    else: await target.answer(text, reply_markup=b.as_markup())

# ==================== РЕФЕРАЛЫ / ПОЛЬЗОВАТЕЛИ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "👥 Рефералы")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_referrals_dashboard")
async def admin_refs(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); target = event.message; edit = True
    else: target = event; edit = False
    r = load_referrals(); b = get_setting("referral_bonus_percent", 5.0)
    tot = sum(len(x.get("referrals_list", [])) for x in r.values())
    earned = sum(x.get("total_earned", 0) for x in r.values())
    text = f"{pe('gift')} <b>Рефералы</b>\n\n{pe('money')} Бонус: {b}%\n{pe('user')} Всего: {tot}\n{pe('money')} {earned:.0f}₴"
    kb = admin_referrals_settings_keyboard()
    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: await target.answer(text, reply_markup=kb)
    else: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_edit_referral_bonus")
async def edit_ref_bonus(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("Введите новый бонус %:")
    await state.set_state(AdminReferralSettingsStates.waiting_for_bonus_percent)

@dp.message(AdminReferralSettingsStates.waiting_for_bonus_percent, F.text)
async def save_ref_bonus(message: types.Message, state: FSMContext):
    try:
        v = float(message.text)
        if not (0<=v<=100): raise ValueError
    except: return await message.answer(f"{pe('cross')} 0-100")
    s = load_settings(); s["referral_bonus_percent"] = v; save_settings(s)
    await message.answer(f"{pe('check')} {v}%", reply_markup=get_admin_reply_keyboard()); await state.clear()

@dp.message(F.from_user.id == ADMIN_ID, F.text == "👤 Пользователи")
async def admin_users(message: types.Message):
    u = load_users()
    if not u: return await message.answer(f"{pe('cart')} Нет", reply_markup=get_admin_reply_keyboard())
    text = f"{pe('user')} ВСЕГО: {len(u)}\n\n"
    for uid, x in sorted(u.items(), key=lambda y: y[1].get("first_seen",""), reverse=True)[:10]:
        text += f"{pe('user')} {x.get('full_name','—')} (@{x.get('username','—')})\nID: {uid}\n"
    if len(u) > 10: text += f"...и ещё {len(u)-10}"
    await message.answer(text, reply_markup=get_admin_reply_keyboard())

@dp.message(F.from_user.id == ADMIN_ID, F.text == "🏠 Главное меню")
async def admin_main(message: types.Message): await message.answer("🏠", reply_markup=get_admin_reply_keyboard())

# ==================== БЭКАПЫ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "💾 Бэкапы")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_backups")
async def admin_backups(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); target = event.message; edit = True
    else: target = event; edit = False
    text = f"{pe('save')} <b>БЭКАПЫ</b>\n\nRailway стирает файлы при перезапуске.\n\nСкачайте бэкапы и вставьте в Variables."
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Скачать все бэкапы", callback_data="admin_download_backups", icon_key="save")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="back", style="danger")
    kb.adjust(1)
    if edit:
        try: await target.edit_text(text, reply_markup=kb.as_markup())
        except: await target.answer(text, reply_markup=kb.as_markup())
    else: await target.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_download_backups")
async def download_backups(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(f"{pe('time')} Собираю...")
    data = {}
    for n in BACKUP_FILES:
        p = f"{n}.json"
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f: data[n] = json.load(f)
    b64 = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()
    with open("backup_all.b64","w") as f: f.write(b64)
    await callback.message.answer_document(FSInputFile("backup_all.b64"), caption=f"{pe('save')} BACKUP_ALL_B64")

# ==================== ПРОМОКОДЫ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "🎟 Промокоды")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_promo_dashboard")
async def admin_promo(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); target = event.message; edit = True
    else: target = event; edit = False
    text = f"{pe('ticket')} <b>ПРОМОКОДЫ</b>"
    kb = admin_promo_codes_keyboard()
    if edit:
        try: await target.edit_text(text, reply_markup=kb)
        except: await target.answer(text, reply_markup=kb)
    else: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_create_promo_code")
async def create_promo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(f"{pe('ticket')} Введите код промокода:")
    await state.set_state(AdminPromoStates.waiting_for_promo_code)

@dp.message(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_promo_code, F.text)
async def promo_code_input(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    if code in load_promo_codes(): return await message.answer(f"{pe('cross')} Уже есть")
    await state.update_data(promo_code=code)
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Процент", callback_data="promo_type_percent", style="primary")
    ibtn(kb, "Фикс", callback_data="promo_type_fixed", icon_key="money", style="primary")
    kb.adjust(2)
    await message.answer(f"Код: <code>{code}</code>\nТип:", reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_discount_type)

@dp.callback_query(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_discount_type, F.data.startswith("promo_type_"))
async def promo_type(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    t = "percent" if callback.data == "promo_type_percent" else "fixed"
    await state.update_data(discount_type=t)
    label = "процент" if t == "percent" else "сумму ₴"
    await callback.message.edit_text(f"Введите {label}:")
    await state.set_state(AdminPromoStates.waiting_for_discount_value)

@dp.message(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_discount_value, F.text)
async def promo_value(message: types.Message, state: FSMContext):
    try:
        v = float(message.text)
        if v <= 0: raise ValueError
    except: return await message.answer(f"{pe('cross')} Число > 0")
    await state.update_data(discount_value=v)
    kb = InlineKeyboardBuilder()
    ibtn(kb, "∞", callback_data="promo_unlimited")
    for n in [1,10,50,100,500]: kb.button(text=f"{n}", callback_data=f"promo_max_{n}")
    kb.adjust(1)
    await message.answer("Макс. использований:", reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_max_uses)

@dp.callback_query(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_max_uses, F.data.startswith("promo_"))
async def promo_max(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    mu = None if callback.data == "promo_unlimited" else int(callback.data.split("_")[-1])
    await state.update_data(max_uses=mu)
    kb = InlineKeyboardBuilder()
    for d in [1,7,30,90]: ibtn(kb, f"{d} дней", callback_data=f"promo_expire_{d}", icon_key="calendar")
    ibtn(kb, "∞", callback_data="promo_expire_0", icon_key="check")
    kb.adjust(2)
    await callback.message.edit_text("Срок:", reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_expires_date)

@dp.callback_query(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_expires_date, F.data.startswith("promo_expire_"))
async def promo_exp(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    d = int(callback.data.split("_")[-1])
    exp = (datetime.now() + timedelta(days=d)).isoformat() if d > 0 else None
    await state.update_data(expires_at=exp)
    await callback.message.edit_text(f"{pe('user')} Username владельца (без @):")
    await state.set_state(AdminPromoStates.waiting_for_owner_username)

@dp.message(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_owner_username, F.text)
async def promo_owner(message: types.Message, state: FSMContext):
    user = message.text.strip().lstrip("@")
    data = await state.get_data()
    p = load_promo_codes()
    p[data["promo_code"]] = {
        "code": data["promo_code"], "discount_type": data["discount_type"],
        "discount_value": data["discount_value"], "max_uses": data["max_uses"],
        "current_uses": 0, "expires_at": data.get("expires_at"), "is_active": True,
        "created_at": datetime.now().isoformat(), "owner_username": user, "total_earned": 0.0,
    }
    save_promo_codes(p)
    desc = f"{data['discount_value']}%" if data["discount_type"] == "percent" else f"{data['discount_value']}₴"
    await message.answer(f"{pe('check')} <b>Создан!</b>\n\n{pe('ticket')} <code>{data['promo_code']}</code>\n{pe('money')} {desc}\n{pe('user')} @{user}", reply_markup=admin_promo_codes_keyboard())
    await state.clear()

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_promo_code_detail_"))
async def promo_detail(callback: types.CallbackQuery):
    await callback.answer()
    code = callback.data.replace("admin_promo_code_detail_", "")
    p = load_promo_codes().get(code)
    if not p: return await callback.answer(f"{pe('cross')} Не найден", show_alert=True)
    status = pe("check") if p.get("is_active", True) else pe("cross")
    desc = f"{p['discount_value']}%" if p["discount_type"] == "percent" else f"{p['discount_value']}₴"
    text = (f"{pe('ticket')} <b>{code}</b>\n\n"
            f"{pe('money')} {desc}\n"
            f"{pe('user')} @{p.get('owner_username','—')}\n"
            f"{pe('pin')} {status}\n"
            f"{pe('chart')} {p.get('current_uses',0)}/{p.get('max_uses') or '∞'}\n"
            f"{pe('money')} {p.get('total_earned',0):.0f}₴")
    kb = InlineKeyboardBuilder()
    if p.get("is_active", True):
        ibtn(kb, "Выключить", callback_data=f"admin_deactivate_promo_{code}", icon_key="cross", style="danger")
    else:
        ibtn(kb, "Включить", callback_data=f"admin_activate_promo_{code}", icon_key="check", style="success")
    ibtn(kb, "Удалить", callback_data=f"admin_delete_promo_{code}", icon_key="trash", style="danger")
    ibtn(kb, "Назад", callback_data="admin_promo_dashboard", icon_key="back", style="danger")
    kb.adjust(1)
    try: await callback.message.edit_text(text, reply_markup=kb.as_markup())
    except: await callback.message.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_deactivate_promo_"))
async def deact(callback: types.CallbackQuery):
    await callback.answer()
    code = callback.data.replace("admin_deactivate_promo_", "")
    p = load_promo_codes()
    if code in p: p[code]["is_active"] = False; save_promo_codes(p)
    await callback.answer(f"{pe('check')} Выключен", show_alert=True); await admin_promo(callback)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_activate_promo_"))
async def act(callback: types.CallbackQuery):
    await callback.answer()
    code = callback.data.replace("admin_activate_promo_", "")
    p = load_promo_codes()
    if code in p: p[code]["is_active"] = True; save_promo_codes(p)
    await callback.answer(f"{pe('check')} Включен", show_alert=True); await admin_promo(callback)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_delete_promo_"))
async def delp(callback: types.CallbackQuery):
    await callback.answer()
    code = callback.data.replace("admin_delete_promo_", "")
    p = load_promo_codes()
    if code in p: del p[code]; save_promo_codes(p)
    await callback.answer(f"{pe('trash')} Удалён", show_alert=True); await admin_promo(callback)

# ==================== ОТЗЫВЫ ====================
@dp.message(F.from_user.id != ADMIN_ID, F.text == "💬 Отзывы")
@dp.callback_query(F.data == "menu_reviews")
async def open_reviews(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); target = event.message
    else: target = event
    try: await target.edit_text(f"{pe('chat')} Отзывы:", reply_markup=reviews_keyboard())
    except: await target.answer(f"{pe('chat')} Отзывы:", reply_markup=reviews_keyboard())

@dp.callback_query(F.data.startswith("leave_review_"))
async def start_review(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    oid = callback.data.replace("leave_review_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await callback.message.answer(f"{pe('star')} Оцените:", reply_markup=stars_keyboard())
        await state.update_data(review_order_id=None)
    else:
        await state.update_data(review_order_id=rk)
        await callback.message.edit_text(f"{pe('star')} Оцените {orders[rk].get('short_id', rk)}:", reply_markup=stars_keyboard())
    await state.set_state(ReviewStates.waiting_for_stars)

@dp.callback_query(ReviewStates.waiting_for_stars, F.data.startswith("stars_"))
async def process_stars(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    r = int(callback.data.split("_")[1])
    await state.update_data(stars=r)
    await callback.message.edit_text(f"{'⭐' * r}\nФото или пропустить:", reply_markup=review_photo_skip_keyboard())
    await state.set_state(ReviewStates.waiting_for_photo_or_skip)

@dp.callback_query(ReviewStates.waiting_for_photo_or_skip, F.data == "skip_photo")
async def skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer(); await state.update_data(photo=None)
    await callback.message.edit_text(f"{pe('chat')} Текст отзыва:")
    await state.set_state(ReviewStates.waiting_for_text)

@dp.message(ReviewStates.waiting_for_photo_or_skip, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer(f"{pe('chat')} Текст отзыва:")
    await state.set_state(ReviewStates.waiting_for_text)

@dp.message(ReviewStates.waiting_for_text, F.text)
async def process_review(message: types.Message, state: FSMContext):
    d = await state.get_data()
    rid = f"rev_{message.from_user.id}_{int(datetime.now().timestamp())}"
    reviews = load_reviews()
    reviews[rid] = {
        "review_id": rid, "user_id": message.from_user.id,
        "username": message.from_user.username, "full_name": message.from_user.full_name,
        "stars": d.get("stars", 5), "text": message.text, "photo": d.get("photo"),
        "order_id": d.get("review_order_id"), "status": "pending", "created_at": datetime.now().isoformat(),
    }
    save_reviews(reviews)
    oid = d.get("review_order_id")
    if oid:
        orders = load_orders(); rk = find_order_key(orders, oid)
        if rk: orders[rk]["reviewed"] = True; save_orders(orders)
    cap = f"{pe('star')} НОВЫЙ ОТЗЫВ\nОт: {message.from_user.full_name}\n@{message.from_user.username}\n{'⭐'*d.get('stars',5)}\n{message.text}"
    try:
        if d.get("photo"): await bot.send_photo(ADMIN_ID, d["photo"], caption=cap, reply_markup=moderation_keyboard(rid))
        else: await bot.send_message(ADMIN_ID, cap, reply_markup=moderation_keyboard(rid))
        await message.answer(f"{pe('heart')} Спасибо!", reply_markup=get_main_reply_keyboard())
    except Exception as e: logger.error(f"Review: {e}")
    await state.clear()

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("approve_"))
async def approve_review(callback: types.CallbackQuery):
    await callback.answer()
    rid = callback.data.replace("approve_", "")
    r = load_reviews().get(rid)
    if not r: return
    text = f"{pe('star')} ОТЗЫВ\n@{r.get('username','—')}\n{'⭐'*r['stars']}\n{r['text']}\n\n@MaskYoY"
    try:
        if r.get("photo"): await bot.send_photo(CHANNEL_ID, r["photo"], caption=text)
        else: await bot.send_message(CHANNEL_ID, text)
        await bot.send_message(r["user_id"], f"{pe('sparkle')} Отзыв опубликован!")
        rr = load_reviews(); rr[rid]["status"] = "approved"; save_reviews(rr)
    except Exception as e: logger.error(f"Approve: {e}")

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("reject_"))
async def reject_review(callback: types.CallbackQuery):
    await callback.answer()
    rid = callback.data.replace("reject_", "")
    rr = load_reviews(); r = rr.get(rid)
    if r:
        r["status"] = "rejected"; save_reviews(rr)
        try: await bot.send_message(r["user_id"], f"{pe('cross')} Отзыв отклонён.")
        except: pass

# ==================== МОИ ЗАКАЗЫ / АККАУНТЫ ====================
@dp.message(F.from_user.id != ADMIN_ID, F.text == "📋 Мои заказы")
@dp.callback_query(F.data == "my_orders")
async def my_orders(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); uid = event.from_user.id; target = event.message
    else: uid = event.from_user.id; target = event
    orders = load_orders()
    mine = {k:v for k,v in orders.items() if v["user_id"] == uid}
    if not mine:
        text = f"{pe('cart')} У вас пока нет заказов"; kb = main_menu_keyboard()
    else:
        text = f"{pe('cart')} <b>ВАШИ ЗАКАЗЫ ({len(mine)})</b>\n\n"
        b = InlineKeyboardBuilder()
        for oid, o in sorted(mine.items(), reverse=True):
            e, _ = STATUS_CONFIG.get(o["status"], (pe("warn"), ""))
            s = method_symbol(o.get("payment_method","uah"))
            short = o.get("short_id", oid[:8])
            tot = o["total"] if isinstance(o["total"], str) else f"{o['total']}{s}"
            text += f"{e} {short} | {o['product']} | {tot}\n"
            ibtn(b, f"{short}", callback_data=f"order_detail_{oid}", icon_key="cart")
        ibtn(b, "Меню", callback_data="main_menu", icon_key="back", style="danger")
        b.adjust(1); kb = b.as_markup()
    try: await target.edit_text(text, reply_markup=kb)
    except: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("order_detail_"))
async def order_detail(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("order_detail_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk: return await callback.answer(f"{pe('cross')} Не найден", show_alert=True)
    o = orders[rk]
    e, st = STATUS_CONFIG.get(o["status"], (pe("warn"), ""))
    s = method_symbol(o.get("payment_method","uah"))
    short = o.get("short_id", rk[:8])
    tot = o["total"] if isinstance(o["total"], str) else f"{o['total']}{s}"
    text = (f"{pe('cart')} <b>ЗАКАЗ {short}</b>\n\n"
            f"Товар: {o['product']}\n"
            f"Оплата: {method_label(o['payment_method'])}\n"
            f"Сумма: {tot}\n"
            f"Статус: {e} {st}\n")
    if o.get("phone"): text += f"{pe('phone')} {o['phone']}\n"
    if o["status"] == "completed": kb = user_order_actions_keyboard(rk)
    elif o["status"] == "awaiting_payment": kb = awaiting_payment_keyboard(rk)
    else:
        b = InlineKeyboardBuilder()
        ibtn(b, "Мои заказы", callback_data="my_orders", icon_key="cart")
        ibtn(b, "Меню", callback_data="main_menu", icon_key="back", style="danger")
        b.adjust(1); kb = b.as_markup()
    try: await callback.message.edit_text(text, reply_markup=kb)
    except: await callback.message.answer(text, reply_markup=kb)

@dp.message(F.from_user.id != ADMIN_ID, F.text == "📦 Мои аккаунты")
@dp.callback_query(F.data == "my_accounts")
async def my_accounts(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); uid = event.from_user.id; target = event.message
    else: uid = event.from_user.id; target = event
    accounts = get_user_accounts(uid)
    if not accounts:
        text = f"{pe('box')} У вас пока нет аккаунтов"; kb = main_menu_keyboard()
    else:
        text = f"{pe('box')} <b>ВАШИ АККАУНТЫ ({len(accounts)})</b>\n\n"
        b = InlineKeyboardBuilder()
        for acc in accounts:
            text += f"{pe('globe')} {acc['country'].upper()} | {pe('phone')} {acc['phone']}\n"
            ibtn(b, f"Код для {acc['phone']}", callback_data=f"request_code_for_{acc['country']}_{acc['session_name']}", icon_key="key")
        ibtn(b, "Меню", callback_data="main_menu", icon_key="back", style="danger")
        b.adjust(1); kb = b.as_markup()
    try: await target.edit_text(text, reply_markup=kb)
    except: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("request_code_for_"))
async def req_code_for(callback: types.CallbackQuery):
    await callback.answer()
    data = callback.data.replace("request_code_for_", "")
    if "_" not in data: return
    c, n = data.split("_", 1)
    meta = load_meta(c, n); phone = meta.get("phone") if meta else "—"
    order_key = None
    for k, o in load_orders().items():
        if o.get("session_name") == n and o.get("country_code") == c: order_key = k; break
    await callback.message.answer(
        f"{pe('key')} <b>Готово!</b>\n\n"
        f"{pe('phone')} Номер: <code>{phone}</code>\n"
        f"{pe('time')} Как только Telegram пришлёт код — перешлю сюда.",
        reply_markup=user_order_actions_keyboard(order_key) if order_key else None)
    asyncio.create_task(start_code_watcher(c, n, callback.from_user.id, order_key))

@dp.callback_query(F.data.startswith("request_code_"))
async def req_code(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("request_code_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk: return
    o = orders[rk]
    c, n, phone = o["country_code"], o["session_name"], o["phone"]
    sess = watcher_path(c, n)
    if not os.path.exists(sess): sess = session_path(c, n)
    if not os.path.exists(sess): return await callback.message.answer(f"{pe('cross')} Файл не найден. @MaskYoY")
    await callback.message.answer(
        f"{pe('key')} <b>Готово!</b>\n\n"
        f"{pe('phone')} <code>{phone}</code>\n"
        f"{pe('time')} Код придёт сюда автоматически.")
    asyncio.create_task(start_code_watcher(c, n, callback.from_user.id, rk))

@dp.callback_query(F.data.startswith("user_replace_"))
async def user_replace(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("user_replace_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if rk: await bot.send_message(ADMIN_ID, f"{pe('refresh')} Замена: {orders[rk].get('short_id', rk)} @{callback.from_user.username}")
    await callback.message.answer(f"{pe('refresh')} Запрос отправлен. @MaskYoY")

@dp.callback_query(F.data.startswith("user_refund_"))
async def user_refund(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("user_refund_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if rk: await bot.send_message(ADMIN_ID, f"{pe('money')} Возврат: {orders[rk].get('short_id', rk)} @{callback.from_user.username}")
    await callback.message.answer(f"{pe('money')} Запрос отправлен. @MaskYoY")

# ==================== ПРОФИЛЬ / РЕФЕРАЛЫ / ПРОМО / FAQ / КАНАЛ ====================
@dp.message(F.from_user.id != ADMIN_ID, F.text == "👤 Профиль")
async def profile_kb(message: types.Message): await show_profile(message)

@dp.callback_query(F.data == "profile_menu")
async def profile_cb(callback: types.CallbackQuery):
    await callback.answer(); await show_profile(callback.message, callback.from_user)

async def show_profile(target, uo=None):
    if uo is None: uo = target.from_user
    uid = uo.id; lvl = get_user_level(uid)
    orders = load_orders()
    comp = [o for o in orders.values() if o["user_id"] == uid and o["status"] == "completed"]
    spent = sum(o.get("total",0) for o in comp if not isinstance(o.get("total",0), str))
    r = load_referrals().get(str(uid), {})
    text = (f"{pe('user')} <b>Профиль</b>\n\n"
            f"🆔 <code>{uid}</code>\n"
            f"{pe('user')} {uo.full_name}\n"
            f"{pe('star')} {lvl['emoji']} {lvl['name']} (-{lvl['discount']}%)\n\n"
            f"{pe('money')} Потрачено: {spent:.2f} ₴\n"
            f"{pe('cart')} Покупок: {len(comp)}\n"
            f"{pe('gift')} Рефералов: {len(r.get('referrals_list',[]))}\n"
            f"{pe('money')} Бонусы: {r.get('total_earned',0):.2f} ₴")
    try: await target.edit_text(text, reply_markup=profile_keyboard())
    except: await target.answer(text, reply_markup=profile_keyboard())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "👥 Рефералы")
@dp.callback_query(F.data == "referral_menu")
async def ref_menu(event):
    if isinstance(event, types.CallbackQuery): await event.answer(); uid = event.from_user.id; target = event.message
    else: uid = event.from_user.id; target = event
    r = load_referrals().get(str(uid), {})
    if not r.get("referral_code"):
        r["referral_code"] = hashlib.md5(f"{uid}_ref_salt".encode()).hexdigest()[:8].upper()
    r.setdefault("referrals_list", []); r.setdefault("total_earned", 0)
    rr = load_referrals(); rr[str(uid)] = r; save_referrals(rr)
    bot_info = await bot.get_me()
    link = f"https://t.me/{bot_info.username}?start=ref_{r['referral_code']}"
    bonus = get_setting("referral_bonus_percent", 5.0)
    text = (f"{pe('gift')} <b>Рефералы</b>\n\n"
            f"{pe('money')} Бонус: {bonus}%\n"
            f"{pe('user')} Приглашено: {len(r['referrals_list'])}\n"
            f"{pe('money')} Заработано: {r['total_earned']:.2f} ₴\n\n"
            f"{pe('link')} <code>{link}</code>")
    kb = referral_menu_keyboard()
    try: await target.edit_text(text, reply_markup=kb)
    except: await target.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "referral_stats")
async def ref_stats(callback: types.CallbackQuery):
    await callback.answer()
    r = load_referrals().get(str(callback.from_user.id), {})
    lst = r.get("referrals_list", [])
    text = f"{pe('chart')} <b>Детали</b>\n\n"
    if not lst: text += "<i>Нет рефералов</i>"
    else:
        for x in lst[-10:]:
            st = pe("check") if x.get("first_purchase_done") else pe("time")
            text += f"{st} @{x.get('username','—')}\n"
    b = InlineKeyboardBuilder(); ibtn(b, "Назад", callback_data="referral_menu", icon_key="back", style="danger")
    await callback.message.edit_text(text, reply_markup=b.as_markup())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "🎟 Промокод")
@dp.callback_query(F.data == "promo_menu")
async def promo_menu_ev(event, state: FSMContext = None):
    if isinstance(event, types.CallbackQuery): await event.answer(); target = event.message
    else: target = event
    b = InlineKeyboardBuilder()
    ibtn(b, "Назад", callback_data="main_menu", icon_key="back", style="danger")
    try: await target.edit_text(f"{pe('ticket')} <b>Введите промокод</b>", reply_markup=b.as_markup())
    except: await target.answer(f"{pe('ticket')} <b>Введите промокод</b>", reply_markup=b.as_markup())
    if state: await state.set_state(PromoStates.waiting_for_promo_code)

@dp.message(PromoStates.waiting_for_promo_code, F.text)
async def check_promo(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID: return
    if message.text.startswith("/"): await state.clear(); return
    code = message.text.strip().upper()
    p = load_promo_codes().get(code)
    if not p: await message.answer(f"{pe('cross')} Не найден"); await state.clear(); return
    if not p.get("is_active", True) or (p.get("max_uses") and p.get("current_uses", 0) >= p["max_uses"]):
        await message.answer(f"{pe('cross')} Неактивен"); await state.clear(); return
    if p.get("expires_at") and datetime.now() > datetime.fromisoformat(p["expires_at"]):
        await message.answer(f"{pe('cross')} Просрочен"); await state.clear(); return
    await message.answer(f"{pe('check')} Промокод <code>{code}</code> принят!", reply_markup=main_menu_keyboard())
    await state.clear()

@dp.message(F.from_user.id != ADMIN_ID, F.text == "❓ FAQ")
async def faq(message: types.Message): await message.answer(FAQ_TEXT, reply_markup=get_main_reply_keyboard())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "📢 Канал")
async def channel(message: types.Message):
    b = InlineKeyboardBuilder()
    ibtn(b, "Перейти", url="http://t.me/owerpass_store", icon_key="megaphone", style="primary")
    await message.answer(f"{pe('megaphone')} Наш канал:", reply_markup=b.as_markup())

# ==================== ГЛАВНОЕ МЕНЮ / ПОДДЕРЖКА / ЧАТ ====================
@dp.callback_query(F.data == "main_menu")
async def go_main(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer(); await state.clear()
    try: await callback.message.edit_text(f"{pe('sparkle')} <b>Меню</b>", reply_markup=main_menu_keyboard())
    except: await callback.message.answer(f"{pe('sparkle')} <b>Меню</b>", reply_markup=main_menu_keyboard())

@dp.callback_query(F.data.startswith("support_"))
async def start_support(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    oid = callback.data.replace("support_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if rk: oid = rk
    await state.update_data(support_order_id=oid)
    await state.set_state(SupportStates.chatting)
    close_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Закрыть чат")]], resize_keyboard=True)
    await callback.message.answer(f"{pe('warn')} Напишите сообщение продавцу.", reply_markup=close_kb)

@dp.message(SupportStates.chatting, F.text == "❌ Закрыть чат")
async def close_support(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(f"{pe('cross')} Закрыто", reply_markup=get_main_reply_keyboard())

@dp.message(SupportStates.chatting)
async def relay_user(message: types.Message, state: FSMContext):
    d = await state.get_data(); oid = d.get("support_order_id", "—")
    orders = load_orders(); rk = find_order_key(orders, oid)
    short = orders[rk].get("short_id", oid) if rk else oid
    await bot.send_message(ADMIN_ID, f"{pe('warn')} @{message.from_user.username} | {short}")
    fwd = await bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
    rel = load_relay(); rel[str(fwd.message_id)] = message.from_user.id; save_relay(rel)
    await message.answer(f"{pe('check')} Отправлено")

@dp.message(F.from_user.id == ADMIN_ID, F.reply_to_message)
async def relay_admin(message: types.Message):
    rel = load_relay(); uid = rel.get(str(message.reply_to_message.message_id))
    if not uid: return
    try:
        await bot.copy_message(uid, message.chat.id, message.message_id)
        await message.answer(f"{pe('check')} Доставлено")
    except Exception as e: await message.answer(f"{pe('cross')} {e}")

# ==================== ОШИБКИ / ЗАПУСК ====================
@dp.errors()
async def on_err(event): logger.error(f"Err: {event.exception}"); return True

async def main():
    print("="*50); print("OverPass Store Bot v7 (split stock + stars shop)"); print("="*50)
    restore_from_env()
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(1)
    if os.path.exists(ACCOUNTS_DIR):
        for c in os.listdir(ACCOUNTS_DIR):
            cd = country_dir(c)
            if not os.path.isdir(cd): continue
            for f in os.listdir(cd):
                if f.endswith(".json"):
                    meta = load_meta(c, f.replace(".json",""))
                    if meta and meta.get("sold_to"):
                        ok = None
                        for k, o in load_orders().items():
                            if o.get("session_name") == meta["session_name"] and o.get("country_code") == c: ok = k; break
                        asyncio.create_task(start_code_watcher(c, meta["session_name"], meta["sold_to"], ok))
    print("Бот запущен!")
    try: await dp.start_polling(bot, drop_pending_updates=True)
    except Exception as e: print(f"Ошибка: {e}")
    finally: await bot.session.close()

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Остановлен")
    except Exception as e: print(f"Ошибка: {e}"); sys.exit(1)
