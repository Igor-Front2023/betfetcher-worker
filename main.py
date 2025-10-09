import os
import asyncio
import signal
import datetime
import traceback
from typing import Optional, Dict, Any

from dotenv import load_dotenv
import aiohttp
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

# === Конфигурация ===
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
API_URL = os.getenv("API_URL", "").strip()
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "180"))
PORT = int(os.getenv("PORT", "10000"))  # Render передаёт порт сюда

if not TOKEN:
    raise SystemExit("❌ BOT_TOKEN не задан.")
if not ADMIN_ID:
    raise SystemExit("❌ ADMIN_ID не задан.")
ADMIN_ID = int(ADMIN_ID)


# === Лог ===
def log(msg: str):
    t = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t} UTC] {msg}", flush=True)


# === Уведомления ===
class Notifier:
    def __init__(self, bot):
        self.bot = bot

    async def notify(self, text: str):
        try:
            await self.bot.send_message(chat_id=ADMIN_ID, text=text[:4000])
        except Exception as e:
            log(f"Notifier error: {e}")


# === Получение данных из API ===
async def get_odds_from_api(session: aiohttp.ClientSession) -> Optional[list]:
    if not API_URL:
        return None
    try:
        async with session.get(API_URL, timeout=20) as resp:
            resp.raise_for_status()
            data = await resp.json()
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            if isinstance(data, list):
                return data
            return None
    except Exception as e:
        log(f"API fetch error: {e}")
        return None


# === Состояние ===
tracked_signals: Dict[str, Dict[str, Any]] = {}


# === Основной цикл парсера ===
async def fetcher_loop(bot, notifier: Notifier, update_interval: int = 180):
    backoff = 5
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                events = await get_odds_from_api(session)
                if events:
                    for ev in events:
                        event_id = str(ev.get("id") or ev.get("event_id") or ev.get("name"))
                        if not event_id:
                            continue
                        if event_id in tracked_signals:
                            continue

                        odds = None
                        o = ev.get("odds") or {}
                        if isinstance(o, dict):
                            for k in ("home", "P1", "1", "odds", "price"):
                                v = o.get(k)
                                if v:
                                    try:
                                        odds = float(v)
                                        break
                                    except:
                                        pass

                        if odds and 1.05 <= odds <= 1.33:
                            text = (
                                f"[SIGNAL]\n"
                                f"Event: {ev.get('name') or 'Unknown'}\n"
                                f"Odds: {odds}\n"
                                f"Event ID: {event_id}"
                            )
                            await notifier.notify(text)
                            tracked_signals[event_id] = {"odds": odds}
                else:
                    await notifier.notify("[heartbeat] Бот жив, но нет событий.")
            await asyncio.sleep(update_interval)
            backoff = 5
        except Exception as e:
            log(f"Fetcher error: {e}")
            tb = traceback.format_exc()
            log(tb)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)


# === Telegram handlers ===
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот запущен и работает.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Активных сигналов: {len(tracked_signals)}")


# === Веб-сервер ===
async def handle_root(request):
    return web.Response(text="🤖 Bot is running on Render!")


async def start_bot(app):
    """Запускается при старте aiohttp сервера"""
    log("🚀 Запуск Telegram бота...")
    bot_app = app["bot_app"]
    notifier = Notifier(bot_app.bot)
    asyncio.create_task(fetcher_loop(bot_app.bot, notifier, UPDATE_INTERVAL))
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.updater.start_polling()
    await notifier.notify("✅ Бот успешно запущен на Render.")


async def cleanup_bot(app):
    """Остановка при завершении"""
    bot_app = app["bot_app"]
    log("🛑 Остановка Telegram бота...")
    await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()


# === Главный запуск ===
def main():
    app = web.Application()
    app.router.add_get("/", handle_root)

    # Telegram Application
    bot_app = Application.builder().token(TOKEN).build()
    bot_app.add_handler(CommandHandler("start", cmd_start))
    bot_app.add_handler(CommandHandler("status", cmd_status))
    app["bot_app"] = bot_app

    app.on_startup.append(start_bot)
    app.on_cleanup.append(cleanup_bot)

    log(f"🌐 Starting web server on port {PORT}...")
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
