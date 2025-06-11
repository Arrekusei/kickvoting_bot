from telegram.ext import ApplicationBuilder, CommandHandler
from telegram import Update
import os
import logging

# -------------------
# 🔧 Настройка логгера
# -------------------
logging.basicConfig(level=logging.DEBUG)

# -------------------
# 🚀 Инициализация бота
# -------------------
application = ApplicationBuilder().token(os.getenv("TOKEN")).build()

# -------------------
# 🚀 Команда /test
# -------------------
async def test_command(update: Update, context):
    await update.message.reply_text("Бот жив!")

application.add_handler(CommandHandler('test', test_command))

# -------------------
# 🚀 Запуск бота
# -------------------
application.run_polling()
