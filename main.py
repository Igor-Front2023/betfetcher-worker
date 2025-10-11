# main.py - entrypoint for Render
import os
import asyncio
import signal
import datetime
import traceback
from aiohttp import web
from telegram.ext import Application, CommandHandler, ContextTypes
from notifier import Notifier
from fetcher import fetcher_loop

def get_env(name: str, required: bool = True, default=None):
    v = os.getenv(name, default)
    if required and (v is None or v == ""):
        raise SystemExit(f"❌ Environment variable {name} is required.")
    return v

BOT_TOKEN = get_env("BOT_TOKEN")
ADMIN_CHAT_ID = int(get_env("ADMIN_CHAT_ID"))
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "180"))
HTTP_PORT = int(os.getenv("PORT", "10000"))
ENABLE_POLLING = os.getenv("ENABLE_POLLING", "0")  # set to "1" to enable polling (not recommended on Render)

def log(msg: str):
    t = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t} UTC] {msg}", flush=True)

# Telegram commands
async def cmd_start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot is running.")

async def cmd_status(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is active.")

# Web healthcheck
async def handle_root(request):
    return web.Response(text="✅ Bot is running on Render!")

async def start_web_server(port):
    web_app = web.Application()
    web_app.router.add_get("/", handle_root)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log(f"🌐 Web server started on port {port}")
    return runner

async def main():
    application = Application.builder().token(BOT_TOKEN.strip()).build()
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("status", cmd_status))

    notifier = Notifier(application.bot, ADMIN_CHAT_ID)

    # start web server
    runner = await start_web_server(HTTP_PORT)

    # Initialize application without polling by default to avoid getUpdates conflicts
    await application.initialize()
    await application.start()
    if ENABLE_POLLING == "1":
        await application.updater.start_polling()
        log("✅ Telegram polling started (ENABLE_POLLING=1)")
    else:
        log("ℹ️ Telegram initialized (polling disabled)")

    # start fetcher loop in background
    fetcher_task = asyncio.create_task(fetcher_loop(notifier, update_interval=UPDATE_INTERVAL))

    # notify admin
    try:
        await notifier.notify("✅ Bot started on Render.")
    except Exception:
        pass

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: stop_event.set())
        except NotImplementedError:
            pass

    await stop_event.wait()
    log("🛑 Shutdown initiated")

    fetcher_task.cancel()
    try:
        await fetcher_task
    except asyncio.CancelledError:
        pass

    if ENABLE_POLLING == "1":
        await application.updater.stop_polling()
    await application.stop()
    await application.shutdown()
    await runner.cleanup()
    log("✅ Shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("Fatal error", e)
        traceback.print_exc()
