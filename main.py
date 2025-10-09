import os
import asyncio
from aiohttp import web
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# --- Telegram команды ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот успешно работает на Render 🚀")

# --- Создаём Telegram Application ---
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

# --- Простой HTTP-сервер (чтобы Render видел порт) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def run_web_server():
    port = int(os.getenv("PORT", 10000))
    web_app = web.Application()
    web_app.router.add_get("/", handle)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Web server started on port {port}")

# --- Главный цикл ---
async def main():
    print("🚀 Initializing bot...")
    await app.initialize()
    await app.start()
    print("🤖 Bot started successfully!")

    # запускаем HTTP сервер параллельно с polling
    server_task = asyncio.create_task(run_web_server())
    polling_task = asyncio.create_task(app.updater.start_polling())

    await asyncio.gather(server_task, polling_task)

    # по завершению корректно останавливаем
    await app.stop()
    await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
