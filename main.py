import os
import asyncio
import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from fetcher import fetcher_loop
from notifier import Notifier

# Загружаем переменные окружения (.env)
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "60"))

if not TOKEN or not ADMIN_ID:
    raise SystemExit("❌ Не заданы BOT_TOKEN или ADMIN_ID в переменных окружения!")

# Команды Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот ставок активен и готов присылать сигналы!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"📡 Бот работает.\n⏰ Последняя проверка: {now} UTC")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 Остановка не реализована в этой версии бота.")

# Фоновая задача (периодическая проверка)
async def background_task(app):
    notifier = Notifier(app.bot, int(ADMIN_ID))
    await fetcher_loop(notifier, update_interval=UPDATE_INTERVAL)

# Основной запуск
async def main():
    application = ApplicationBuilder().token(TOKEN).build()

    # Регистрируем команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stop", stop))

    # Запуск фоновой задачи
    asyncio.create_task(background_task(application))

    print("✅ Бот успешно запущен и ожидает команды в Telegram...")
    await application.run_polling(close_loop=False)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Бот остановлен вручную.")
