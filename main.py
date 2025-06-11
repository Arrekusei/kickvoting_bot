from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import os
import logging
import json
import asyncio
from flask import Flask, request

# -------------------
# 🔧 Настройка логгера
# -------------------
logging.basicConfig(level=logging.DEBUG)

# -------------------
# 🚀 Инициализация бота
# -------------------
application = ApplicationBuilder().token(os.getenv("TOKEN")).build()

# -------------------
# 🗂 Хранилище голосований
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
# 🗳 Команда /vote — показ кнопок
# -------------------
async def vote_command(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("Да", callback_data="yes"),
         InlineKeyboardButton("Нет", callback_data="no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Какой ваш выбор?", reply_markup=reply_markup)

# -------------------
# 🔄 Обработка нажатий на кнопки
# -------------------
async def handle_vote(update: Update, context):
    query = update.callback_query
    data = query.data
    user_id = str(query.from_user.id)

    votes = load_votes()
    current_vote = votes["current_vote"]
    if not current_vote:
        await query.answer("Голосование не начато.")
        return

    # Сохраняем голос
    current_vote["voters"][user_id] = data
    save_votes(votes)

    # Всплывающее сообщение
    await query.answer(f"Вы выбрали: {data}")

    # Сообщение в чат
    await query.message.reply_text(f"Ваш выбор: {data}")

# -------------------
# 🛑 Команда /end_vote — завершение голосования
# -------------------
async def end_vote_command(update: Update, context):
    votes = load_votes()
    current_vote = votes["current_vote"]
    if not current_vote:
        await update.message.reply_text("Голосование не начато.")
        return

    # Подсчёт результатов
    results = {}
    for vote in current_vote["voters"].values():
        results[vote] = results.get(vote, 0) + 1

    result_text = "Результаты голосования:\n"
    for option, count in results.items():
        result_text += f"{option}: {count} голос(а/ов)\n"

    # Отправляем результаты в чат
    await update.message.reply_text(result_text)

    # Очищаем голосование
    votes["current_vote"] = None
    save_votes(votes)

    logging.info("Голосование завершено.")

# -------------------
# 📊 Команда /results — отображение результатов (для админов)
# -------------------
async def results_command(update: Update, context):
    votes = load_votes()
    current_vote = votes["current_vote"]
    if not current_vote or not current_vote["voters"]:
        await update.message.reply_text("Голосование не было проведено или ещё не началось.")
        return

    # Подсчёт результатов
    results = {}
    for vote in current_vote["voters"].values():
        results[vote] = results.get(vote, 0) + 1

    result_text = "Результаты голосования:\n"
    for option, count in results.items():
        result_text += f"{option}: {count} голос(а/ов)\n"

    await update.message.reply_text(result_text)
    logging.info("Отправлены результаты голосования.")

# -------------------
# 🚀 Команда /test — для тестирования
# -------------------
async def test_command(update: Update, context):
    await update.message.reply_text("Бот жив!")

# -------------------
# 🧪 Регистрация обработчиков
# -------------------
application.add_handler(CommandHandler('test', test_command))
application.add_handler(CommandHandler('vote', vote_command))
application.add_handler(CommandHandler('end_vote', end_vote_command))
application.add_handler(CommandHandler('results', results_command))
application.add_handler(CallbackQueryHandler(handle_vote))

# -------------------
# 🌐 Flask App & Webhook
# -------------------
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def webhook():
    from telegram.ext import Update
    data = request.get_json()
    logging.info(f"Получено: {data}")
    update = Update.de_json(data, application.bot)
    asyncio.run(application.update_queue.put(update))
    return 'ok'

@app.route('/')
def index():
    return "Bot is running!"

# -------------------
# 🚀 Запуск сервиса
# -------------------
if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 80))
    app.run(host='0.0.0.0', port=PORT)
