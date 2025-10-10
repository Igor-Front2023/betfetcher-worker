# fetcher.py
import os
import asyncio
import aiohttp
import datetime
import re
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup

API_URL = os.getenv('API_URL', '').strip()
USE_PLAYWRIGHT = os.getenv('USE_PLAYWRIGHT', '0') == '1'
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
             "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# TTL для отслеживаемых сигналов (секунд) — сигналы старше будут удаляться
TRACKED_SIGNAL_TTL = int(os.getenv("TRACKED_SIGNAL_TTL", str(60*60)))  # 1 час по умолчанию

# регулярка для коэффициентов вида 1.23 или 1,23
odds_re = re.compile(r"([1-9]\d?\.[0-9]{2}|[1-9]\d?,[0-9]{2}|[1-9]\d?\.[0-9])")

async def get_odds_from_api(session: aiohttp.ClientSession) -> Optional[list]:
    if not API_URL:
        return None
    try:
        async with session.get(API_URL, timeout=20, headers={"User-Agent": USER_AGENT}) as resp:
            resp.raise_for_status()
            data = await resp.json()
            if isinstance(data, dict):
                # ожидаем .data или просто список
                return data.get('data') or data.get('events') or data.get('result') or data
            return data
    except Exception as e:
        print("API fetch error:", e)
        return None

async def fetch_live_from_pari(session: aiohttp.ClientSession) -> List[Dict[str, Any]]:
    """Попытка статического парсинга pari.ru/live/ — может работать не всегда (JS)."""
    url = "https://pari.ru/live/"
    try:
        async with session.get(url, timeout=20, headers={"User-Agent": USER_AGENT}) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            candidates = []
            # собираем текстовые блоки, пытаемся извлечь команды и коэффициенты
            for block in soup.select("div, a, li"):
                text = block.get_text(" ", strip=True)
                if not text:
                    continue
                # ищем коэффициент в тексте
                m = odds_re.search(text)
                if m:
                    # пытаемся извлечь название команд (примерно: "Team A - Team B")
                    teams = None
                    # common separators
                    for sep in [" - ", " vs ", " VS ", " v ", " x "]:
                        if sep in text:
                            teams = text.split(sep)[0:2]
                            break
                    if not teams:
                        # fallback: берем подряд слова (плохо, но лучше чем ничего)
                        tokens = text.split()
                        if len(tokens) >= 4:
                            teams = [" ".join(tokens[:2]), " ".join(tokens[2:4])]
                        else:
                            teams = ["?".strip(), "?".strip()]

                    odds_str = m.group(0).replace(",", ".")
                    try:
                        odds_f = float(odds_str)
                    except:
                        continue

                    link = None
                    a = block.find_parent("a")
                    if a and a.get("href"):
                        href = a["href"]
                        link = href if href.startswith("http") else "https://pari.ru" + href

                    candidates.append({
                        "teams": f"{teams[0].strip()} vs {teams[1].strip()}",
                        "odds": odds_f,
                        "link": link or url,
                        "source": "pari.static"
                    })
            return candidates
    except Exception as e:
        print("Error fetching pari.ru static:", e)
        return []

async def fetch_with_playwright(page_url: str) -> List[Dict[str, Any]]:
    """
    Опциональная: используется только если USE_PLAYWRIGHT=True и playwright установлен.
    Возвращает те же поля, что и static-версия, но после рендеринга JS.
    """
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return []

    results = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(user_agent=USER_AGENT)
            await page.goto(page_url, timeout=30000)
            content = await page.content()
            # используй тот же html-парсер, реюзим логику
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")
            text_blocks = soup.select("div, a, li")
            for block in text_blocks:
                text = block.get_text(" ", strip=True)
                if not text:
                    continue
                m = odds_re.search(text)
                if m:
                    teams = None
                    for sep in [" - ", " vs ", " VS ", " v ", " x "]:
                        if sep in text:
                            teams = text.split(sep)[0:2]
                            break
                    if not teams:
                        tokens = text.split()
                        if len(tokens) >= 4:
                            teams = [" ".join(tokens[:2]), " ".join(tokens[2:4])]
                        else:
                            teams = ["?", "?"]
                    odds_str = m.group(0).replace(",", ".")
                    try:
                        odds_f = float(odds_str)
                    except:
                        continue
                    link = None
                    a = block.find_parent("a")
                    if a and a.get("href"):
                        href = a["href"]
                        link = href if href.startswith("http") else "https://pari.ru" + href
                    results.append({
                        "teams": f"{teams[0].strip()} vs {teams[1].strip()}",
                        "odds": odds_f,
                        "link": link or page_url,
                        "source": "pari.playwright"
                    })
            await browser.close()
    except Exception as e:
        print("Playwright fetch error:", e)
    return results

async def analyze_event(session: aiohttp.ClientSession, event: Dict[str, Any]) -> float:
    """
    Анализ события: попытка получить дополнительную статистику (через публичные API типа SofaScore),
    если не удалось — fallback по коэффициенту (чем ближе к 1.1, тем выше оценка).
    Возвращает вероятность в диапазоне [0,1].
    """
    odds = float(event.get("odds", 0.0))
    teams = event.get("teams", "")
    # heuristic fallback:
    if 1.05 <= odds <= 1.4:
        # простая эвристика: нормируем коэфф в диапазон 0.7..0.9
        # 1.1 -> 0.88, 1.3 -> 0.74, 1.4 -> 0.7
        score = max(0.7, 0.9 - ((odds - 1.1) * 0.8))
    else:
        score = 0.0

    # Try to improve with SofaScore if possible (best-effort)
    try:
        # Простой поиск по имени команды (внешний API — может не работать без адаптации)
        base = "https://api.sofascore.com/api/v1/search"
        # возьмём первую команду
        team_name = teams.split(" vs ")[0].strip()
        if team_name:
            params = {"query": team_name}
            async with session.get(base, params=params, timeout=10, headers={"User-Agent": USER_AGENT}) as resp:
                if resp.status == 200:
                    j = await resp.json()
                    # j может содержать ключи 'players','teams' и т.д. — это экспериментальная часть
                    # если нашли полезные данные — увеличим score немного
                    if isinstance(j, dict) and j.get("teams"):
                        score = min(0.95, score + 0.03)
    except Exception:
        # не критично
        pass

    return float(score)

# Текущий трекер сигналов (в памяти) — ключи: uid -> {sent_at, odds, teams, link}
tracked_signals = {}

def cleanup_tracked_signals():
    now = datetime.datetime.utcnow().timestamp()
    to_delete = []
    for uid, meta in tracked_signals.items():
        sent_ts = meta.get("sent_ts", 0)
        if now - sent_ts > TRACKED_SIGNAL_TTL:
            to_delete.append(uid)
    for uid in to_delete:
        tracked_signals.pop(uid, None)

async def fetcher_loop(notifier, update_interval:int = 180):
    backoff = 5
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                cleanup_tracked_signals()
                events = await get_odds_from_api(session)
                if not events:
                    # если нет API_URL или он не ответил — пробуем парсить pari.ru
                    events = await fetch_live_from_pari(session)
                    # если задействован playwright — попробуем и его как fallback
                    if USE_PLAYWRIGHT and not events:
                        pw = await fetch_with_playwright("https://pari.ru/live/")
                        if pw:
                            events = pw

                signals_to_send = []
                for ev in events or []:
                    try:
                        odds = float(ev.get("odds", 0.0))
                    except Exception:
                        continue
                    # требуемый диапазон коэфов для отправки: 1.10 - 1.40 (пользователь просил 1.1-1.4)
                    if not (1.10 <= odds <= 1.40):
                        continue

                    # uid: используем link+teams+odds для уникальности (также можно добавить timestamp)
                    uid = (ev.get("link") or ev.get("teams") or "") + f"::{odds}"
                    # если уже отправляли ровно с таким odds — пропускаем
                    if uid in tracked_signals:
                        continue

                    prob = await analyze_event(session, ev)
                    if prob >= 0.70:
                        signals_to_send.append((ev, prob, uid))

                # отправляем сигналы (по 2 события за итерацию — как просили)
                if signals_to_send:
                    # сортируем по probability desc, выбираем топ-2
                    signals_to_send.sort(key=lambda x: x[1], reverse=True)
                    to_send = signals_to_send[:2]
                    for ev, prob, uid in to_send:
                        text = (
                            f"[SIGNAL]\n"
                            f"Event: {ev.get('teams')}\n"
                            f"Odds: {ev.get('odds')}\n"
                            f"Probability: {int(prob*100)}%\n"
                            f"Link: {ev.get('link')}\n"
                            f"Source: {ev.get('source', 'unknown')}"
                        )
                        await notifier.notify(text)
                        tracked_signals[uid] = {
                            "sent_at": datetime.datetime.utcnow().isoformat(),
                            "sent_ts": datetime.datetime.utcnow().timestamp(),
                            "odds": ev.get("odds"),
                            "teams": ev.get("teams"),
                            "link": ev.get("link")
                        }
                else:
                    # heartbeat (только если не было ничего полезного)
                    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    await notifier.notify(f"[heartbeat] {now} UTC — нет подходящих событий.")

                await asyncio.sleep(update_interval)
                backoff = 5
            except Exception as e:
                print("Error in fetcher_loop:", e)
                await notifier.notify(f"⚠️ Ошибка в fetcher_loop: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)
