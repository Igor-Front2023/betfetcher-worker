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
ADMIN_ID = os.getenv("ADMIN_ID")  # обязателен
API_URL = os.getenv("API_URL", "").strip()  # внешняя API для событий (опционально)
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "180"))  # сек
HTTP_PORT = int(os.getenv("PORT", os.getenv("PORT", 10000)))

if not TOKEN:
    raise SystemExit("BOT_TOKEN не задан в переменных окружения.")
if not ADMIN_ID:
    raise SystemExit("ADMIN_ID не задан в переменных окружения.")
ADMIN_ID = int(ADMIN_ID)

# === Простые утилиты ===
def log(msg: str):
    t = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{t} UTC] {msg}", flush=True)

# === Notifier: отправляет сообщения админу / в чат ===
class Notifier:
    def __init__(self, bot):
        self.bot = bot
        self.admin_id = ADMIN_ID

    async def notify(self, text: str):
        try:
            # ограничиваем длину, чтобы не упало
            await self.bot.send_message(chat_id=self.admin_id, text=text[:4000])
        except Exception as e:
            log(f"Notifier error: {e}")

# === Парсер / fetcher ===
async def get_odds_from_api(session: aiohttp.ClientSession) -> Optional[list]:
    if not API_URL:
        return None
    try:
        async with session.get(API_URL, timeout=20) as resp:
            resp.raise_for_status()
            data = await resp.json()
            # ожидаем либо список, либо {"data": [...]}
            if isinstance(data, dict) and "data" in data:
                return data["data"]
            if isinstance(data, list):
                return data
            return None
    except Exception as e:
        log(f"API fetch error: {e}")
        return None

# in-memory store: tracked signals {event_id: {info...}}
tracked_signals: Dict[str, Dict[str, Any]] = {}

async def fetcher_loop(bot, notifier: Notifier, update_interval: int = 180):
    """
    Основной цикл: опрашивает API каждое update_interval секунд,
    ищет подходящие коэффициенты (1.05..1.33) и отправляет сигнал.
    Также следит за settlement (если API возвращает status/result).
    """
    backoff = 5
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                events = await get_odds_from_api(session)
                if events:
                    # Пройтись по элементам, найти сигналы
                    for ev in events:
                        # пытаемся извлечь ID (если нет — формируем из имени+time)
                        event_id = ev.get("id") or ev.get("event_id") or (ev.get("name") or "") + "_" + str(ev.get("timestamp") or "")
                        # проверим уже отправленные
                        if event_id in tracked_signals:
                            # если в API есть результат/статус — послать итог
                            status = ev.get("status") or ev.get("result") or ev.get("finished")
                            if status:
                                if not tracked_signals[event_id].get("settled"):
                                    # решаем, выиграла ставка или проиграла — примерная логика
                                    settled_text = f"[SETTLED]\nEvent: {ev.get('teams') or ev.get('name')}\nResult: {status}\nOdds: {tracked_signals[event_id].get('odds')}\n"
                                    await notifier.notify(settled_text)
                                    tracked_signals[event_id]["settled"] = True
                            continue

                        # извлечём коэффициент на home/winner
                        odds = None
                        o = ev.get("odds") or ev.get("markets") or {}
                        if isinstance(o, dict):
                            odds_candidates = [o.get(k) for k in ("home", "P1", "1", "odds")]
                            for cand in odds_candidates:
                                if cand:
                                    try:
                                        odds = float(cand)
                                        break
                                    except:
                                        # иногда cand — dict/list
                                        if isinstance(cand, (dict, list)):
                                            # доп. попытки
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
                        # если нашли коэффициент и он в диапазоне — сигнал
                        if odds and 1.05 <= odds <= 1.33:
                            # формируем текст
                            sport = ev.get("sport") or ev.get("league") or ev.get("category") or "Unknown"
                            teams = ev.get("teams") or ev.get("name") or ev.get("title") or "Event"
                            where_to_bet = ev.get("bet_on") or "Home / 1"  # если API не даёт, ставим общий текст
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
                    # heartbeat если API не задан или нет данных
                    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    await notifier.notify(f"[heartbeat] {now} UTC — бот жив. Нет событий или не указан API_URL.")
            backoff = 5
            await asyncio.sleep(update_interval)
        except Exception as e:
            # логирование + уведомление админу, затем экспоненциальный бэкофф
            tb = traceback.format_exc()
            log(f"Error in fetcher_loop: {e}\n{tb}")
            try:
                await notifier.notify(f"⚠️ Error in fetcher_loop: {e}\n{str(e)[:200]}")
            except Exception:
                pass
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)


# === Telegram handlers & app ===
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает. Я пришлю сигналы и статус.")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    active = len(tracked_signals)
    await update.message.reply_text(f"Бот активен. Отслеживаем сигналов: {active}. {now} UTC")

# создаём Application (telegram)
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", cmd_start))
application.add_handler(CommandHandler("status", cmd_status))

# === Web server (Render требует прослушивание порта) ===
async def handle_root(request):
    return web.Response(text="Bot is running!")

async def start_web_server(runner_container):
    web_app = web.Application()
    web_app.router.add_get("/", handle_root)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", HTTP_PORT)
    await site.start()
    runner_container["runner"] = runner
    log(f"✅ Web server started on port {HTTP_PORT}")

async def stop_web_server(runner_container):
    runner = runner_container.get("runner")
    if runner:
        await runner.cleanup()
        log("✅ Web server stopped")

# === Главная логика запуска — аккуратно управляем lifecycle ===
async def main():
    notifier = Notifier(application.bot)
    runner_container = {}

    # сигнал для graceful shutdown
    stop_event = asyncio.Event()

    # зарегистрируем обработчики сигналов (SIGINT, SIGTERM)
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: stop_event.set())
        except NotImplementedError:
            # Windows or unsupported
            pass

    log("🚀 Initializing Telegram Application...")
    await application.initialize()
    await application.start()
    log("🤖 Telegram application started")

    # запустим polling вручную (не использовать app.run_polling)
    await application.updater.start_polling()
    log("📡 Updater polling started")

    # запустим веб-сервер
    web_task = asyncio.create_task(start_web_server(runner_container))

    # запустим fetcher_loop как фоновую задачу
    fetcher_task = asyncio.create_task(fetcher_loop(application.bot, notifier, update_interval=UPDATE_INTERVAL))

    log("✅ All background tasks started — bot is ready.")
    # оповестим админа
    try:
        await notifier.notify("✅ Бот успешно запущен и работает на Render.")
    except Exception:
        pass

    # ждём сигнала остановки
    await stop_event.wait()
    log("🔻 Shutdown signal received, stopping...")

    # корректная остановка фоновых задач и updater
    try:
        log("Stopping fetcher task...")
        fetcher_task.cancel()
        try:
            await fetcher_task
        except asyncio.CancelledError:
            pass
    except Exception as e:
        log(f"Error while cancelling fetcher_task: {e}")

    try:
        log("Stopping updater polling...")
        await application.updater.stop()
    except Exception as e:
        log(f"Error stopping updater: {e}")

    try:
        log("Stopping application...")
        await application.stop()
    except Exception as e:
        log(f"Error stopping application: {e}")

    try:
        log("Shutting down application...")
        await application.shutdown()
    except Exception as e:
        log(f"Error during shutdown: {e}")

    try:
        log("Stopping web server...")
        await stop_web_server(runner_container)
    except Exception as e:
        log(f"Error stopping web server: {e}")

    log("✅ Graceful shutdown complete.")

# запуск
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        log(f"Fatal error in main: {e}")
        raise
