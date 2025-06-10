import os
import json
from datetime import datetime, timedelta
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    CallbackContext
)
from dotenv import load_dotenv
from flask import Flask, request

# -------------------
# 🔧 Настройка логгера
# -------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def log_event(level, message):
    if level == 'info':
        logging.info(message)
    elif level == 'debug':
        logging.debug(message)
    elif level == 'warning':
        logging.warning(message)
    elif level == 'error':
        logging.error(message)
    elif level == 'critical':
        logging.critical(message)

# -------------------
# 📂 Хранилище данных
# -------------------
VOTES_FILE = 'votes.json'

def load_votes():
    if not os.path.exists(VOTES_FILE):
        return {}
    with open(VOTES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_votes(votes):
    with open(VOTES_FILE, 'w', encoding='utf-8') as f:
        json.dump(votes, f, indent=4)

# -------------------
# 🎯 Состояния для конверсации
# -------------------
TITLE, TEXT, OPTIONS, DURATION, CONFIRM = range(5)
WAITING_FOR_FILE_OR_CONTINUE, CONFIRM_KICK = 6, 7

# -------------------
# 🔄 Проверка, является ли пользователь админом
# -------------------
async def is_admin(bot, chat_id, user_id):
    try:
        members = await bot.get_chat_members(chat_id)
        admins = [m.user.id for m in members if m.status in ['creator', 'administrator']]
        return user_id in admins
    except Exception as e:
        log_event('error', f"Ошибка при получении админов: {e}")
        return False

# -------------------
# 🚀 Команда /start_vote
# -------------------
async def start_vote(update: Update, context: CallbackContext):
    user_id = update.message.from_user.id
    chat_id = update.effective_message.chat_id

    if chat_id != user_id:
        await update.message.reply_text("Пожалуйста, используйте команду /start_vote в личных сообщениях с ботом.")
        return

    title = update.message.text.split(' ', 1)[1].strip('"')
    context.user_data['title'] = title
    context.user_data['admin_id'] = user_id
    await update.message.reply_text("Введите текст поста:")
    log_event('info', f"Администратор @{update.message.from_user.username} начал запуск голосования '{title}'")
    return TEXT

# -------------------
# 🗒️ Шаги заполнения
# -------------------
async def get_text(update: Update, context: CallbackContext):
    context.user_data['text'] = update.message.text
    await update.message.reply_text("Введите варианты ответов через запятую, например: Яблоко, Ананас, Курица")
    return OPTIONS

async def get_options(update: Update, context: CallbackContext):
    options = [opt.strip() for opt in update.message.text.split(',')]
    context.user_data['options'] = options
    await update.message.reply_text("Введите время на голосование, например 2m, или 2h, или 7d")
    return DURATION

def parse_duration(duration_str):
    match = re.match(r'(\d+)([mhd])', duration_str)
    if not match:
        raise ValueError("Неверный формат времени. Используйте: 5m, 2h, 1d")

    value, unit = int(match.group(1)), match.group(2)
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)

async def get_duration(update: Update, context: CallbackContext):
    try:
        duration = parse_duration(update.message.text)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return DURATION

    context.user_data['duration'] = duration.total_seconds()
    await update.message.reply_text("Начать голосование? Да или Нет")
    return CONFIRM

async def confirm_start(update: Update, context: CallbackContext):
    answer = update.message.text.lower()

    if answer == "да":
        data = load_votes()
        vote_id = len(data) + 1
        admin_id = context.user_data.get('admin_id')

        # Сохраняем данные голосования
        data[vote_id] = {
            "title": context.user_data['title'],
            "text": context.user_data['text'],
            "options": context.user_data['options'],
            "voters": {},
            "started_at": datetime.now().isoformat(),
            "duration": context.user_data['duration'],
            "admin_id": admin_id
        }

        save_votes(data)

        # Создаем клавиатуру
        keyboard = [
            [InlineKeyboardButton(option, callback_data=str(i))]
            for i, option in enumerate(context.user_data['options'])
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Отправляем сообщение с голосованием
        chat_id = context.user_data.get('chat_id_for_vote', -1001234567890)  # заменить на реальный ID чата
        await context.bot.send_message(chat_id, f"{context.user_data['title']}\n\n{context.user_data['text']}", reply_markup=reply_markup)

        log_event('info', f"Голосование '{context.user_data['title']}' успешно начато в чате {chat_id}")
        await update.message.reply_text("Голосование успешно начато!")

    elif answer == "нет":
        await update.message.reply_text("Голосование отменено. Чтобы начать снова, используйте /start_vote.")
    else:
        await update.message.reply_text("Пожалуйста, ответьте 'Да' или 'Нет'")
        return CONFIRM

    return ConversationHandler.END

# -------------------
# 🗳️ Обработка голосов
# -------------------
async def handle_vote(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = str(query.from_user.id)
    choice = int(query.data)

    data = load_votes()
    active_vote = next((v for v in data.values()), None)

    if not active_vote:
        await query.answer("Голосование не активно.")
        return

    if choice >= len(active_vote["options"]):
        await query.answer("Неверный вариант.")
        return

    active_vote["voters"][user_id] = choice
    save_votes(data)
    await query.answer("Ваш голос учтён.")

# -------------------
# 📊 Завершение голосования
# -------------------
async def end_vote(update: Update, context: CallbackContext):
    data = load_votes()
    active_vote = next((v for v in data.values()), None)

    if not active_vote:
        await update.message.reply_text("Голосование не активно.")
        return

    admin_id = active_vote.get("admin_id")
    if not admin_id or admin_id != update.effective_user.id:
        await update.message.reply_text("Вы не являетесь автором этого голосования.")
        return

    # Генерация voters_list.txt
    voters_file = "voters_list.txt"
    with open(voters_file, 'w', encoding='utf-8') as f:
        f.write("Nickname;ID;Choice;Voted at\n")
        for user_id, choice in active_vote["voters"].items():
            try:
                user = await context.bot.get_chat(int(user_id))
                nickname = user.username or "Неизвестный"
                vote_time = datetime.fromisoformat(active_vote["started_at"])
                line = f"{nickname};{user_id};{active_vote['options'][choice]};{vote_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f.write(line)
            except Exception as e:
                log_event('error', f"Ошибка получения данных пользователя {user_id}: {e}")

    # Получение всех участников группы
    chat_id = active_vote.get('chat_id_for_vote')
    try:
        members = await context.bot.get_chat_members(chat_id)
        all_users = [str(m.user.id) for m in members]
    except Exception as e:
        log_event('error', f"Ошибка получения участников: {e}")
        return

    non_voters = [uid for uid in all_users if uid not in active_vote["voters"]]

    # Генерация non_voters_list.txt
    non_voters_file = "non_voters_list.txt"
    with open(non_voters_file, 'w', encoding='utf-8') as f:
        f.write("Nickname;ID\n")
        for member in non_voters:
            try:
                user = await context.bot.get_chat(int(member))
                nickname = user.username or "Неизвестный"
                f.write(f"{nickname};{member}\n")
            except Exception as e:
                log_event('error', f"Ошибка получения данных пользователя {member}: {e}")
                f.write(f"Неизвестный;{member}\n")

    # Отправка файлов только админу
    try:
        await context.bot.send_message(admin_id, "Результаты голосования:")
        with open(voters_file, 'rb') as f:
            await context.bot.send_document(admin_id, document=InputFile(f), caption="Список тех, кто проголосовал")

        with open(non_voters_file, 'rb') as f:
            await context.bot.send_document(admin_id, document=InputFile(f), caption="Список тех, кто не участвовал")
    except Exception as e:
        log_event('error', f"Ошибка отправки результатов админу: {e}")

    # Очистка временных файлов
    os.remove(voters_file)
    os.remove(non_voters_file)

# -------------------
# ⚠️ Исключение пользователей
# -------------------
async def kick_non_voters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    bot = context.bot

    # Получаем список исключаемых
    data = load_votes()
    active_vote = next((v for v in data.values()), None)
    if not active_vote:
        await update.message.reply_text("Голосование не найдено.")
        return

    try:
        members = await bot.get_chat_members(chat_id)
        all_users = [str(m.user.id) for m in members]
    except Exception as e:
        log_event('error', f"Ошибка получения участников: {e}")
        return

    non_voter_ids = [uid for uid in all_users if uid not in active_vote["voters"]]
    if not non_voter_ids:
        await update.message.reply_text("Нет пользователей для исключения.")
        return

    create_kick_file(non_voter_ids, "kick_list.txt")

    with open("kick_list.txt", "rb") as f:
        await update.message.reply_document(document=InputFile(f), caption="Список пользователей, которые будут исключены.")

    keyboard = [
        [InlineKeyboardButton("Изменить список", callback_data="edit_list"),
         InlineKeyboardButton("Продолжить", callback_data="continue_kick")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Хотите изменить список? Загрузите новый файл или нажмите кнопку.", reply_markup=reply_markup)

    context.user_data['non_voter_ids'] = non_voter_ids
    return WAITING_FOR_FILE_OR_CONTINUE

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data == "edit_list":
        await query.answer("Пожалуйста, загрузите новый файл со списком.")
        return WAITING_FOR_FILE_OR_CONTINUE
    elif data == "continue_kick":
        await query.answer("Подтвердите действие.")
        await query.message.reply_text("Вы уверены? Да / Нет")
        return CONFIRM_KICK

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    path = await file.download_to_drive(custom_path="updated_kick_list.txt")

    new_user_ids = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()[1:]
        for line in lines:
            parts = line.strip().split(";")
            if len(parts) >= 2:
                new_user_ids.append(parts[1])

    context.user_data['non_voter_ids'] = new_user_ids
    await update.message.reply_text("Список обновлён. Подтвердите действие: Да / Нет")
    return CONFIRM_KICK

async def confirm_kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.message.text.lower()

    if answer == "да":
        non_voter_ids = context.user_data.get('non_voter_ids', [])
        chat_id = update.effective_chat.id
        bot = context.bot

        for user_id in non_voter_ids:
            try:
                await bot.ban_chat_member(chat_id, int(user_id))
                log_event('info', f"Пользователь {user_id} был исключен.")
            except Exception as e:
                log_event('error', f"Ошибка исключения пользователя {user_id}: {e}")

        await update.message.reply_text("Процедура исключения завершена.")

    elif answer == "нет":
        await update.message.reply_text("Действие отменено.")

    return ConversationHandler.END

# -------------------
# 🧪 Вспомогательные функции
# -------------------
def create_kick_file(users, filename="kick_list.txt"):
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("Nickname;ID\n")
        for user_id in users:
            try:
                user = context.bot.get_chat(int(user_id))
                nickname = user.username or "Неизвестный"
                f.write(f"{nickname};{user_id}\n")
            except Exception as e:
                f.write(f"Неизвестный;{user_id}\n")

# -------------------
# 🧩 Регистрация обработчиков
# -------------------
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start_vote', start_vote)],
    states={
        TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_text)],
        OPTIONS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_options)],
        DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_duration)],
        CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_start)]
    },
    fallbacks=[]
)

kick_handler = ConversationHandler(
    entry_points=[CommandHandler("kick_non_voters", kick_non_voters)],
    states={
        WAITING_FOR_FILE_OR_CONTINUE: [
            CallbackQueryHandler(handle_button),
            MessageHandler(filters.Document.TEXT & ~filters.COMMAND, handle_file)
        ],
        CONFIRM_KICK: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_kick)
        ]
    },
    fallbacks=[]
)

# -------------------
# 🌐 Flask App & Webhook
# -------------------
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    from telegram.ext importApplicationBuilder
    data = request.get_json(force=True)
    update = Update.de_json(data, ApplicationBuilder().token(os.getenv("TOKEN")).build())
    asyncio.run(app.dispatcher.process_update(update))
    return 'ok'

# -------------------
# 🚀 Запуск бота
# -------------------
load_dotenv()
app.dispatcher = ApplicationBuilder().token(os.getenv("TOKEN")).build().dispatcher

app.add_handler(conv_handler)
app.add_handler(kick_handler)
app.add_handler(CallbackQueryHandler(handle_vote))
app.add_handler(CommandHandler('end_vote', end_vote))

if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 80))
    app.run(host='0.0.0.0', port=PORT)
