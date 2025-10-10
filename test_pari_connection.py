import asyncio
from datetime import datetime
from fetcher import get_working_pari_host, fetch_pari_events


async def test_pari_connection():
    print("🔍 Проверяем доступные зеркала PARI...")
    base_url = await get_working_pari_host()

    if not base_url:
        print("❌ Не найдено ни одного доступного зеркала PARI.")
        return

    print(f"✅ Используем зеркало: {base_url}")

    try:
        sports = await fetch_pari_events(base_url)
        print(f"✅ Получено данных: {len(sports)} видов спорта")

        total_events = 0
        found_signals = []

        for sport in sports:
            sport_name = sport.get("name", "Неизвестно")
            for event in sport.get("events", []):
                teams = event.get("name", "—")
                odds_raw = event.get("markets", [])

                valid_odds = []
                for market in odds_raw:
                    for outcome in market.get("outcomes", []):
                        try:
                            odd = float(outcome.get("price", "0").replace(",", "."))
                            if 1.1 <= odd <= 1.4:
                                valid_odds.append(odd)
                        except Exception:
                            continue

                if valid_odds:
                    found_signals.append({
                        "sport": sport_name,
                        "teams": teams,
                        "odds": valid_odds
                    })
                total_events += 1

        print(f"📊 Всего событий: {total_events}")
        print(f"🎯 Найдено подходящих: {len(found_signals)}")

        # показать первые 5 результатов
        for s in found_signals[:5]:
            print("\n---------------------------")
            print(f"🏅 {s['sport']}")
            print(f"⚔️ {s['teams']}")
            print(f"💰 Коэф: {', '.join(map(str, s['odds']))}")
            print("---------------------------")

    except Exception as e:
        print(f"❌ Ошибка при обращении к PARI API: {e}")


if __name__ == "__main__":
    print(f"🚀 Тест запущен {datetime.utcnow()} UTC\n")
    asyncio.run(test_pari_connection())

