import aiohttp
import asyncio

URL = "https://line-lb01-w.pb06e2-resources.com/events/list?lang=ru&scopeMarket=2300"

async def fetch_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(URL, headers={"User-Agent": "Mozilla/5.0"}) as resp:
            return await resp.json()

async def main():
    data = await fetch_data()
    all_events = data.get("events", [])
    live_infos = data.get("liveEventInfos", [])

    # Индексируем события по ID для быстрого доступа
    events_map = {e["id"]: e for e in all_events}

    live_events = []
    for info in live_infos:
        event_id = info.get("eventId")
        base = events_map.get(event_id)
        if base:
            sport_id = base.get("sportId")
            team1 = base.get("team1")
            team2 = base.get("team2")
            live_events.append({
                "id": event_id,
                "sportId": sport_id,
                "team1": team1,
                "team2": team2,
                "timer": info.get("timer"),
                "score": info.get("scoreComment"),
            })

    print(f"📺 Найдено live событий: {len(live_events)}")
    for ev in live_events[:10]:  # покажем первые 10
        print(f"{ev['team1']} vs {ev['team2']} | {ev['score']} | ⏱ {ev['timer']}")

if __name__ == "__main__":
    asyncio.run(main())




