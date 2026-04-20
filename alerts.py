import logging
import requests
from datetime import datetime, timezone, timedelta
from config import (WEBHOOK_NBA, WEBHOOK_MLB, WEBHOOK_TENNIS,
                    WEBHOOK_VIDEOGAMES, WEBHOOK_OTHER)
from scorer import Score

log = logging.getLogger(__name__)

COLORS = {
    "STRONG SIGNAL": 0xFF4500,
    "DECENT SIGNAL": 0xFFD700,
    "MILD SIGNAL":   0x00BFFF,
    "INFORMATIONAL": 0x888888,
}

# Kalshi uses city names in titles
NBA_CITIES = [
    "new york", "boston", "miami", "chicago", "cleveland", "denver",
    "minnesota", "oklahoma", "golden state", "memphis", "milwaukee",
    "new orleans", "atlanta", "detroit", "indiana", "los angeles",
    "orlando", "philadelphia", "phoenix", "portland", "sacramento",
    "san antonio", "toronto", "utah", "washington", "brooklyn",
    "charlotte", "dallas", "houston", "memphis"
]
NBA_PLAYERS = [
    "lebron", "curry", "durant", "jokic", "giannis", "tatum", "embiid",
    "luka", "morant", "edwards", "towns", "brunson", "mitchell",
    "harden", "banchero", "mobley", "allen", "hart", "barrett",
    "donovan", "jalen", "evan", "jarrett", "nickeil", "jonathan",
    "karl-anthony", "anthony", "josh", "rj"
]
MLB_KEYWORDS = [
    "yankees", "red sox", "dodgers", "mets", "cubs", "braves", "astros",
    "manzardo", "kwan", "arrighetti", "baseball", "mlb", "pitcher",
    "home run", "hits", "strikeout"
]
TENNIS_KEYWORDS = [
    "harris", "garin", "llamas", "rodesch", "gaubas", "trungelliti",
    "tennis", "atp", "wta", "wimbledon", "open", "set", "game"
]

def _get_webhook(title: str) -> str:
    t = title.lower()
    # Check NBA cities and player names
    if any(kw in t for kw in NBA_CITIES) or any(kw in t for kw in NBA_PLAYERS):
        # Double check it's not baseball
        if not any(kw in t for kw in MLB_KEYWORDS):
            return WEBHOOK_NBA
    if any(kw in t for kw in MLB_KEYWORDS):
        return WEBHOOK_MLB
    if any(kw in t for kw in TENNIS_KEYWORDS):
        return WEBHOOK_TENNIS
    # Sports multigame tickers go to NBA by default
    if "kxmvesports" in t or "kxnba" in t:
        return WEBHOOK_NBA
    return WEBHOOK_OTHER

def _route_name(title: str) -> str:
    t = title.lower()
    if any(kw in t for kw in NBA_CITIES) or any(kw in t for kw in NBA_PLAYERS):
        if not any(kw in t for kw in MLB_KEYWORDS):
            return "NBA"
    if any(kw in t for kw in MLB_KEYWORDS): return "MLB"
    if any(kw in t for kw in TENNIS_KEYWORDS): return "TENNIS"
    return "OTHER"

def _bar(n: int) -> str:
    return "█" * round(n / 10) + "░" * (10 - round(n / 10))

def _format_est(ts_str: str) -> str:
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        est = dt.astimezone(timezone(timedelta(hours=-5)))
        return est.strftime("%b %d %I:%M %p EST")
    except Exception:
        return "unknown"


def send_alert(trade: dict, market: dict, s: Score, same_side: int):
    title = market.get("title") or trade.get("ticker", "Unknown")
    webhook = _get_webhook(title)
    if not webhook:
        return

    ticker = trade.get("ticker", "")
    taker  = trade.get("taker_side", "yes")
    side   = "YES" if taker == "yes" else "NO"
    side_e = "🟢" if side == "YES" else "🔴"

    try:
        yes_price   = float(trade.get("yes_price_dollars") or 0)
        count       = float(trade.get("count_fp") or trade.get("count", 0))
        price_cents = yes_price * 100 if taker == "yes" else (1 - yes_price) * 100
        usd         = count * yes_price if taker == "yes" else count * (1 - yes_price)
    except Exception:
        return

    ts       = trade.get("created_time", "")
    cons_str = f"{same_side + 1} trades this side" if same_side > 0 else "first trade this side"
    market_url = f"https://kalshi.com/markets/{ticker.split('-')[0].lower()}" if ticker else "https://kalshi.com"

    embed = {
        "title": f"{s.emoji} {s.label} — Kalshi Whale",
        "color": COLORS.get(s.label, 0x888888),
        "fields": [
            {"name": "📌 Market",
             "value": title[:200],
             "inline": False},
            {"name": f"{side_e} Side & Price",
             "value": f"**{side}** @ **{price_cents:.1f}¢**",
             "inline": True},
            {"name": "💰 Size",
             "value": f"**${usd:,.0f}**",
             "inline": True},
            {"name": "📊 Confidence Score",
             "value": f"`{_bar(s.total)}` **{s.total}/100**\n{s.reason}",
             "inline": False},
            {"name": "🔬 Breakdown",
             "value": (f"Size: `{s.size_pts}/50` • "
                       f"Consensus: `{s.consensus_pts}/30` • "
                       f"Conviction: `{s.conviction_pts}/20`"),
             "inline": False},
            {"name": "📈 Context",
             "value": cons_str,
             "inline": False},
            {"name": "🔗 Links",
             "value": f"[Market]({market_url})",
             "inline": False},
        ],
        "footer": {"text": f"Kalshi Whale Alert  •  Trade placed: {_format_est(ts)}"},
    }

    try:
        r = requests.post(webhook, json={"embeds": [embed]}, timeout=5)
        r.raise_for_status()
        log.info(f"✅ [KALSHI {_route_name(title)}] ${usd:,.0f} {side} @ {price_cents:.1f}¢ [{s.total}/100]")
    except Exception as e:
        log.error(f"Discord failed: {e}")
