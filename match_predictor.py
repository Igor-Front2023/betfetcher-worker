# match_predictor.py - H2H + odds-based predictor with caching
import asyncio
import re
import time
try:
    from stats_fetcher_playwright import fetch_h2h as _fetch_h2h
except Exception:
    _fetch_h2h = None

_h2h_cache = {}  # key -> (ts, data)
H2H_TTL = 3600  # seconds

def norm(name: str):
    return re.sub(r'[^a-zA-Z0-9\\s]','', name).strip().lower()

async def fetch_h2h_cached(team1, team2):
    key = f"{norm(team1)}|{norm(team2)}"
    now = time.time()
    cached = _h2h_cache.get(key)
    if cached and now - cached[0] < H2H_TTL:
        return cached[1]
    if _fetch_h2h:
        try:
            data = await _fetch_h2h('', team1=team1, team2=team2, limit=8)
            _h2h_cache[key] = (now, data)
            return data
        except Exception:
            return None
    return None

async def analyze_event(event: dict) -> float:
    """
    Returns estimated probability (0..1) that the specified selection will win.
    Strategy:
      - Try H2H via Playwright parser if available.
      - Combine H2H win ratio and implied odds to produce probability.
    """
    odds = float(event.get('odds') or 1.0)
    teams = event.get('teams','')
    # split teams heuristically by common separators
    parts = [p.strip() for p in re.split(r'[-–—vsVS@]', teams) if p.strip()]
    team1 = parts[0] if parts else None
    team2 = parts[1] if len(parts)>1 else None

    # Try H2H
    try:
        if team1 and team2:
            h2h = await fetch_h2h_cached(team1, team2)
            if h2h and isinstance(h2h, dict):
                a = h2h.get('a_wins') or h2h.get('wins_a') or h2h.get('wins1') or 0
                b = h2h.get('b_wins') or h2h.get('wins_b') or h2h.get('wins2') or 0
                draws = h2h.get('draws') or 0
                total = max(1, a + b + draws)
                favorite_ratio = max(a,b)/total
                implied = 1.0/odds if odds>0 else 0.5
                # combine: 60% H2H, 40% implied
                prob = 0.6*favorite_ratio + 0.4*implied
                return min(0.99, max(0.0, prob))
    except Exception:
        pass

    # Fallback: implied odds shrunk toward 0.5
    implied = 1.0/odds if odds>0 else 0.5
    prob = 0.5*(implied + 0.5)
    return min(0.99, max(0.0, prob))
