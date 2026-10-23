import asyncio
import logging
import json
import os
import sys
import hashlib
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ==================== КОНФИГ ====================
BOT_TOKEN = "8975688414:AAGUC6Ag9ADN_p7Tb0R9a8xsLEnsFHFkWZM"
ADMIN_ID = 8543473783
CHANNEL_ID = "-1004311525622"
STORE_CHANNEL_ID = "-1004292126045"

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ==================== ПРЕМИУМ ЭМОДЗИ ====================
# key -> (emoji_id, fallback)
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
}

def pe(key: str) -> str:
    """HTML-тег для ТЕКСТА сообщений (с фолбэком)."""
    eid, sym = EMOJI.get(key, (None, ""))
    return f"<tg-emoji emoji-id='{eid}'>{sym}</tg-emoji>" if eid else sym

def eid(key: str):
    """ID для icon_custom_emoji_id в inline-кнопках."""
    return EMOJI.get(key, (None, ""))[0]

def btn_icon(kb_builder, icon_key: str):
    """Прокидываем последнюю добавленную кнопку с иконкой.
    Используем как: ibtn(kb, "Текст", data, icon_key='star', style='primary')"""
    pass

def ibtn(builder, text, callback_data=None, url=None, icon_key=None, style=None):
    """Универсальный билдер inline-кнопки с icon_custom_emoji_id."""
    kw = {"text": text}
    if callback_data is not None: kw["callback_data"] = callback_data
    if url is not None: kw["url"] = url
    if style: kw["style"] = style
    if icon_key and eid(icon_key):
        try:
            kw["icon_custom_emoji_id"] = eid(icon_key)
        except Exception:
            pass
    try:
        builder.add(InlineKeyboardButton(**kw))
    except TypeError:
        # если aiogram не поддерживает icon_custom_emoji_id — откатываемся
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
PROMOTIONS_FILE = "promotions.json"
BROADCASTS_FILE = "broadcasts.json"
TRAFFIC_SOURCES_FILE = "traffic_sources.json"
SETTINGS_FILE = "settings.json"
ORDER_COUNTER_FILE = "order_counter.json"
CHAT_HISTORY_FILE = "chat_history.json"
PROMO_EARNINGS_FILE = "promo_earnings.json"

def load_json(p):
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(p, d):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

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
def load_promotions(): return load_json(PROMOTIONS_FILE)
def save_promotions(x): save_json(PROMOTIONS_FILE, x)
def load_broadcasts(): return load_json(BROADCASTS_FILE)
def save_broadcasts(x): save_json(BROADCASTS_FILE, x)
def load_traffic_sources(): return load_json(TRAFFIC_SOURCES_FILE)
def save_traffic_sources(x): save_json(TRAFFIC_SOURCES_FILE, x)
def load_settings(): return load_json(SETTINGS_FILE)
def save_settings(x): save_json(SETTINGS_FILE, x)
def load_order_counter(): return load_json(ORDER_COUNTER_FILE)
def save_order_counter(x): save_json(ORDER_COUNTER_FILE, x)
def load_chat_history(): return load_json(CHAT_HISTORY_FILE)
def save_chat_history(x): save_json(CHAT_HISTORY_FILE, x)
def load_promo_earnings(): return load_json(PROMO_EARNINGS_FILE)
def save_promo_earnings(x): save_json(PROMO_EARNINGS_FILE, x)

# ==================== НАСТРОЙКИ ====================
DEFAULT_SETTINGS = {
    "referral_bonus_percent": 5.0,
    "promo_owner_commission_percent": 20.0,
    "level_bronze_min": 0,    "level_bronze_discount": 0,
    "level_silver_min": 500,  "level_silver_discount": 3,
    "level_gold_min": 1500,   "level_gold_discount": 5,
    "level_platinum_min": 3000, "level_platinum_discount": 7,
    "level_vip_min": 5000,    "level_vip_discount": 10,
}
if not os.path.exists(SETTINGS_FILE):
    save_settings(DEFAULT_SETTINGS)

def get_setting(k, d=None):
    return load_settings().get(k, DEFAULT_SETTINGS.get(k, d))

LEVEL_KEYS = {"bronze": "Бронза", "silver": "Серебро", "gold": "Золото",
              "platinum": "Платина", "vip": "VIP"}

# ==================== ПОЛЬЗОВАТЕЛИ ====================
async def add_user(user_id, username=None, full_name=None, ref_code=None):
    users = load_users(); referrals = load_referrals()
    key = str(user_id); is_new = key not in users
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
            src = load_traffic_sources()
            src.setdefault(ref_code, {
                "total_visits": 0, "total_registrations": 0,
                "total_purchases": 0, "total_revenue": 0.0,
                "created_at": datetime.now().isoformat(),
            })
            src[ref_code]["total_visits"] += 1
            src[ref_code]["total_registrations"] += 1
            save_traffic_sources(src)
    own_code = users[key].get("referral_code") or \
               hashlib.md5(f"{user_id}_ref_salt".encode()).hexdigest()[:8].upper()
    users[key]["referral_code"] = own_code
    users[key]["last_active"] = datetime.now().isoformat()
    if username: users[key]["username"] = username
    if full_name: users[key]["full_name"] = full_name
    referrals.setdefault(key, {"user_id": user_id, "referral_code": own_code,
                               "referrals_list": [], "total_earned": 0.0})
    referrals[key].setdefault("referral_code", own_code)
    referrals[key].setdefault("referrals_list", [])
    referrals[key].setdefault("total_earned", 0.0)
    save_users(users); save_referrals(referrals)
    return is_new

DEFAULT_REQUISITES = {
    "uah": f"{pe('money')} <b>Карта Моно:</b> <code>4874 0700 2513 7454</code>",
    "stars": f"{pe('star')} <b>Отправьте звёзды в ЛС:</b> @MaskYoY",
    "nft": "🖼 <b>NFT оплата в ЛС:</b> @MaskYoY",
}
if not os.path.exists(REQUISITES_FILE):
    save_requisites(DEFAULT_REQUISITES)

def get_requisites(m):
    return load_requisites().get(m, DEFAULT_REQUISITES.get(m, "Уточните у продавца"))

# ==================== КАТАЛОГ ====================
CATEGORIES = {
    "regular": {
        "name": f"{pe('cart')} Обычные номера",
        "products": {
            "🇲🇲 Мьянма (+95)":       {"uah": 30,  "stars": 40,  "nft": False},
            "🇺🇸 США (+1)":           {"uah": 45,  "stars": 65,  "nft": False},
            "🇨🇴 Колумбия (+57)":     {"uah": 45,  "stars": 65,  "nft": False},
            "🇧🇩 Бангладеш (+880)":   {"uah": 45,  "stars": 65,  "nft": False},
            "🇫🇷 Франция (+33)":      {"uah": 75,  "stars": 100, "nft": False},
            "🇧🇷 Бразилия (+55)":     {"uah": 75,  "stars": 100, "nft": False},
            "🇺🇿 Узбекистан (+998)":  {"uah": 75,  "stars": 100, "nft": False},
            "🇹🇭 Таиланд (+66)":      {"uah": 80,  "stars": 100, "nft": False},
            "🇬🇧 Великобритания (+44)": {"uah": 120, "stars": 115, "nft": False},
            "🇺🇦 Украина (+380)":     {"uah": 150, "stars": 150, "nft": False},
            "🇧🇾 Беларусь (+375)":    {"uah": 150, "stars": 200, "nft": False},
            "🇰🇿 Казахстан (+7)":     {"uah": 150, "stars": 200, "nft": False},
            "🇵🇱 Польша (+48)":       {"uah": 150, "stars": 200, "nft": False},
            "🇷🇺 Россия (+7)":        {"uah": 150, "stars": 200, "nft": False},
            "🇩🇪 Германия (+49)":     {"uah": 150, "stars": 200, "nft": False},
        },
    },
    "premium": {
        "name": f"{pe('star')} Premium номера",
        "products": {
            "🇺🇸 США (+1)":          {"uah": 180, "stars": 250, "nft": False},
            "🇨🇦 Канада (+1)":       {"uah": 180, "stars": 250, "nft": False},
            "🇺🇿 Узбекистан (+998)": {"uah": 350, "stars": 400, "nft": False},
            "🇺🇦 Украина (+380)":    {"uah": 350, "stars": 400, "nft": False},
            "🇰🇿 Казахстан (+7)":    {"uah": "от 130 до 450", "stars": 500, "nft": False},
            "🇩🇪 Германия (+49)":    {"uah": 400, "stars": 500, "nft": False},
        },
    },
    "physical": {
        "name": f"{pe('user')} Физические номера",
        "products": {
            "🇺🇸 США (+1)":          {"uah": 100, "stars": 150, "nft": False},
            "🇺🇦 Украина (+380)":    {"uah": 200, "stars": 300, "nft": False},
            "🇺🇿 Узбекистан (+998)": {"uah": 100, "stars": 150, "nft": False},
            "🇨🇴 Колумбия (+57)":    {"uah": 100, "stars": 150, "nft": False},
            "🇹🇭 Таиланд (+66)":     {"uah": 120, "stars": 175, "nft": False},
            "🇫🇷 Франция (+33)":     {"uah": 150, "stars": 200, "nft": False},
            "🇰🇿 Казахстан (+77)":   {"uah": 200, "stars": 300, "nft": False},
            "🇭🇺 Венгрия (+36)":     {"uah": 200, "stars": 300, "nft": False},
            "🇬🇱 Гренландия (+299)": {"uah": 250, "stars": 350, "nft": False},
            "🇵🇱 Польша (+48)":      {"uah": 250, "stars": 350, "nft": False},
        },
    },
}

# ==================== ЗВЁЗДЫ ====================
STAR_PACKAGES = [
    {"count": 85, "price": 60},
    {"count": 43, "price": 35},
    {"count": 21, "price": 15},
    {"count": 13, "price": 7},
]

def calculate_stars_price(total_stars: int):
    if total_stars <= 0:
        return 0, []
    remaining, price, used = total_stars, 0, []
    for pkg in STAR_PACKAGES:
        c, p = pkg["count"], pkg["price"]
        if remaining >= c:
            qty = remaining // c
            price += qty * p
            used.append({"count": c, "qty": qty})
            remaining %= c
    if remaining > 0:
        price += STAR_PACKAGES[-1]["price"]
        used.append({"count": STAR_PACKAGES[-1]["count"], "qty": 1})
    return price, used

# ==================== FSM ====================
class ReviewStates(StatesGroup):
    waiting_for_stars = State()
    waiting_for_photo_or_skip = State()
    waiting_for_text = State()

class OrderStates(StatesGroup):
    waiting_for_quantity = State()
    waiting_for_custom_quantity = State()
    waiting_for_payment_method = State()
    waiting_for_confirmation = State()

class StarStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_payment = State()
    waiting_for_confirm = State()

class CheckoutPromoStates(StatesGroup):
    waiting_for_promo_code = State()

class AdminStates(StatesGroup):
    waiting_for_phone = State()
    waiting_for_code = State()
    waiting_for_requisites_edit = State()
    waiting_for_broadcast = State()

class SupportStates(StatesGroup):
    chatting = State()

class PromoStates(StatesGroup):
    waiting_for_promo_code = State()

class AdminPromoStates(StatesGroup):
    waiting_for_promo_code = State()
    waiting_for_discount_type = State()
    waiting_for_discount_value = State()
    waiting_for_owner_id = State()
    waiting_for_commission = State()
    waiting_for_max_uses = State()
    waiting_for_expires_date = State()

class AdminPromotionStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_products = State()
    waiting_for_new_prices = State()
    waiting_for_duration = State()

class AdminBroadcastTemplateStates(StatesGroup):
    waiting_for_days = State()
    waiting_for_text = State()
    waiting_for_button = State()

class AdminLevelStates(StatesGroup):
    waiting_for_min_spent = State()
    waiting_for_discount = State()

class AdminReferralSettingsStates(StatesGroup):
    waiting_for_bonus_percent = State()

class AdminChatStates(StatesGroup):
    waiting_for_message = State()

STATUS_CONFIG = {
    "awaiting_payment": (pe("time"), "Ожидает оплаты"),
    "paid": (pe("money"), "Оплачен"),
    "phone_sent": ("📱", "Номер отправлен"),
    "code_sent": ("🔑", "Код отправлен"),
    "completed": (pe("check"), "Выполнен"),
    "rejected": (pe("warn"), "Отклонен"),
    "replaced": ("🔄", "Заменен"),
    "refunded": (pe("money"), "Возврат"),
}

def method_label(m):
    return {"uah": f"{pe('money')} Гривны",
            "stars": f"{pe('star')} Stars",
            "nft": "🖼 NFT"}.get(m, m)

def method_symbol(m):
    return {"uah": "₴", "stars": "⭐", "nft": "💎"}.get(m, "")

def generate_order_id():
    return f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{os.urandom(2).hex().upper()}"

def generate_short_order_id():
    c = load_order_counter(); cur = c.get("current", 0) + 1
    c["current"] = cur; save_order_counter(c)
    return f"#{cur:06d}"

def get_user_level(user_id):
    u = load_users().get(str(user_id), {})
    spent = u.get("total_spent", 0)
    levels = [
        ("VIP", get_setting("level_vip_min", 5000), get_setting("level_vip_discount", 10), "👑"),
        ("Платина", get_setting("level_platinum_min", 3000), get_setting("level_platinum_discount", 7), "💎"),
        ("Золото", get_setting("level_gold_min", 1500), get_setting("level_gold_discount", 5), "🥇"),
        ("Серебро", get_setting("level_silver_min", 500), get_setting("level_silver_discount", 3), "🥈"),
        ("Бронза", 0, 0, "🥉"),
    ]
    for name, mn, d, e in levels:
        if spent >= mn:
            return {"name": name, "discount": d, "emoji": e}
    return {"name": "Бронза", "discount": 0, "emoji": "🥉"}

def find_order_key(orders, oid):
    if not oid: return None
    oid = str(oid).strip()
    if oid in orders: return oid
    clean = oid.replace("#", "").strip()
    for k, o in orders.items():
        if str(k).replace("#", "").strip() == clean: return k
        if str(o.get("order_id", "")).replace("#", "").strip() == clean: return k
        if str(o.get("short_id", "")).replace("#", "").strip() == clean: return k
    return None

async def check_subscription(uid):
    try:
        m = await bot.get_chat_member(chat_id=STORE_CHANNEL_ID, user_id=uid)
        return m.status in ("member", "administrator", "creator")
    except Exception:
        return False

async def process_referral_bonus(referrer_id, referred_id, order_total):
    try: order_total = float(order_total)
    except Exception: return
    if order_total <= 0: return
    referrals = load_referrals(); rk = str(referrer_id)
    if rk not in referrals: return
    rdata = referrals[rk]; rdata.setdefault("referrals_list", [])
    users = load_users()
    if users.get(str(referred_id), {}).get("orders_count", 0) > 1: return
    for r in rdata["referrals_list"]:
        if r.get("user_id") == referred_id and r.get("bonus_promo_code"): return
    amount = round(order_total * get_setting("referral_bonus_percent", 5.0) / 100, 2)
    if amount <= 0: return
    code = "REF" + hashlib.md5(f"{referrer_id}_{referred_id}_{datetime.now().timestamp()}".encode()).hexdigest()[:8].upper()
    promos = load_promo_codes()
    promos[code] = {
        "code": code, "discount_type": "fixed", "discount_value": amount,
        "max_uses": 1, "current_uses": 0,
        "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
        "is_active": True, "created_at": datetime.now().isoformat(),
        "description": "Реферальный бонус", "owner_id": referrer_id,
        "commission_percent": 0,
    }
    save_promo_codes(promos)
    for r in rdata["referrals_list"]:
        if r.get("user_id") == referred_id:
            r["first_purchase_done"] = True
            r["bonus_amount"] = amount
            r["bonus_promo_code"] = code
            break
    rdata["total_earned"] = rdata.get("total_earned", 0) + amount
    save_referrals(referrals)
    try:
        await bot.send_message(referrer_id,
            f"{pe('gift')} <b>Реферальный бонус!</b>\n"
            f"Ваш реферал совершил первую покупку.\n"
            f"Сумма бонуса: <b>{amount:.2f} ₴</b>\n"
            f"Промокод: <code>{code}</code>\n"
            f"<i>Одноразовый, действует 30 дней.</i>")
    except Exception as e:
        logger.error(f"ref bonus: {e}")

def update_traffic_source_stats(name, purchases=0, revenue=0.0):
    if not name: return
    try: revenue = float(revenue)
    except Exception: revenue = 0.0
    src = load_traffic_sources()
    src.setdefault(name, {"total_visits": 0, "total_registrations": 0,
                          "total_purchases": 0, "total_revenue": 0.0,
                          "created_at": datetime.now().isoformat()})
    src[name]["total_purchases"] += purchases
    src[name]["total_revenue"] += revenue
    save_traffic_sources(src)

async def schedule_reminder(order_id, delay=300):
    await asyncio.sleep(delay)
    orders = load_orders(); rk = find_order_key(orders, order_id)
    if not rk: return
    o = orders[rk]
    if o["status"] == "completed" and not o.get("reviewed") and not o.get("reminder_sent"):
        o["reminder_sent"] = True; save_orders(orders)
        kb = InlineKeyboardBuilder()
        ibtn(kb, "Оставить отзыв", callback_data=f"leave_review_{rk}", icon_key="star", style="primary")
        ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
        kb.adjust(1)
        try:
            await bot.send_message(o["user_id"],
                f"👋 <b>Напоминаем</b>\nВы не оставили отзыв по заказу <b>{o.get('short_id', rk)}</b>.",
                reply_markup=kb.as_markup())
        except Exception as e:
            logger.error(f"reminder: {e}")

# ==================== КЛАВИАТУРЫ ====================
def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    # Reply-кнопки НЕ поддерживают премиум-эмодзи — только Unicode.
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="🛍 Каталог"), KeyboardButton(text="⭐ Купить Stars"))
    b.row(KeyboardButton(text="🛒 Оформить заказ"), KeyboardButton(text="📋 Мои заказы"))
    b.row(KeyboardButton(text="👤 Профиль"), KeyboardButton(text="👥 Рефералы"))
    b.row(KeyboardButton(text="💬 Отзывы"), KeyboardButton(text="❓ FAQ"))
    b.row(KeyboardButton(text="🎟 Промокод"), KeyboardButton(text="📢 Канал"))
    return b.as_markup(resize_keyboard=True)

def get_admin_reply_keyboard() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    b.row(KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📈 Панель управления"))
    b.row(KeyboardButton(text="📋 Все заказы"), KeyboardButton(text="⏳ Ожидают оплаты"))
    b.row(KeyboardButton(text="✅ Выполненные"), KeyboardButton(text="❌ Отклонённые"))
    b.row(KeyboardButton(text="💰 Реквизиты"), KeyboardButton(text="📢 Рассылка"))
    b.row(KeyboardButton(text="🔥 Акции"), KeyboardButton(text="🎟 Промокоды"))
    b.row(KeyboardButton(text="⭐ Уровни"), KeyboardButton(text="👥 Рефералы"))
    b.row(KeyboardButton(text="📊 Аналитика"), KeyboardButton(text="🔗 Источники"))
    b.row(KeyboardButton(text="🏠 Клиентское меню"))
    return b.as_markup(resize_keyboard=True)

def subscribe_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Подписаться", url="http://t.me/owerpass_store", style="primary")
    ibtn(kb, "Я подписался", callback_data="check_sub", icon_key="check", style="success")
    kb.adjust(1); return kb.as_markup()

def main_menu_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Каталог", callback_data="menu_catalog", icon_key="cart", style="primary")
    ibtn(kb, "Stars", callback_data="menu_stars", icon_key="star", style="primary")
    ibtn(kb, "Заказы", callback_data="my_orders", icon_key="cart")
    ibtn(kb, "Отзывы", callback_data="menu_reviews", icon_key="star")
    ibtn(kb, "FAQ", callback_data="show_faq", icon_key="warn")
    ibtn(kb, "Профиль", callback_data="profile_menu", icon_key="user")
    ibtn(kb, "Рефералы", callback_data="referral_menu", icon_key="gift")
    ibtn(kb, "Промокод", callback_data="promo_menu")
    ibtn(kb, "Канал", url="http://t.me/owerpass_store", style="primary")
    kb.adjust(2, 2, 2, 2); return kb.as_markup()

def catalog_keyboard():
    kb = InlineKeyboardBuilder()
    for k, v in CATEGORIES.items():
        ibtn(kb, v["name"], callback_data=f"cat_{k}", icon_key="cart", style="primary")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def category_products_keyboard(category):
    kb = InlineKeyboardBuilder()
    promos = load_promotions(); active = {}
    now = datetime.now()
    for _, p in promos.items():
        if p.get("is_active", True) and p.get("starts_at") and p.get("ends_at"):
            try:
                if datetime.fromisoformat(p["starts_at"]) <= now <= datetime.fromisoformat(p["ends_at"]):
                    active.update(p.get("new_prices", {}))
            except Exception: pass
    for pname, pd in CATEGORIES[category]["products"].items():
        clean = pname
        for flag in ["🇲🇲","🇺🇸","🇨🇴","🇧🇩","🇫🇷","🇧🇷","🇺🇿","🇹🇭","🇬🇧","🇺🇦","🇧🇾","🇰🇿","🇵🇱","🇷🇺","🇩🇪","🇨🇦","🇭🇺","🇬🇱"]:
            if pname.startswith(flag):
                clean = pname[len(flag):].strip(); break
        uah = pd["uah"]
        if pname in active:
            txt = f"{pname} — {active[pname]}₴ (было {uah}₴)"
            ibtn(kb, txt, callback_data=f"product_{category}_{clean}", icon_key="fire")
        else:
            txt = f"{pname} — {uah}₴ / {pd['stars']}⭐"
            ibtn(kb, txt, callback_data=f"product_{category}_{clean}")
    ibtn(kb, "В каталог", callback_data="menu_catalog", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def quantity_keyboard():
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text=f"{i} шт.", callback_data=f"qty_{i}")
    ibtn(kb, "Другое", callback_data="qty_custom", icon_key="cart")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(5, 1, 1); return kb.as_markup()

def payment_method_keyboard(can_nft=False):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Гривны", callback_data="pay_uah", icon_key="money", style="primary")
    ibtn(kb, "Stars", callback_data="pay_stars", icon_key="star", style="primary")
    if can_nft:
        ibtn(kb, "NFT", callback_data="pay_nft", style="primary")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(2, 1); return kb.as_markup()

def confirm_order_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Подтвердить", callback_data="confirm_order", icon_key="check", style="success")
    ibtn(kb, "Кол-во", callback_data="edit_quantity")
    ibtn(kb, "Оплата", callback_data="edit_payment_method", icon_key="money")
    ibtn(kb, "Промокод", callback_data="apply_promo_at_checkout", icon_key="gift")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def awaiting_payment_keyboard(order_id):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Написать продавцу", url="https://t.me/MaskYoY", style="primary")
    ibtn(kb, "Поддержка", callback_data=f"support_{order_id}", icon_key="warn")
    ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
    ibtn(kb, "Меню", callback_data="main_menu")
    kb.adjust(1); return kb.as_markup()

def user_number_actions_keyboard(order_id):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Запросить код", callback_data=f"user_request_code_{order_id}", icon_key="time", style="primary")
    ibtn(kb, "Подтвердить вход", callback_data=f"user_confirm_login_{order_id}", icon_key="check", style="success")
    ibtn(kb, "Поддержка", callback_data=f"support_{order_id}", icon_key="warn")
    kb.adjust(1); return kb.as_markup()

def user_order_actions_keyboard(order_id):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Оставить отзыв", callback_data=f"leave_review_{order_id}", icon_key="star", style="success")
    ibtn(kb, "Замена", callback_data=f"user_replace_{order_id}")
    ibtn(kb, "Возврат", callback_data=f"user_refund_{order_id}", icon_key="money", style="danger")
    ibtn(kb, "Повторить", callback_data=f"repeat_order_{order_id}")
    ibtn(kb, "Все заказы", callback_data="my_orders", icon_key="cart")
    kb.adjust(1); return kb.as_markup()

def reviews_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Смотреть отзывы", url="https://t.me/owerpass_repa", icon_key="star", style="primary")
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def stars_keyboard():
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        ibtn(kb, f"{i} ⭐", callback_data=f"stars_{i}", icon_key="star")
    kb.adjust(5); return kb.as_markup()

def review_photo_skip_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Пропустить", callback_data="skip_photo", icon_key="check", style="primary")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def moderation_keyboard(rid):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Одобрить", callback_data=f"approve_{rid}", icon_key="check", style="success")
    ibtn(kb, "Отклонить", callback_data=f"reject_{rid}", icon_key="warn", style="danger")
    kb.adjust(2); return kb.as_markup()

def admin_order_management_keyboard(order_id, status):
    kb = InlineKeyboardBuilder()
    if status == "awaiting_payment":
        ibtn(kb, "Подтвердить оплату", callback_data=f"admin_confirm_payment_{order_id}", icon_key="check", style="success")
        ibtn(kb, "Отклонить", callback_data=f"admin_reject_{order_id}", icon_key="warn", style="danger")
    elif status == "paid":
        ibtn(kb, "Выдать номер", callback_data=f"admin_send_phone_{order_id}", icon_key="user", style="primary")
        ibtn(kb, "Отклонить", callback_data=f"admin_reject_{order_id}", icon_key="warn", style="danger")
    elif status == "phone_sent":
        ibtn(kb, "Выдать код", callback_data=f"admin_send_code_{order_id}", icon_key="time", style="primary")
        ibtn(kb, "Отклонить", callback_data=f"admin_reject_{order_id}", icon_key="warn", style="danger")
    elif status == "code_sent":
        ibtn(kb, "Завершить", callback_data=f"admin_confirm_login_{order_id}", icon_key="check", style="success")
        ibtn(kb, "Отклонить", callback_data=f"admin_reject_{order_id}", icon_key="warn", style="danger")
    elif status == "completed":
        ibtn(kb, "Возврат", callback_data=f"admin_refund_{order_id}", icon_key="money", style="danger")
    ibtn(kb, "К списку", callback_data="admin_back_to_list")
    ibtn(kb, "Обновить", callback_data=f"admin_order_detail_{order_id}", icon_key="time")
    kb.adjust(1); return kb.as_markup()

def admin_all_orders_keyboard(page=0, per_page=5, status_filter=None):
    kb = InlineKeyboardBuilder()
    orders = load_orders()
    filtered = {k: v for k, v in orders.items() if v["status"] == status_filter} if status_filter else orders
    lst = sorted(filtered.items(), reverse=True)
    total_pages = (len(lst) + per_page - 1) // per_page
    if total_pages == 0:
        ibtn(kb, "Обновить", callback_data="admin_page_0", icon_key="time"); kb.adjust(1); return kb.as_markup()
    start = page * per_page; end = start + per_page
    for oid, o in lst[start:end]:
        sid = o.get("short_id", oid[:8])
        sym = method_symbol(o.get("payment_method", "uah"))
        total = o["total"] if isinstance(o["total"], str) else f"{o['total']}{sym}"
        ibtn(kb, f"{sid} | {o['product'][:15]} | {total}", callback_data=f"admin_order_detail_{oid}")
    if total_pages > 1:
        if page > 0: kb.button(text="⬅️", callback_data=f"admin_page_{page-1}")
        if page < total_pages - 1: kb.button(text="➡️", callback_data=f"admin_page_{page+1}")
        ibtn(kb, "Обновить", callback_data=f"admin_page_{page}", icon_key="time")
    if status_filter:
        ibtn(kb, "Сбросить фильтр", callback_data="admin_page_0", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def requisites_edit_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Гривны", callback_data="edit_req_uah", icon_key="money")
    ibtn(kb, "Звёзды", callback_data="edit_req_stars", icon_key="star")
    ibtn(kb, "NFT", callback_data="edit_req_nft")
    kb.adjust(1); return kb.as_markup()

def profile_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Рефералы", callback_data="referral_menu", icon_key="gift")
    ibtn(kb, "Мои заказы", callback_data="my_orders", icon_key="cart")
    ibtn(kb, "Последний заказ", callback_data="repeat_last_order")
    ibtn(kb, "Главное меню", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def referral_menu_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Моя статистика", callback_data="referral_stats", icon_key="star")
    ibtn(kb, "Назад", callback_data="profile_menu", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def promo_menu_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Назад", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_dashboard_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Заказы", callback_data="admin_orders_dashboard", icon_key="cart")
    ibtn(kb, "Рефералы", callback_data="admin_referrals_dashboard", icon_key="gift")
    ibtn(kb, "Акции", callback_data="admin_promotions_dashboard", icon_key="fire")
    ibtn(kb, "Промокоды", callback_data="admin_promo_dashboard")
    ibtn(kb, "Уровни", callback_data="admin_levels_dashboard", icon_key="star")
    ibtn(kb, "Рассылки", callback_data="admin_broadcasts_dashboard")
    ibtn(kb, "Аналитика", callback_data="admin_analytics_dashboard")
    ibtn(kb, "Источники", callback_data="admin_traffic_dashboard")
    ibtn(kb, "Обновить", callback_data="admin_dashboard_refresh", icon_key="time")
    kb.adjust(2, 2, 2, 2, 1); return kb.as_markup()

def admin_promotions_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Создать акцию", callback_data="admin_create_promotion", icon_key="fire", style="primary")
    for promo_id, promo in list(load_promotions().items())[:10]:
        status = "🟢" if promo.get("is_active", True) else "🔴"
        ibtn(kb, f"{status} {promo.get('name', 'Без названия')}", callback_data=f"admin_promo_detail_{promo_id}")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_promo_codes_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Создать промокод", callback_data="admin_create_promo_code", icon_key="gift", style="primary")
    earnings = load_promo_earnings()
    for code, data in list(load_promo_codes().items())[:10]:
        status = "🟢" if data.get("is_active", True) else "🔴"
        uses = f"{data.get('current_uses', 0)}/{data.get('max_uses') or '∞'}"
        earned = earnings.get(code, {}).get("total_earned", 0)
        ibtn(kb, f"{status} {code} ({uses}) 💰{earned:.0f}₴", callback_data=f"admin_promo_code_detail_{code}", icon_key="money")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_levels_keyboard():
    kb = InlineKeyboardBuilder()
    for key, name, emoji in [("bronze","Бронза","🥉"),("silver","Серебро","🥈"),("gold","Золото","🥇"),("platinum","Платина","💎"),("vip","VIP","👑")]:
        ibtn(kb, name, callback_data=f"admin_edit_level_{key}", icon_key="star")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_broadcasts_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Создать рассылку", callback_data="admin_create_broadcast_template", style="primary")
    for bc_id, bc in load_broadcasts().items():
        status = "🟢" if bc.get("is_active", True) else "🔴"
        ibtn(kb, f"{status} {bc.get('days_inactive', '?')} дней", callback_data=f"admin_broadcast_detail_{bc_id}")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_referrals_settings_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Изменить бонус %", callback_data="admin_edit_referral_bonus", icon_key="money")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_traffic_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_analytics_keyboard():
    kb = InlineKeyboardBuilder()
    ibtn(kb, "По дням", callback_data="admin_analytics_by_days", icon_key="time")
    ibtn(kb, "По часам", callback_data="admin_analytics_by_hours", icon_key="time")
    ibtn(kb, "По странам", callback_data="admin_analytics_by_country", icon_key="user")
    ibtn(kb, "Назад", callback_data="admin_dashboard_refresh", icon_key="warn", style="danger")
    kb.adjust(1); return kb.as_markup()

def admin_order_card_keyboard(order_id, status, user_id):
    kb = InlineKeyboardBuilder()
    if status == "awaiting_payment":
        ibtn(kb, "Подтвердить", callback_data=f"admin_confirm_payment_{order_id}", icon_key="check", style="success")
    elif status == "paid":
        ibtn(kb, "Выдать номер", callback_data=f"admin_send_phone_{order_id}", icon_key="user")
    elif status == "phone_sent":
        ibtn(kb, "Выдать код", callback_data=f"admin_send_code_{order_id}", icon_key="time")
    elif status == "code_sent":
        ibtn(kb, "Завершить", callback_data=f"admin_confirm_login_{order_id}", icon_key="check", style="success")
    elif status == "completed":
        ibtn(kb, "Возврат", callback_data=f"admin_refund_{order_id}", icon_key="money", style="danger")
    ibtn(kb, "Чат с покупателем", callback_data=f"admin_chat_with_user_{order_id}", icon_key="user")
    ibtn(kb, "Отменить", callback_data=f"admin_reject_{order_id}", icon_key="warn", style="danger")
    ibtn(kb, "Назад к списку", callback_data="admin_back_to_list")
    ibtn(kb, "Обновить", callback_data=f"admin_order_detail_{order_id}", icon_key="time")
    kb.adjust(1); return kb.as_markup()

# ==================== ТЕКСТЫ ====================
FAQ_TEXT = (
    f"<b>{pe('warn')} Частые вопросы</b>\n\n"
    f"<b>🛒 Как купить?</b>\n"
    f"1️⃣ Выберите товар в каталоге\n"
    f"2️⃣ Укажите количество\n"
    f"3️⃣ Выберите способ оплаты\n"
    f"4️⃣ Подтвердите заказ\n"
    f"5️⃣ Оплатите и свяжитесь с продавцом\n\n"
    f"<b>{pe('money')} Способы оплаты:</b>\n"
    f"• {pe('money')} Гривны\n"
    f"• {pe('star')} Telegram Stars\n"
    f"• 🖼 NFT\n\n"
    f"<b>{pe('gift')} Бонусы:</b>\n"
    f"• 5% с первой покупки реферала (промокодом)\n"
    f"• Скидки по уровням: Бронза → VIP\n\n"
    f"<b>📞 Контакты:</b>\n"
    f"• Продавец: @MaskYoY\n"
    f"• Канал: @owerpass_store\n"
    f"• Отзывы: @owerpass_repa"
)

# ==================== СТАРТ ====================
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    ref_code = None
    if message.text and len(message.text.split()) > 1:
        ref_code = message.text.split()[1]
    is_new = await add_user(message.from_user.id, message.from_user.username,
                            message.from_user.full_name, ref_code=ref_code)
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            f"{pe('warn')} <b>Админ-панель</b>\nВыберите действие:",
            reply_markup=get_admin_reply_keyboard(),
        )
        return
    if not await check_subscription(message.from_user.id):
        await message.answer(
            f"{pe('warn')} <b>Подпишитесь на канал</b>\nДля доступа к магазину необходимо подписаться!",
            reply_markup=subscribe_keyboard(),
        )
        return
    txt = f"{pe('star')} <b>Добро пожаловать в OverPass Store!</b>\n\n"
    txt += "🔹 Продажа номеров Telegram\n"
    txt += "🔹 Аккаунты TikTok, Discord\n"
    txt += "🔹 Эксклюзивные юзернеймы\n\n"
    if is_new and ref_code:
        if ref_code.startswith("ref_"):
            txt += f"{pe('gift')} Вы зарегистрированы по реферальной ссылке!\n"
            txt += "<i>Совершите первую покупку, чтобы друг получил бонус.</i>\n\n"
        else:
            txt += f"📊 Источник: <code>{ref_code}</code>\n\n"
    txt += "Используйте кнопки ниже:"
    await message.answer(txt, reply_markup=get_main_reply_keyboard())

# ==================== ПОЛЬЗОВАТЕЛЬСКИЕ ОБРАБОТЧИКИ ====================
@dp.message(F.from_user.id != ADMIN_ID, F.text == "🛍 Каталог")
@dp.callback_query(F.data == "menu_catalog")
async def open_catalog(event, state: FSMContext = None):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        try:
            await event.message.edit_text(f"{pe('cart')} <b>Выберите категорию:</b>", reply_markup=catalog_keyboard())
        except Exception:
            await event.message.answer(f"{pe('cart')} <b>Выберите категорию:</b>", reply_markup=catalog_keyboard())
    else:
        if not await check_subscription(event.from_user.id):
            await event.answer(f"{pe('warn')} Подпишитесь на канал!", reply_markup=subscribe_keyboard())
            return
        await event.answer(f"{pe('cart')} <b>Выберите категорию:</b>", reply_markup=catalog_keyboard())

@dp.callback_query(F.data.startswith("cat_"))
async def show_category(callback: types.CallbackQuery):
    await callback.answer()
    category = callback.data.replace("cat_", "")
    if category not in CATEGORIES:
        await callback.answer("❌ Категория не найдена", show_alert=True); return
    try:
        await callback.message.edit_text(
            f"{CATEGORIES[category]['name']}\nВыберите товар:",
            reply_markup=category_products_keyboard(category),
        )
    except Exception:
        await callback.message.answer(
            f"{CATEGORIES[category]['name']}\nВыберите товар:",
            reply_markup=category_products_keyboard(category),
        )

@dp.callback_query(F.data.startswith("product_"))
async def process_product_selection(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_", 2)
    if len(parts) < 3:
        await callback.answer("❌ Ошибка данных", show_alert=True); return
    category, clean = parts[1], parts[2]
    full = None
    for p in CATEGORIES[category]["products"].keys():
        cp = p
        for flag in ["🇲🇲","🇺🇸","🇨🇴","🇧🇩","🇫🇷","🇧🇷","🇺🇿","🇹🇭","🇬🇧","🇺🇦","🇧🇾","🇰🇿","🇵🇱","🇷🇺","🇩🇪","🇨🇦","🇭🇺","🇬🇱"]:
            if p.startswith(flag):
                cp = p[len(flag):].strip(); break
        if cp == clean:
            full = p; break
    if not full:
        await callback.answer("❌ Товар не найден", show_alert=True); return
    await state.update_data(category=category, product=full)
    try:
        await callback.message.edit_text(
            f"{pe('check')} Выбрано: {full}\n🔢 Выберите количество:",
            reply_markup=quantity_keyboard(),
        )
    except Exception:
        await callback.message.answer(
            f"{pe('check')} Выбрано: {full}\n🔢 Выберите количество:",
            reply_markup=quantity_keyboard(),
        )
    await state.set_state(OrderStates.waiting_for_quantity)

@dp.callback_query(OrderStates.waiting_for_quantity, F.data.startswith("qty_"))
async def process_quantity(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.data == "qty_custom":
        await callback.message.edit_text("✏️ Введите количество числом:")
        await state.set_state(OrderStates.waiting_for_custom_quantity)
        return
    q = int(callback.data.split("_")[1])
    await state.update_data(quantity=q)
    await ask_payment_method(callback.message, state, callback.from_user.id)
    await state.set_state(OrderStates.waiting_for_payment_method)

@dp.message(OrderStates.waiting_for_custom_quantity)
async def process_custom_quantity(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        await message.answer("❌ Введите корректное число!"); return
    await state.update_data(quantity=int(message.text))
    await ask_payment_method(message, state, message.from_user.id)
    await state.set_state(OrderStates.waiting_for_payment_method)

async def ask_payment_method(target, state, user_id):
    data = await state.get_data()
    product = data["product"]; qty = data["quantity"]
    pd = CATEGORIES[data["category"]]["products"][product]
    can_nft = pd.get("nft", False)
    uah = pd["uah"]; stars = pd["stars"]
    uah_total = uah if isinstance(uah, str) else uah * qty
    stars_total = stars * qty
    lvl = get_user_level(user_id); disc = lvl.get("discount", 0)
    disc_txt = ""
    if disc > 0 and isinstance(uah_total, (int, float)):
        da = uah_total * disc / 100; uah_total -= da
        disc_txt = f"\n{pe('gift')} Ваша скидка {disc}%: -{da:.0f}₴"
    txt = (
        f"📦 Товар: {product}\n"
        f"🔢 Количество: {qty} шт.\n"
        f"💱 <b>Выберите способ оплаты:</b>\n"
        f"{pe('money')} Гривны: {uah_total if isinstance(uah_total,str) else f'{uah_total:.2f}'} ₴\n"
        f"{pe('star')} Звёзды: {stars_total} ⭐"
    )
    if can_nft:
        txt += f"\n🖼 NFT: {stars_total} ⭐ (эквивалент)"
    if disc_txt: txt += disc_txt
    try:
        await target.edit_text(txt, reply_markup=payment_method_keyboard(can_nft))
    except Exception:
        await target.answer(txt, reply_markup=payment_method_keyboard(can_nft))

@dp.callback_query(OrderStates.waiting_for_payment_method, F.data.startswith("pay_"))
async def process_payment_method(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    method = callback.data.replace("pay_", "")
    await state.update_data(payment_method=method)
    await show_order_confirmation(callback, state)

async def show_order_confirmation(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    pd = CATEGORIES[data["category"]]["products"][data["product"]]
    method = data["payment_method"]; qty = data["quantity"]
    total = pd[method] if isinstance(pd[method], str) else pd[method] * qty
    disc_amt = 0
    if not isinstance(total, str):
        lvl = get_user_level(callback.from_user.id)
        disc_amt = total * lvl.get("discount", 0) / 100
        total -= disc_amt
    promo_code = data.get("promo_code")
    if promo_code and not isinstance(total, str):
        promo = load_promo_codes().get(promo_code.upper())
        if promo and promo.get("is_active", True):
            exp = False
            if promo.get("expires_at") and datetime.now() > datetime.fromisoformat(promo["expires_at"]):
                exp = True
            if not exp:
                if promo["discount_type"] == "percent":
                    d = total * promo["discount_value"] / 100
                else:
                    d = min(promo["discount_value"], total)
                total -= d; disc_amt += d
    sym = method_symbol(method)
    total_txt = total if isinstance(total, str) else f"{total:.2f} {sym}"
    txt = (
        f"📋 <b>Подтверждение заказа</b>\n"
        f"Товар: {data['product']}\n"
        f"Количество: {qty} шт.\n"
        f"Оплата: {method_label(method)}\n"
        f"Сумма: <b>{total_txt}</b>\n"
    )
    if disc_amt > 0:
        txt += f"{pe('gift')} Скидки: -{disc_amt:.2f} {sym}\n"
    txt += "\nВсё верно?"
    try:
        await callback.message.edit_text(txt, reply_markup=confirm_order_keyboard())
    except Exception:
        await callback.message.answer(txt, reply_markup=confirm_order_keyboard())
    await state.set_state(OrderStates.waiting_for_confirmation)

@dp.callback_query(OrderStates.waiting_for_confirmation, F.data == "edit_quantity")
async def edit_quantity_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("🔢 Выберите количество:", reply_markup=quantity_keyboard())
    await state.set_state(OrderStates.waiting_for_quantity)

@dp.callback_query(OrderStates.waiting_for_confirmation, F.data == "edit_payment_method")
async def edit_pay_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await ask_payment_method(callback.message, state, callback.from_user.id)
    await state.set_state(OrderStates.waiting_for_payment_method)

@dp.callback_query(OrderStates.waiting_for_confirmation, F.data == "apply_promo_at_checkout")
async def apply_promo_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("🎟 Введите промокод:")
    await state.set_state(CheckoutPromoStates.waiting_for_promo_code)

@dp.message(CheckoutPromoStates.waiting_for_promo_code, F.text)
async def process_promo_at_checkout(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    promo = load_promo_codes().get(code)
    if not promo:
        await message.answer("❌ Промокод не найден"); return
    if not promo.get("is_active", True):
        await message.answer("❌ Промокод неактивен"); return
    if promo.get("max_uses") and promo.get("current_uses", 0) >= promo["max_uses"]:
        await message.answer("❌ Промокод исчерпан"); return
    if promo.get("expires_at") and datetime.now() > datetime.fromisoformat(promo["expires_at"]):
        await message.answer("❌ Срок действия истёк"); return
    await state.update_data(promo_code=code)
    await message.answer(f"{pe('check')} Промокод <code>{code}</code> применён!")
    class FakeCB:
        def __init__(self, m): self.message = m; self.from_user = m.from_user
        async def answer(self): pass
    fake = FakeCB(message)
    await show_order_confirmation(fake, state)

@dp.callback_query(OrderStates.waiting_for_confirmation, F.data == "confirm_order")
async def confirm_order_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await create_order(callback, state)

async def create_order(source, state: FSMContext):
    data = await state.get_data()
    category = data["category"]; product = data["product"]
    qty = data["quantity"]; method = data["payment_method"]
    pd = CATEGORIES[category]["products"][product]
    total = pd[method] if isinstance(pd[method], str) else pd[method] * qty
    disc_amt = 0
    if not isinstance(total, str):
        lvl = get_user_level(source.from_user.id)
        disc_amt = total * lvl.get("discount", 0) / 100
        total -= disc_amt
    sym = method_symbol(method)
    promo_code = data.get("promo_code")
    promo_owner_commission = 0
    promo_owner_id = None
    if promo_code and not isinstance(total, str):
        promos = load_promo_codes()
        promo = promos.get(promo_code.upper())
        if promo and promo.get("is_active", True):
            exp = False
            if promo.get("expires_at") and datetime.now() > datetime.fromisoformat(promo["expires_at"]):
                exp = True
            if promo.get("max_uses") and promo.get("current_uses", 0) >= promo["max_uses"]:
                exp = True
            if not exp:
                if promo["discount_type"] == "percent":
                    d = total * promo["discount_value"] / 100
                else:
                    d = min(promo["discount_value"], total)
                before_promo = total
                total -= d; disc_amt += d
                comm_pct = promo.get("commission_percent", get_setting("promo_owner_commission_percent", 20.0))
                promo_owner_commission = before_promo * comm_pct / 100
                promo_owner_id = promo.get("owner_id")
                promo["current_uses"] = promo.get("current_uses", 0) + 1
                promos[promo_code.upper()] = promo
                save_promo_codes(promos)
                if promo_owner_id:
                    earn = load_promo_earnings()
                    earn.setdefault(promo_code.upper(), {
                        "code": promo_code.upper(), "owner_id": promo_owner_id,
                        "total_earned": 0, "transactions": [],
                    })
                    earn[promo_code.upper()]["total_earned"] += promo_owner_commission
                    earn[promo_code.upper()]["transactions"].append({
                        "order_id": None, "amount": promo_owner_commission,
                        "date": datetime.now().isoformat(),
                        "buyer_id": source.from_user.id,
                    })
                    save_promo_earnings(earn)
    legacy_id = generate_order_id(); short_id = generate_short_order_id()
    if isinstance(source, types.CallbackQuery):
        u = source.from_user; target = source.message
    else:
        u = source.from_user; target = source
    orders = load_orders()
    orders[legacy_id] = {
        "order_id": legacy_id, "short_id": short_id,
        "user_id": u.id, "username": u.username or "нет имени",
        "full_name": u.full_name, "category": category,
        "category_name": CATEGORIES[category]["name"],
        "product": product, "quantity": qty, "payment_method": method,
        "price_per_unit": pd[method], "total": total,
        "discount_amount": disc_amt, "promo_code": promo_code,
        "promo_owner_commission": promo_owner_commission,
        "promo_owner_id": promo_owner_id,
        "status": "awaiting_payment",
        "created_at": datetime.now().isoformat(),
        "phone": None, "code": None,
        "reviewed": False, "reminder_sent": False,
    }
    save_orders(orders)
    if promo_owner_commission > 0:
        earn = load_promo_earnings()
        if promo_code.upper() in earn and earn[promo_code.upper()]["transactions"]:
            earn[promo_code.upper()]["transactions"][-1]["order_id"] = legacy_id
            save_promo_earnings(earn)
    total_disp = total if isinstance(total, str) else f"{total:.2f} {sym}"
    admin_msg = (
        f"📱 <b>Новый заказ {short_id}</b>\n"
        f"👤 @{u.username or 'нет имени'} | {u.full_name}\n"
        f"ID: <code>{u.id}</code>\n\n"
        f"📂 {CATEGORIES[category]['name']}\n"
        f"📦 {product}\n"
        f"🔢 {qty} шт.\n"
        f"💳 {method_label(method)}\n"
        f"💰 <b>{total_disp}</b>\n"
    )
    if disc_amt > 0: admin_msg += f"{pe('gift')} Скидки: -{disc_amt:.2f} {sym}\n"
    if promo_code and promo_owner_commission > 0:
        admin_msg += f"\n🎟 Промокод: <code>{promo_code}</code>\n"
        admin_msg += f"{pe('money')} Комиссия владельцу: <b>{promo_owner_commission:.2f} ₴</b>\n"
        if promo_owner_id:
            owner = load_users().get(str(promo_owner_id), {})
            admin_msg += f"👤 Владелец: @{owner.get('username', f'ID:{promo_owner_id}')}\n"
    admin_msg += "\nСтатус: ⏳ Ожидает оплаты"
    try:
        await bot.send_message(ADMIN_ID, admin_msg,
            reply_markup=admin_order_management_keyboard(legacy_id, "awaiting_payment"))
    except Exception as e:
        logger.error(f"admin notif: {e}")
    req = get_requisites(method)
    pay_msg = (
        f"{pe('check')} <b>Заказ {short_id} создан!</b>\n"
        f"📂 {CATEGORIES[category]['name']}\n"
        f"📦 {product}\n"
        f"🔢 {qty} шт.\n"
        f"💳 {method_label(method)}\n"
        f"💰 <b>{total_disp}</b>\n"
    )
    if disc_amt > 0: pay_msg += f"{pe('gift')} Скидки: -{disc_amt:.2f} {sym}\n"
    pay_msg += f"\n📌 <b>Реквизиты:</b>\n{req}\n\n<i>После оплаты нажмите кнопку связи с продавцом.</i>"
    try:
        await target.edit_text(pay_msg, reply_markup=awaiting_payment_keyboard(legacy_id))
    except Exception:
        await target.answer(pay_msg, reply_markup=awaiting_payment_keyboard(legacy_id))
    await state.clear()

# ==================== ПОКУПКА ЗВЁЗД ====================
@dp.message(F.text == "⭐ Купить Stars")
@dp.callback_query(F.data == "menu_stars")
async def start_star_purchase(event, state: FSMContext = None):
    if isinstance(event, types.CallbackQuery):
        await event.answer(); msg = event.message
    else:
        if not await check_subscription(event.from_user.id):
            await event.answer(f"{pe('warn')} Подпишитесь на канал!", reply_markup=subscribe_keyboard()); return
        msg = event
    txt = (
        f"{pe('star')} <b>Покупка Telegram Stars</b>\n\n"
        f"Пакеты:\n"
        f"🔸 13 ⭐ — 7 ₴\n"
        f"🔸 21 ⭐ — 15 ₴\n"
        f"🔸 43 ⭐ — 35 ₴\n"
        f"🔸 85 ⭐ — 60 ₴\n\n"
        f"<i>Суммы больше складываются из пакетов.\n"
        f"Например, 106 = 85+21 = 75 ₴.</i>\n\n"
        f"👇 Введите количество звезд:"
    )
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    try:
        await msg.edit_text(txt, reply_markup=kb.as_markup())
    except Exception:
        await msg.answer(txt, reply_markup=kb.as_markup())
    if state:
        await state.set_state(StarStates.waiting_for_amount)

@dp.message(StarStates.waiting_for_amount, F.text.isdigit())
async def process_star_amount(message: types.Message, state: FSMContext):
    amt = int(message.text)
    if amt < 13:
        await message.answer("❌ Минимум — 13 звёзд."); return
    price, pkgs = calculate_stars_price(amt)
    comp = " + ".join(f"{p['count']}×{p['qty']}" for p in pkgs)
    await state.update_data(star_amount=amt, star_price=price)
    txt = (
        f"{pe('check')} <b>Расчёт</b>\n"
        f"Количество: <b>{amt} ⭐</b>\n"
        f"Состав: {comp}\n"
        f"💰 <b>Итого: {price} ₴</b>\n\n"
        f"Выберите способ оплаты:"
    )
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Гривны", callback_data="star_pay_uah", icon_key="money", style="primary")
    ibtn(kb, "Stars", callback_data="star_pay_stars", icon_key="star", style="primary")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(2, 1)
    await message.answer(txt, reply_markup=kb.as_markup())
    await state.set_state(StarStates.waiting_for_payment)

@dp.callback_query(StarStates.waiting_for_payment, F.data.startswith("star_pay_"))
async def process_star_pay(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    method = callback.data.replace("star_pay_", "")
    await state.update_data(star_method=method)
    data = await state.get_data()
    txt = (
        f"📋 <b>Подтверждение</b>\n"
        f"Товар: {data['star_amount']} ⭐\n"
        f"Оплата: {method_label(method)}\n"
        f"💰 Сумма: {data['star_price']} ₴\n\nВсё верно?"
    )
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Подтвердить", callback_data="confirm_star_order", icon_key="check", style="success")
    ibtn(kb, "Отмена", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    await callback.message.edit_text(txt, reply_markup=kb.as_markup())
    await state.set_state(StarStates.waiting_for_confirm)

@dp.callback_query(StarStates.waiting_for_confirm, F.data == "confirm_star_order")
async def confirm_star_order(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    legacy_id = generate_order_id(); short_id = generate_short_order_id()
    u = callback.from_user
    orders = load_orders()
    orders[legacy_id] = {
        "order_id": legacy_id, "short_id": short_id,
        "user_id": u.id, "username": u.username or "нет имени",
        "full_name": u.full_name, "category": "stars",
        "category_name": "Покупка Stars",
        "product": f"{data['star_amount']} Stars",
        "quantity": 1, "payment_method": data["star_method"],
        "price_per_unit": data["star_price"], "total": data["star_price"],
        "discount_amount": 0, "promo_code": None,
        "promo_owner_commission": 0, "promo_owner_id": None,
        "status": "awaiting_payment",
        "created_at": datetime.now().isoformat(),
        "phone": None, "code": None,
        "reviewed": False, "reminder_sent": False,
    }
    save_orders(orders)
    sym = method_symbol(data["star_method"])
    req = get_requisites(data["star_method"])
    admin_msg = (
        f"📱 <b>Новый заказ {short_id}</b>\n"
        f"👤 @{u.username or 'нет имени'}\n"
        f"ID: <code>{u.id}</code>\n\n"
        f"📂 Покупка Stars\n"
        f"📦 {data['star_amount']} ⭐\n"
        f"💳 {method_label(data['star_method'])}\n"
        f"💰 <b>{data['star_price']} {sym}</b>\n\nСтатус: ⏳ Ожидает оплаты"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_msg,
            reply_markup=admin_order_management_keyboard(legacy_id, "awaiting_payment"))
    except Exception as e:
        logger.error(f"star admin notif: {e}")
    pay_msg = (
        f"{pe('check')} <b>Заказ {short_id} создан!</b>\n"
        f"📦 {data['star_amount']} ⭐\n"
        f"💳 {method_label(data['star_method'])}\n"
        f"💰 <b>{data['star_price']} {sym}</b>\n\n"
        f"📌 <b>Реквизиты:</b>\n{req}\n\n"
        f"<i>После оплаты свяжитесь с продавцом.</i>"
    )
    try:
        await callback.message.edit_text(pay_msg, reply_markup=awaiting_payment_keyboard(legacy_id))
    except Exception:
        await callback.message.answer(pay_msg, reply_markup=awaiting_payment_keyboard(legacy_id))
    await state.clear()

# ==================== ПОЛЬЗОВАТЕЛЬСКИЕ ОСТАЛЬНЫЕ ====================
@dp.message(F.from_user.id != ADMIN_ID, F.text == "📋 Мои заказы")
@dp.callback_query(F.data == "my_orders")
async def show_my_orders(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer(); uid = event.from_user.id; target = event.message
    else:
        if not await check_subscription(event.from_user.id):
            await event.answer(f"{pe('warn')} Подпишитесь на канал!", reply_markup=subscribe_keyboard()); return
        uid = event.from_user.id; target = event
    orders = load_orders()
    mine = {k: v for k, v in orders.items() if v["user_id"] == uid}
    if not mine:
        msg = "📋 У вас пока нет заказов.\n🛒 Нажмите «Оформить заказ»."
        try: await target.edit_text(msg, reply_markup=main_menu_keyboard())
        except Exception: await target.answer(msg, reply_markup=main_menu_keyboard())
        return
    kb = InlineKeyboardBuilder()
    txt = f"📋 <b>Ваши заказы ({len(mine)})</b>\n"
    for oid, o in sorted(mine.items(), reverse=True):
        emoji, stat = STATUS_CONFIG.get(o["status"], ("❓", "?"))
        sid = o.get("short_id", oid[:8])
        sym = method_symbol(o.get("payment_method", "uah"))
        total = o["total"] if isinstance(o["total"], str) else f"{o['total']}{sym}"
        txt += f"{emoji} {sid} | {o['product']} x{o['quantity']} | {total} | {stat}\n"
        ibtn(kb, f"{sid}", callback_data=f"order_detail_{oid}", icon_key="cart")
    ibtn(kb, "Главное меню", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    try: await target.edit_text(txt, reply_markup=kb.as_markup())
    except Exception: await target.answer(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("order_detail_"))
async def show_order_detail(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("order_detail_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await callback.answer("❌ Заказ не найден", show_alert=True); return
    o = orders[rk]
    emoji, stat = STATUS_CONFIG.get(o["status"], ("❓", "?"))
    sym = method_symbol(o.get("payment_method", "uah"))
    sid = o.get("short_id", rk[:8])
    total = o["total"] if isinstance(o["total"], str) else f"{o['total']} {sym}"
    txt = (
        f"📋 <b>Заказ {sid}</b>\n"
        f"Товар: {o['product']}\n"
        f"Количество: {o['quantity']} шт.\n"
        f"Оплата: {method_label(o['payment_method'])}\n"
        f"Сумма: {total}\n"
        f"Дата: {datetime.fromisoformat(o['created_at']).strftime('%d.%m.%Y %H:%M')}\n"
        f"Статус: {emoji} {stat}\n"
    )
    if o.get("phone"): txt += f"\n📱 Номер: {o['phone']}\n"
    if o["status"] == "completed": kb = user_order_actions_keyboard(rk)
    elif o["status"] in ("phone_sent", "code_sent"): kb = user_number_actions_keyboard(rk)
    elif o["status"] == "awaiting_payment": kb = awaiting_payment_keyboard(rk)
    else:
        b = InlineKeyboardBuilder()
        ibtn(b, "Все заказы", callback_data="my_orders", icon_key="cart")
        ibtn(b, "Главное меню", callback_data="main_menu", icon_key="warn", style="danger")
        b.adjust(1); kb = b.as_markup()
    try: await callback.message.edit_text(txt, reply_markup=kb)
    except Exception: await callback.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data.startswith("user_request_code_"))
async def user_request_code(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("user_request_code_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await callback.answer("❌ Не найден", show_alert=True); return
    o = orders[rk]
    if not o.get("phone"):
        await callback.answer("❌ Номер ещё не отправлен", show_alert=True); return
    sid = o.get("short_id", rk)
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Выдать код", callback_data=f"admin_send_code_{rk}", icon_key="time", style="primary")
    try:
        await bot.send_message(ADMIN_ID,
            f"🔑 <b>Запрос кода</b>\nЗаказ: {sid}\nПокупатель: @{o['username']}\nНомер: {o['phone']}",
            reply_markup=kb.as_markup())
    except Exception: pass
    await callback.message.answer(f"{pe('time')} Запрос кода отправлен продавцу.")

@dp.callback_query(F.data.startswith("user_confirm_login_"))
async def user_confirm_login(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("user_confirm_login_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await callback.answer("❌ Не найден", show_alert=True); return
    o = orders[rk]
    if o.get("status") == "completed":
        await callback.answer("✅ Уже выполнен", show_alert=True); return
    o["status"] = "completed"; o["completed_at"] = datetime.now().isoformat()
    o["reminder_sent"] = False; save_orders(orders)
    users = load_users(); uk = str(o["user_id"])
    if uk in users:
        if not isinstance(o.get("total", 0), str):
            users[uk]["total_spent"] = users[uk].get("total_spent", 0) + o.get("total", 0)
        users[uk]["orders_count"] = users[uk].get("orders_count", 0) + 1
        save_users(users)
        if users[uk].get("referred_by"):
            await process_referral_bonus(users[uk]["referred_by"], o["user_id"], o.get("total", 0))
        ts = users[uk].get("traffic_source")
        if ts: update_traffic_source_stats(ts, purchases=1, revenue=o.get("total", 0))
    sid = o.get("short_id", rk)
    try:
        await bot.send_message(ADMIN_ID,
            f"{pe('check')} <b>Покупатель подтвердил вход</b>\n"
            f"Заказ: {sid}\nНомер: {o.get('phone', '—')}")
    except Exception: pass
    try:
        await callback.message.edit_text(
            f"{pe('check')} <b>Заказ {sid} выполнен!</b>\n"
            f"Оставьте отзыв:",
            reply_markup=user_order_actions_keyboard(rk))
    except Exception:
        await callback.message.answer(
            f"{pe('check')} <b>Заказ {sid} выполнен!</b>",
            reply_markup=user_order_actions_keyboard(rk))
    asyncio.create_task(schedule_reminder(rk))

@dp.callback_query(F.data.startswith("user_replace_"))
async def user_replace(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("user_replace_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if rk:
        sid = orders[rk].get("short_id", rk)
        try:
            await bot.send_message(ADMIN_ID,
                f"🔄 <b>Запрос на замену</b>\nЗаказ: {sid}\nОт: @{callback.from_user.username or '—'}")
        except Exception: pass
    await callback.message.answer("🔄 Запрос на замену отправлен продавцу.\n📞 @MaskYoY")

@dp.callback_query(F.data.startswith("user_refund_"))
async def user_refund(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("user_refund_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if rk:
        sid = orders[rk].get("short_id", rk)
        try:
            await bot.send_message(ADMIN_ID,
                f"{pe('money')} <b>Запрос на возврат</b>\nЗаказ: {sid}\nОт: @{callback.from_user.username or '—'}")
        except Exception: pass
    await callback.message.answer("💰 Запрос на возврат отправлен.\n📞 @MaskYoY")

@dp.message(F.from_user.id != ADMIN_ID, F.text == "💬 Отзывы")
@dp.callback_query(F.data == "menu_reviews")
async def open_reviews(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        try: await event.message.edit_text(f"💬 <b>Отзывы покупателей</b>", reply_markup=reviews_keyboard())
        except Exception: await event.message.answer(f"💬 <b>Отзывы покупателей</b>", reply_markup=reviews_keyboard())
    else:
        await event.answer(f"💬 <b>Отзывы покупателей</b>", reply_markup=reviews_keyboard())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "❓ FAQ")
@dp.callback_query(F.data == "show_faq")
async def show_faq(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        try: await event.message.edit_text(FAQ_TEXT, reply_markup=main_menu_keyboard())
        except Exception: await event.message.answer(FAQ_TEXT, reply_markup=main_menu_keyboard())
    else:
        await event.answer(FAQ_TEXT, reply_markup=get_main_reply_keyboard())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "📢 Канал")
async def show_channel(message: types.Message):
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Перейти в канал", url="http://t.me/owerpass_store", style="primary")
    await message.answer("Нажмите кнопку:", reply_markup=kb.as_markup())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "🛒 Оформить заказ")
async def order_from_kb(message: types.Message, state: FSMContext):
    if not await check_subscription(message.from_user.id):
        await message.answer(f"{pe('warn')} Подпишитесь на канал!", reply_markup=subscribe_keyboard()); return
    await state.clear()
    await message.answer(f"{pe('cart')} <b>Выберите категорию:</b>", reply_markup=catalog_keyboard())

@dp.callback_query(F.data == "check_sub")
async def check_sub_cb(callback: types.CallbackQuery):
    await callback.answer()
    if await check_subscription(callback.from_user.id):
        try: await callback.message.edit_text(f"{pe('check')} Спасибо за подписку!", reply_markup=main_menu_keyboard())
        except Exception: await callback.message.answer(f"{pe('check')} Спасибо за подписку!", reply_markup=main_menu_keyboard())
        await callback.message.answer("Используйте кнопки ниже:", reply_markup=get_main_reply_keyboard())
    else:
        await callback.answer("❌ Вы не подписались!", show_alert=True)

@dp.callback_query(F.data == "main_menu")
async def main_menu_cb(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer(); await state.clear()
    try: await callback.message.edit_text("👋 <b>Главное меню</b>", reply_markup=main_menu_keyboard())
    except Exception: await callback.message.answer("👋 <b>Главное меню</b>", reply_markup=main_menu_keyboard())

# ==================== ОТЗЫВЫ ====================
@dp.callback_query(F.data.startswith("leave_review_"))
async def start_review(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    oid = callback.data.replace("leave_review_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await callback.answer("❌ Не найден", show_alert=True); return
    o = orders[rk]
    if o["status"] != "completed":
        await callback.answer("❌ Нельзя оставить отзыв", show_alert=True); return
    await state.update_data(review_order_id=rk)
    try:
        await callback.message.edit_text(
            f"Оцените покупку:\nЗаказ: {o.get('short_id', rk)}\nТовар: {o['product']}",
            reply_markup=stars_keyboard())
    except Exception:
        await callback.message.answer(
            f"Оцените покупку:\nЗаказ: {o.get('short_id', rk)}\nТовар: {o['product']}",
            reply_markup=stars_keyboard())
    await state.set_state(ReviewStates.waiting_for_stars)

@dp.callback_query(ReviewStates.waiting_for_stars, F.data.startswith("stars_"))
async def process_stars(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    r = int(callback.data.split("_")[1])
    await state.update_data(stars=r)
    await callback.message.edit_text(
        f"{'⭐'*r}\n📸 Отправьте скриншот покупки (необязательно).",
        reply_markup=review_photo_skip_keyboard())
    await state.set_state(ReviewStates.waiting_for_photo_or_skip)

@dp.callback_query(ReviewStates.waiting_for_photo_or_skip, F.data == "skip_photo")
async def skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(photo=None)
    await callback.message.edit_text("✏️ Напишите текст отзыва:")
    await state.set_state(ReviewStates.waiting_for_text)

@dp.message(ReviewStates.waiting_for_photo_or_skip, F.photo)
async def process_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await message.answer("✏️ Напишите текст отзыва:")
    await state.set_state(ReviewStates.waiting_for_text)

@dp.message(ReviewStates.waiting_for_text, F.text)
async def process_review_text(message: types.Message, state: FSMContext):
    d = await state.get_data()
    rid = f"rev_{message.from_user.id}_{int(datetime.now().timestamp())}"
    reviews = load_reviews()
    reviews[rid] = {
        "review_id": rid, "user_id": message.from_user.id,
        "username": message.from_user.username,
        "full_name": message.from_user.full_name,
        "stars": d.get("stars", 5), "text": message.text,
        "photo": d.get("photo"), "order_id": d.get("review_order_id"),
        "status": "pending", "created_at": datetime.now().isoformat(),
    }
    save_reviews(reviews)
    oid = d.get("review_order_id")
    if oid:
        orders = load_orders(); rk = find_order_key(orders, oid)
        if rk:
            orders[rk]["reviewed"] = True; save_orders(orders)
    short_id = oid or "—"
    cap = (
        f"<b>Новый отзыв</b>\n"
        f"ID: {rid}\n"
        f"От: {message.from_user.full_name}\n"
        f"@{message.from_user.username}\n"
        f"Заказ: {short_id}\n"
        f"Оценка: {'⭐'*d.get('stars',5)}\n"
        f"Текст: {message.text}"
    )
    try:
        if d.get("photo"):
            await bot.send_photo(ADMIN_ID, d["photo"], caption=cap, reply_markup=moderation_keyboard(rid))
        else:
            await bot.send_message(ADMIN_ID, cap, reply_markup=moderation_keyboard(rid))
        await message.answer("🙏 Спасибо за отзыв!\nОн будет опубликован после проверки.",
                             reply_markup=get_main_reply_keyboard())
    except Exception as e:
        logger.error(f"review send: {e}")
        await message.answer("❌ Ошибка при отправке отзыва.")
    await state.clear()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_review(callback: types.CallbackQuery):
    await callback.answer()
    rid = callback.data.replace("approve_", "")
    reviews = load_reviews(); r = reviews.get(rid)
    if not r:
        await callback.answer("❌ Не найден", show_alert=True); return
    txt = (
        f"⭐️ <b>Новый отзыв</b>\n"
        f"Покупатель: @{r.get('username', 'Покупатель')}\n"
        f"Оценка: {'⭐️'*r['stars']}\n"
        f"Отзыв: {r['text']}\n"
        f"Купить: @MaskYoY\nКанал: @owerpass_store"
    )
    try:
        if r.get("photo"): await bot.send_photo(CHANNEL_ID, r["photo"], caption=txt)
        else: await bot.send_message(CHANNEL_ID, txt)
        await bot.send_message(r["user_id"], f"{pe('check')} Ваш отзыв опубликован! Спасибо!")
        r["status"] = "approved"; save_reviews(reviews)
        await callback.answer("✅ Опубликован", show_alert=True)
    except Exception as e:
        logger.error(f"approve: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("reject_"))
async def reject_review(callback: types.CallbackQuery):
    await callback.answer()
    rid = callback.data.replace("reject_", "")
    reviews = load_reviews(); r = reviews.get(rid)
    if r:
        r["status"] = "rejected"; save_reviews(reviews)
        try: await bot.send_message(r["user_id"], "❌ Ваш отзыв отклонен.\n📞 @MaskYoY")
        except Exception: pass
    await callback.answer("❌ Отклонен", show_alert=True)

# ==================== ПРОФИЛЬ / РЕФЕРАЛЫ / ПРОМО ====================
@dp.message(F.from_user.id != ADMIN_ID, F.text == "👤 Профиль")
@dp.callback_query(F.data == "profile_menu")
async def show_profile(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer(); uid = event.from_user.id; u = event.from_user; target = event.message
    else:
        uid = event.from_user.id; u = event.from_user; target = event
    if uid == ADMIN_ID: return
    lvl = get_user_level(uid)
    orders = load_orders()
    my = [o for o in orders.values() if o["user_id"] == uid]
    comp = [o for o in my if o["status"] == "completed"]
    spent = sum(o["total"] for o in comp if not isinstance(o.get("total", 0), str))
    refs = load_referrals().get(str(uid), {})
    txt = (
        f"{pe('user')} <b>Ваш профиль</b>\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"👤 Имя: {u.full_name}\n"
        f"📧 @{u.username or 'не указано'}\n"
        f"{pe('star')} <b>Уровень:</b> {lvl['emoji']} {lvl['name']}\n"
        f"{pe('gift')} Скидка: {lvl['discount']}%\n"
        f"{pe('money')} Потрачено: {spent:.2f} ₴\n"
        f"📦 Покупок: {len(comp)}\n"
        f"👥 Рефералов: {len(refs.get('referrals_list', []))}\n"
        f"💸 Бонусов: {refs.get('total_earned', 0):.2f} ₴"
    )
    kb = profile_keyboard()
    try: await target.edit_text(txt, reply_markup=kb)
    except Exception: await target.answer(txt, reply_markup=kb)

@dp.message(F.from_user.id != ADMIN_ID, F.text == "👥 Рефералы")
@dp.callback_query(F.data == "referral_menu")
async def show_referral_menu(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer(); uid = event.from_user.id; target = event.message
    else:
        uid = event.from_user.id; target = event
    if uid == ADMIN_ID: return
    referrals = load_referrals(); rd = referrals.get(str(uid), {})
    if not rd.get("referral_code"):
        rd["referral_code"] = hashlib.md5(f"{uid}_ref_salt".encode()).hexdigest()[:8].upper()
    rd.setdefault("referrals_list", []); rd.setdefault("total_earned", 0)
    referrals[str(uid)] = rd; save_referrals(referrals)
    code = rd["referral_code"]
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{code}"
    percent = get_setting("referral_bonus_percent", 5.0)
    txt = (
        f"{pe('gift')} <b>Реферальная программа</b>\n"
        f"Ваш бонус: <b>{percent}%</b> с первой покупки реферала (промокодом).\n\n"
        f"👥 Приглашено: {len(rd['referrals_list'])}\n"
        f"💸 Бонусов: {rd['total_earned']:.2f} ₴\n"
        f"🔗 <code>{link}</code>\n"
        f"Код: <code>{code}</code>"
    )
    kb = referral_menu_keyboard()
    try: await target.edit_text(txt, reply_markup=kb)
    except Exception: await target.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "referral_stats")
async def referral_stats(callback: types.CallbackQuery):
    await callback.answer()
    rd = load_referrals().get(str(callback.from_user.id), {})
    txt = "📊 <b>Ваши рефералы</b>\n"
    lst = rd.get("referrals_list", [])
    if not lst: txt += "<i>Пока никого</i>"
    else:
        for r in lst[-10:]:
            st = "✅ купил" if r.get("first_purchase_done") else "⏳ не купил"
            d = datetime.fromisoformat(r["date"]).strftime("%d.%m.%Y")
            txt += f"👤 @{r.get('username', '—')} — {st} ({d})\n"
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Назад", callback_data="referral_menu", icon_key="warn", style="danger")
    try: await callback.message.edit_text(txt, reply_markup=kb.as_markup())
    except Exception: await callback.message.answer(txt, reply_markup=kb.as_markup())

@dp.message(F.from_user.id != ADMIN_ID, F.text == "🎟 Промокод")
@dp.callback_query(F.data == "promo_menu")
async def show_promo(event, state: FSMContext = None):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        if event.from_user.id == ADMIN_ID: return
        try: await event.message.edit_text("🎟 <b>Промокоды</b>\nВведите ваш промокод:", reply_markup=promo_menu_keyboard())
        except Exception: await event.message.answer("🎟 <b>Промокоды</b>\nВведите ваш промокод:", reply_markup=promo_menu_keyboard())
    else:
        if event.from_user.id == ADMIN_ID: return
        await event.answer("🎟 <b>Промокоды</b>\nВведите ваш промокод:", reply_markup=promo_menu_keyboard())
    if state: await state.set_state(PromoStates.waiting_for_promo_code)

@dp.message(PromoStates.waiting_for_promo_code, F.text)
async def process_user_promo(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID: return
    if message.text.startswith("/"): await state.clear(); return
    code = message.text.strip().upper()
    promo = load_promo_codes().get(code)
    if not promo:
        await message.answer("❌ Промокод не найден"); await state.clear(); return
    if not promo.get("is_active", True):
        await message.answer("❌ Промокод неактивен"); await state.clear(); return
    if promo.get("max_uses") and promo.get("current_uses", 0) >= promo["max_uses"]:
        await message.answer("❌ Промокод исчерпан"); await state.clear(); return
    if promo.get("expires_at") and datetime.now() > datetime.fromisoformat(promo["expires_at"]):
        await message.answer("❌ Срок истёк"); await state.clear(); return
    desc = f"{promo['discount_value']}%" if promo["discount_type"] == "percent" else f"{promo['discount_value']} ₴"
    await message.answer(
        f"{pe('check')} Промокод <code>{code}</code> принят!\n"
        f"{pe('gift')} {desc} скидки.\nБудет применён при следующем заказе.",
        reply_markup=main_menu_keyboard())
    await state.clear()

@dp.callback_query(F.data == "repeat_last_order")
async def repeat_last(callback: types.CallbackQuery):
    await callback.answer()
    orders = load_orders()
    mine = [o for o in orders.values() if o["user_id"] == callback.from_user.id and o["status"] == "completed"]
    if not mine:
        await callback.message.answer("❌ Нет завершённых заказов"); return
    last = max(mine, key=lambda x: x.get("completed_at", x.get("created_at", "")))
    txt = (
        f"🔁 <b>Повторить?</b>\n"
        f"📦 {last['product']}\n"
        f"🔢 {last['quantity']} шт.\n"
        f"💰 {last['total']}"
    )
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Да, повторить", callback_data=f"confirm_repeat_{last['order_id']}", icon_key="check", style="success")
    ibtn(kb, "Нет", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    try: await callback.message.edit_text(txt, reply_markup=kb.as_markup())
    except Exception: await callback.message.answer(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("repeat_order_"))
async def repeat_specific(callback: types.CallbackQuery):
    await callback.answer()
    oid = callback.data.replace("repeat_order_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await callback.answer("❌ Не найден", show_alert=True); return
    o = orders[rk]
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Да, повторить", callback_data=f"confirm_repeat_{rk}", icon_key="check", style="success")
    ibtn(kb, "Нет", callback_data="main_menu", icon_key="warn", style="danger")
    kb.adjust(1)
    try: await callback.message.edit_text(f"🔁 Повторить заказ {o.get('short_id', rk)}?", reply_markup=kb.as_markup())
    except Exception: await callback.message.answer(f"🔁 Повторить заказ {o.get('short_id', rk)}?", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("confirm_repeat_"))
async def confirm_repeat(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    oid = callback.data.replace("confirm_repeat_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await callback.answer("❌ Не найден", show_alert=True); return
    o = orders[rk]
    await state.update_data(category=o["category"], product=o["product"], quantity=o["quantity"])
    await ask_payment_method(callback.message, state, callback.from_user.id)
    await state.set_state(OrderStates.waiting_for_payment_method)

# ==================== ПОДДЕРЖКА ====================
@dp.callback_query(F.data.startswith("support_"))
async def start_support(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    oid = callback.data.replace("support_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if rk: oid = rk
    await state.update_data(support_order_id=oid)
    await state.set_state(SupportStates.chatting)
    close_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Закрыть чат")]], resize_keyboard=True)
    await callback.message.answer(
        "🆘 Напишите ваше сообщение — оно уйдёт продавцу.\n"
        "Ответ придёт сюда же. Для выхода нажмите кнопку ниже.",
        reply_markup=close_kb)

@dp.message(SupportStates.chatting, F.text == "❌ Закрыть чат")
async def close_support(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Чат закрыт.", reply_markup=get_main_reply_keyboard())

@dp.message(SupportStates.chatting, F.text | F.photo | F.document | F.video | F.animation)
async def relay_user(message: types.Message, state: FSMContext):
    d = await state.get_data()
    oid = d.get("support_order_id", "—")
    orders = load_orders(); rk = find_order_key(orders, oid)
    sid = orders[rk].get("short_id", oid) if rk else oid
    header = (
        f"🆘 <b>Сообщение от покупателя</b>\n"
        f"Заказ: {sid}\n"
        f"От: @{message.from_user.username or '—'}\n"
        f"<i>Ответьте реплаем на это сообщение — ответ дойдёт покупателю.</i>"
    )
    try:
        await bot.send_message(ADMIN_ID, header)
        fwd = await bot.copy_message(ADMIN_ID, message.chat.id, message.message_id)
        relay = load_relay(); relay[str(fwd.message_id)] = message.from_user.id
        save_relay(relay)
        hist = load_chat_history()
        hist.setdefault(rk or oid, []).append({
            "sender": "user",
            "text": message.text or f"[{message.content_type}]",
            "date": datetime.now().isoformat(),
        })
        save_chat_history(hist)
        await message.answer("✅ Сообщение отправлено продавцу.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

@dp.message(F.from_user.id == ADMIN_ID, F.reply_to_message)
async def relay_admin_to_user(message: types.Message):
    relay = load_relay(); uid = relay.get(str(message.reply_to_message.message_id))
    if not uid: return
    try:
        await bot.copy_message(uid, message.chat.id, message.message_id)
        await message.answer("✅ Ответ доставлен покупателю")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")

# ==================== АДМИН: СТАТИСТИКА / ЗАКАЗЫ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📊 Статистика")
async def admin_stats(message: types.Message):
    orders = load_orders(); users = load_users()
    counts = {}; rev_uah = 0; rev_stars = 0
    for o in orders.values():
        counts[o["status"]] = counts.get(o["status"], 0) + 1
        if o["status"] == "completed" and not isinstance(o.get("total", 0), str):
            if o.get("payment_method") == "uah": rev_uah += o["total"]
            elif o.get("payment_method") == "stars": rev_stars += o["total"]
    txt = (
        f"📊 <b>Статистика</b>\n"
        f"👤 Пользователей: <b>{len(users)}</b>\n"
        f"📦 Заказов: <b>{len(orders)}</b>\n\n"
        f"✅ Выполнено: {counts.get('completed', 0)}\n"
        f"🔄 В обработке: {counts.get('paid', 0) + counts.get('phone_sent', 0) + counts.get('code_sent', 0)}\n"
        f"⏳ Ожидают: {counts.get('awaiting_payment', 0)}\n"
        f"❌ Отклонено: {counts.get('rejected', 0)}\n\n"
        f"{pe('money')} Доход:\n• Гривны: <b>{rev_uah:.2f} ₴</b>\n• Stars: <b>{rev_stars} ⭐</b>\n\n"
        f"📈 Средний чек: <b>{rev_uah // max(counts.get('completed', 1), 1)} ₴</b>"
    )
    await message.answer(txt, reply_markup=get_admin_reply_keyboard())

async def show_admin_orders(message_or_cb, page=0, status_filter=None, edit=False):
    orders = load_orders()
    filtered = {k: v for k, v in orders.items() if v["status"] == status_filter} if status_filter else orders
    lst = sorted(filtered.items(), reverse=True)
    per_page = 5
    if not lst:
        txt = "📋 Нет заказов"
        if edit and hasattr(message_or_cb, "edit_text"):
            await message_or_cb.edit_text(txt, reply_markup=admin_all_orders_keyboard(0, per_page, status_filter))
        else:
            await message_or_cb.answer(txt, reply_markup=get_admin_reply_keyboard())
        return
    total_pages = (len(lst) + per_page - 1) // per_page
    page = max(0, min(page, total_pages - 1))
    start = page * per_page
    end = min(start + per_page, len(lst))
    label = f" (фильтр: {STATUS_CONFIG.get(status_filter, ('',''))[1]})" if status_filter else ""
    txt = f"📋 <b>Заказы{label} — {page+1}/{total_pages}</b>\n"
    for oid, o in lst[start:end]:
        emoji, stat = STATUS_CONFIG.get(o["status"], ("❓","?"))
        sym = method_symbol(o.get("payment_method", "uah"))
        total = o["total"] if isinstance(o["total"], str) else f"{o['total']}{sym}"
        txt += f"{emoji} {o.get('short_id', oid[:8])} | {o['product'][:15]} | {total}\n"
    kb = admin_all_orders_keyboard(page, per_page, status_filter)
    if edit and hasattr(message_or_cb, "edit_text"):
        try: await message_or_cb.edit_text(txt, reply_markup=kb)
        except Exception: await message_or_cb.answer(txt, reply_markup=kb)
    else:
        await message_or_cb.answer(txt, reply_markup=kb)

@dp.message(F.from_user.id == ADMIN_ID, F.text == "📋 Все заказы")
async def a_all_orders(m): await show_admin_orders(m, 0, None)
@dp.message(F.from_user.id == ADMIN_ID, F.text == "⏳ Ожидают оплаты")
async def a_pending(m): await show_admin_orders(m, 0, "awaiting_payment")
@dp.message(F.from_user.id == ADMIN_ID, F.text == "✅ Выполненные")
async def a_completed(m): await show_admin_orders(m, 0, "completed")
@dp.message(F.from_user.id == ADMIN_ID, F.text == "❌ Отклонённые")
async def a_rejected(m): await show_admin_orders(m, 0, "rejected")

@dp.callback_query(F.data.startswith("admin_page_"))
async def a_page(cb: types.CallbackQuery):
    await cb.answer()
    page = int(cb.data.split("_")[2])
    await show_admin_orders(cb.message, page, None, edit=True)

@dp.callback_query(F.data == "admin_back_to_list")
async def a_back(cb: types.CallbackQuery):
    await cb.answer()
    await show_admin_orders(cb.message, 0, None, edit=True)

@dp.callback_query(F.data.startswith("admin_order_detail_"))
async def a_detail(cb: types.CallbackQuery):
    await cb.answer()
    oid = cb.data.replace("admin_order_detail_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await cb.answer("❌ Не найден", show_alert=True); return
    o = orders[rk]
    emoji, stat = STATUS_CONFIG.get(o["status"], ("❓","?"))
    sym = method_symbol(o.get("payment_method","uah"))
    total = o["total"] if isinstance(o["total"], str) else f"{o['total']} {sym}"
    txt = (
        f"📦 <b>Заказ {o.get('short_id', rk)}</b>\n"
        f"👤 @{o.get('username', '—')}\n"
        f"ID: <code>{o['user_id']}</code>\n"
        f"📅 {datetime.fromisoformat(o['created_at']).strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📂 {o.get('category_name', '—')}\n"
        f"📦 {o['product']} × {o['quantity']}\n"
        f"💳 {method_label(o['payment_method'])}\n"
        f"💰 <b>{total}</b>\n"
    )
    if o.get("phone"): txt += f"📱 {o['phone']}\n"
    if o.get("code"): txt += f"🔑 {o['code']}\n"
    if o.get("promo_code") and o.get("promo_owner_commission", 0) > 0:
        txt += f"\n🎟 Промокод: <code>{o['promo_code']}</code>\n"
        txt += f"{pe('money')} Комиссия: {o['promo_owner_commission']:.2f} ₴\n"
        if o.get("promo_owner_id"):
            owner = load_users().get(str(o["promo_owner_id"]), {})
            txt += f"👤 Владелец: @{owner.get('username', f'ID:{o[\"promo_owner_id\"]}')}\n"
    txt += f"\nСтатус: {emoji} {stat}"
    try: await cb.message.edit_text(txt, reply_markup=admin_order_management_keyboard(rk, o["status"]))
    except Exception: await cb.message.answer(txt, reply_markup=admin_order_management_keyboard(rk, o["status"]))

# ==================== АДМИН: УПРАВЛЕНИЕ СТАТУСАМИ ====================
@dp.callback_query(F.data.startswith("admin_confirm_payment_"))
async def a_confirm_pay(cb: types.CallbackQuery):
    await cb.answer()
    oid = cb.data.replace("admin_confirm_payment_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await cb.answer("❌ Не найден", show_alert=True); return
    o = orders[rk]
    o["status"] = "paid"; o["paid_at"] = datetime.now().isoformat(); save_orders(orders)
    sym = method_symbol(o.get("payment_method", "uah"))
    try:
        await bot.send_message(o["user_id"],
            f"{pe('check')} <b>Оплата подтверждена!</b>\n"
            f"Заказ: {o.get('short_id', rk)}\n"
            f"📦 {o['product']}\n"
            f"💰 {o['total']} {sym}\n"
            f"Продавец скоро отправит номер.")
    except Exception: pass
    await a_detail(cb)

@dp.callback_query(F.data.startswith("admin_reject_"))
async def a_reject(cb: types.CallbackQuery):
    await cb.answer()
    oid = cb.data.replace("admin_reject_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await cb.answer("❌ Не найден", show_alert=True); return
    o = orders[rk]; o["status"] = "rejected"; save_orders(orders)
    try:
        await bot.send_message(o["user_id"],
            f"❌ Заказ {o.get('short_id', rk)} отклонён\n📞 @MaskYoY")
    except Exception: pass
    await a_detail(cb)

@dp.callback_query(F.data.startswith("admin_refund_"))
async def a_refund(cb: types.CallbackQuery):
    await cb.answer()
    oid = cb.data.replace("admin_refund_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await cb.answer("❌ Не найден", show_alert=True); return
    o = orders[rk]; o["status"] = "refunded"; save_orders(orders)
    try:
        await bot.send_message(o["user_id"],
            f"{pe('money')} Возврат по заказу {o.get('short_id', rk)} оформлен.")
    except Exception: pass
    await a_detail(cb)

@dp.callback_query(F.data.startswith("admin_confirm_login_"))
async def a_confirm_login(cb: types.CallbackQuery):
    await cb.answer()
    oid = cb.data.replace("admin_confirm_login_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await cb.answer("❌ Не найден", show_alert=True); return
    o = orders[rk]
    if o.get("status") == "completed":
        await cb.answer("✅ Уже выполнен", show_alert=True); return
    o["status"] = "completed"; o["completed_at"] = datetime.now().isoformat()
    o["reminder_sent"] = False; save_orders(orders)
    users = load_users(); uk = str(o["user_id"])
    if uk in users:
        if not isinstance(o.get("total", 0), str):
            users[uk]["total_spent"] = users[uk].get("total_spent", 0) + o["total"]
        users[uk]["orders_count"] = users[uk].get("orders_count", 0) + 1
        save_users(users)
        if users[uk].get("referred_by"):
            await process_referral_bonus(users[uk]["referred_by"], o["user_id"], o.get("total", 0))
        ts = users[uk].get("traffic_source")
        if ts: update_traffic_source_stats(ts, purchases=1, revenue=o.get("total", 0))
    try:
        await bot.send_message(o["user_id"],
            f"{pe('check')} <b>Заказ выполнен!</b>\n"
            f"Номер: {o.get('phone', '—')}\nОставьте отзыв:",
            reply_markup=user_order_actions_keyboard(rk))
    except Exception: pass
    asyncio.create_task(schedule_reminder(rk))
    await a_detail(cb)

# ==================== АДМИН: ВЫДАЧА НОМЕРА (НОВЫЙ ФОРМАТ) ====================
@dp.callback_query(F.data.startswith("admin_send_phone_"))
async def a_send_phone_start(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    oid = cb.data.replace("admin_send_phone_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await cb.answer("❌ Не найден", show_alert=True); return
    await state.update_data(admin_order_id=rk)
    await cb.message.answer(f"📱 Отправьте номер для заказа {orders[rk].get('short_id', rk)}")
    await state.set_state(AdminStates.waiting_for_phone)

@dp.message(AdminStates.waiting_for_phone)
async def a_send_phone_process(message: types.Message, state: FSMContext):
    d = await state.get_data(); oid = d.get("admin_order_id")
    if not oid:
        await message.answer("❌ Нет ID заказа"); await state.clear(); return
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await message.answer("❌ Заказ не найден"); await state.clear(); return
    o = orders[rk]; sid = o.get("short_id", rk)
    digits = "".join(ch for ch in message.text if ch.isdigit())
    if not digits:
        await message.answer("❌ Номер не содержит цифр"); return
    phone = f"+{digits}"
    o["phone"] = phone; o["status"] = "phone_sent"
    o["phone_sent_at"] = datetime.now().isoformat(); save_orders(orders)

    product = o["product"]; cname = "Неизвестно"; ccode = ""
    if "(" in product and ")" in product:
        parts = product.split("(")
        ccode = parts[1].replace(")", "").strip()
        name_part = parts[0].strip()
        for flag in ["🇲🇲","🇺🇸","🇨🇴","🇧🇩","🇫🇷","🇧🇷","🇺🇿","🇹🇭","🇬🇧","🇺🇦","🇧🇾","🇰🇿","🇵🇱","🇷🇺","🇩🇪","🇨🇦","🇭🇺","🇬🇱"]:
            name_part = name_part.replace(flag, "").strip()
        cname = name_part

    client_msg = (
        f"🎉 <b>ВАШ АККАУНТ</b>\n\n"
        f"🌍 Страна: {cname} ({ccode})\n"
        f"📱 Ваш номер: <code>{phone}</code>\n\n"
        f"<b>Как войти:</b>\n"
        f"1. Войдите в новый аккаунт Telegram\n"
        f"2. Используйте номер выше для входа\n"
        f"3. Нажмите кнопку и получите код\n\n"
        f"<i>Код придёт сюда автоматически!</i>"
    )
    try:
        await bot.send_message(o["user_id"], client_msg,
            reply_markup=user_number_actions_keyboard(rk))
        await message.answer(f"✅ Номер отправлен покупателю {sid}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()

@dp.callback_query(F.data.startswith("admin_send_code_"))
async def a_send_code_start(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    oid = cb.data.replace("admin_send_code_", "")
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await cb.answer("❌ Не найден", show_alert=True); return
    await state.update_data(admin_order_id=rk)
    await cb.message.answer(f"🔑 Отправьте код для заказа {orders[rk].get('short_id', rk)}")
    await state.set_state(AdminStates.waiting_for_code)

@dp.message(AdminStates.waiting_for_code)
async def a_send_code_process(message: types.Message, state: FSMContext):
    d = await state.get_data(); oid = d.get("admin_order_id")
    if not oid:
        await message.answer("❌ Нет ID заказа"); await state.clear(); return
    orders = load_orders(); rk = find_order_key(orders, oid)
    if not rk:
        await message.answer("❌ Заказ не найден"); await state.clear(); return
    o = orders[rk]; code = message.text.strip()
    o["code"] = code; o["status"] = "code_sent"
    o["code_sent_at"] = datetime.now().isoformat(); save_orders(orders)
    try:
        await bot.send_message(o["user_id"],
            f"🔑 <b>Код подтверждения</b>\n"
            f"Заказ: {o.get('short_id', rk)}\n"
            f"Код: <code>{code}</code>\n\n"
            f"Введите сейчас же и нажмите «Подтвердить вход».",
            reply_markup=user_number_actions_keyboard(rk))
        await message.answer(f"✅ Код отправлен покупателю {o.get('short_id', rk)}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()

# ==================== АДМИН: РЕКВИЗИТЫ / РАССЫЛКА ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "💰 Реквизиты")
async def a_req(message: types.Message):
    r = load_requisites()
    txt = (
        f"💰 <b>Текущие реквизиты:</b>\n"
        f"{pe('money')} Гривны:\n{r.get('uah', '—')}\n\n"
        f"{pe('star')} Звёзды:\n{r.get('stars', '—')}\n\n"
        f"🖼 NFT:\n{r.get('nft', '—')}\n\nВыберите что изменить:"
    )
    await message.answer(txt, reply_markup=requisites_edit_keyboard())

@dp.callback_query(F.data.startswith("edit_req_"))
async def a_edit_req(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    m = cb.data.replace("edit_req_", "")
    await state.update_data(edit_req_method=m)
    labels = {"uah":"Гривны","stars":"Звёзды","nft":"NFT"}
    await cb.message.answer(f"✏️ Введите новые реквизиты для {labels.get(m, m)}:")
    await state.set_state(AdminStates.waiting_for_requisites_edit)

@dp.message(AdminStates.waiting_for_requisites_edit)
async def a_save_req(message: types.Message, state: FSMContext):
    d = await state.get_data(); m = d["edit_req_method"]
    r = load_requisites(); r[m] = message.text; save_requisites(r)
    labels = {"uah":"Гривны","stars":"Звёзды","nft":"NFT"}
    await message.answer(f"{pe('check')} Реквизиты для {labels.get(m, m)} обновлены!",
                         reply_markup=get_admin_reply_keyboard())
    await state.clear()

@dp.message(F.from_user.id == ADMIN_ID, F.text == "📢 Рассылка")
async def a_broadcast(message: types.Message, state: FSMContext):
    users = load_users()
    if not users:
        await message.answer("❌ Нет пользователей", reply_markup=get_admin_reply_keyboard()); return
    await message.answer(
        f"📢 Отправьте сообщение для рассылки {len(users)} пользователям.\n"
        f"/cancel — отмена.")
    await state.set_state(AdminStates.waiting_for_broadcast)

@dp.message(AdminStates.waiting_for_broadcast)
async def a_broadcast_process(message: types.Message, state: FSMContext):
    if message.text == "/cancel":
        await message.answer("❌ Отменено", reply_markup=get_admin_reply_keyboard())
        await state.clear(); return
    users = load_users(); ok = 0; fail = 0
    status = await message.answer(f"⏳ Отправка {len(users)} пользователям...")
    for uid_str in users.keys():
        try:
            await bot.copy_message(int(uid_str), message.chat.id, message.message_id)
            ok += 1; await asyncio.sleep(0.05)
        except Exception:
            fail += 1
    await status.edit_text(
        f"{pe('check')} Рассылка завершена\n📤 Отправлено: {ok}\n❌ Ошибок: {fail}",
        reply_markup=get_admin_reply_keyboard())
    await state.clear()

# ==================== АДМИН: ПРОМОКОДЫ ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "🎟 Промокоды")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_promo_dashboard")
async def a_promo_menu(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        try: await event.message.edit_text("🎟 <b>Промокоды</b>", reply_markup=admin_promo_codes_keyboard())
        except Exception: await event.message.answer("🎟 <b>Промокоды</b>", reply_markup=admin_promo_codes_keyboard())
    else:
        await event.answer("🎟 <b>Промокоды</b>", reply_markup=admin_promo_codes_keyboard())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_create_promo_code")
async def a_create_promo(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.edit_text("🎟 Введите код промокода (например, SALE2026):")
    await state.set_state(AdminPromoStates.waiting_for_promo_code)

@dp.message(AdminPromoStates.waiting_for_promo_code, F.text)
async def a_promo_code(message: types.Message, state: FSMContext):
    await state.update_data(promo_code=message.text.strip().upper())
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Процентная", callback_data="promo_type_percent", style="primary")
    ibtn(kb, "Фиксированная", callback_data="promo_type_fixed", icon_key="money", style="primary")
    kb.adjust(2)
    await message.answer(
        f"Код: <code>{message.text.strip().upper()}</code>\nТип скидки?",
        reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_discount_type)

@dp.callback_query(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_discount_type, F.data.startswith("promo_type_"))
async def a_promo_type(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    t = "percent" if cb.data == "promo_type_percent" else "fixed"
    await state.update_data(discount_type=t)
    label = "процент (10)" if t == "percent" else "сумму в грн (50)"
    await cb.message.edit_text(f"Введите {label}:")
    await state.set_state(AdminPromoStates.waiting_for_discount_value)

@dp.message(AdminPromoStates.waiting_for_discount_value, F.text)
async def a_promo_value(message: types.Message, state: FSMContext):
    try: v = float(message.text)
    except ValueError:
        await message.answer("❌ Не число"); return
    await state.update_data(discount_value=v)
    await message.answer("Введите ID владельца промокода (кто будет получать комиссию):")
    await state.set_state(AdminPromoStates.waiting_for_owner_id)

@dp.message(AdminPromoStates.waiting_for_owner_id, F.text)
async def a_promo_owner(message: types.Message, state: FSMContext):
    try: oid = int(message.text)
    except ValueError:
        await message.answer("❌ Неверный ID"); return
    await state.update_data(owner_id=oid)
    default_comm = get_setting("promo_owner_commission_percent", 20.0)
    await message.answer(f"Введите % комиссии владельцу (по умолчанию {default_comm}%):")
    await state.set_state(AdminPromoStates.waiting_for_commission)

@dp.message(AdminPromoStates.waiting_for_commission, F.text)
async def a_promo_comm(message: types.Message, state: FSMContext):
    try:
        c = float(message.text)
        if not 0 <= c <= 100: raise ValueError
    except ValueError:
        await message.answer("❌ Введите 0–100"); return
    await state.update_data(commission_percent=c)
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Без ограничений", callback_data="promo_unlimited")
    for n in [10, 50, 100, 500]:
        kb.button(text=f"{n} использований", callback_data=f"promo_max_{n}")
    kb.adjust(1)
    await message.answer("Макс. использований:", reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_max_uses)

@dp.callback_query(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_max_uses, F.data.startswith("promo_"))
async def a_promo_max(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    if cb.data == "promo_unlimited":
        mu = None
    else:
        mu = int(cb.data.split("_")[-1])
    await state.update_data(max_uses=mu)
    kb = InlineKeyboardBuilder()
    for days in [1, 7, 30, 90]:
        kb.button(text=f"{days} дней", callback_data=f"promo_expire_{days}")
    ibtn(kb, "Навсегда", callback_data="promo_expire_0")
    kb.adjust(2)
    await cb.message.edit_text("Срок действия:", reply_markup=kb.as_markup())
    await state.set_state(AdminPromoStates.waiting_for_expires_date)

@dp.callback_query(F.from_user.id == ADMIN_ID, AdminPromoStates.waiting_for_expires_date, F.data.startswith("promo_expire_"))
async def a_promo_exp(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    days = int(cb.data.split("_")[-1])
    d = await state.get_data()
    exp = (datetime.now() + timedelta(days=days)).isoformat() if days > 0 else None
    promos = load_promo_codes()
    promos[d["promo_code"]] = {
        "code": d["promo_code"], "discount_type": d["discount_type"],
        "discount_value": d["discount_value"], "max_uses": d["max_uses"],
        "current_uses": 0, "expires_at": exp, "is_active": True,
        "created_at": datetime.now().isoformat(),
        "owner_id": d["owner_id"],
        "commission_percent": d["commission_percent"],
    }
    save_promo_codes(promos)
    desc = f"{d['discount_value']}%" if d["discount_type"] == "percent" else f"{d['discount_value']} ₴"
    owner = load_users().get(str(d["owner_id"]), {})
    oname = owner.get("username", f"ID:{d['owner_id']}")
    txt = (
        f"{pe('check')} <b>Промокод создан!</b>\n"
        f"🎟 Код: <code>{d['promo_code']}</code>\n"
        f"💰 Скидка: {desc}\n"
        f"👤 Владелец: @{oname}\n"
        f"{pe('money')} Комиссия: {d['commission_percent']}%\n"
        f"🔢 Макс. использований: {d['max_uses'] or '∞'}\n"
    )
    if exp: txt += f"📅 До: {datetime.fromisoformat(exp).strftime('%d.%m.%Y')}\n"
    else: txt += "📅 Навсегда\n"
    try: await cb.message.edit_text(txt, reply_markup=admin_promo_codes_keyboard())
    except Exception: await cb.message.answer(txt, reply_markup=admin_promo_codes_keyboard())
    await state.clear()

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_promo_code_detail_"))
async def a_promo_detail(cb: types.CallbackQuery):
    await cb.answer()
    code = cb.data.replace("admin_promo_code_detail_", "")
    promos = load_promo_codes(); p = promos.get(code)
    if not p:
        await cb.answer("❌ Не найден", show_alert=True); return
    earn = load_promo_earnings().get(code, {})
    status = "🟢 Активен" if p.get("is_active", True) else "🔴 Неактивен"
    desc = f"{p['discount_value']}%" if p["discount_type"] == "percent" else f"{p['discount_value']} ₴"
    uses = f"{p.get('current_uses', 0)}/{p.get('max_uses') or '∞'}"
    total = earn.get("total_earned", 0)
    owner = load_users().get(str(p.get("owner_id")), {}) if p.get("owner_id") else {}
    oname = owner.get("username", f"ID:{p.get('owner_id')}") if p.get("owner_id") else "—"
    txt = (
        f"🎟 <b>Промокод {code}</b>\n"
        f"💰 Скидка: {desc}\n"
        f"👤 Владелец: @{oname}\n"
        f"{pe('money')} Комиссия: {p.get('commission_percent', 20)}%\n"
        f"Статус: {status}\n"
        f"🔢 Использований: {uses}\n"
        f"💰 Заработано: <b>{total:.2f} ₴</b>\n"
    )
    if p.get("expires_at"):
        txt += f"📅 До: {datetime.fromisoformat(p['expires_at']).strftime('%d.%m.%Y')}\n"
    else: txt += "📅 Навсегда\n"
    kb = InlineKeyboardBuilder()
    if p.get("is_active", True):
        ibtn(kb, "Деактивировать", callback_data=f"admin_deactivate_promo_{code}", icon_key="warn", style="danger")
    else:
        ibtn(kb, "Активировать", callback_data=f"admin_activate_promo_{code}", icon_key="check", style="success")
    ibtn(kb, "Удалить", callback_data=f"admin_delete_promo_{code}", style="danger")
    ibtn(kb, "Назад", callback_data="admin_promo_dashboard", style="danger")
    kb.adjust(1)
    try: await cb.message.edit_text(txt, reply_markup=kb.as_markup())
    except Exception: await cb.message.answer(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_deactivate_promo_"))
async def a_promo_deactivate(cb: types.CallbackQuery):
    await cb.answer()
    code = cb.data.replace("admin_deactivate_promo_", "")
    p = load_promo_codes()
    if code in p: p[code]["is_active"] = False; save_promo_codes(p)
    await cb.answer("✅ Деактивировано", show_alert=True)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_activate_promo_"))
async def a_promo_activate(cb: types.CallbackQuery):
    await cb.answer()
    code = cb.data.replace("admin_activate_promo_", "")
    p = load_promo_codes()
    if code in p: p[code]["is_active"] = True; save_promo_codes(p)
    await cb.answer("✅ Активировано", show_alert=True)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_delete_promo_"))
async def a_promo_delete(cb: types.CallbackQuery):
    await cb.answer()
    code = cb.data.replace("admin_delete_promo_", "")
    p = load_promo_codes()
    if code in p: del p[code]; save_promo_codes(p)
    await cb.answer("🗑 Удалено", show_alert=True)

# ==================== АДМИН: ПАНЕЛЬ, УРОВНИ, РЕФЕРАЛЫ, АНАЛИТИКА ====================
@dp.message(F.from_user.id == ADMIN_ID, F.text == "📈 Панель управления")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_dashboard_refresh")
async def admin_dashboard(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
    orders = load_orders(); users = load_users()
    total_rev = 0; comp = 0
    for o in orders.values():
        if o["status"] == "completed" and not isinstance(o.get("total", 0), str):
            total_rev += o["total"]; comp += 1
    avg = total_rev / comp if comp else 0
    txt = (
        f"📊 <b>Панель управления</b>\n"
        f"👤 Пользователей: {len(users)}\n"
        f"📦 Заказов: {len(orders)}\n"
        f"✅ Выполнено: {comp}\n"
        f"💰 Оборот: {total_rev:.2f} ₴\n"
        f"📈 Средний чек: {avg:.2f} ₴"
    )
    if isinstance(event, types.CallbackQuery):
        try: await event.message.edit_text(txt, reply_markup=admin_dashboard_keyboard())
        except Exception: await event.message.answer(txt, reply_markup=admin_dashboard_keyboard())
    else:
        await event.answer(txt, reply_markup=admin_dashboard_keyboard())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_orders_dashboard")
async def a_orders_dash(cb: types.CallbackQuery):
    await cb.answer()
    await show_admin_orders(cb.message, 0, None, edit=True)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_promotions_dashboard")
async def a_promos_dash(cb: types.CallbackQuery):
    await cb.answer()
    try: await cb.message.edit_text("🔥 <b>Акции</b>", reply_markup=admin_promotions_keyboard())
    except Exception: await cb.message.answer("🔥 <b>Акции</b>", reply_markup=admin_promotions_keyboard())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_levels_dashboard")
async def a_levels(cb: types.CallbackQuery):
    await cb.answer()
    cfg = {
        "Бронза": ("🥉", get_setting("level_bronze_min", 0), get_setting("level_bronze_discount", 0)),
        "Серебро": ("🥈", get_setting("level_silver_min", 500), get_setting("level_silver_discount", 3)),
        "Золото": ("🥇", get_setting("level_gold_min", 1500), get_setting("level_gold_discount", 5)),
        "Платина": ("💎", get_setting("level_platinum_min", 3000), get_setting("level_platinum_discount", 7)),
        "VIP": ("👑", get_setting("level_vip_min", 5000), get_setting("level_vip_discount", 10)),
    }
    txt = f"{pe('star')} <b>Уровни</b>\n"
    for name, (e, mn, disc) in cfg.items():
        txt += f"{e} <b>{name}</b> — {mn} ₴ / {disc}%\n"
    try: await cb.message.edit_text(txt, reply_markup=admin_levels_keyboard())
    except Exception: await cb.message.answer(txt, reply_markup=admin_levels_keyboard())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data.startswith("admin_edit_level_"))
async def a_edit_level(cb: types.CallbackQuery):
    await cb.answer()
    key = cb.data.replace("admin_edit_level_", "")
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Изменить порог", callback_data="edit_level_min", icon_key="money")
    ibtn(kb, "Изменить скидку", callback_data="edit_level_discount", icon_key="gift")
    ibtn(kb, "Назад", callback_data="admin_levels_dashboard", style="danger")
    kb.adjust(1)
    await cb.message.edit_text(f"Уровень {LEVEL_KEYS.get(key, key)} — что изменить?",
                                reply_markup=kb.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "edit_level_min")
async def a_level_min_start(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.edit_text("Введите новый порог (₴):")
    await state.set_state(AdminLevelStates.waiting_for_min_spent)

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "edit_level_discount")
async def a_level_disc_start(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    await cb.message.edit_text("Введите скидку (%):")
    await state.set_state(AdminLevelStates.waiting_for_discount)

@dp.message(AdminLevelStates.waiting_for_min_spent, F.text)
async def a_level_min_save(message: types.Message, state: FSMContext):
    try: v = float(message.text)
    except ValueError:
        await message.answer("❌ Не число"); return
    settings = load_settings()
    # Простой вариант: сохраняем в bronze по умолчанию, но можно доработать логику выбора уровня
    settings["level_silver_min"] = v; save_settings(settings)
    await message.answer(f"{pe('check')} Порог обновлён: {v} ₴",
                         reply_markup=get_admin_reply_keyboard())
    await state.clear()

@dp.message(AdminLevelStates.waiting_for_discount, F.text)
async def a_level_disc_save(message: types.Message, state: FSMContext):
    try:
        v = float(message.text)
        if not 0 <= v <= 100: raise ValueError
    except ValueError:
        await message.answer("❌ Введите 0–100"); return
    settings = load_settings(); settings["level_silver_discount"] = v
    save_settings(settings)
    await message.answer(f"{pe('check')} Скидка обновлена: {v}%",
                         reply_markup=get_admin_reply_keyboard())
    await state.clear()

@dp.message(F.from_user.id == ADMIN_ID, F.text == "👥 Рефералы")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_referrals_dashboard")
async def a_refs(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
    refs = load_referrals()
    percent = get_setting("referral_bonus_percent", 5.0)
    total = sum(len(r.get("referrals_list", [])) for r in refs.values())
    earned = sum(r.get("total_earned", 0) for r in refs.values())
    top = sorted([(u, r) for u, r in refs.items() if r.get("referrals_list")],
                 key=lambda x: len(x[1].get("referrals_list", [])), reverse=True)[:5]
    txt = (
        f"👥 <b>Рефералы</b>\n"
        f"💰 Бонус: {percent}%\n"
        f"👥 Всего рефералов: {total}\n"
        f"💸 Бонусов выдано: {earned:.2f} ₴\n"
    )
    users = load_users()
    for i, (uid, r) in enumerate(top, 1):
        un = users.get(str(uid), {}).get("username", "—")
        txt += f"{i}. @{un} — {len(r.get('referrals_list', []))} реф.\n"
    if isinstance(event, types.CallbackQuery):
        try: await event.message.edit_text(txt, reply_markup=admin_referrals_settings_keyboard())
        except Exception: await event.message.answer(txt, reply_markup=admin_referrals_settings_keyboard())
    else:
        await event.answer(txt, reply_markup=admin_referrals_settings_keyboard())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_edit_referral_bonus")
async def a_ref_bonus_start(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer()
    cur = get_setting("referral_bonus_percent", 5.0)
    await cb.message.edit_text(f"Текущий бонус: {cur}%\nВведите новый %:")
    await state.set_state(AdminReferralSettingsStates.waiting_for_bonus_percent)

@dp.message(AdminReferralSettingsStates.waiting_for_bonus_percent, F.text)
async def a_ref_bonus_save(message: types.Message, state: FSMContext):
    try:
        v = float(message.text)
        if not 0 <= v <= 100: raise ValueError
    except ValueError:
        await message.answer("❌ 0–100"); return
    s = load_settings(); s["referral_bonus_percent"] = v; save_settings(s)
    await message.answer(f"{pe('check')} Бонус: {v}%", reply_markup=get_admin_reply_keyboard())
    await state.clear()

@dp.message(F.from_user.id == ADMIN_ID, F.text == "📊 Аналитика")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_dashboard")
async def a_analytics(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
        try: await event.message.edit_text("📊 <b>Аналитика</b>", reply_markup=admin_analytics_keyboard())
        except Exception: await event.message.answer("📊 <b>Аналитика</b>", reply_markup=admin_analytics_keyboard())
    else:
        await event.answer("📊 <b>Аналитика</b>", reply_markup=admin_analytics_keyboard())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_by_days")
async def a_an_days(cb: types.CallbackQuery):
    await cb.answer()
    orders = load_orders(); now = datetime.now()
    days = {}
    for i in range(30):
        d = (now - timedelta(days=i)).strftime("%d.%m")
        days[d] = {"r": 0, "o": 0}
    for o in orders.values():
        if o["status"] == "completed" and o.get("completed_at"):
            try:
                dt = datetime.fromisoformat(o["completed_at"])
                if (now - dt).days < 30 and not isinstance(o.get("total", 0), str):
                    k = dt.strftime("%d.%m")
                    if k in days:
                        days[k]["r"] += o["total"]; days[k]["o"] += 1
            except Exception: pass
    txt = "📊 <b>По дням (30)</b>\n"
    for k in reversed(list(days.keys())):
        if days[k]["o"]:
            txt += f"📅 {k}: {days[k]['r']:.0f} ₴ ({days[k]['o']})\n"
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Назад", callback_data="admin_analytics_dashboard", style="danger")
    try: await cb.message.edit_text(txt, reply_markup=kb.as_markup())
    except Exception: await cb.message.answer(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_by_hours")
async def a_an_hours(cb: types.CallbackQuery):
    await cb.answer()
    orders = load_orders(); hours = {h: {"r": 0, "o": 0} for h in range(24)}
    for o in orders.values():
        if o["status"] == "completed" and o.get("completed_at"):
            try:
                dt = datetime.fromisoformat(o["completed_at"])
                if not isinstance(o.get("total", 0), str):
                    hours[dt.hour]["r"] += o["total"]; hours[dt.hour]["o"] += 1
            except Exception: pass
    txt = "⏰ <b>По часам</b>\n"
    for h in range(24):
        if hours[h]["o"]:
            txt += f"{h:02d}:00 — {hours[h]['r']:.0f} ₴ ({hours[h]['o']})\n"
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Назад", callback_data="admin_analytics_dashboard", style="danger")
    try: await cb.message.edit_text(txt, reply_markup=kb.as_markup())
    except Exception: await cb.message.answer(txt, reply_markup=kb.as_markup())

@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_analytics_by_country")
async def a_an_country(cb: types.CallbackQuery):
    await cb.answer()
    orders = load_orders(); stats = {}
    for o in orders.values():
        if o["status"] == "completed":
            p = o["product"]; country = "—"
            for flag in ["🇲🇲","🇺🇸","🇨🇴","🇧🇩","🇫🇷","🇧🇷","🇺🇿","🇹🇭","🇬🇧","🇺🇦","🇧🇾","🇰🇿","🇵🇱","🇷🇺","🇩🇪","🇨🇦","🇭🇺","🇬🇱"]:
                if p.startswith(flag):
                    parts = p.split()
                    if len(parts) > 1: country = parts[1]
                    break
            stats.setdefault(country, {"r": 0, "o": 0})
            if not isinstance(o.get("total", 0), str):
                stats[country]["r"] += o["total"]
            stats[country]["o"] += 1
    txt = "🌍 <b>По странам</b>\n"
    for c, s in sorted(stats.items(), key=lambda x: x[1]["r"], reverse=True):
        txt += f"• {c}: {s['r']:.0f} ₴ ({s['o']})\n"
    kb = InlineKeyboardBuilder()
    ibtn(kb, "Назад", callback_data="admin_analytics_dashboard", style="danger")
    try: await cb.message.edit_text(txt, reply_markup=kb.as_markup())
    except Exception: await cb.message.answer(txt, reply_markup=kb.as_markup())

@dp.message(F.from_user.id == ADMIN_ID, F.text == "🔗 Источники")
@dp.callback_query(F.from_user.id == ADMIN_ID, F.data == "admin_traffic_dashboard")
async def a_traffic(event):
    if isinstance(event, types.CallbackQuery):
        await event.answer()
    src = load_traffic_sources()
    if not src:
        txt = "🔗 <b>Источники</b>\n<i>Нет данных. Используйте /start reddit</i>"
    else:
        txt = "🔗 <b>Источники</b>\n"
        for name, d in sorted(src.items(), key=lambda x: x[1].get("total_revenue", 0), reverse=True):
            v = d.get("total_visits", 0); p = d.get("total_purchases", 0)
            rev = d.get("total_revenue", 0)
            conv = p / v * 100 if v else 0
            txt += f"<b>{name}</b>: {v} 👁, {p} 🛒, {rev:.0f} ₴, конв. {conv:.1f}%\n"
    if isinstance(event, types.CallbackQuery):
        try: await event.message.edit_text(txt, reply_markup=admin_traffic_keyboard())
        except Exception: await event.message.answer(txt, reply_markup=admin_traffic_keyboard())
    else:
        await event.answer(txt, reply_markup=admin_traffic_keyboard())

@dp.message(F.from_user.id == ADMIN_ID, F.text == "🔥 Акции")
async def a_promotions(message: types.Message):
    try: await message.answer("🔥 <b>Акции</b>", reply_markup=admin_promotions_keyboard())
    except Exception: pass

@dp.message(F.from_user.id == ADMIN_ID, F.text == "📢 Рассылки")
async def a_broadcasts_dash(message: types.Message):
    txt = "📢 <b>Авторассылки</b>\n"
    bcs = load_broadcasts()
    if not bcs: txt += "<i>Нет настроенных</i>"
    else:
        for bc_id, bc in bcs.items():
            st = "🟢" if bc.get("is_active", True) else "🔴"
            txt += f"{st} {bc.get('days_inactive', '?')} дней\n"
    await message.answer(txt, reply_markup=admin_broadcasts_keyboard())

@dp.message(F.from_user.id == ADMIN_ID, F.text == "⭐ Уровни")
async def a_levels_msg(message: types.Message):
    cfg = {
        "Бронза": ("🥉", get_setting("level_bronze_min", 0), get_setting("level_bronze_discount", 0)),
        "Серебро": ("🥈", get_setting("level_silver_min", 500), get_setting("level_silver_discount", 3)),
        "Золото": ("🥇", get_setting("level_gold_min", 1500), get_setting("level_gold_discount", 5)),
        "Платина": ("💎", get_setting("level_platinum_min", 3000), get_setting("level_platinum_discount", 7)),
        "VIP": ("👑", get_setting("level_vip_min", 5000), get_setting("level_vip_discount", 10)),
    }
    txt = f"{pe('star')} <b>Уровни</b>\n"
    for name, (e, mn, disc) in cfg.items():
        txt += f"{e} <b>{name}</b> — {mn} ₴ / {disc}%\n"
    await message.answer(txt, reply_markup=admin_levels_keyboard())

@dp.message(F.from_user.id == ADMIN_ID, F.text == "🏠 Клиентское меню")
async def a_client_menu(message: types.Message):
    await message.answer("Клиентское меню:", reply_markup=get_main_reply_keyboard())

# ==================== ФОНОВЫЕ ЗАДАЧИ ====================
async def auto_broadcast_scheduler():
    while True:
        try:
            bcs = load_broadcasts()
            users = load_users()
            orders = load_orders()
            now = datetime.now()
            for bc_id, bc in bcs.items():
                if not bc.get("is_active", True): continue
                days_in = bc.get("days_inactive")
                if not days_in: continue
                for uid_str, ud in users.items():
                    uid = int(uid_str)
                    user_orders = [o for o in orders.values() if o["user_id"] == uid and o["status"] == "completed"]
                    if not user_orders: continue
                    last = max(user_orders, key=lambda x: x.get("completed_at", x.get("created_at", "")))
                    try:
                        last_dt = datetime.fromisoformat(last.get("completed_at", last["created_at"]))
                    except Exception:
                        continue
                    if (now - last_dt).days == days_in:
                        sent_key = f"sent_bc_{bc_id}"
                        if ud.get(sent_key): continue
                        try:
                            kb = None
                            if bc.get("button_text") and bc.get("button_url"):
                                kb_b = InlineKeyboardBuilder()
                                kb_b.button(text=bc["button_text"], url=bc["button_url"])
                                kb = kb_b.as_markup()
                            await bot.send_message(uid, bc["message_text"], reply_markup=kb)
                            users[uid_str][sent_key] = now.isoformat()
                            save_users(users)
                            await asyncio.sleep(0.1)
                        except Exception as e:
                            logger.error(f"bc: {e}")
        except Exception as e:
            logger.error(f"sched: {e}")
        await asyncio.sleep(3600)

# ==================== ЗАПУСК ====================
async def main():
    print("=" * 50)
    print("OverPass Store Bot")
    print("Premium emoji in text + icon_custom_emoji_id in buttons")
    print("=" * 50)
    await bot.delete_webhook(drop_pending_updates=True)
    await asyncio.sleep(1)
    print("Bot started!")
    print("=" * 50)
    asyncio.create_task(auto_broadcast_scheduler())
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped by user")
    except Exception as e:
        print(f"Start error: {e}")
        sys.exit(1)
