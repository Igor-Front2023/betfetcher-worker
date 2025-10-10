"""
# Попытка найти счет внутри блока
sc = re.search(r"\d{1,2}:\d{1,2}(?:\s*\d{1,2}:\d{1,2})*", blk)
if not sc:
continue
score = sc.group(0)
# Попытка найти дату рядом
dt_match = re.search(r"\d{1,2}[\./\-]\d{1,2}[\./\-]\d{2,4}|\d{4}-\d{2}-\d{2}", blk)
date = dt_match.group(0) if dt_match else None


# Найти победителя: если присутствуют имена команд — попытаться сравнить голы
winner = None
if ":" in score and team1 and team2:
# возьмём только первый сет/результат до пробела
first_score = score.split()[0]
try:
a_str, b_str = first_score.split(":")
a = int(a_str)
b = int(b_str)
if a > b:
winner = team1
elif b > a:
winner = team2
else:
winner = "Draw"
except Exception:
winner = None


record = {"date": date, "score": score, "winner": winner, "raw_text": blk}
key = (date, score, blk[:40])
if key in seen:
continue
seen.add(key)
results.append(record)
if len(results) >= limit:
return results


return results




async def fetch_h2h(url: str, team1: Optional[str] = None, team2: Optional[str] = None, limit: int = 5, headless: bool = True, timeout: int = DEFAULT_TIMEOUT, proxy: Optional[Dict[str, Any]] = None, wait_for_selector: Optional[str] = "div.h2h__table") -> List[Dict[str, Any]]:
"""Главная функция для внешнего вызова.


url: прямая ссылка на страницу матча/H2H (пример из flashscorekz.com)
team1, team2: опциональные строки с именами команд/игроков — полезны для определения победителя
limit: число последних встреч
proxy: опционально, если нужен прокси для доступа
wait_for_selector: селектор, по которому ждём появления блока H2H


Возвращает список записей: {"date","score","winner","raw_text"}
"""
try:
html = await _load_page_content(url, headless=headless, timeout=timeout, proxy=proxy, wait_for_selector=wait_for_selector)
except Exception as e:
# Внешняя ошибка — возвращаем пустой список, пусть вызывающий код решит что с ней делать
print(f"[stats_fetcher_playwright] Ошибка загрузки страницы {url}: {e}")
return []


soup = BeautifulSoup(html, "html.parser")
h2h = _extract_h2h_from_soup(soup, team1=team1, team2=team2, limit=limit)
return h2h




# При запуске как скрипт — демонстрация работы
if __name__ == "__main__":
import argparse


parser = argparse.ArgumentParser(description="Fetch H2H from Flashscore-like page using Playwright")
parser.add_argument("url", help="match/h2h url (flashscorekz or similar)")
parser.add_argument("team1", help="team/player 1 name", nargs="?", default=None)
parser.add_argument("team2", help="team/player 2 name", nargs="?", default=None)
parser.add_argument("--limit", type=int, default=5)
parser.add_argument("--no-headless", dest="headless", action="store_false")
parser.add_argument("--proxy", type=str, default=None, help="proxy server like http://host:port")


args = parser.parse_args()


proxy_config = None
if args.proxy:
proxy_config = {"server": args.proxy}


async def _demo():
data = await fetch_h2h(args.url, team1=args.team1, team2=args.team2, limit=args.limit, headless=args.headless, proxy=proxy_config)
print("H2H results:")
for r in data:
print(r)


asyncio.run(_demo())
