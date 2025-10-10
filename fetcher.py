import asyncio
from datetime import datetime
import aiohttp


async def get_working_pari_host():
    """Проверяет зеркала PARI и возвращает первый доступный."""
    hosts = [
        "https://line-lb01-w.pb06e2-resources.com",
        "https://line-lb02-w.pb06e2-resources.com",
        "https://line-lb51-w.pb06e2-resources.com",
        "https://line-lb52-w.pb06e2-resources.com",
    ]
    test_path = "/events/list?lang=ru&scopeMarket=2300"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0",
        "Accept": "*/*",
    }

    async with aiohttp.ClientSession() as session:
        for host in hosts:
            url = f"{host}{test_path}"
            try:
                async with session.get(url, headers=headers, timeout=5) as response:
                    if response.status == 200:
                        print(f"✅ Рабочий сервер PARI: {host}")
                        return host
            except Exception as e:
                print(f"⚠️ {host} не отвечает ({e})")
                continue

    print("❌ Нет доступных серверов PARI.")
    return None


async def fetch_pari_events(base_url):
    """Запрашивает live-события с PARI."""
    url = f"{base_url}/events/list?lang=ru&scopeMarket=2300"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0",
        "Accept": "*/*",
        "Referer": "https://pari.ru/",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, timeout=10) as response:
            if response.status != 200:
                raise ConnectionError(f"HTTP {response.status}")
            data = await response.json(content_type=None)
            return data.get("sports", [])


async def fetcher_loop(notifier, update_interval=120):
    """Основной цикл парсинга и авто-переподключения."""
    base_url = await get_working_pari_host()
    if not base_url:
        print("❌ Не удалось найти рабочий сервер PARI при запуске.")
        await notifier.send_to_admin("❌ Ошибка: нет доступных серверов PARI.")
        return

    while True:
        try:
            sports = await fetch_pari_events(base_url)
        except Exception as e:
            print(f"⚠️ Ошибка при обращении к {base_url}: {e}")
            await notifier.send_to_admin(f"⚠️ Потеряно соединение с {base_url}, ищем новое зеркало...")
            base_url = await get_working_pari_host()
            if not base_url:
                print("⛔ Все зеркала недоступны. Ждем 2 минуты и пробуем снова.")
                await asyncio.sleep(update_interval)
                continue
            else:
                await notifier.send_to_admin(f"✅ Переключились на {base_url}")
                continue

        # Фильтрация по коэффициентам 1.1–1.4
        signals = []
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
                    signals.append({
                        "sport": sport_name,
                        "teams": teams,
                        "odds": valid_odds
                    })

        # Отправляем результаты
        if signals:
            text = "🎯 Найдены подходящие события:\n\n"
            for s in signals[:5]:
                text += (
                    f"🏅 {s['sport']}\n"
                    f"⚔️ {s['teams']}\n"
                    f"💰 Коэф: {', '.join(map(str, s['odds']))}\n\n"
                )
            await notifier.send_to_admin(text)
        else:
            print(f"[heartbeat] {datetime.utcnow()} — нет подходящих событий.")

        await asyncio.sleep(update_interval)
