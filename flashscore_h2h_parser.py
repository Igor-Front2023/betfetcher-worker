import asyncio
from playwright.async_api import async_playwright
import re
import json

MATCH_ID = "xzFatGtA"

async def main():
    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(locale="ru-RU")
        page = await context.new_page()

        # Переходим на страницу матча
        url = f"https://www.flashscore.com/match/{MATCH_ID}/#/h2h/overall"
        print(f"🌐 Открываем {url}")
        await page.goto(url)

        # Перехватываем запросы
        async def handle_request(request):
            if "/x/feed/h2h_" in request.url:
                print(f"\n📡 Найден реальный запрос: {request.url}")
                response = await request.response()
                text = await response.text()
                print(f"📦 Длина данных: {len(text)} символов")

                if "¬" in text:
                    print("✅ Похоже на реальные данные FlashScore.")
                    parts = re.split(r"¬", text)
                    data = {}
                    for p in parts:
                        if "÷" in p:
                            k, v = p.split("÷", 1)
                            data[k] = v
                    print(json.dumps(data, ensure_ascii=False, indent=2))
                else:
                    print("⚠️ Получен HTML, а не данные.")

        page.on("requestfinished", handle_request)

        # Даем время запросу выполниться
        await asyncio.sleep(10)
        await browser.close()

asyncio.run(main())


