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

NBA_KEYWORDS = [
    "nba", "hawks", "celtics", "nets", "hornets", "bulls", "cavaliers",
    "mavericks", "nuggets", "pistons", "warriors", "rockets", "pacers",
    "clippers", "lakers", "grizzlies", "heat", "bucks", "timberwolves",
    "pelicans", "knicks", "thunder", "magic", "76ers", "suns",
    "trail blazers", "blazers", "kings", "spurs", "raptors", "jazz",
    "wizards", "playoff", "finals", "championship"
]


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
    """Fetch all open NBA markets."""
    markets = []
    cursor = None

    while True:
        params = {"status": "open", "limit": 200}
        if cursor:
            params["cursor"] = cursor

        data = _get("/markets", params)
        if not data:
            break

        batch = data.get("markets", [])
        for m in batch:
            title = (m.get("title") or m.get("subtitle") or "").lower()
            ticker = (m.get("ticker") or "").upper()
            if any(kw in title for kw in NBA_KEYWORDS) or "NBA" in ticker:
                markets.append(m)

        cursor = data.get("cursor")
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
