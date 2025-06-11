from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import os
import logging

# -------------------
# 🔧 Логгер
# -------------------
logging.basicConfig(level=logging.DEBUG)

# -------------------
# 🚀 Инициализация
# -------------------
application = ApplicationBuilder().token(os.getenv("TOKEN")).build()

# -------------------
# 🗳 Команда /vote
# -------------------
async def vote_command(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("Да", callback_data="yes"),
         InlineKeyboardButton("Нет", callback_data="no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Какой ваш выбор?", reply_markup=reply_markup)


# -------------------
# 🗳 Команда /test
# -------------------
async def test_command(update: Update, context):
    await update.message.reply_text("Бот жив!")

# -------------------
# 🔄 Обработка нажатий на кнопки
# -------------------
async def handle_vote(update: Update, context):
    query = update.callback_query
    data = query.data
    user = query.from_user
    logging.info(f"Пользователь {user.username} ({user.id}) выбрал '{data}'")
    # Всплывающее сообщение
    await query.answer(f"Вы выбрали: {data}")
    # Ответ в чат
    await query.message.reply_text(f"Ваш выбор: {data}")

# -------------------
# 📤 Регистрация обработчиков
# -------------------
application.add_handler(CommandHandler('test', test_command))
application.add_handler(CommandHandler('vote', vote_command))
application.add_handler(CallbackQueryHandler(handle_vote))

# -------------------
# 🚀 Запуск бота
# -------------------
application.run_polling()
