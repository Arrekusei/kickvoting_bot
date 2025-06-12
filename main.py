import os
import json
from datetime import datetime, timedelta
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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
import re

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
        return {"current_vote": None}
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
        vote_id = len(data.get("history", [])) + 1
        admin_id = context.user_data.get('admin_id')

        # Сохраняем данные голосования
        data["current_vote"] = {
            "id": vote_id,
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
        chat_id = -1001234567890  # Замени на ID реальной группы
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
# 🗳 Обработка голосов
# -------------------
async def handle_vote(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = str(query.from_user.id)
    choice = int(query.data)

    data = load_votes()
    current_vote = data.get("current_vote")
    if not current_vote:
        await query.answer("Голосование не активно.")
        return

    if choice >= len(current_vote["options"]):
        await query.answer("Неверный вариант.")
        return

    current_vote["voters"][user_id] = choice
    data["history"].append(current_vote)
    data["current_vote"] = None
    save_votes(data)
    await query.answer("Ваш голос учтён.")

# -------------------
# 📊 Команда /end_vote
# -------------------
async def end_vote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_votes()
    current_vote = data.get("current_vote")
    if not current_vote:
        await update.message.reply_text("Голосование не найдено.")
        return

    admin_id = current_vote.get("admin_id")
    if admin_id != update.effective_user.id:
        await update.message.reply_text("Вы не являетесь автором этого голосования.")
        return

    # Генерация voters_list.txt
    voters_file = "voters_list.txt"
    with open(voters_file, 'w', encoding='utf-8') as f:
        f.write("Nickname;ID;Choice;Voted at\n")
        for user_id, choice in current_vote["voters"].items():
            try:
                user = await context.bot.get_chat(int(user_id))
                nickname = user.username or "Неизвестный"
                vote_time = datetime.fromisoformat(current_vote["started_at"])
                line = f"{nickname};{user_id};{current_vote['options'][choice]};{vote_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f.write(line)
            except Exception as e:
                log_event('error', f"Ошибка получения данных пользователя {user_id}: {e}")

    # Получение всех участников группы
    chat_id = current_vote.get("chat_id_for_vote")
    try:
        members = await context.bot.get_chat_members(chat_id)
        all_users = [str(m.user.id) for m in members]
    except Exception as e:
        log_event('error', f"Ошибка получения участников: {e}")
        return

    non_voters = [uid for uid in all_users if uid not in current_vote["voters"]]

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
            await context.bot.send_document(admin_id, document=f, caption="Список тех, кто проголосовал")

        with open(non_voters_file, 'rb') as f:
            await context.bot.send_document(admin_id, document=f, caption="Список тех, кто не участвовал")
    except Exception as e:
        log_event('error', f"Ошибка отправки результатов админу: {e}")

    # Очистка временных файлов
    os.remove(voters_file)
    os.remove(non_voters_file)

# -------------------
# ⚠️ Команда /kick_non_voters
# -------------------
async def kick_non_voters(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_votes()
    current_vote = data.get("current_vote")
    if not current_vote:
        await update.message.reply_text("Голосование не найдено.")
        return

    admin_id = current_vote.get("admin_id")
    if admin_id != update.effective_user.id:
        await update.message.reply_text("Вы не являетесь автором этого голосования.")
        return

    chat_id = update.effective_chat.id

    try:
        members = await context.bot.get_chat_members(chat_id)
        all_users = [str(m.user.id) for m in members]
    except Exception as e:
        log_event('error', f"Ошибка получения участников: {e}")
        return

    non_voter_ids = [uid for uid in all_users if uid not in current_vote["voters"]]
    if not non_voter_ids:
        await update.message.reply_text("Нет пользователей для исключения.")
        return

    create_kick_file(non_voter_ids, "kick_list.txt")

    with open("kick_list.txt", "rb") as f:
        await context.bot.send_document(admin_id, document=f, caption="Список пользователей, которые будут исключены.")

    keyboard = [
        [InlineKeyboardButton("Изменить список", callback_data="edit_list"),
         InlineKeyboardButton("Продолжить", callback_data="continue_kick")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Хотите изменить список? Загрузите новый файл или нажмите кнопку.", reply_markup=reply_markup)

    context.user_data['non_voter_ids'] = non_voter_ids
    return WAITING_FOR_FILE_OR_CONTINUE

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

application = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()

application.add_handler(conv_handler)
application.add_handler(CallbackQueryHandler(handle_vote))
application.add_handler(CommandHandler('end_vote', end_vote_command))
application.add_handler(CommandHandler('kick_non_voters', kick_non_voters))

# -------------------
# 🚀 Запуск бота
# -------------------
if __name__ == '__main__':
    application.run_polling()
