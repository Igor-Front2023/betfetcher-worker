import os
import asyncio
import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Загружаем .env
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "180"))  # интервал в секундах (по умолчанию 3 мин)

if not TOKEN or not ADMIN_ID:
    raise SystemExit("❌ Пожалуйста, укажи BOT_TOKEN и ADMIN_ID в переменных окружения.")

# === Команды бота ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот ставок запущен и готов к работе!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"📡 Бот активен.\nПоследняя проверка: {now}")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🛑 Остановка фоновой задачи не реализована.")

# === Уведомление админа при ошибках ===
async def notify_admin(bot, message: str):
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=message)
    except Exception as e:
        print(f"⚠️ Ошибка при уведомлении админа: {e}")

# === Фоновая задача ===
async def fetcher_loop(bot):
    """Основной цикл — парсинг или API-запросы"""
    while True:
        try:
            print("🔄 Проверка линии ставок...")

            # --- Твоя логика парсинга или сбора данных ---
            # Например: await fetch_latest_bets()
            # Или просто тестовое уведомление:
            await bot.send_message(chat_id=ADMIN_ID, text="📊 Тестовый сигнал: бот работает!")

            await asyncio.sleep(UPDATE_INTERVAL)
        except Exception as e:
            error_msg = f"⚠️ Ошибка в fetcher_loop:\n{e}"
            print(error_msg)
            await notify_admin(bot, error_msg)
            await asyncio.sleep(10)  # перезапуск через 10 сек

# === Основной запуск ===
async def main_async():
    app = ApplicationBuilder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("stop", stop))

    # Запуск фоновой задачи
    asyncio.create_task(fetcher_loop(app.bot))

    print("✅ Bot started. Listening for commands...")
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main_async())
