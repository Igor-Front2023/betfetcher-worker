import requests
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}


def fetch_from_api():
    """Пробуем получить live события из открытых API"""
    api_urls = [
        "https://api.pari.ru/api/v1/events/live",
        "https://api.flashscore.com/x/feed/d_live_1_",
    ]
    for url in api_urls:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.ok and "application/json" in r.headers.get("Content-Type", ""):
                data = r.json()
                return parse_json_data(data)
        except Exception as e:
            print(f"[API fail] {url}: {e}")
    return []


def parse_json_data(data):
    """Парсим JSON (пример для Pari)"""
    events = []
    if not data:
        return events

    if isinstance(data, dict) and "events" in data:
        for e in data["events"]:
            try:
                sport = e.get("sport", {}).get("name", "unknown")
                teams = f"{e['competitors'][0]['name']} vs {e['competitors'][1]['name']}"
                odds = [o["value"] for o in e.get("markets", [])[0].get("outcomes", [])]
                events.append({
                    "sport": sport,
                    "teams": teams,
                    "odds": odds,
                })
            except Exception:
                continue
    return events


def fetch_from_html():
    """Если API недоступен — парсим HTML"""
    urls = ["https://www.flashscorekz.com/", "https://pari.ru/live"]
    events = []
    for url in urls:
        try:
            html = requests.get(url, headers=HEADERS, timeout=10).text
            soup = BeautifulSoup(html, "html.parser")
            matches = soup.select(".event__match")
            for m in matches[:10]:
                teams = " ".join([t.get_text(strip=True) for t in m.select(".event__participant")])
                odds = [o.get_text(strip=True) for o in m.select(".event__odd")]
                if teams and odds:
                    events.append({
                        "sport": "unknown",
                        "teams": teams,
                        "odds": odds,
                    })
        except Exception as e:
            print(f"[HTML fail] {url}: {e}")
    return events


def get_live_events():
    """Универсальная функция"""
    events = fetch_from_api()
    if not events:
        events = fetch_from_html()
    print(f"[{datetime.utcnow()}] Найдено событий: {len(events)}")
    return events
