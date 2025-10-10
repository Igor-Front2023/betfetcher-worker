import aiohttp
import asyncio

async def test_pari_api():
    url = "https://line-lb51-w.pb06e2-resources.com/events/list?lang=ru&version=61335119010&scopeMarket=2300"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:139.0) Gecko/20100101 Firefox/139.0",
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.8,en-US;q=0.5,en;q=0.3",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            print(f"🔗 Статус ответа: {response.status}")
            text = await response.text()
            print(f"📦 Первые 500 символов ответа:\n{text[:500]}")

asyncio.run(test_pari_api())
