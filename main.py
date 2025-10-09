# main.py — Render-ready (без .env)
import os
import asyncio
import signal
import datetime
import traceback
from typing import Optional, Dict, Any
import aiohttp
from aiohttp import web
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === Конфиг из окружения ===
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "180"))
HTTP_PORT = int(os.getenv("PORT", 10000))

if not TOKEN:
    raise SystemExit("❌ BOT_TOKEN не задан.")
if not ADMIN_ID:
    raise SystemExit("❌ ADMIN_ID не задан.")
ADMIN_ID = int(ADMIN_ID)

# === Логирование ===
def log(msg: str):
    t = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t} UTC] {msg}", flush=True)

# === Уведомления админу ===
class Notifier:
    def __init__(self, bot):
        self.bot = bot
        self.admin_id = ADMIN_ID

    async def notify(self, text: str):
        try:
            await self.bot.send_message(chat_id=self.admin_id, text=text[:4000])
        except Exception as e:
            log(f"Notifier error: {e}")

# === Хранилище отправленных сигналов ===
tracked_signals: Dict[str, Dict[str, Any]] = {}

# === Парсер Pari.ru ===
async def fetch_live_events(session: aiohttp.ClientSession):
    url = "https://pari.ru/live/"
    try:
        async with session.get(url, timeout=20) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            events = []

            # пример парсинга: ищем блоки матчей (адаптировать под структуру сайта)
            for match_div in soup.select("div.live-event-row"):
                try:
                    teams = match_div.select_one("div.team-names").get_text(strip=True)
                    odds_str = match_div.select_one("div.odds-value").get_text(strip=True)
                    odds = float(odds_str.replace(",", "."))
                    link = match_div.select_one("a.event-link")["href"]
                    events.append({
                        "teams": teams,
                        "odds": odds,
                        "link": f"https://pari.ru{link}"
                    })
                except Exception:
                    continue
            return events
    except Exception as e:
        log(f"Error fetching live events: {e}")
        return []

# === Простейший анализ статистики ===
async def analyze_event(session: aiohttp.ClientSession, event):
    # Здесь можно подключить парсер истории очных встреч
    # Для примера: событие считается валидным, если odds 1.05–1.33
    odds = event["odds"]
    if 1.05 <= odds <= 1.33:
        probability = 0.75  # пример оценки 75%
        return probability
    return 0.0

# === Основной цикл обработки ===
async def fetcher_loop(bot, notifier: Notifier, update_interval: int = 180):
    backoff = 5
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                events = await fetch_live_events(session)
                if events:
                    for ev in events:
                        event_id = ev["teams"] + "_" + str(ev["odds"])
                        if event_id in tracked_signals:
                            continue
                        prob = await analyze_event(session, ev)
                        if prob >= 0.7:
                            text = (
                                f"[SIGNAL]\n"
                                f"Event: {ev['teams']}\n"
                                f"Odds: {ev['odds']}\n"
                                f"Probability: {int(prob*100)}%\n"
                                f"Link: {ev['link']}"
                            )
                            await notifier.notify(text)
                            tracked_signals[event_id] = {
                                "sent_at": datetime.datetime.utcnow().isoformat(),
                                "odds": ev["odds"],
                                "teams": ev["teams"],
                                "link": ev["link"]
                            }
                else:
                    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    await notifier.notify(f"[heartbeat] {now} UTC — бот жив. Нет данных.")
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

# === Telegram команды ===
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Бот запущен и работает.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active = len(tracked_signals)
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    await update.message.reply_text(f"✅ Бот активен. Отслеживаем сигналов: {active}\n{now} UTC")

# === Инициализация Telegram ===
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("status", cmd_status))

# === Веб-сервер Render ===
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
