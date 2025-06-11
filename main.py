from telegram.ext import ApplicationBuilder, CommandHandler
from telegram import Update
from flask import Flask, request
import os
import asyncio
import logging

# -------------------
# 🔧 Настройка логгера
# -------------------
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
application = ApplicationBuilder().token(os.getenv("TOKEN")).build()

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    logging.info(f"Получено: {data}")
    update = Update.de_json(data, application.bot)  # <-- теперь работает
    asyncio.run(application.update_queue.put(update))
    return 'ok'

@app.route('/')
def index():
    return "Бот жив!"

# -------------------
# 🚀 Команда /test
# -------------------
async def test_command(update, context):
    user = update.effective_user
    chat_id = update.effective_chat.id
    logging.debug(f"Пользователь {user.username} ({user.id}) написал /test")
    await update.message.reply_text("Бот жив!")

application.add_handler(CommandHandler('test', test_command))

# -------------------
# 🚀 Запуск Flask
# -------------------
if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 80))
    app.run(host='0.0.0.0', port=PORT)
