# stats_fetcher_playwright.py
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


async def fetch_h2h(url: str, team1: str = None, team2: str = None, limit: int = 5):
    """
    Получает статистику очных встреч (H2H) с сайта Flashscore.
    Использует Playwright для рендеринга динамического контента.
    Возвращает список матчей в формате:
    [
        {"date": "...", "score": "2:0", "winner": "Team1"},
        ...
    ]
    """
    print(f"🌐 Загружаем H2H страницу: {url}")

    matches = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, timeout=60000)
            await page.wait_for_selector("div.h2h__table", timeout=25000)

            html = await page.content()
            await browser.close()

        soup = BeautifulSoup(html, "html.parser")

        # Ищем все ряды матчей
        match_blocks = soup.select("div.h2h__table div.h2h__row") or soup.select("div.h2h__table div")

        for row in match_blocks[:limit]:
            text = row.get_text(" ", strip=True)

            # Ищем дату и счёт
            date = ""
            score = ""
            parts = text.split()
            for part in parts:
                if ":" in part and len(part) <= 5:  # 2:0, 1:1, 3:2
                    score = part
                if "-" in part and len(part.split("-")) == 3:  # дата формата 2025-10-01
                    date = part

            # Определяем победителя по счёту
            winner = "Draw"
            try:
                if ":" in score:
                    left, right = score.split(":")
                    left, right = int(left), int(right)
                    if left > right:
                        winner = team1 or "Team1"
                    elif right > left:
                        winner = team2 or "Team2"
            except Exception:
                pass

            matches.append({
                "date": date,
                "score": score,
                "winner": winner,
                "text": text
            })

        print(f"✅ Найдено {len(matches)} очных матчей")
        return matches

    except Exception as e:
        print(f"⚠️ Ошибка при загрузке H2H данных: {e}")
        return matches


# Пример теста
if __name__ == "__main__":
    async def main():
        url = "https://www.flashscorekz.com/match/tennis/back-dayeon-WWkxyOw9/reyngold-ekaterina-lpjDUxQf/h2h/all-surfaces/?mid=xzFatGtA"
        data = await fetch_h2h(url, team1="Back Dayeon", team2="Reyngold Ekaterina")
        for m in data:
            print(m)

    asyncio.run(main())
