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


def get_recent_trades_global(limit: int = 100, cursor: str = None) -> list[dict]:
    """
    Get recent trades across ALL Kalshi markets.
    Much more efficient than polling individual markets.
    """
    params = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    data = _get("/markets/trades", params)
    if data and isinstance(data.get("trades"), list):
        return data["trades"]
    return []


def get_market_info(ticker: str) -> dict:
    """Get market details including title."""
    data = _get(f"/markets/{ticker}")
    if data and data.get("market"):
        return data["market"]
    return {}
