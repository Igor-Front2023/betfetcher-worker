import os
import asyncio
from aiohttp import web
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# --- Команды телеграм-бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот успешно запущен на Render 🚀")

# --- Telegram App ---
app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

# --- HTTP сервер (Render требует порт) ---
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
    print(f"✅ Web server running on port {port}")

# --- Главный запуск ---
async def main():
    print("🚀 Starting bot...")
    await asyncio.gather(
        app.run_polling(),
        run_web_server()
    )

if __name__ == "__main__":
    asyncio.run(main())
