import asyncio
from datetime import datetime
from live_parser import get_live_events


async def fetcher_loop(notifier):
    """Основной цикл парсинга"""
    while True:
        events = get_live_events()
        signals = []

        # фильтрация по коэффициентам 1.1–1.4
        for e in events:
            valid_odds = []
            for o in e["odds"]:
                try:
                    odd = float(o.replace(',', '.'))
                    if 1.1 <= odd <= 1.4:
                        valid_odds.append(odd)
                except ValueError:
                    continue
            if valid_odds:
                signals.append({
                    "sport": e["sport"],
                    "teams": e["teams"],
                    "odds": valid_odds,
                })

        # если что-то нашли — отправляем админу
        if signals:
            text = "🎯 Найдены подходящие события:\n\n"
            for s in signals[:5]:
                text += f"🏅 {s['sport']}\n⚔️ {s['teams']}\n💰 Коэф: {', '.join(map(str, s['odds']))}\n\n"
            await notifier.send_to_admin(text)
        else:
            print(f"[heartbeat] {datetime.utcnow()} — нет подходящих событий.")

        await asyncio.sleep(120)  # проверяем каждые 2 минуты
