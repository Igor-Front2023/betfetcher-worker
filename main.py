# main.py
import os
import asyncio
import signal
import datetime
import traceback
from aiohttp import web
from telegram.ext import Application, CommandHandler, ContextTypes
from notifier import Notifier
from fetcher import fetcher_loop


# === 🔧 Конфигурация из переменных окружения ===
def get_env(name: str, required: bool = True, default=None):
    """Безопасное получение переменных окружения"""
    value = os.getenv(name, default)
    if required and not value:
        raise SystemExit(f"❌ Переменная {name} не задана (добавь в Render → Environment).")
    return value


BOT_TOKEN = get_env("BOT_TOKEN")
ADMIN_CHAT_ID = int(get_env("ADMIN_CHAT_ID"))
UPDATE_INTERVAL = int(get_env("UPDATE_INTERVAL", required=False, default="180"))
HTTP_PORT = int(get_env("PORT", required=False, default="10000"))


# === 🧠 Утилиты ===
def log(msg: str):
    """Форматированный лог в консоль"""
    t = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t} UTC] {msg}", flush=True)


# === 🤖 Команды Telegram ===
async def cmd_start(update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот запущен и готов к работе.\nИспользуйте /status для проверки состояния.")

async def cmd_status(update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"✅ Бот активен\n{now} UTC")


# === 🌐 HTTP сервер (для Render Healthcheck) ===
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


# === 🚀 Главная функция ===
async def main():
    log("🚀 Initializing Telegram bot...")

    try:
        application = Application.builder().token(BOT_TOKEN.strip()).build()
    except Exception as e:
        raise SystemExit(f"❌ Ошибка при инициализации бота. Проверь токен. ({e})")

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("status", cmd_status))

    notifier = Notifier(application.bot, ADMIN_CHAT_ID)

    # Запуск Telegram и HTTP
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    log("✅ Telegram polling started")

    runner_container = {}
    web_task = asyncio.create_task(start_web_server(runner_container))
    fetcher_task = asyncio.create_task(fetcher_loop(notifier, update_interval=UPDATE_INTERVAL))

    try:
        await notifier.notify("✅ Бот успешно запущен и готов к анализу событий.")
    except Exception as e:
        log(f"⚠️ Не удалось отправить уведомление админу: {e}")

    # Контроль сигналов
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def _on_signal():
        stop_event.set()

    try:
        loop.add_signal_handler(signal.SIGINT, _on_signal)
        loop.add_signal_handler(signal.SIGTERM, _on_signal)
    except NotImplementedError:
        pass  # для Windows и Render

    await stop_event.wait()
    log("🛑 Остановка бота...")

    # Завершение
    fetcher_task.cancel()
    try:
        await fetcher_task
    except asyncio.CancelledError:
        pass

    await application.updater.stop_polling()
    await application.stop()
    await application.shutdown()
    await stop_web_server(runner_container)
    log("✅ Завершение работы успешно.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print("❌ Fatal error in main:", e)
        traceback.print_exc()
