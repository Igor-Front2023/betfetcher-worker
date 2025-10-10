import asyncio
import re
import json
import traceback
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None

import requests

DEBUG = True


async def fetch_h2h(url: str, team1: str = None, team2: str = None, limit: int = 5):
    print(f"🌐 fetch_h2h: {url} (team1={team1}, team2={team2})")

    # Попробуем сначала API Flashscore
    api_result = await fetch_h2h_via_api(url, team1, team2, limit)
    if api_result:
        print("✅ Найдено через API Flashscore")
        return api_result

    # Если API не сработал — используем Playwright
    if async_playwright:
        try:
            async with async_playwright() as p:
                print("🚀 Launching Chromium...")
                browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
                page = await browser.new_page()

                await page.goto(url, timeout=60000)
                print("✅ Страница загружена")

                # Кликаем по H2H, если нужно
                try:
                    await page.click("a:has-text('H2H')")
                    print("🟢 Открыта вкладка H2H")
                    await asyncio.sleep(3)
                except Exception:
                    pass

                await asyncio.sleep(3)
                html = await page.content()
                soup = BeautifulSoup(html, "html.parser")

                matches = extract_matches_from_html(soup, team1, team2, limit)

                if not matches:
                    print("⚠️ Данных в DOM нет, пробуем fallback")
                    scripts = soup.find_all("script")
                    for s in scripts:
                        if "h2h" in s.text.lower():
                            snippet = re.findall(r"[A-Z][^<>]{10,80}", s.text)
                            matches = [{"text": snip, "winner": "?"} for snip in snippet[:limit]]
                            break

                await browser.close()
                return matches

        except Exception as e:
            print(f"⚠️ Ошибка Playwright: {e}")
            traceback.print_exc()

    # Если ничего не вышло — fallback requests
    print("🔁 Используем requests fallback...")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        matches = extract_matches_from_html(soup, team1, team2, limit)
        print(f"✅ Найдено {len(matches)} матчей через requests fallback")
        return matches
    except Exception as e:
        print(f"❌ Ошибка requests fallback: {e}")
        traceback.print_exc()
        return []


async def fetch_h2h_via_api(url, team1, team2, limit):
    """Извлекает H2H напрямую из API Flashscore."""
    try:
        match_id = re.search(r"match/([^/]+)/", url)
        if not match_id:
            return []
        match_id = match_id.group(1)

        api_url = f"https://d.flashscore.com/x/feed/h2h_{match_id}_1_en_1"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(api_url, headers=headers, timeout=15)

        if r.status_code != 200 or not r.text.strip():
            return []

        # Flashscore возвращает JSONP → чистим
        data_raw = r.text.strip()
        data_clean = re.sub(r"^[^(]+\(|\);?$", "", data_raw)
        data = json.loads(data_clean)

        results = []
        for item in data.get("events", [])[:limit]:
            text = f"{item.get('T1', {}).get('Nm')} vs {item.get('T2', {}).get('Nm')} | {item.get('Sc', {}).get('FS')}"
            winner = "Draw"
            if team1 and team1.lower() in text.lower():
                winner = team1
            elif team2 and team2.lower() in text.lower():
                winner = team2
            results.append({"text": text, "winner": winner})

        return results

    except Exception as e:
        if DEBUG:
            print(f"⚠️ Ошибка API Flashscore: {e}")
        return []


def extract_matches_from_html(soup, team1, team2, limit):
    matches = []
    for table in soup.select("div.h2h__table, table.h2h"):
        rows = table.select("div.h2h__row, tr")
        for row in rows[:limit]:
            text = " ".join(row.stripped_strings)
            if not text:
                continue
            winner = "Draw"
            if team1 and team1.lower() in text.lower():
                winner = team1
            elif team2 and team2.lower() in text.lower():
                winner = team2
            matches.append({"text": text, "winner": winner})
    return matches


if __name__ == "__main__":
    test_url = "https://www.flashscore.com/match/tennis/back-dayeon-WWkxyOw9/reyngold-ekaterina-lpjDUxQf/h2h/all-surfaces/?mid=xzFatGtA"
    result = asyncio.run(fetch_h2h(test_url, "Back Dayeon", "Reyngold Ekaterina"))
    print("\n📊 Итоговый результат:")
    for r in result:
        print(" -", r)
