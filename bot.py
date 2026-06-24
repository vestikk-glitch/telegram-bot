import os
import requests
import json
import time
import re
import asyncio
import threading
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# ═══════════════════════════════════════
#  НАСТРОЙКИ
# ═══════════════════════════════════════
TOKEN = "8721365430:AAHL7Wp4btODeQKoYNafPWoomt5erBGYnZM"
SERVER_URL = "https://key-server-4jkz.onrender.com"
PASSWORD = "1337"

ADMINS = [1745668867]
RESELLERS = []  # Добавляются через бота

DEFAULT_COOLDOWN = 1800  # 30 минут
reseller_cooldowns = {}
reseller_last_gen = {}

BANNED = []
LOGS = []
online_users = {}
user_last_key = {}
users_db = {}

start_time = time.time()

# ═══════════════════════════════════════
#  СТАТИСТИКА КЛЮЧЕЙ
# ═══════════════════════════════════════
key_stats = {}  # {key: {"user_id": 123, "username": "name", "activated": "2026-06-24", "expiry": "..."}}
active_sessions = {}  # {user_id: {"key": "TOOL-XXX", "started": 1234567890}}
STATS_FILE = "stats.json"

# ═══════════════════════════════════════
#  ПРОВЕРКА ПРАВ
# ═══════════════════════════════════════
def is_admin(user_id):
    return user_id in ADMINS

def is_reseller(user_id):
    return user_id in RESELLERS

def is_banned(user_id):
    return user_id in BANNED

def has_access(user_id):
    return is_admin(user_id) or is_reseller(user_id)

def log_action(text):
    timestamp = datetime.now().strftime("%d.%m %H:%M")
    LOGS.append(f"[{timestamp}] {text}")
    if len(LOGS) > 200:
        LOGS.pop(0)

def get_reseller_cooldown(user_id):
    return reseller_cooldowns.get(user_id, DEFAULT_COOLDOWN)

# ═══════════════════════════════════════
#  СОХРАНЕНИЕ СТАТИСТИКИ
# ═══════════════════════════════════════
def save_stats():
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "key_stats": key_stats,
                "active_sessions": active_sessions,
                "user_last_key": user_last_key,
                "users_db": users_db
            }, f, indent=4, ensure_ascii=False)
    except:
        pass

def load_stats():
    global key_stats, active_sessions, user_last_key, users_db
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            key_stats.update(data.get("key_stats", {}))
            active_sessions.update(data.get("active_sessions", {}))
            user_last_key.update(data.get("user_last_key", {}))
            users_db.update(data.get("users_db", {}))
    except:
        pass

# ═══════════════════════════════════════
#  ОТСЛЕЖИВАНИЕ АКТИВАЦИИ
# ═══════════════════════════════════════
def track_key_activation(user_id, username, key, expiry):
    key_stats[key] = {
        "user_id": user_id,
        "username": username or f"ID{user_id}",
        "activated": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "expiry": expiry
    }
    active_sessions[user_id] = {
        "key": key,
        "started": time.time()
    }
    log_action(f"🔑 Ключ {key} активирован пользователем {username} ({user_id})")
    save_stats()

# ═══════════════════════════════════════
#  ПИНГ ДЛЯ RENDER (ЧТОБЫ НЕ ЗАСЫПАЛ)
# ═══════════════════════════════════════
def ping_self():
    url = "https://telegram-bot-4exc.onrender.com"
    while True:
        try:
            response = requests.get(url, timeout=10)
            print(f"✅ Пинг успешен! Статус: {response.status_code}")
        except Exception as e:
            print(f"❌ Ошибка пинга: {e}")
        time.sleep(600)

threading.Thread(target=ping_self, daemon=True).start()
# ═══════════════════════════════════════
#  КОМАНДА /start
# ═══════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID{user_id}"
    
    online_users[user_id] = time.time()
    
    if user_id not in users_db:
        users_db[user_id] = {"username": username, "first_seen": time.time(), "last_active": time.time()}
    else:
        users_db[user_id]["username"] = username
        users_db[user_id]["last_active"] = time.time()
    
    if is_banned(user_id):
        await update.message.reply_text("🚫 Вы заблокированы!")
        return
    
    if is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("🔑 Сгенерировать ключ", callback_data="generate")],
            [InlineKeyboardButton("✏️ Кастомный ключ (админ)", callback_data="admin_custom_key")],
            [InlineKeyboardButton("📋 Список ключей", callback_data="list")],
            [InlineKeyboardButton("🗑️ Удалить ключ", callback_data="delete")],
            [InlineKeyboardButton("🗑️ Удалить все ключи", callback_data="delete_all")],
            [InlineKeyboardButton("🔄 Сбросить ключ", callback_data="reset")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("📈 Аналитика ключей", callback_data="key_analytics")],
            [InlineKeyboardButton("🏆 Топ пользователей", callback_data="top_users")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="users_list")],
            [InlineKeyboardButton("🔍 Поиск пользователя", callback_data="find_user")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="broadcast")],
            [InlineKeyboardButton("📝 Логи", callback_data="logs")],
            [InlineKeyboardButton("🚫 Бан-лист", callback_data="ban_menu")],
            [InlineKeyboardButton("👥 Мои реселлеры", callback_data="my_resellers")],
            [InlineKeyboardButton("➕ Добавить реселлера", callback_data="add_reseller")],
            [InlineKeyboardButton("➖ Удалить реселлера", callback_data="remove_reseller")],
            [InlineKeyboardButton("⚙️ Настройка задержки", callback_data="cooldown_settings")],
            [InlineKeyboardButton("💾 Бэкап ключей", callback_data="backup_keys")],
            [InlineKeyboardButton("📊 Статус сервера", callback_data="server_status")],
            [InlineKeyboardButton("📊 Активации ключей", callback_data="key_stats_admin")],
            [InlineKeyboardButton("ℹ️ Инфо о ключе", callback_data="info_key")],
            [InlineKeyboardButton("📤 Отправить ключ", callback_data="send_key")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🤖 Добро пожаловать, АДМИН!\n\nВыберите действие:", reply_markup=reply_markup)
        log_action(f"Админ {user_id} открыл меню")
        return
    
    if is_reseller(user_id):
        cooldown = get_reseller_cooldown(user_id)
        cooldown_min = cooldown // 60
        keyboard = [
            [InlineKeyboardButton("🔑 Сгенерировать ключ", callback_data="generate")],
            [InlineKeyboardButton("✏️ Создать кастомный ключ", callback_data="custom_key")],
            [InlineKeyboardButton("📋 Мои ключи", callback_data="my_keys")],
            [InlineKeyboardButton("⏳ Время до генерации", callback_data="my_cooldown")],
            [InlineKeyboardButton("📊 Статистика ключей", callback_data="reseller_stats")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🤖 Добро пожаловать, Реселлер!\n\n"
            f"✅ Генерировать ключи (до 30 дней, задержка {cooldown_min} мин)\n"
            f"✅ Создавать кастомные ключи (до 67 дней, задержка {cooldown_min} мин)\n"
            f"✅ Смотреть свои ключи\n"
            f"✅ Проверять время до следующей генерации",
            reply_markup=reply_markup
        )
        return
    
    # ОБЫЧНЫЙ ПОЛЬЗОВАТЕЛЬ
    last_key_time = user_last_key.get(user_id, 0)
    now = time.time()
    can_get_key = (now - last_key_time) >= 86400
    
    if not can_get_key:
        remaining = int(86400 - (now - last_key_time))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await update.message.reply_text(
            f"⏳ Ты уже получал ключ сегодня!\n\nСледующий ключ через {hours}ч {minutes}м."
        )
        return
    
    keyboard = [[InlineKeyboardButton("✅ Продолжить", callback_data="get_free_key")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"👋 Добро пожаловать, {username}!\n\n"
        "📢 Скрипт в Telegram: @MultiToolRubg\n\n"
        "Хочешь получить ключ на 2 часа?\nНажми 'Продолжить'.",
        reply_markup=reply_markup
    )
# ═══════════════════════════════════════
#  ПОЛУЧИТЬ БЕСПЛАТНЫЙ КЛЮЧ
# ═══════════════════════════════════════
async def get_free_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    last_key_time = user_last_key.get(user_id, 0)
    now = time.time()
    can_get_key = (now - last_key_time) >= 86400
    
    if not can_get_key:
        remaining = int(86400 - (now - last_key_time))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await query.edit_message_text(f"⏳ Подожди {hours}ч {minutes}м!")
        return
    
    try:
        response = requests.get(f"{SERVER_URL}/generate", params={"days": 0.0833, "password": PASSWORD})
        data = response.json()
        if "key" in data:
            key = data['key']
            user_last_key[user_id] = now
            username = query.from_user.username or f"ID{user_id}"
            track_key_activation(user_id, username, key, data['expiry'])
            await query.edit_message_text(
                f"🎉 Держи!\n\n🔑 Ключ: <code>{key}</code>\n⏳ Активен: 2 часа\n📅 Истекает: {data['expiry']}\n\n❤️ Приятной игры!",
                parse_mode="HTML"
            )
            log_action(f"Пользователь {user_id} получил бесплатный ключ {key} на 2 часа")
        else:
            await query.edit_message_text(f"❌ Ошибка: {data.get('error', 'Unknown error')}")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ═══════════════════════════════════════
#  ГЕНЕРАЦИЯ КЛЮЧЕЙ (С ЗАДЕРЖКОЙ)
# ═══════════════════════════════════════
async def generate_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if is_banned(user_id):
        await query.edit_message_text("🚫 Вы заблокированы!")
        return
    if not has_access(user_id):
        await query.edit_message_text("❌ Недостаточно прав!")
        return
    
    is_res = is_reseller(user_id)
    if is_res:
        keyboard = [
            [InlineKeyboardButton("🕐 1 час", callback_data="gen_0.0417")],
            [InlineKeyboardButton("🕒 3 часа", callback_data="gen_0.125")],
            [InlineKeyboardButton("🕕 6 часов", callback_data="gen_0.25")],
            [InlineKeyboardButton("📅 1 день", callback_data="gen_1")],
            [InlineKeyboardButton("📅 3 дня", callback_data="gen_3")],
            [InlineKeyboardButton("📅 7 дней", callback_data="gen_7")],
            [InlineKeyboardButton("📅 30 дней", callback_data="gen_30")],
            [InlineKeyboardButton("✏️ Кастомный", callback_data="custom_key")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")],
        ]
        title = f"📅 Реселлер (до 30 дней, задержка {get_reseller_cooldown(user_id)//60} мин):"
    else:
        keyboard = [
            [InlineKeyboardButton("🕐 1 час", callback_data="gen_0.0417")],
            [InlineKeyboardButton("🕒 3 часа", callback_data="gen_0.125")],
            [InlineKeyboardButton("🕕 6 часов", callback_data="gen_0.25")],
            [InlineKeyboardButton("🕛 12 часов", callback_data="gen_0.5")],
            [InlineKeyboardButton("📅 1 день", callback_data="gen_1")],
            [InlineKeyboardButton("📅 3 дня", callback_data="gen_3")],
            [InlineKeyboardButton("📅 7 дней", callback_data="gen_7")],
            [InlineKeyboardButton("📅 30 дней", callback_data="gen_30")],
            [InlineKeyboardButton("📅 90 дней", callback_data="gen_90")],
            [InlineKeyboardButton("📅 365 дней", callback_data="gen_365")],
            [InlineKeyboardButton("✏️ Кастомный", callback_data="custom_key")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")],
        ]
        title = "📅 Админ:"
    await query.edit_message_text(title, reply_markup=InlineKeyboardMarkup(keyboard))

async def generate_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if is_banned(user_id):
        await query.edit_message_text("🚫 Вы заблокированы!")
        return
    if not has_access(user_id):
        await query.edit_message_text("❌ Недостаточно прав!")
        return
    
    days = float(query.data.split("_")[1])
    is_res = is_reseller(user_id)
    
    if is_res:
        cooldown = get_reseller_cooldown(user_id)
        last_time = reseller_last_gen.get(user_id, 0)
        now = time.time()
        if now - last_time < cooldown:
            remaining = int(cooldown - (now - last_time))
            minutes = remaining // 60
            seconds = remaining % 60
            await query.edit_message_text(f"⏳ Подождите {minutes}м {seconds}с перед следующим ключом!")
            return
        reseller_last_gen[user_id] = now
    
    if is_res and days > 30:
        await query.edit_message_text("❌ Реселлер до 30 дней!")
        return
    
    if days < 1:
        hours = int(days * 24)
        time_str = f"{hours} час" + ("а" if hours > 1 and hours < 5 else "ов" if hours > 4 else "")
    else:
        days_int = int(days)
        time_str = "1 день" if days_int == 1 else f"{days_int} дня" if days_int <= 4 else f"{days_int} дней"
    
    await query.edit_message_text(f"⏳ Генерация на {time_str}...")
    
    try:
        response = requests.get(f"{SERVER_URL}/generate", params={"days": days, "password": PASSWORD})
        data = response.json()
        if "key" in data:
            message = f"✅ Ключ создан!\n\n🔑 <code>{data['key']}</code>\n📅 Срок: {time_str}\n⏳ Истекает: {data['expiry']}\n\n❤️ Приятной игры!"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            await query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
            log_action(f"Пользователь {user_id} создал ключ {data['key']} на {time_str}")
        else:
            await query.edit_message_text(f"❌ Ошибка: {data.get('error', 'Unknown error')}")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")
# ═══════════════════════════════════════
#  КАСТОМНЫЙ КЛЮЧ (АДМИН)
# ═══════════════════════════════════════
async def admin_custom_key_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    context.user_data['state'] = 'awaiting_admin_custom_key'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text("✏️ Введите кастомный ключ (буквы, цифры, пробелы → _):\n\nПример: <code>MYSUPERKEY</code>", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_admin_custom_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    custom_key = re.sub(r'[^a-zA-Z0-9_]', '', update.message.text.strip().replace(' ', '_'))
    if not custom_key or len(custom_key) < 3:
        await update.message.reply_text("❌ Минимум 3 символа!")
        return
    context.user_data['admin_custom_key_name'] = custom_key
    context.user_data['state'] = 'awaiting_admin_custom_days'
    keyboard = [
        [InlineKeyboardButton("1 день", callback_data="admin_days_1")],
        [InlineKeyboardButton("3 дня", callback_data="admin_days_3")],
        [InlineKeyboardButton("7 дней", callback_data="admin_days_7")],
        [InlineKeyboardButton("30 дней", callback_data="admin_days_30")],
        [InlineKeyboardButton("90 дней", callback_data="admin_days_90")],
        [InlineKeyboardButton("365 дней", callback_data="admin_days_365")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"✅ Ключ: <code>{custom_key}</code>\n📅 Выберите срок:", parse_mode="HTML", reply_markup=reply_markup)

async def admin_days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Только для админа!")
        return
    days = int(query.data.split("_")[2])
    custom_key = context.user_data.get('admin_custom_key_name', '')
    context.user_data['state'] = ''
    try:
        check = requests.get(f"{SERVER_URL}/check?key={custom_key}")
        if check.json().get('valid', False):
            await query.edit_message_text("❌ Такой ключ уже существует!")
            return
        response = requests.get(f"{SERVER_URL}/addkey", params={"key": custom_key, "days": days, "password": PASSWORD})
        data = response.json()
        if "message" in data:
            time_str = "1 день" if days == 1 else f"{days} дня" if days <= 4 else f"{days} дней"
            message = f"✅ Кастомный ключ создан!\n\n🔑 <code>{custom_key}</code>\n📅 Срок: {time_str}\n❤️ Приятной игры!"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            await query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
            log_action(f"Админ {user_id} создал кастомный ключ {custom_key} на {days} дней")
        else:
            await query.edit_message_text(f"❌ Ошибка: {data.get('error', 'Unknown error')}")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ═══════════════════════════════════════
#  КАСТОМНЫЙ КЛЮЧ (РЕСЕЛЛЕР)
# ═══════════════════════════════════════
async def custom_key_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if is_banned(user_id):
        await query.edit_message_text("🚫 Вы заблокированы!")
        return
    if not is_reseller(user_id):
        await query.edit_message_text("❌ Только для реселлеров!")
        return
    context.user_data['state'] = 'awaiting_custom_key'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text("✏️ Введите кастомный ключ (буквы, цифры, пробелы → _):", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_custom_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_reseller(user_id) or is_banned(user_id):
        await update.message.reply_text("❌ Недостаточно прав!")
        context.user_data['state'] = ''
        return
    custom_key = re.sub(r'[^a-zA-Z0-9_]', '', update.message.text.strip().replace(' ', '_'))
    if not custom_key or len(custom_key) < 3:
        await update.message.reply_text("❌ Минимум 3 символа!")
        return
    context.user_data['custom_key_name'] = custom_key
    context.user_data['state'] = 'awaiting_custom_days'
    keyboard = [
        [InlineKeyboardButton("1 день", callback_data="reseller_days_1")],
        [InlineKeyboardButton("3 дня", callback_data="reseller_days_3")],
        [InlineKeyboardButton("7 дней", callback_data="reseller_days_7")],
        [InlineKeyboardButton("30 дней", callback_data="reseller_days_30")],
        [InlineKeyboardButton("67 дней", callback_data="reseller_days_67")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"✅ Ключ: <code>{custom_key}</code>\n📅 Выберите срок (макс. 67 дней):", parse_mode="HTML", reply_markup=reply_markup)

async def reseller_days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_reseller(user_id):
        await query.edit_message_text("❌ Только для реселлеров!")
        return
    
    cooldown = get_reseller_cooldown(user_id)
    last_time = reseller_last_gen.get(user_id, 0)
    now = time.time()
    if now - last_time < cooldown:
        remaining = int(cooldown - (now - last_time))
        minutes = remaining // 60
        seconds = remaining % 60
        await query.edit_message_text(f"⏳ Подождите {minutes}м {seconds}с перед следующим кастомным ключом!")
        return
    
    days = int(query.data.split("_")[2])
    custom_key = context.user_data.get('custom_key_name', '')
    context.user_data['state'] = ''
    try:
        check = requests.get(f"{SERVER_URL}/check?key={custom_key}")
        if check.json().get('valid', False):
            await query.edit_message_text("❌ Такой ключ уже существует!")
            return
        response = requests.get(f"{SERVER_URL}/addkey", params={"key": custom_key, "days": days, "password": PASSWORD})
        data = response.json()
        if "message" in data:
            reseller_last_gen[user_id] = now
            time_str = "1 день" if days == 1 else f"{days} дня" if days <= 4 else f"{days} дней"
            message = f"✅ Кастомный ключ создан!\n\n🔑 <code>{custom_key}</code>\n📅 Срок: {time_str}\n❤️ Приятной игры!"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            await query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
            log_action(f"Реселлер {user_id} создал кастомный ключ {custom_key} на {days} дней")
        else:
            await query.edit_message_text(f"❌ Ошибка: {data.get('error', 'Unknown error')}")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")
# ═══════════════════════════════════════
#  МОИ КЛЮЧИ (РЕСЕЛЛЕР)
# ═══════════════════════════════════════
async def my_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not is_reseller(user_id):
        await query.edit_message_text("❌ Только для реселлеров!")
        return
    
    try:
        response = requests.get(f"{SERVER_URL}/list")
        data = response.json()
        
        if not data:
            await query.edit_message_text("📭 Нет ключей в базе.")
            return
        
        message = f"📋 <b>Твои ключи:</b>\n\n"
        count = 0
        for item in data[:20]:
            status = "✅" if item.get("active", False) else "❌"
            message += f"{status} <code>{item['key']}</code>\n"
            message += f"   📅 Истекает: {item['expiry']}\n\n"
            count += 1
        
        if len(data) > 20:
            message += f"... и ещё {len(data) - 20} ключей"
        
        if count == 0:
            await query.edit_message_text("📭 Ты ещё не создал ни одного ключа.")
            return
        
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        log_action(f"Реселлер {user_id} посмотрел свои ключи")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ═══════════════════════════════════════
#  ВРЕМЯ ДО ГЕНЕРАЦИИ (РЕСЕЛЛЕР)
# ═══════════════════════════════════════
async def my_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if not is_reseller(user_id):
        await query.edit_message_text("❌ Только для реселлеров!")
        return
    
    cooldown = get_reseller_cooldown(user_id)
    last_time = reseller_last_gen.get(user_id, 0)
    now = time.time()
    
    if last_time == 0:
        await query.edit_message_text("✅ Ты ещё не создавал ключи! Можешь генерировать в любое время.")
        return
    
    elapsed = now - last_time
    if elapsed >= cooldown:
        await query.edit_message_text("✅ Время ожидания прошло! Можешь генерировать новый ключ.")
        return
    
    remaining = int(cooldown - elapsed)
    minutes = remaining // 60
    seconds = remaining % 60
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text(
        f"⏳ <b>Время до следующей генерации</b>\n\n"
        f"🕐 Осталось: <b>{minutes}м {seconds}с</b>\n"
        f"📌 Задержка: {cooldown//60} минут",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    log_action(f"Реселлер {user_id} проверил время до генерации")

# ═══════════════════════════════════════
#  НАСТРОЙКА ЗАДЕРЖКИ (АДМИН)
# ═══════════════════════════════════════
async def cooldown_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    
    context.user_data['state'] = 'awaiting_cooldown_id'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text(
        "✏️ Введите ID реселлера для настройки задержки:\n\n"
        "Пример: <code>8025773144</code>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_cooldown_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    
    try:
        target_id = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Введите корректный ID (только цифры)!")
        return
    
    context.user_data['cooldown_target'] = target_id
    context.user_data['state'] = ''
    
    if target_id not in RESELLERS:
        keyboard = [[InlineKeyboardButton("➕ Добавить реселлера", callback_data="add_reseller")]]
        await update.message.reply_text(
            f"⚠️ Пользователь <code>{target_id}</code> не является реселлером!\n\n"
            f"Сначала добавьте его как реселлера.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    current = get_reseller_cooldown(target_id)
    current_min = current // 60
    status = "Нет задержки" if current == 0 else f"{current_min} минут"
    
    keyboard = [
        [InlineKeyboardButton("🔇 Выключить задержку", callback_data="cd_value_0")],
        [InlineKeyboardButton("⏱️ 10 минут", callback_data="cd_value_600")],
        [InlineKeyboardButton("⏱️ 30 минут", callback_data="cd_value_1800")],
        [InlineKeyboardButton("⏱️ 1 час", callback_data="cd_value_3600")],
        [InlineKeyboardButton("🔙 Назад", callback_data="cooldown_settings")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    username = users_db.get(target_id, {}).get("username", f"ID{target_id}")
    await update.message.reply_text(
        f"⚙️ <b>Настройка задержки для {username}</b>\n\n"
        f"Текущая задержка: <b>{status}</b>\n\n"
        f"Выберите новое значение:",
        parse_mode="HTML",
        reply_markup=reply_markup
    )

async def cooldown_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    
    target_id = context.user_data.get('cooldown_target')
    if not target_id:
        await query.edit_message_text("❌ Ошибка: сначала введите ID реселлера!")
        return
    
    value = int(query.data.split("_")[2])
    reseller_cooldowns[target_id] = value
    
    try:
        if value == 0:
            text = "✅ Теперь у тебя НЕТ ЗАДЕРЖКИ на генерацию ключей!"
        else:
            text = f"✅ Теперь у тебя задержка на ключи: {value//60} минут!"
        await context.bot.send_message(chat_id=target_id, text=text)
    except:
        pass
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="cooldown_settings")]]
    await query.edit_message_text(
        f"✅ Задержка для пользователя {target_id} установлена!\n\n"
        f"⏱️ Новое значение: {'Нет задержки' if value == 0 else f'{value//60} минут'}\n"
        f"📩 Реселлеру отправлено уведомление.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    log_action(f"Админ {query.from_user.id} установил задержку {value} для {target_id}")
# ═══════════════════════════════════════
#  УПРАВЛЕНИЕ РЕСЕЛЛЕРАМИ
# ═══════════════════════════════════════
async def add_reseller_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    context.user_data['state'] = 'awaiting_reseller_id'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text("✏️ Введите ID пользователя для добавления в реселлеры:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_add_reseller(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    try:
        target_id = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Введите корректный ID!")
        return
    context.user_data['state'] = ''
    if target_id in RESELLERS:
        await update.message.reply_text(f"⚠️ {target_id} уже реселлер!")
        return
    if target_id in ADMINS:
        await update.message.reply_text(f"⚠️ {target_id} является админом!")
        return
    RESELLERS.append(target_id)
    log_action(f"Админ {user_id} добавил реселлера {target_id}")
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await update.message.reply_text(f"✅ Пользователь <code>{target_id}</code> добавлен в реселлеры!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    try:
        await context.bot.send_message(chat_id=target_id, text="🎉 Теперь ты реселлер!\n\n✅ Генерируй ключи (до 30 дней)\n✅ Создавай кастомные ключи\nНапиши /start")
    except:
        pass

async def my_resellers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    if not RESELLERS:
        await query.edit_message_text("📭 У вас нет реселлеров.")
        return
    message = "👥 <b>Мои реселлеры:</b>\n\n"
    for uid in RESELLERS:
        username = users_db.get(uid, {}).get("username", f"ID{uid}")
        cooldown = get_reseller_cooldown(uid)
        cooldown_str = "Нет" if cooldown == 0 else f"{cooldown//60} мин"
        message += f"• {username} (<code>{uid}</code>)\n  ⏱️ Задержка: {cooldown_str}\n\n"
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def remove_reseller_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    if not RESELLERS:
        await query.edit_message_text("📭 Нет реселлеров для удаления.")
        return
    keyboard = []
    for uid in RESELLERS:
        username = users_db.get(uid, {}).get("username", f"ID{uid}")
        keyboard.append([InlineKeyboardButton(f"❌ {username} ({uid})", callback_data=f"remove_res_{uid}")])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back")])
    await query.edit_message_text("🗑️ Выберите реселлера для удаления:", reply_markup=InlineKeyboardMarkup(keyboard))

async def remove_reseller_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Только для админа!")
        return
    target_id = int(query.data.split("_")[2])
    if target_id not in RESELLERS:
        await query.edit_message_text("❌ Этот пользователь уже не реселлер!")
        return
    RESELLERS.remove(target_id)
    if target_id in reseller_cooldowns:
        del reseller_cooldowns[target_id]
    if target_id in reseller_last_gen:
        del reseller_last_gen[target_id]
    log_action(f"Админ {user_id} удалил реселлера {target_id}")
    try:
        await context.bot.send_message(chat_id=target_id, text="❌ Вы исключены из реселлеров!\n\nВы больше не можете генерировать ключи.\nПо вопросам обращайтесь к @gde_sloppy")
    except:
        pass
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text(f"✅ Реселлер <code>{target_id}</code> успешно удалён!\n\n📩 Ему отправлено уведомление.", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))	
# ═══════════════════════════════════════
#  СПИСОК, УДАЛЕНИЕ, СБРОС, ИНФО, ОТПРАВКА
# ═══════════════════════════════════════
async def list_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    try:
        response = requests.get(f"{SERVER_URL}/list")
        data = response.json()
        if not data:
            await query.edit_message_text("📭 Нет ключей в базе.")
            return
        message = "📋 <b>ВСЕ КЛЮЧИ</b>\n\n"
        for i, item in enumerate(data[:30], 1):
            status = "✅" if item.get("active", False) else "❌"
            message += f"{i}. {status} <code>{item['key']}</code>\n"
            message += f"   📅 Истекает: {item['expiry']}\n\n"
        if len(data) > 30:
            message += f"... и ещё {len(data) - 30} ключей"
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        log_action(f"Админ {query.from_user.id} посмотрел все ключи")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def delete_key_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    context.user_data['state'] = 'awaiting_delete_key'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text("✏️ Введите ключ для удаления:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_delete_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    key = update.message.text.strip()
    context.user_data['state'] = ''
    try:
        response = requests.get(f"{SERVER_URL}/deletekey", params={"key": key, "password": PASSWORD})
        data = response.json()
        if data.get("message"):
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            await update.message.reply_text(f"✅ Ключ <code>{key}</code> удалён!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
            log_action(f"Админ {user_id} удалил ключ {key}")
        else:
            await update.message.reply_text(f"❌ Ошибка: {data.get('error', 'Не найден')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def delete_all_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    keyboard = [
        [InlineKeyboardButton("✅ ДА, УДАЛИТЬ ВСЕ", callback_data="confirm_delete_all")],
        [InlineKeyboardButton("❌ ОТМЕНА", callback_data="back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "⚠️ <b>ВНИМАНИЕ!</b>\n\n"
        "Вы собираетесь УДАЛИТЬ ВСЕ КЛЮЧИ!\n"
        "Это действие НЕЛЬЗЯ ОТМЕНИТЬ.\n\n"
        "Вы уверены?",
        parse_mode="HTML",
        reply_markup=reply_markup
    )

async def confirm_delete_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    try:
        response = requests.get(f"{SERVER_URL}/list")
        data = response.json()
        if not data:
            await query.edit_message_text("📭 Нет ключей для удаления.")
            return
        deleted = 0
        for item in data:
            key = item["key"]
            try:
                del_resp = requests.get(f"{SERVER_URL}/deletekey", params={"key": key, "password": PASSWORD})
                if del_resp.json().get("message"):
                    deleted += 1
            except:
                pass
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🗑️ <b>УДАЛЕНО ВСЕХ КЛЮЧЕЙ: {deleted}</b>\n\n"
            f"✅ База ключей очищена!",
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        log_action(f"Админ {query.from_user.id} удалил все ключи ({deleted} шт)")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def reset_key_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    context.user_data['state'] = 'awaiting_reset_key'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text("🔄 Введите ключ для сброса (удалить и создать новый):", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_reset_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    old_key = update.message.text.strip()
    context.user_data['state'] = ''
    try:
        check = requests.get(f"{SERVER_URL}/check?key={old_key}")
        if not check.json().get('valid', False):
            await update.message.reply_text(f"❌ Ключ <code>{old_key}</code> не существует!", parse_mode="HTML")
            return
        del_resp = requests.get(f"{SERVER_URL}/deletekey", params={"key": old_key, "password": PASSWORD})
        if not del_resp.json().get("message"):
            await update.message.reply_text("❌ Ошибка при удалении!")
            return
        gen_resp = requests.get(f"{SERVER_URL}/generate", params={"days": 30, "password": PASSWORD})
        data = gen_resp.json()
        if "key" in data:
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            await update.message.reply_text(
                f"🔄 <b>Ключ сброшен!</b>\n\n"
                f"❌ Старый: <code>{old_key}</code>\n"
                f"✅ Новый: <code>{data['key']}</code>\n"
                f"📅 Срок: 30 дней\n"
                f"⏳ Истекает: {data['expiry']}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            log_action(f"Админ {user_id} сбросил ключ {old_key} → {data['key']}")
        else:
            await update.message.reply_text(f"❌ Ошибка: {data.get('error', 'Unknown error')}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def info_key_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    context.user_data['state'] = 'awaiting_info_key'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text("ℹ️ Введите ключ для проверки:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_info_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    key = update.message.text.strip()
    context.user_data['state'] = ''
    try:
        response = requests.get(f"{SERVER_URL}/check?key={key}")
        data = response.json()
        if data.get('valid', False):
            expiry = data.get('expiry', 'Неизвестно')
            message = f"ℹ️ <b>Информация о ключе</b>\n\n"
            message += f"🔑 <code>{key}</code>\n"
            message += f"✅ Статус: <b>АКТИВЕН</b>\n"
            message += f"📅 Истекает: {expiry}\n"
            if expiry != 'Неизвестно':
                expiry_date = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                remaining = expiry_date - datetime.now()
                if remaining.total_seconds() > 0:
                    days = remaining.days
                    hours = remaining.seconds // 3600
                    message += f"⏳ Осталось: {days}д {hours}ч\n"
        else:
            message = f"❌ Ключ <code>{key}</code> <b>НЕ АКТИВЕН</b>\n\n"
            message += "🔴 Возможно истек или не существует."
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        await update.message.reply_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        log_action(f"Админ {user_id} проверил ключ {key}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def send_key_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    context.user_data['state'] = 'awaiting_send_key_user'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text("📤 Введите ID пользователя для отправки ключа:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_send_key_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    try:
        target_id = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Введите корректный ID!")
        return
    context.user_data['send_target'] = target_id
    context.user_data['state'] = 'awaiting_send_key_days'
    keyboard = [
        [InlineKeyboardButton("1 день", callback_data="send_days_1")],
        [InlineKeyboardButton("3 дня", callback_data="send_days_3")],
        [InlineKeyboardButton("7 дней", callback_data="send_days_7")],
        [InlineKeyboardButton("30 дней", callback_data="send_days_30")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")],
    ]
    await update.message.reply_text(f"📤 Отправить ключ пользователю <code>{target_id}</code>\n\nВыберите срок:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))

async def send_days_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.edit_message_text("❌ Только для админа!")
        return
    days = int(query.data.split("_")[2])
    target_id = context.user_data.get('send_target')
    if not target_id:
        await query.edit_message_text("❌ Ошибка: не найден получатель!")
        return
    try:
        response = requests.get(f"{SERVER_URL}/generate", params={"days": days, "password": PASSWORD})
        data = response.json()
        if "key" in data:
            key = data['key']
            time_str = "1 день" if days == 1 else f"{days} дня" if days <= 4 else f"{days} дней"
            try:
                await context.bot.send_message(
                    chat_id=target_id,
                    text=f"🎉 <b>Вам отправлен ключ!</b>\n\n"
                         f"🔑 <code>{key}</code>\n"
                         f"📅 Срок: {time_str}\n"
                         f"⏳ Истекает: {data['expiry']}\n\n"
                         f"❤️ Приятной игры!",
                    parse_mode="HTML"
                )
                user_msg = f"✅ Ключ отправлен пользователю <code>{target_id}</code>!"
            except:
                user_msg = f"⚠️ Ключ создан, но не удалось отправить пользователю <code>{target_id}</code> (бот заблокирован?)"
            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            await query.edit_message_text(
                f"📤 <b>Результат</b>\n\n"
                f"🔑 <code>{key}</code>\n"
                f"📅 Срок: {time_str}\n"
                f"{user_msg}",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            log_action(f"Админ {user_id} отправил ключ {key} пользователю {target_id}")
        else:
            await query.edit_message_text(f"❌ Ошибка: {data.get('error', 'Unknown error')}")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")
# ═══════════════════════════════════════
#  ПОИСК, РАССЫЛКА, БАН-ЛИСТ (ЧАСТЬ 1)
# ═══════════════════════════════════════
async def find_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    context.user_data['state'] = 'awaiting_find_user'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text("🔍 Введите ID или username:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_find_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    query_text = update.message.text.strip()
    context.user_data['state'] = ''
    found = []
    for uid, data in users_db.items():
        username = data.get("username", "")
        if query_text in str(uid) or query_text.lower() in username.lower():
            found.append((uid, data))
    if not found:
        await update.message.reply_text("❌ Не найдено!")
        return
    message = f"🔍 <b>Найдено {len(found)}:</b>\n\n"
    for uid, data in found[:10]:
        first_seen = datetime.fromtimestamp(data.get("first_seen", 0)).strftime("%d.%m %H:%M")
        last_active = datetime.fromtimestamp(data.get("last_active", 0)).strftime("%d.%m %H:%M")
        message += f"• <code>{uid}</code> — {data.get('username', '')}\n  📅 Первый раз: {first_seen}\n  ⏳ Последний: {last_active}\n\n"
    if len(found) > 10:
        message += f"... и ещё {len(found) - 10} пользователей"
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await update.message.reply_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    log_action(f"Админ {user_id} искал пользователя: {query_text}")

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    context.user_data['state'] = 'awaiting_broadcast'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await query.edit_message_text("📢 Введите сообщение для рассылки:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    message_text = update.message.text
    context.user_data['state'] = ''
    msg = await update.message.reply_text("⏳ Отправка...")
    sent = 0
    failed = 0
    for uid in users_db.keys():
        try:
            await context.bot.send_message(chat_id=uid, text=f"📢 <b>Объявление</b>\n\n{message_text}", parse_mode="HTML")
            sent += 1
        except:
            failed += 1
        await asyncio.sleep(0.5)
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
    await msg.edit_text(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Не доставлено: {failed}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    log_action(f"Админ {user_id} сделал рассылку: {message_text[:50]}...")

async def ban_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    keyboard = [
        [InlineKeyboardButton("🚫 Забанить пользователя", callback_data="ban_user")],
        [InlineKeyboardButton("✅ Разбанить пользователя", callback_data="unban_user")],
        [InlineKeyboardButton("📋 Список забаненных", callback_data="banned_list")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("🚫 <b>Управление бан-листом</b>\n\nВыберите действие:", parse_mode="HTML", reply_markup=reply_markup)

async def ban_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    context.user_data['state'] = 'awaiting_ban_user'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="ban_menu")]]
    await query.edit_message_text("🚫 Введите ID пользователя для бана:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    try:
        target_id = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Введите корректный ID!")
        return
    context.user_data['state'] = ''
    if target_id in ADMINS:
        await update.message.reply_text("❌ Нельзя забанить админа!")
        return
    if target_id in BANNED:
        await update.message.reply_text(f"⚠️ Пользователь {target_id} уже забанен!")
        return
    BANNED.append(target_id)
    log_action(f"Админ {user_id} забанил {target_id}")
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="ban_menu")]]
    await update.message.reply_text(f"✅ Пользователь <code>{target_id}</code> забанен!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    try:
        await context.bot.send_message(chat_id=target_id, text="🚫 Вы были забанены в боте!")
    except:
        pass

async def unban_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    context.user_data['state'] = 'awaiting_unban_user'
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="ban_menu")]]
    await query.edit_message_text("✅ Введите ID пользователя для разбана:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Только для админа!")
        return
    try:
        target_id = int(update.message.text.strip())
    except:
        await update.message.reply_text("❌ Введите корректный ID!")
        return
    context.user_data['state'] = ''
    if target_id not in BANNED:
        await update.message.reply_text(f"⚠️ Пользователь {target_id} не в бане!")
        return
    BANNED.remove(target_id)
    log_action(f"Админ {user_id} разбанил {target_id}")
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="ban_menu")]]
    await update.message.reply_text(f"✅ Пользователь <code>{target_id}</code> разбанен!", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    try:
        await context.bot.send_message(chat_id=target_id, text="✅ Вы были разбанены в боте!")
    except:
        pass

async def banned_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    if not BANNED:
        await query.edit_message_text("📭 Нет забаненных пользователей.")
        return
    message = "🚫 <b>ЗАБАНЕННЫЕ</b>\n\n"
    for uid in BANNED:
        username = users_db.get(uid, {}).get("username", f"ID{uid}")
        message += f"• {username} (<code>{uid}</code>)\n"
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="ban_menu")]]
    await query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
# ═══════════════════════════════════════
#  БЭКАП, СТАТУС БОТА, НАЗАД, MAIN (ЧАСТЬ 2)
# ═══════════════════════════════════════
async def backup_keys(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    await query.edit_message_text("⏳ Создание бэкапа...")
    try:
        response = requests.get(f"{SERVER_URL}/list")
        data = response.json()
        if not data:
            await query.edit_message_text("📭 Нет ключей для бэкапа.")
            return
        filename = f"keys_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = f"/sdcard/Download/{filename}"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        with open(filepath, "rb") as f:
            await context.bot.send_document(
                chat_id=query.from_user.id,
                document=f,
                filename=filename,
                caption=f"💾 Бэкап ключей\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n📦 Всего ключей: {len(data)}"
            )
        await query.delete_message()
        log_action(f"Админ {query.from_user.id} сделал бэкап ключей ({len(data)} шт)")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

async def bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("❌ Только для админа!")
        return
    try:
        response = requests.get(f"{SERVER_URL}/list")
        data = response.json()
        total_keys = len(data)
        active_keys = sum(1 for k in data if k.get("active", False))
        total_users = len(users_db)
        online = sum(1 for uid, d in users_db.items() if (time.time() - d.get("last_active", 0)) < 1800)
        uptime_seconds = int(time.time() - start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        message = (
            "📊 <b>СТАТУС БОТА</b>\n\n"
            f"🤖 Бот: @MultiToolRubgBot\n"
            f"⏱️ Работает: {days}д {hours}ч {minutes}м\n\n"
            f"👥 Пользователей: {total_users}\n"
            f"🟢 Онлайн: {online}\n"
            f"🔴 Оффлайн: {total_users - online}\n\n"
            f"🔑 Всего ключей: {total_keys}\n"
            f"✅ Активных: {active_keys}\n"
            f"❌ Неактивных: {total_keys - active_keys}\n\n"
            f"👤 Админов: {len(ADMINS)}\n"
            f"👥 Реселлеров: {len(RESELLERS)}\n"
            f"🚫 Заблокированных: {len(BANNED)}"
        )
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        await query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
        log_action(f"Админ {query.from_user.id} посмотрел статус бота")
    except Exception as e:
        await query.edit_message_text(f"❌ Ошибка: {str(e)}")

# ═══════════════════════════════════════
#  КНОПКА НАЗАД (ИСПРАВЛЕННАЯ)
# ═══════════════════════════════════════
async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    
    user_id = query.from_user.id
    
    if is_banned(user_id):
        await query.edit_message_text("🚫 Вы заблокированы!")
        return
    
    if is_admin(user_id):
        keyboard = [
            [InlineKeyboardButton("🔑 Сгенерировать ключ", callback_data="generate")],
            [InlineKeyboardButton("✏️ Кастомный ключ (админ)", callback_data="admin_custom_key")],
            [InlineKeyboardButton("📋 Список ключей", callback_data="list")],
            [InlineKeyboardButton("🗑️ Удалить ключ", callback_data="delete")],
            [InlineKeyboardButton("🗑️ Удалить все ключи", callback_data="delete_all")],
            [InlineKeyboardButton("🔄 Сбросить ключ", callback_data="reset")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("📈 Аналитика ключей", callback_data="key_analytics")],
            [InlineKeyboardButton("🏆 Топ пользователей", callback_data="top_users")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="users_list")],
            [InlineKeyboardButton("🔍 Поиск пользователя", callback_data="find_user")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="broadcast")],
            [InlineKeyboardButton("📝 Логи", callback_data="logs")],
            [InlineKeyboardButton("🚫 Бан-лист", callback_data="ban_menu")],
            [InlineKeyboardButton("👥 Мои реселлеры", callback_data="my_resellers")],
            [InlineKeyboardButton("➕ Добавить реселлера", callback_data="add_reseller")],
            [InlineKeyboardButton("➖ Удалить реселлера", callback_data="remove_reseller")],
            [InlineKeyboardButton("⚙️ Настройка задержки", callback_data="cooldown_settings")],
            [InlineKeyboardButton("💾 Бэкап ключей", callback_data="backup_keys")],
            [InlineKeyboardButton("📊 Статус сервера", callback_data="server_status")],
            [InlineKeyboardButton("📊 Активации ключей", callback_data="key_stats_admin")],
            [InlineKeyboardButton("ℹ️ Инфо о ключе", callback_data="info_key")],
            [InlineKeyboardButton("📤 Отправить ключ", callback_data="send_key")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🤖 Добро пожаловать, АДМИН!\n\nВыберите действие:", reply_markup=reply_markup)
        return
    
    if is_reseller(user_id):
        cooldown = get_reseller_cooldown(user_id)
        cooldown_min = cooldown // 60
        keyboard = [
            [InlineKeyboardButton("🔑 Сгенерировать ключ", callback_data="generate")],
            [InlineKeyboardButton("✏️ Создать кастомный ключ", callback_data="custom_key")],
            [InlineKeyboardButton("📋 Мои ключи", callback_data="my_keys")],
            [InlineKeyboardButton("⏳ Время до генерации", callback_data="my_cooldown")],
            [InlineKeyboardButton("📊 Статистика ключей", callback_data="reseller_stats")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"🤖 Добро пожаловать, Реселлер!\n\n"
            f"✅ Генерировать ключи (до 30 дней, задержка {cooldown_min} мин)\n"
            f"✅ Создавать кастомные ключи (до 67 дней, задержка {cooldown_min} мин)\n"
            f"✅ Смотреть свои ключи\n"
            f"✅ Проверять время до следующей генерации",
            reply_markup=reply_markup
        )
        return
    
    # Обычный пользователь
    keyboard = [[InlineKeyboardButton("✅ Продолжить", callback_data="get_free_key")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "👋 Добро пожаловать!\n\n"
        "Хочешь получить ключ на 2 часа?\nНажми 'Продолжить'.",
        reply_markup=reply_markup
    )

# ═══════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════
def main():
    load_stats()
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    
    application.add_handler(CallbackQueryHandler(get_free_key, pattern="^get_free_key$"))
    application.add_handler(CallbackQueryHandler(generate_key, pattern="^generate$"))
    application.add_handler(CallbackQueryHandler(generate_callback, pattern="^gen_"))
    application.add_handler(CallbackQueryHandler(admin_custom_key_start, pattern="^admin_custom_key$"))
    application.add_handler(CallbackQueryHandler(admin_days_callback, pattern="^admin_days_"))
    application.add_handler(CallbackQueryHandler(custom_key_start, pattern="^custom_key$"))
    application.add_handler(CallbackQueryHandler(reseller_days_callback, pattern="^reseller_days_"))
    application.add_handler(CallbackQueryHandler(my_keys, pattern="^my_keys$"))
    application.add_handler(CallbackQueryHandler(my_cooldown, pattern="^my_cooldown$"))
    application.add_handler(CallbackQueryHandler(cooldown_settings, pattern="^cooldown_settings$"))
    application.add_handler(CallbackQueryHandler(cooldown_value, pattern="^cd_value_"))
    application.add_handler(CallbackQueryHandler(add_reseller_start, pattern="^add_reseller$"))
    application.add_handler(CallbackQueryHandler(my_resellers, pattern="^my_resellers$"))
    application.add_handler(CallbackQueryHandler(remove_reseller_start, pattern="^remove_reseller$"))
    application.add_handler(CallbackQueryHandler(remove_reseller_callback, pattern="^remove_res_"))
    application.add_handler(CallbackQueryHandler(list_keys, pattern="^list$"))
    application.add_handler(CallbackQueryHandler(delete_key_start, pattern="^delete$"))
    application.add_handler(CallbackQueryHandler(delete_all_keys, pattern="^delete_all$"))
    application.add_handler(CallbackQueryHandler(confirm_delete_all, pattern="^confirm_delete_all$"))
    application.add_handler(CallbackQueryHandler(reset_key_start, pattern="^reset$"))
    application.add_handler(CallbackQueryHandler(info_key_start, pattern="^info_key$"))
    application.add_handler(CallbackQueryHandler(send_key_start, pattern="^send_key$"))
    application.add_handler(CallbackQueryHandler(send_days_callback, pattern="^send_days_"))
    application.add_handler(CallbackQueryHandler(stats, pattern="^stats$"))
    application.add_handler(CallbackQueryHandler(reseller_stats, pattern="^reseller_stats$"))
    application.add_handler(CallbackQueryHandler(key_analytics, pattern="^key_analytics$"))
    application.add_handler(CallbackQueryHandler(top_users, pattern="^top_users$"))
    application.add_handler(CallbackQueryHandler(logs, pattern="^logs$"))
    application.add_handler(CallbackQueryHandler(users_list, pattern="^users_list$"))
    application.add_handler(CallbackQueryHandler(users_filter, pattern="^users_"))
    application.add_handler(CallbackQueryHandler(find_user_start, pattern="^find_user$"))
    application.add_handler(CallbackQueryHandler(broadcast_start, pattern="^broadcast$"))
    application.add_handler(CallbackQueryHandler(ban_menu, pattern="^ban_menu$"))
    application.add_handler(CallbackQueryHandler(ban_user_start, pattern="^ban_user$"))
    application.add_handler(CallbackQueryHandler(unban_user_start, pattern="^unban_user$"))
    application.add_handler(CallbackQueryHandler(banned_list, pattern="^banned_list$"))
    application.add_handler(CallbackQueryHandler(backup_keys, pattern="^backup_keys$"))
    application.add_handler(CallbackQueryHandler(bot_status, pattern="^bot_status$"))
    application.add_handler(CallbackQueryHandler(server_status, pattern="^server_status$"))
    application.add_handler(CallbackQueryHandler(key_stats_admin, pattern="^key_stats_admin$"))
    application.add_handler(CallbackQueryHandler(online_players, pattern="^online_players$"))
    application.add_handler(CallbackQueryHandler(back, pattern="^back$"))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state', '')
    if state == 'awaiting_admin_custom_key':
        await handle_admin_custom_key(update, context)
    elif state == 'awaiting_custom_key':
        await handle_custom_key(update, context)
    elif state == 'awaiting_cooldown_id':
        await handle_cooldown_id(update, context)
    elif state == 'awaiting_reseller_id':
        await handle_add_reseller(update, context)
    elif state == 'awaiting_delete_key':
        await handle_delete_key(update, context)
    elif state == 'awaiting_reset_key':
        await handle_reset_key(update, context)
    elif state == 'awaiting_info_key':
        await handle_info_key(update, context)
    elif state == 'awaiting_send_key_user':
        await handle_send_key_user(update, context)
    elif state == 'awaiting_find_user':
        await handle_find_user(update, context)
    elif state == 'awaiting_broadcast':
        await handle_broadcast(update, context)
    elif state == 'awaiting_ban_user':
        await handle_ban_user(update, context)
    elif state == 'awaiting_unban_user':
        await handle_unban_user(update, context)
    else:
        await update.message.reply_text("❓ Неизвестная команда. Используйте /start")

if __name__ == "__main__":
    main()

