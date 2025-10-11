# fetcher.py - PARI parser + analyzer
import aiohttp
import asyncio
import re
from notifier import Notifier
from match_predictor import analyze_event

PARI_LIVE_URL = "https://pari.ru/live/"

async def fetch_live_html(session: aiohttp.ClientSession) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    async with session.get(PARI_LIVE_URL, headers=headers, timeout=20) as resp:
        resp.raise_for_status()
        return await resp.text()

def extract_number(s: str):
    try:
        if not s:
            return None
        txt = re.sub(r'[^0-9,\\.]', '', s)
        if not txt:
            return None
        return float(txt.replace(',', '.'))
    except Exception:
        return None

from bs4 import BeautifulSoup

async def parse_events_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")
    events = []
    # Find event blocks by class name pattern used on pari.ru
    for block in soup.find_all("div", class_=lambda c: c and "sport-base-event" in c):
        try:
            # Teams/title detection
            teams = None
            sel = block.select_one(".sport-base-event__main__caption--JLR1n, .sport-sub-event__name--J7jv6, .table-component-text--Tjj3g, .team-names, .team-name")
            if sel:
                teams = sel.get_text(" ", strip=True)
            if not teams:
                teams = block.get_text(" ", strip=True)[:140]

            # collect numeric-like spans
            odds = []
            for span in block.find_all(["span","div"]):
                txt = span.get_text(strip=True)
                num = extract_number(txt)
                if num:
                    odds.append(num)
            odds = sorted(set(odds))

            # create events for odds in target range
            for o in odds:
                if 1.05 <= o <= 1.33:
                    link_el = block.select_one("a[href]")
                    link = link_el["href"] if link_el and link_el.get("href") else PARI_LIVE_URL
                    if link.startswith("/"):
                        link = "https://pari.ru" + link
                    events.append({
                        "teams": teams,
                        "odds": o,
                        "link": link
                    })
        except Exception:
            continue
    return events

async def fetch_and_analyze(notifier: Notifier):
    async with aiohttp.ClientSession() as session:
        html = await fetch_live_html(session)
        events = await parse_events_from_html(html)
        results = []
        for ev in events:
            try:
                prob = await analyze_event(ev)
            except Exception:
                prob = 0.0
            if prob and prob >= 0.7:
                text = (f"[SIGNAL]\\nEvent: {ev['teams']}\\nOdds: {ev['odds']}\\nProbability: {int(prob*100)}%\\nLink: {ev['link']}")
                await notifier.notify(text)
                results.append({"event": ev, "prob": prob})
        return results

async def fetcher_loop(notifier: Notifier, update_interval: int = 180):
    backoff = 5
    while True:
        try:
            print("🔄 Fetching PARI.live...")
            signals = await fetch_and_analyze(notifier)
            if not signals:
                print("No matching signals found.")
            backoff = 5
            await asyncio.sleep(update_interval)
        except Exception as e:
            print("Fetcher loop error:", e)
            try:
                await notifier.notify(f"⚠️ Fetcher error: {e}")
            except Exception:
                pass
            await asyncio.sleep(backoff)
            backoff = min(backoff*2, 300)
