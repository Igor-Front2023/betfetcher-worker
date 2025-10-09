import os
import asyncio
import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from fetcher import fetcher_loop
from notifier import Notifier

# Загружаем переменные окружения
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "60"))

# Проверка на наличие обязательных переменных
if not TOKEN or not ADMIN_ID:
    raise SystemExit("❌ Please set BOT_TOKEN and ADMIN_ID in environment variables.")

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот ставок активен. Я буду присылать сигналы сюда.")

# Команда /status
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"📡 Бот работает. Последняя проверка: {now} UTC")

# Команда /stop (пока не активна)
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 Остановка не реализована в этой версии.")

# Фоновая задача
async def background_task(app):
    notifier = Notifier(app.bot, int(ADMIN_ID))
    await fetcher_loop(notifier, update_interval=UPDATE_INTERVAL)

# Основная асинхронная функция
async def main_async():
    # Создаём экземпляр бота
    app = ApplicationBuilder().token(TOKEN).build()

    # Добавляем команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stop", stop))

    # Запускаем фоновый цикл
    asyncio.create_task(background_task(app))

    print("✅ Bot started and is listening for commands...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

# Точка входа
if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Bot stopped manually.")

