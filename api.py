"""
Kalshi public API — no auth required for market data.
Base: https://api.elections.kalshi.com/trade-api/v2
"""
import time
import logging
import requests

log = logging.getLogger(__name__)
BASE = "https://api.elections.kalshi.com/trade-api/v2"

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

# Kalshi uses city names and player names in titles, not team names
NBA_KEYWORDS = [
    # City names Kalshi uses
    "new york", "boston", "miami", "chicago", "cleveland", "denver",
    "minneapolis", "oklahoma", "golden state", "memphis", "milwaukee",
    "new orleans", "atlanta", "detroit", "indiana", "los angeles",
    "orlando", "philadelphia", "phoenix", "portland", "sacramento",
    "san antonio", "toronto", "utah", "washington",
    # Player names for props
    "lebron", "curry", "durant", "jokic", "giannis", "tatum", "embiid",
    "luka", "morant", "edwards", "towns", "brunson", "mitchell",
    "harden", "banchero", "mobley", "allen", "hart", "barrett",
    # Series ticker prefix
    "kxmvesportsmultigame", "kxnba",
]

SPORTS_TICKERS = ["KXMVESPORTSMULTIGAMEEXTENDED", "KXMVESPORTSMULTIGAME"]


def _get(path: str, params: dict = {}, retries: int = 3):
    for i in range(retries):
        try:
            r = SESSION.get(f"{BASE}{path}", params=params, timeout=12)
            r.raise_for_status()
            return r.json()
        except requests.HTTPError as e:
            code = e.response.status_code
            if code == 429:
                time.sleep(2 ** i)
            elif code in (400, 404):
                return None
            else:
                if i == retries - 1:
                    return None
                time.sleep(1)
        except Exception as e:
            if i == retries - 1:
                log.debug(f"Request failed: {e}")
                return None
            time.sleep(1)
    return None


def get_nba_markets() -> list[dict]:
    """Fetch open NBA/sports markets — uses ticker prefix and city/player name matching."""
    markets = []
    cursor = None
    pages = 0

    while pages < 10:
        params = {"status": "open", "limit": 200}
        if cursor:
            params["cursor"] = cursor

        data = _get("/markets", params)
        if not data:
            break

        batch = data.get("markets", [])
        for m in batch:
            title  = (m.get("title") or "").lower()
            ticker = (m.get("ticker") or "").upper()

            # Match by ticker prefix (Kalshi sports markets)
            is_sports_ticker = any(ticker.startswith(t) for t in SPORTS_TICKERS)
            # Match by NBA city/player names in title
            is_nba_title = any(kw in title for kw in NBA_KEYWORDS)

            if is_sports_ticker or is_nba_title:
                markets.append(m)

        cursor = data.get("cursor")
        log.info(f"Kalshi page {pages}: {len(batch)} markets, {len(markets)} sports so far")
        pages += 1
        if not cursor or not batch:
            break

    return markets


def get_market_trades(ticker: str, limit: int = 50) -> list[dict]:
    """Get recent trades for a specific market."""
    data = _get(f"/markets/{ticker}/trades", {"limit": limit})
    if data and isinstance(data.get("trades"), list):
        return data["trades"]
    return []


def get_global_trades(limit: int = 100) -> list[dict]:
    """Get recent trades across all markets."""
    data = _get("/markets/trades", {"limit": limit})
    if data and isinstance(data.get("trades"), list):
        return data["trades"]
    return []
