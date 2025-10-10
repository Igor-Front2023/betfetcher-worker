# main.py
import os
import asyncio
import signal
import datetime
import traceback
from typing import Dict, Any
from aiohttp import web
from telegram.ext import Application, CommandHandler, ContextTypes
from notifier import Notifier
from fetcher import fetcher_loop, tracked_signals

# Конфиг
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "180"))
HTTP_PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise SystemExit("❌ BOT_TOKEN не задан.")
if not ADMIN_ID:
    raise SystemExit("❌ ADMIN_ID не задан.")
ADMIN_ID = int(ADMIN_ID)

def log(msg: str):
    t = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t} UTC] {msg}", flush=True)

# Telegram handlers
async def cmd_start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот запущен и работает. Используйте /status.")

async def cmd_status(update, context: ContextTypes.DEFAULT_TYPE):
    active = len(tracked_signals)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"✅ Бот активен. Отслеживаем сигналов: {active}\n{now} UTC")

# веб-хендлер для проверки доступности
async def handle_root(request):
    return web.Response(text="✅ Bot is running!")

async def start_web_server(runner_container):
    web_app = web.Application()
    web_app.router.add_get("/", handle_root)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await site.start()
    runner_container["runner"] = runner
    log(f"🌐 Web server started on port {HTTP_PORT}")

async def stop_web_server(runner_container):
    runner = runner_container.get("runner")
    if runner:
        await runner.cleanup()
        log("🌐 Web server stopped")

async def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("status", cmd_status))

    log("🚀 Initializing bot...")
    await application.initialize()
    await application.start()
    # start polling
    await application.updater.start_polling()
    log("✅ Telegram polling started")

    notifier = Notifier(application.bot, ADMIN_ID)

    runner_container = {}
    web_task = asyncio.create_task(start_web_server(runner_container))
    fetcher_task = asyncio.create_task(fetcher_loop(notifier, update_interval=UPDATE_INTERVAL))

    try:
        await notifier.notify("✅ Бот успешно запущен.")
    except Exception:
        pass

    # graceful shutdown on signals
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    def _on_signal():
        stop_event.set()
    try:
        loop.add_signal_handler(signal.SIGINT, _on_signal)
        loop.add_signal_handler(signal.SIGTERM, _on_signal)
    except NotImplementedError:
        pass

    await stop_event.wait()
    log("🛑 Stopping...")

    fetcher_task.cancel()
    try:
        await fetcher_task
    except asyncio.CancelledError:
        pass

    await application.updater.stop_polling()
    await application.stop()
    await application.shutdown()
    await stop_web_server(runner_container)
    log("✅ Graceful shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("Fatal error in main:", e)
        raise
