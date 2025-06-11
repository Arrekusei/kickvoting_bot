from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler
import os
import logging
import asyncio
from flask import Flask, request

# -------------------
# 🔧 Настройка логгера
# -------------------
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
application = ApplicationBuilder().token(os.getenv("TOKEN")).build()

# -------------------
# 🚀 Команда /test
# -------------------
async def test_command(update: Update, context):
    await update.message.reply_text("Бот жив!")

# -------------------
# 📤 Регистрация обработчиков
# -------------------
application.add_handler(CommandHandler('test', test_command))  # <-- Важно!

# -------------------
# 🌐 Функция webhook
# -------------------
@app.route('/webhook', methods=['POST'])
def webhook():
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
    PORT = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=PORT)
