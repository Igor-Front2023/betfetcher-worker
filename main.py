import os
import asyncio
import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "180"))

if not TOKEN or not ADMIN_ID:
    raise SystemExit("❌ Укажи BOT_TOKEN и ADMIN_ID в переменных окружения Render!")

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот ставок запущен и работает!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"📡 Бот активен.\nПоследняя проверка: {now}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 Остановка фонового процесса не реализована.")

# === Фоновая задача ===
async def fetcher_loop(bot):
    while True:
        try:
            print("🔄 Проверка линии ставок...")
            await bot.send_message(chat_id=ADMIN_ID, text="📊 Тестовый сигнал: бот работает!")
            await asyncio.sleep(UPDATE_INTERVAL)
        except Exception as e:
            print(f"⚠️ Ошибка в fetcher_loop: {e}")
            await asyncio.sleep(10)

# === Запуск ===
async def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stop", stop))

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    asyncio.create_task(fetcher_loop(app.bot))

    print("✅ Bot started. Listening for commands...")

    # держим процесс живым
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
