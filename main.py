from telegram.ext import ApplicationBuilder, CommandHandler
from flask import Flask, request
import os
import asyncio
import logging

# Настройка логгера
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
application = ApplicationBuilder().token(os.getenv("TOKEN")).build()

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    logging.info(f"Получено: {data}")
    update = Update.de_json(data, application.bot)
    asyncio.run(application.update_queue.put(update))
    return 'ok'

@app.route('/')
def index():
    return "Бот жив!"

# Тестовая команда
async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот жив!")

application.add_handler(CommandHandler('test', test_command))

if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 80))
    app.run(host='0.0.0.0', port=PORT)
