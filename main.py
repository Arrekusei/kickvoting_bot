from telegram.ext import ApplicationBuilder, CommandHandler
from telegram import Update
import os
import logging

# -------------------
# 🔧 Настройка логгера
# -------------------
logging.basicConfig(level=logging.DEBUG)

# -------------------
# 🚀 Команда /test
# -------------------
async def test_command(update: Update, context):
    await update.message.reply_text("Бот жив!")

# -------------------
# 📤 Регистрация обработчиков
# -------------------
application = ApplicationBuilder().token(os.getenv("TOKEN")).build()
application.add_handler(CommandHandler('test', test_command))

# -------------------
# 🚀 Запуск бота
# -------------------
application.run_polling()
