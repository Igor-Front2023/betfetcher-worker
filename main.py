# main.py — полностью самодостаточный для деплоя на Render (web service)
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

# === Конфиг из окружения ===
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
API_URL = os.getenv("API_URL", "").strip()
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "180"))
HTTP_PORT = int(os.getenv("PORT", 10000))
RENDER_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")

if not TOKEN:
    raise SystemExit("BOT_TOKEN не задан в переменных окружения.")
if not ADMIN_ID:
    raise SystemExit("ADMIN_ID не задан в переменных окружения.")
ADMIN_ID = int(ADMIN_ID)

# === Утилита логов ===
def log(msg: str):
    t = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t} UTC] {msg}", flush=True)

# === Notifier ===
class Notifier:
    def __init__(self, bot):
        self.bot = bot
        self.admin_id = ADMIN_ID

    async def notify(self, text: str):
        try:
            await self.bot.send_message(chat_id=self.admin_id, text=text[:4000])
        except Exception as e:
            log(f"Notifier error: {e}")

# === Fetcher API ===
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

# === Трекер сигналов ===
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
                                settled_text = f"[SETTLED]\nEvent: {ev.get('teams') or ev.get('name')}\nResult: {status}\nOdds: {tracked_signals[event_id].get('odds')}\n"
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
                                        if isinstance(cand, dict):
                                            for kk in ("price", "value"):
                                                if kk in cand:
                                                    try:
                                                        odds = float(cand[kk])
                                                        break
                                                    except:
                                                        pass
                                        elif isinstance(cand, list) and len(cand) > 0:
                                            try:
                                                odds = float(cand[0])
                                            except:
                                                pass
                        if odds and 1.05 <= odds <= 1.33:
                            sport = ev.get("sport") or ev.get("league") or ev.get("category") or "Unknown"
                            teams = ev.get("teams") or ev.get("name") or ev.get("title") or "Event"
                            where_to_bet = ev.get("bet_on") or "Home / 1"
                            text = (
                                f"[SIGNAL]\nSport: {sport}\nEvent: {teams}\nOdds: {odds}\nPlace bet: {where_to_bet}\n"
                                f"Event ID: {event_id}\n(Detected by external API)"
                            )
                            await notifier.notify(text)
                            tracked_signals[event_id] = {
                                "odds": odds,
                                "event": teams,
                                "sport": sport,
                                "sent_at": datetime.datetime.utcnow().isoformat(),
                                "settled": False
                            }
                else:
                    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    await notifier.notify(f"[heartbeat] {now} UTC — бот жив. Нет событий или не указан API_URL.")
            backoff = 5
            await asyncio.sleep(update_interval)
        except Exception as e:
            tb = traceback.format_exc()
            log(f"Error in fetcher_loop: {e}\n{tb}")
            try:
                await notifier.notify(f"⚠️ Error in fetcher_loop: {e}")
            except Exception:
                pass
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)

# === Telegram Handlers ===
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает. Я пришлю сигналы и статус.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    active = len(tracked_signals)
    await update.message.reply_text(f"Бот активен. Отслеживаем сигналов: {active}. {now} UTC")

# === Telegram App ===
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("status", cmd_status))

# === Webhook / HTTP server ===
async def handle_root(request):
    return web.Response(text="Bot is running!")

async def start_webhook(app, notifier):
    webhook_url = f"https://{RENDER_HOSTNAME}/{TOKEN}"
    await app.bot.set_webhook(webhook_url)
    log(f"📡 Webhook set to {webhook_url}")

    web_app = web.Application()
    web_app.router.add_post(f"/{TOKEN}", app.webhook_handler())
    web_app.router.add_get("/", handle_root)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await site.start()
    log(f"✅ Web server started on port {HTTP_PORT}")

    return runner

async def main():
    notifier = Notifier(application.bot)
    runner = None

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: stop_event.set())
        except NotImplementedError:
            pass

    log("🚀 Initializing Telegram Application...")
    await application.initialize()
    await application.start()
    log("🤖 Telegram application started")

    # Стартуем webhook
    runner = await start_webhook(application, notifier)

    # Запуск fetcher_loop
    fetcher_task = asyncio.create_task(fetcher_loop(application.bot, notifier, update_interval=UPDATE_INTERVAL))

    try:
        await notifier.notify("✅ Бот успешно запущен через Webhook (Render Web Service).")
    except Exception:
        pass

    log("✅ Все процессы запущены.")
    await stop_event.wait()

    log("🔻 Shutdown signal received.")
    fetcher_task.cancel()
    try:
        await fetcher_task
    except asyncio.CancelledError:
        pass

    await application.stop()
    await application.shutdown()

    if runner:
        await runner.cleanup()
        log("✅ Web server stopped")

    log("✅ Graceful shutdown complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log(f"Fatal error in main: {e}")
        raise
