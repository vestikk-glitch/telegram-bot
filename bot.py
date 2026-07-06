import json
import time
import asyncio
import threading
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# ═══════════════════════════════════════
#  ПИНГ ДЛЯ RENDER (ЧТОБЫ НЕ ЗАСЫПАЛ)
# ═══════════════════════════════════════
BOT_URL = "https://telegram-bot-4exc.onrender.com"  # ⚠️ ЗАМЕНИ НА СВОЙ URL!

def ping_self():
    while True:
        try:
            response = requests.get(BOT_URL, timeout=10)
            print(f"✅ Пинг успешен! Статус: {response.status_code}")
        except Exception as e:
            print(f"❌ Ошибка пинга: {e}")
        time.sleep(600)  # 10 минут

threading.Thread(target=ping_self, daemon=True).start()
# ═══════════════════════════════════════
#  НАСТРОЙКИ
# ═══════════════════════════════════════
TOKEN = "8946856377:AAHHIh0ye6k18dwQit0d8PaIyvnv6p5O2dg"
ADMIN_ID = 1745668867

# ═══════════════════════════════════════
#  СИСТЕМА ТИКЕТОВ (ПОДДЕРЖКА)
# ═══════════════════════════════════════
tickets = {}
ticket_counter = 500
TICKETS_FILE = "tickets.json"

def load_tickets():
    global tickets, ticket_counter
    try:
        with open(TICKETS_FILE, "r") as f:
            data = json.load(f)
            tickets = data.get("tickets", {})
            ticket_counter = data.get("ticket_counter", 500)
    except:
        tickets = {}
        ticket_counter = 500

def save_tickets():
    with open(TICKETS_FILE, "w") as f:
        json.dump({
            "tickets": tickets,
            "ticket_counter": ticket_counter
        }, f, indent=4, ensure_ascii=False)

load_tickets()

def create_ticket(user_id, username, question_type, message):
    global ticket_counter
    ticket_counter += 1
    ticket_id = ticket_counter
    
    tickets[str(ticket_id)] = {
        "user_id": user_id,
        "username": username,
        "question_type": question_type,
        "message": message,
        "status": "open",
        "created": time.time(),
        "key": None,
        "chat_link": None,
        "messages": [{"from": "user", "text": message, "time": time.time()}]
    }
    save_tickets()
    return ticket_id

async def notify_admin(ticket_id, context):
    data = tickets[str(ticket_id)]
    created = datetime.fromtimestamp(data["created"]).strftime("%d.%m %H:%M")
    
    text = (
        f"🆕 <b>НОВЫЙ ТИКЕТ!</b>\n\n"
        f"📌 <b>Тикет #{ticket_id}</b>\n"
        f"👤 Пользователь: @{data['username']}\n"
        f"🆔 ID: {data['user_id']}\n"
        f"📂 Тема: {data['question_type']}\n"
        f"📝 Вопрос: {data['message']}\n"
        f"📅 Создан: {created}\n"
        f"📌 Статус: 🟡 На рассмотрении"
    )
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"📩 Ответить на тикет #{ticket_id}", callback_data=f"reply_ticket_{ticket_id}")],
                [InlineKeyboardButton(f"✅ Одобрить тикет #{ticket_id}", callback_data=f"approve_ticket_{ticket_id}")]
            ])
        )
    except:
        pass
        # ═══════════════════════════════════════
#  КОМАНДА /start
# ═══════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Проверяем, есть ли активный тикет
    user_ticket = None
    for tid, data in tickets.items():
        if data["user_id"] == user_id and data["status"] == "open":
            user_ticket = tid
            break
    
    # Проверяем, есть ли закрытый тикет
    closed_ticket = None
    for tid, data in tickets.items():
        if data["user_id"] == user_id and data["status"] == "closed":
            closed_ticket = tid
            break
    
    # Если админ
    if user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("🎫 Управление тикетами", callback_data="admin_tickets")],
        ]
        await update.message.reply_text(
            "👑 <b>АДМИН ПАНЕЛЬ</b>\n\n"
            f"📊 Всего тикетов: {len(tickets)}\n"
            f"🟢 Открытых: {sum(1 for t in tickets.values() if t['status'] == 'open')}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Если у пользователя есть активный тикет
    if user_ticket:
        keyboard = [
            [InlineKeyboardButton("📊 Статус тикета", callback_data=f"ticket_status_{user_ticket}")],
        ]
        await update.message.reply_text(
            f"📩 <b>У ВАС ЕСТЬ АКТИВНЫЙ ТИКЕТ!</b>\n\n"
            f"📌 <b>Тикет #{user_ticket}</b>\n"
            f"📌 Статус: <b>🟡 На рассмотрении</b>\n\n"
            f"⏳ Ожидайте ответа администратора.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return
    
    # Если у пользователя есть закрытый тикет
    if closed_ticket:
        data = tickets[str(closed_ticket)]
        if data.get("chat_link") and data.get("key"):
            keyboard = [
                [InlineKeyboardButton("📊 Статус тикета", callback_data=f"ticket_status_{closed_ticket}")],
                [InlineKeyboardButton("🔄 Создать новый тикет", callback_data="ticket_new")],
            ]
            await update.message.reply_text(
                f"📩 <b>У ВАС ЕСТЬ ЗАКРЫТЫЙ ТИКЕТ</b>\n\n"
                f"📌 <b>Тикет #{closed_ticket}</b>\n"
                f"📌 Статус: <b>✅ Закрыт</b>\n\n"
                f"Если у вас новый вопрос, создайте новый тикет.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
    
    # Новый пользователь
    keyboard = [
        [InlineKeyboardButton("🎮 Получить ключ + приватный чат + скрипт", callback_data="ticket_key")],
        [InlineKeyboardButton("❓ Другой вопрос", callback_data="ticket_other")],
    ]
    await update.message.reply_text(
        "📩 <b>ТЕХНИЧЕСКАЯ ПОДДЕРЖКА</b>\n\n"
        "Выберите тему вопроса:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
        # ═══════════════════════════════════════
#  ВЫБОР ТЕМЫ
# ═══════════════════════════════════════
async def ticket_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем ещё раз
    for tid, data in tickets.items():
        if data["user_id"] == user_id and data["status"] == "open":
            await query.edit_message_text(
                "❌ <b>У ВАС УЖЕ ЕСТЬ АКТИВНЫЙ ТИКЕТ!</b>\n\n"
                f"📌 Тикет #{tid}\n"
                "⏳ Ожидайте ответа администратора.",
                parse_mode="HTML"
            )
            return
    
    choice = query.data
    context.user_data['ticket_type'] = choice
    
    if choice == "ticket_key":
        keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data="start")]]
        await query.edit_message_text(
            "🎮 <b>ПОЛУЧИТЬ КЛЮЧ + ПРИВАТНЫЙ ЧАТ + СКРИПТ</b>\n\n"
            "Напишите <b>#key</b> для получения ключа и ссылки на приватный чат.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data['state'] = 'awaiting_key_request'
    else:
        keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data="start")]]
        await query.edit_message_text(
            "❓ <b>ДРУГОЙ ВОПРОС</b>\n\n"
            "Напишите ваш вопрос, и мы ответим вам в ближайшее время.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data['state'] = 'awaiting_other_question'
        # ═══════════════════════════════════════
#  ОБРАБОТКА ВВОДА
# ═══════════════════════════════════════
async def handle_support_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"ID{user_id}"
    text = update.message.text
    state = context.user_data.get('state', '')
    
    if state == 'awaiting_key_request':
        if text.lower().strip() == "#key":
            ticket_id = create_ticket(user_id, username, "Получить ключ + приватный чат + скрипт", text)
            await update.message.reply_text(
                f"✅ <b>ТИКЕТ СОЗДАН!</b>\n\n"
                f"📌 <b>Тикет #{ticket_id}</b>\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M')}\n"
                f"📌 Статус: <b>🟡 На рассмотрении</b>\n\n"
                f"⏳ Ожидайте ответа администратора.",
                parse_mode="HTML"
            )
            await notify_admin(ticket_id, context)
            context.user_data['state'] = ''
        else:
            await update.message.reply_text(
                "❌ <b>АЛЁ! Я ТЕБЯ ПРОСИЛ НАПИСАТЬ ТОЛЬКО #key</b>\n\n"
                "Напишите <b>#key</b> для получения ключа и ссылки на приватный чат.",
                parse_mode="HTML"
            )
    
    elif state == 'awaiting_other_question':
        ticket_id = create_ticket(user_id, username, "Другой вопрос", text)
        await update.message.reply_text(
            f"✅ <b>ТИКЕТ СОЗДАН!</b>\n\n"
            f"📌 <b>Тикет #{ticket_id}</b>\n"
            f"⏰ Время: {datetime.now().strftime('%H:%M')}\n"
            f"📌 Статус: <b>🟡 На рассмотрении</b>\n\n"
            f"Мы ответим вам в ближайшее время. 🙏",
            parse_mode="HTML"
        )
        await notify_admin(ticket_id, context)
        context.user_data['state'] = ''

async def ticket_new(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Проверяем, нет ли активного тикета
    for tid, data in tickets.items():
        if data["user_id"] == user_id and data["status"] == "open":
            await query.edit_message_text(
                "❌ <b>У ВАС УЖЕ ЕСТЬ АКТИВНЫЙ ТИКЕТ!</b>\n\n"
                f"📌 Тикет #{tid}\n"
                "⏳ Ожидайте ответа администратора.",
                parse_mode="HTML"
            )
            return
    
    keyboard = [
        [InlineKeyboardButton("🎮 Получить ключ + приватный чат + скрипт", callback_data="ticket_key")],
        [InlineKeyboardButton("❓ Другой вопрос", callback_data="ticket_other")],
        [InlineKeyboardButton("🔙 Назад", callback_data="start")],
    ]
    await query.edit_message_text(
        "📩 <b>СОЗДАНИЕ НОВОГО ТИКЕТА</b>\n\n"
        "Выберите тему вопроса:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
        )
    # ═══════════════════════════════════════
#  СТАТУС ТИКЕТА (ПОЛЬЗОВАТЕЛЬ)
# ═══════════════════════════════════════
async def ticket_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ticket_id = query.data.split("_")[2]
    data = tickets.get(ticket_id)
    
    if not data:
        await query.edit_message_text("❌ Тикет не найден!")
        return
    
    created = datetime.fromtimestamp(data["created"]).strftime("%d.%m.%Y %H:%M")
    
    if data["status"] == "open":
        status_text = "🟡 На рассмотрении"
        status_desc = "⏳ Администратор ещё не ответил на ваш запрос."
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="start")]]
    else:
        status_text = "✅ ОДОБРЕН!"
        chat_link = data.get("chat_link", "Ссылка не найдена")
        key = data.get("key", "Ключ не найден")
        status_desc = (
            f"✅ <b>Ваш тикет одобрен!</b>\n\n"
            f"🔑 <b>Ваш ключ:</b> <code>{key}</code>\n"
            f"📅 Действителен: 7 дней\n\n"
            f"🔗 <b>Ссылка на приватный чат:</b>\n"
            f"{chat_link}"
        )
        keyboard = [
            [InlineKeyboardButton("🔗 Перейти в чат", url=chat_link)] if chat_link and chat_link.startswith("http") else [],
            [InlineKeyboardButton("🔙 Назад", callback_data="start")]
        ]
        keyboard = [row for row in keyboard if row]
    
    await query.edit_message_text(
        f"📌 <b>ТИКЕТ #{ticket_id}</b>\n\n"
        f"📅 Создан: {created}\n"
        f"📌 Статус: <b>{status_text}</b>\n\n"
        f"{status_desc}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # ═══════════════════════════════════════
#  АДМИН ПАНЕЛЬ
# ═══════════════════════════════════════
async def admin_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Только для админа!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📋 Открытые тикеты", callback_data="admin_list_open")],
        [InlineKeyboardButton("📋 Все тикеты", callback_data="admin_list_all")],
        [InlineKeyboardButton("🔙 Назад", callback_data="start")],
    ]
    
    await query.edit_message_text(
        f"👑 <b>УПРАВЛЕНИЕ ПОДДЕРЖКОЙ</b>\n\n"
        f"📊 Всего тикетов: {len(tickets)}\n"
        f"🟢 Открытых: {sum(1 for t in tickets.values() if t['status'] == 'open')}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def admin_list_tickets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Только для админа!")
        return
    
    filter_type = query.data.split("_")[2]
    
    filtered = {}
    for tid, data in tickets.items():
        if filter_type == "open" and data["status"] == "open":
            filtered[tid] = data
        elif filter_type == "all":
            filtered[tid] = data
    
    if not filtered:
        await query.edit_message_text("📭 Нет тикетов.")
        return
    
    keyboard = []
    for tid, data in filtered.items():
        username = data.get("username", f"ID{data['user_id']}")
        created = datetime.fromtimestamp(data["created"]).strftime("%d.%m %H:%M")
        status_emoji = "🟢" if data["status"] == "open" else "🔴"
        keyboard.append([
            InlineKeyboardButton(
                f"{status_emoji} #{tid} @{username} ({created})",
                callback_data=f"view_ticket_{tid}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="admin_tickets")])
    
    await query.edit_message_text(
        f"📋 <b>ТИКЕТЫ ({len(filtered)})</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # ═══════════════════════════════════════
#  ПРОСМОТР ТИКЕТА (АДМИН)
# ═══════════════════════════════════════
async def view_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Только для админа!")
        return
    
    ticket_id = query.data.split("_")[2]
    data = tickets.get(ticket_id)
    
    if not data:
        await query.edit_message_text("❌ Тикет не найден!")
        return
    
    created = datetime.fromtimestamp(data["created"]).strftime("%d.%m.%Y %H:%M")
    status = "🟢 Открыт" if data["status"] == "open" else "🔴 Закрыт"
    
    message = (
        f"📌 <b>Тикет #{ticket_id}</b>\n\n"
        f"👤 Пользователь: @{data['username']}\n"
        f"🆔 ID: {data['user_id']}\n"
        f"📂 Тема: {data['question_type']}\n"
        f"📅 Создан: {created}\n"
        f"📌 Статус: {status}\n"
    )
    
    if data.get("key"):
        message += f"🔑 Ключ: <code>{data['key']}</code>\n"
    if data.get("chat_link"):
        message += f"🔗 Ссылка: {data['chat_link']}\n"
    
    message += f"\n📝 <b>Вопрос:</b>\n{data['message']}\n"
    
    if data.get("messages") and len(data["messages"]) > 1:
        message += "\n📜 <b>История:</b>\n"
        for msg in data["messages"][-5:]:
            who = "👤 Пользователь" if msg["from"] == "user" else "👑 Админ"
            time_msg = datetime.fromtimestamp(msg["time"]).strftime("%H:%M")
            message += f"{who} ({time_msg}): {msg['text']}\n"
    
    keyboard = [
        [InlineKeyboardButton("📩 Ответить", callback_data=f"reply_ticket_{ticket_id}")],
        [InlineKeyboardButton("✅ Одобрить (выдать ключ)", callback_data=f"approve_ticket_{ticket_id}")],
        [InlineKeyboardButton("❌ Закрыть", callback_data=f"close_ticket_{ticket_id}")],
        [InlineKeyboardButton("🔙 Назад", callback_data="admin_tickets")],
    ]
    
    await query.edit_message_text(message, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(keyboard))
    # ═══════════════════════════════════════
#  ОДОБРЕНИЕ ТИКЕТА (ВЫДАЧА КЛЮЧА + ССЫЛКИ)
# ═══════════════════════════════════════
async def approve_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Только для админа!")
        return
    
    ticket_id = query.data.split("_")[2]
    data = tickets.get(ticket_id)
    
    if not data:
        await query.edit_message_text("❌ Тикет не найден!")
        return
    
    # Запрашиваем ссылку
    context.user_data['approve_ticket'] = ticket_id
    context.user_data['state'] = 'awaiting_chat_link'
    
    keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data=f"view_ticket_{ticket_id}")]]
    await query.edit_message_text(
        f"🔗 <b>Введите ссылку на приватный чат</b>\n\n"
        f"Тикет #{ticket_id}\n"
        f"Пользователь: @{data['username']}\n\n"
        f"Отправьте ссылку:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_chat_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Только для админа!")
        return
    
    ticket_id = context.user_data.get('approve_ticket')
    if not ticket_id or ticket_id not in tickets:
        await update.message.reply_text("❌ Тикет не найден!")
        return
    
    chat_link = update.message.text.strip()
    data = tickets[ticket_id]
    
    # Генерируем ключ
    try:
        response = requests.get(f"https://key-server-4jkz.onrender.com/generate?days=7&password=1337")
        key_data = response.json()
        if "key" in key_data:
            data["key"] = key_data["key"]
            tickets[ticket_id]["key"] = data["key"]
            tickets[ticket_id]["chat_link"] = chat_link
            tickets[ticket_id]["status"] = "closed"
            save_tickets()
        else:
            await update.message.reply_text("❌ Ошибка генерации ключа!")
            return
    except:
        await update.message.reply_text("❌ Ошибка подключения к серверу!")
        return
    
    # Отправляем пользователю
    try:
        await context.bot.send_message(
            chat_id=data["user_id"],
            text=f"✅ <b>ВАШ ТИКЕТ #{ticket_id} ОДОБРЕН!</b>\n\n"
                 f"✅ Ваш тикет одобрен!\n\n"
                 f"🔑 <b>Ваш ключ:</b> <code>{data['key']}</code>\n"
                 f"📅 Действителен: 7 дней\n\n"
                 f"🔗 <b>Ссылка на приватный чат:</b>\n"
                 f"{chat_link}",
            parse_mode="HTML"
        )
    except:
        await update.message.reply_text("❌ Не удалось отправить сообщение пользователю!")
        return
    
    context.user_data['state'] = ''
    
    await update.message.reply_text(
        f"✅ Тикет #{ticket_id} одобрен и закрыт!\n\n"
        f"👤 Пользователю отправлен ключ и ссылка.",
        parse_mode="HTML"
    )
    # ═══════════════════════════════════════
#  ОТВЕТ НА ТИКЕТ (АДМИН)
# ═══════════════════════════════════════
async def reply_ticket_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Только для админа!")
        return
    
    ticket_id = query.data.split("_")[2]
    context.user_data['reply_ticket'] = ticket_id
    context.user_data['state'] = 'awaiting_admin_reply'
    
    keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data=f"view_ticket_{ticket_id}")]]
    await query.edit_message_text(
        f"✏️ <b>Ответ на тикет #{ticket_id}</b>\n\n"
        f"Напишите ваш ответ:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Только для админа!")
        return
    
    ticket_id = context.user_data.get('reply_ticket')
    if not ticket_id or ticket_id not in tickets:
        await update.message.reply_text("❌ Тикет не найден!")
        return
    
    reply_text = update.message.text
    data = tickets[ticket_id]
    
    if "messages" not in data:
        data["messages"] = []
    data["messages"].append({"from": "admin", "text": reply_text, "time": time.time()})
    save_tickets()
    
    context.user_data['state'] = ''
    
    try:
        await context.bot.send_message(
            chat_id=data["user_id"],
            text=f"📩 <b>Ответ на ваш тикет #{ticket_id}</b>\n\n"
                 f"👑 Администратор:\n{reply_text}\n\n"
                 f"Если есть вопросы — пишите в этот чат.",
            parse_mode="HTML"
        )
        await update.message.reply_text(f"✅ Ответ на тикет #{ticket_id} отправлен!")
    except:
        await update.message.reply_text("❌ Не удалось отправить ответ пользователю!")

async def close_ticket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ Только для админа!")
        return
    
    ticket_id = query.data.split("_")[2]
    
    if ticket_id not in tickets:
        await query.edit_message_text("❌ Тикет не найден!")
        return
    
    tickets[ticket_id]["status"] = "closed"
    save_tickets()
    
    await query.edit_message_text(f"✅ Тикет #{ticket_id} закрыт!")
    # ═══════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════
def main():
    application = Application.builder().token(TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler("start", start))
    
    # Callback query handlers
    application.add_handler(CallbackQueryHandler(ticket_choice, pattern="^ticket_"))
    application.add_handler(CallbackQueryHandler(ticket_status, pattern="^ticket_status_"))
    application.add_handler(CallbackQueryHandler(ticket_new, pattern="^ticket_new$"))
    application.add_handler(CallbackQueryHandler(admin_tickets, pattern="^admin_tickets$"))
    application.add_handler(CallbackQueryHandler(admin_list_tickets, pattern="^admin_list_"))
    application.add_handler(CallbackQueryHandler(view_ticket, pattern="^view_ticket_"))
    application.add_handler(CallbackQueryHandler(reply_ticket_start, pattern="^reply_ticket_"))
    application.add_handler(CallbackQueryHandler(approve_ticket, pattern="^approve_ticket_"))
    application.add_handler(CallbackQueryHandler(close_ticket, pattern="^close_ticket_"))
    
    # Message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state', '')
    if state == 'awaiting_key_request' or state == 'awaiting_other_question':
        await handle_support_input(update, context)
    elif state == 'awaiting_chat_link':
        await handle_chat_link(update, context)
    elif state == 'awaiting_admin_reply':
        await handle_admin_reply(update, context)
    else:
        await update.message.reply_text(
            "❓ Неизвестная команда.\n"
            "Используйте /start для начала."
        )

if __name__ == "__main__":
    main()
    
    
    
    
