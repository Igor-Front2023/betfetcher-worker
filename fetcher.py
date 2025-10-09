import os
import asyncio
import aiohttp
import datetime
from typing import Optional

API_URL = os.getenv('API_URL', '').strip()

async def get_odds_from_api(session: aiohttp.ClientSession) -> Optional[list]:
    if not API_URL:
        return None
    try:
        async with session.get(API_URL, timeout=20) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data.get('data') if isinstance(data, dict) else data
    except Exception as e:
        print('API fetch error:', e)
        return None

async def fetcher_loop(notifier, update_interval:int = 60):
    async with aiohttp.ClientSession() as session:
        while True:
            events = await get_odds_from_api(session)
            if events:
                signals = []
                for ev in events:
                    try:
                        odds = ev.get('odds') or ev.get('markets') or {}
                        home = None
                        if isinstance(odds, dict):
                            home = odds.get('home') or odds.get('P1') or odds.get('1')
                        if home:
                            try:
                                home_f = float(home)
                                if 1.05 <= home_f <= 1.33:
                                    signals.append((ev, home_f))
                            except:
                                pass
                    except Exception:
                        continue
                for ev, prob in signals:
                    text = f"[SIGNAL]\nEvent: {ev.get('teams') or ev.get('sport') or ev.get('name')}\nOdds: {prob}\n(Detected by external API)"
                    await notifier.notify(text)
            else:
                now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                await notifier.notify(f"[heartbeat] {now} UTC — бот жив. Нет событий или не указан API_URL.")
            await asyncio.sleep(update_interval)
