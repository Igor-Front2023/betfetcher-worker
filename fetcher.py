# fetcher.py
import aiohttp
import asyncio
from notifier import Notifier
from match_predictor import analyze_event

API_URL = "https://pari.ru/api/v1/events/live"

async def fetch_live_data():
    """Получает live события с PARI."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(API_URL, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("sports", [])
                else:
                    print(f"⚠️ Ошибка PARI: {response.status}")
        except Exception as e:
            print(f"⚠️ Ошибка соединения с PARI: {e}")
    return []

async def process_sport(sport_data, notifier):
    """Обрабатывает один вид спорта и ищет интересные события."""
    sport_name = sport_data.get("name", "Неизвестно")
    events = sport_data.get("events", [])
    signals = []

    for event in events:
        teams = event.get("name", "N/A")
        markets = event.get("markets", [])

        valid_odds = []
        for market in markets:
            outcomes = market.get("outcomes", [])
            for o in outcomes:
                odd = o.get("odd", 0)
                if 1.1 <= odd <= 1.4:
                    valid_odds.append({
                        "name": o.get("name", "Unknown"),
                        "odd": odd
                    })

        if valid_odds:
            event_data = {
                "sport": sport_name,
                "teams": teams,
                "odds": valid_odds
            }
            signals.append(event_data)

            # Анализ H2H через Flashscore
            try:
                await analyze_event(event_data, notifier)
            except Exception as e:
                print(f"⚠️ Ошибка анализа: {e}")

    return signals

async def fetch_and_analyze(notifier):
    """Основной цикл: получение событий + анализ."""
    sports = await fetch_live_data()
    all_signals = []

    for sport in sports:
        signals = await process_sport(sport, notifier)
        all_signals.extend(signals)

    return all_signals

async def fetcher_loop(notifier: Notifier):
    """Циклический сбор и анализ событий."""
    while True:
        print("🔄 Обновление данных с PARI...")
        try:
            signals = await fetch_and_analyze(notifier)
            if not signals:
                print("❌ Подходящих событий не найдено.")
        except Exception as e:
            print(f"⚠️ Ошибка цикла fetcher_loop: {e}")

        await asyncio.sleep(120)  # интервал обновления 2 минуты
