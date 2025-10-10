import asyncio
import aiohttp
from datetime import datetime


PARI_API_URL = "https://line-lb01-w.pb06e2-resources.com/list?lang=ru&scopeMarket=2300"


async def get_live_events():
    """Получает live события с сайта PARI"""
    async with aiohttp.ClientSession() as session:
        async with session.get(PARI_API_URL) as resp:
            if resp.status != 200:
                print(f"[error] {datetime.utcnow()} — ошибка запроса: {resp.status}")
                return []

            data = await resp.json()

            events = data.get("events", [])
            custom_factors = data.get("customFactors", [])
            live_infos = data.get("liveEventInfos", [])

            result = []
            for ev in events:
                ev_id = ev.get("id")
                name = ev.get("name") or f"Event {ev_id}"
                sport_id = ev.get("sportId") or "unknown"

                # фильтрация коэффициентов
                event_factors = [f for f in custom_factors if f.get("e") == ev_id]
                odds = []
                for f in event_factors:
                    val = f.get("v")
                    try:
                        val = float(val)
                        if 1.1 <= val <= 1.4:
                            odds.append(val)
                    except (ValueError, TypeError):
                        continue

                if odds:
                    result.append({
                        "sport": sport_id,
                        "teams": name,
                        "odds": odds,
                    })

            print(f"[{datetime.utcnow()}] Получено событий: {len(events)}, найдено с нужными коэфами: {len(result)}")
            return result


async def fetcher_loop(notifier):
    """Основной цикл парсинга"""
    while True:
        try:
            events = await get_live_events()
            if not events:
                print(f"[heartbeat] {datetime.utcnow()} — нет подходящих событий.")
            else:
                text = "🎯 Найдены подходящие события:\n\n"
                for s in events[:5]:
                    text += f"🏅 {s['sport']}\n⚔️ {s['teams']}\n💰 Коэф: {', '.join(map(str, s['odds']))}\n\n"
                await notifier.send_to_admin(text)

        except Exception as e:
            print(f"[error] {datetime.utcnow()} — {e}")

        await asyncio.sleep(120)  # каждые 2 минуты


# Тестовая точка запуска
if __name__ == "__main__":
    class DummyNotifier:
        async def send_to_admin(self, msg):
            print("-> Сообщение админу:\n", msg)

    asyncio.run(fetcher_loop(DummyNotifier()))
