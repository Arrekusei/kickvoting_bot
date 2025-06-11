from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler
from flask import Flask, request
import os
import asyncio
import logging

# -------------------
# 🔧 Логгер
# -------------------
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
application = ApplicationBuilder().token(os.getenv("TOKEN")).build()

# -------------------
# 🚀 Команда /test
# -------------------
async def test_command(update: Update, context):
    await update.message.reply_text("Бот жив!")

application.add_handler(CommandHandler('test', test_command))

# -------------------
# 🌐 Webhook
# -------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    logging.info(f"Получено: {data}")
    
    try:
        update = Update.de_json(data, application.bot)
        asyncio.run(application.update_queue.put(update))
        logging.debug("Сообщение добавлено в очередь")
    except Exception as e:
        logging.error(f"Ошибка: {e}")

    return 'ok'

@app.route('/')
def index():
    return "Bot is running!"

# -------------------
# 🚀 Запуск
# -------------------
if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=PORT)
