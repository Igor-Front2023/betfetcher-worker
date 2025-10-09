# main.py — адаптирован под Render (без .env)
import os
import asyncio
import signal
import datetime
import traceback
from typing import Optional, Dict, Any

import aiohttp
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === Конфиг из окружения ===
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # обязателен
API_URL = os.getenv("API_URL", "").strip()
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "180"))
HTTP_PORT = int(os.getenv("PORT", 10000))

if not TOKEN:
    raise SystemExit("❌ BOT_TOKEN не задан в Environment Variables.")
if not ADMIN_ID:
    raise SystemExit("❌ ADMIN_ID не задан в Environment Variables.")
ADMIN_ID = int(ADMIN_ID)


# === Утилита логирования ===
def log(msg: str):
    t = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t} UTC] {msg}", flush=True)


# === Класс для уведомлений админа ===
class Notifier:
    def __init__(self, bot):
        self.bot = bot
        self.admin_id = ADMIN_ID

    async def notify(self, text: str):
        try:
            await self.bot.send_message(chat_id=self.admin_id, text=text[:4000])
        except Exception as e:
            log(f"Notifier error: {e}")


# === Получение данных с внешнего API ===
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


tracked_signals: Dict[str, Dict[str, Any]] = {}


async def fetcher_loop(bot, notifier: Notifier, update_interval: int = 180):
    backoff = 5
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                events = await get_odds_from_api(session)
                if events:
                    for ev in events:
                        event_id = ev.get("id") or ev.get("event_id") or (ev.get("name") or "") + "_" + str(ev.get("timestamp") or "")
                        if event_id in tracked_signals:
                            status = ev.get("status") or ev.get("result") or ev.get("finished")
                            if status and not tracked_signals[event_id].get("settled"):
                                settled_text = f"[SETTLED]\nEvent: {ev.get('teams') or ev.get('name')}\nResult: {status}\nOdds: {tracked_signals[event_id].get('odds')}"
                                await notifier.notify(settled_text)
                                tracked_signals[event_id]["settled"] = True
                            continue

                        odds = None
                        o = ev.get("odds") or ev.get("markets") or {}
                        if isinstance(o, dict):
                            for k in ("home", "P1", "1", "odds"):
                                cand = o.get(k)
                                if cand:
                                    try:
                                        odds = float(cand)
                                        break
                                    except:
                                        pass

                        if odds and 1.05 <= odds <= 1.33:
                            sport = ev.get("sport") or ev.get("league") or "Unknown"
                            teams = ev.get("teams") or ev.get("name") or "Event"
                            where_to_bet = ev.get("bet_on") or "Home / 1"
                            text = f"[SIGNAL]\nSport: {sport}\nEvent: {teams}\nOdds: {odds}\nPlace bet: {where_to_bet}\nEvent ID: {event_id}"
                            await notifier.notify(text)
                            tracked_signals[event_id] = {"odds": odds, "event": teams, "sport": sport, "sent_at": datetime.datetime.utcnow().isoformat(), "settled": False}
                else:
                    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    await notifier.notify(f"[heartbeat] {now} UTC — бот жив. Нет данных или API_URL не задан.")
            backoff = 5
            await asyncio.sleep(update_interval)
        except Exception as e:
            tb = traceback.format_exc()
            log(f"Error in fetcher_loop: {e}\n{tb}")
            try:
                await notifier.notify(f"⚠️ Ошибка в fetcher_loop: {e}")
            except Exception:
                pass
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)


# === Telegram-команды ===
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот запущен и работает.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    active = len(tracked_signals)
    await update.message.reply_text(f"✅ Бот активен. Отслеживаем сигналов: {active}\n{now} UTC")


# === Инициализация Telegram ===
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("status", cmd_status))


# === Веб-сервер для Render ===
async def handle_root(request):
    return web.Response(text="✅ Bot is running on Render!")

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


# === Основная функция ===
async def main():
    notifier = Notifier(application.bot)
    runner_container = {}
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: stop_event.set())
        except NotImplementedError:
            pass

    log("🚀 Initializing bot...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    log("✅ Telegram polling started")

    web_task = asyncio.create_task(start_web_server(runner_container))
    fetcher_task = asyncio.create_task(fetcher_loop(application.bot, notifier, update_interval=UPDATE_INTERVAL))

    try:
        await notifier.notify("✅ Бот успешно запущен на Render (без .env).")
    except Exception:
        pass

    await stop_event.wait()
    log("🛑 Stopping bot...")

    fetcher_task.cancel()
    await application.updater.stop()
    await application.stop()
    await application.shutdown()
    await stop_web_server(runner_container)
    log("✅ Graceful shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log(f"Fatal error in main: {e}")
        raise
