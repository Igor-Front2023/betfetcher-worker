import aiohttp
import asyncio

async def test_pari_api():
    url = "https://line-lb01-w.pb06e2-resources.com/list?lang=ru&scopeMarket=2300"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            print("🔗 Статус ответа:", response.status)
            data = await response.json()
            print("✅ Получено событий:", len(data.get("events", [])))

            # Печатаем первые 3 события, чтобы убедиться, что данные живые
            for ev in data.get("events", [])[:3]:
                print("\n🏅 Вид спорта:", ev.get("sportId"))
                print("⚔️ Событие:", ev.get("name"))
                print("📊 Кол-во коэффициентов:", len(ev.get("customFactors", [])))

asyncio.run(test_pari_api())
