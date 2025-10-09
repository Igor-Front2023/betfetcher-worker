import os
import asyncio
import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from fetcher import fetcher_loop
from notifier import Notifier

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "60"))

if not TOKEN or not ADMIN_ID:
    raise SystemExit("Please set BOT_TOKEN and ADMIN_ID in environment variables.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот ставок активен. Я буду присылать сигналы сюда.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"📡 Бот работает. Последняя проверка: {now} UTC")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 Остановка не реализована в этой версии.")

async def background_task(app):
    notifier = Notifier(app.bot, int(ADMIN_ID))
    await fetcher_loop(notifier, update_interval=UPDATE_INTERVAL)

async def main_async():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stop", stop))
    asyncio.create_task(background_task(app))
    print("✅ Bot started. Listening for commands...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main_async())
