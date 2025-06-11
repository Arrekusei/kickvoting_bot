from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler
import os
import logging
import asyncio
from flask import Flask, request
import threading

# -------------------
# 🔧 Настройка логгера
# -------------------
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
application = None  # Объявляем глобально

# -------------------
# 🚀 Команда /test
# -------------------
async def test_command(update: Update, context):
    await update.message.reply_text("Бот жив!")

# -------------------
# 📤 Регистрация обработчиков
# -------------------
def setup_bot():
    global application
    application = ApplicationBuilder().token(os.getenv("TOKEN")).build()
    application.add_handler(CommandHandler('test', test_command))

# -------------------
# 🌐 Функция webhook
# -------------------
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    logging.info(f"Получено: {data}")

    if application is None:
        logging.error("Application не инициализирован")
        return 'error', 500

    try:
        update = Update.de_json(data, application.bot)
        asyncio.run(application.update_queue.put(update))
        logging.debug("Сообщение добавлено в очередь")
    except Exception as e:
        logging.error(f"Ошибка при обработке: {e}")

    return 'ok'

@app.route('/')
def index():
    return "Bot is running!"

# -------------------
# 🔄 Запуск PTB в отдельном потоке
# -------------------
def run_ptb_app():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    application.run_polling(poll_interval=0.5)  # <-- Не забудь удалить это позже

# -------------------
# 🚀 Запуск сервиса
# -------------------
if __name__ == '__main__':
    PORT = int(os.environ.get("PORT", 10000))
    
    # Инициализация бота
    setup_bot()

    # Запуск PTB в отдельном потоке
    ptb_thread = threading.Thread(target=run_ptb_app, daemon=True)
    ptb_thread.start()

    # Запуск Flask
    app.run(host='0.0.0.0', port=PORT)
