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

# Explicit NBA team names only — no city names that overlap with MLB
NBA_TEAMS = [
    "timberwolves", "wolves", "nuggets", "cavaliers", "cavs", "celtics",
    "knicks", "bucks", "pacers", "heat", "magic", "76ers", "sixers",
    "thunder", "warriors", "lakers", "clippers", "suns", "grizzlies",
    "pelicans", "hawks", "pistons", "raptors", "nets", "hornets",
    "bulls", "mavericks", "mavs", "rockets", "trail blazers", "blazers",
    "kings", "spurs", "jazz", "wizards"
]

# NBA explicit context words
NBA_CONTEXT = [
    "points scored", "wins by", "winner", "game 1", "game 2", "game 3",
    "game 4", "game 5", "game 6", "game 7", "spread", "playoff",
    "nba", "basketball", "rebounds", "assists"
]

# MLB — team names AND baseball-specific words
MLB_TEAMS = [
    "yankees", "red sox", "dodgers", "mets", "cubs", "braves", "astros",
    "guardians", "rockies", "tigers", "royals", "angels", "marlins",
    "brewers", "twins", "phillies", "pirates", "padres", "cardinals",
    "rays", "rangers", "blue jays", "nationals", "orioles", "athletics",
    "mariners", "white sox", "reds", "giants"
]
MLB_KEYWORDS = ["runs", "innings", "pitcher", "hits", "strikeout", "mlb", "baseball", " m winner", "total runs"]

TENNIS_KEYWORDS = [
    "atp", "wta", "wimbledon", "roland garros", "us open", "australian open",
    "challenger", "wuning", "tennis", "grand slam", "match winner"
]

VIDEOGAME_KEYWORDS = [
    "cs2", "csgo", "valorant", "league of legends", "lol", "dota",
    "overwatch", "call of duty", "cod", "navi", "natus vincere", "faze",
    "vitality", "astralis", "g2", "fnatic", "team liquid", "esport",
    "blast", "pgl", "iem", "esl", "fortnite"
]


def _get_webhook(title: str) -> str:
    t = title.lower()

    # MLB check first — specific team names OR baseball keywords
    if any(kw in t for kw in MLB_KEYWORDS) or any(kw in t for kw in MLB_TEAMS):
        return WEBHOOK_MLB

    # Tennis
    if any(kw in t for kw in TENNIS_KEYWORDS):
        return WEBHOOK_TENNIS

    # Esports
    if any(kw in t for kw in VIDEOGAME_KEYWORDS):
        return WEBHOOK_VIDEOGAMES

    # NBA — must match an actual NBA team name (not just a city)
    has_nba_team = any(kw in t for kw in NBA_TEAMS)
    has_nba_ctx  = any(kw in t for kw in NBA_CONTEXT)

    if has_nba_team or has_nba_ctx:
        return WEBHOOK_NBA

    return WEBHOOK_OTHER


def _route_name(title: str) -> str:
    t = title.lower()
    if any(kw in t for kw in MLB_KEYWORDS) or any(kw in t for kw in MLB_TEAMS):
        return "MLB"
    if any(kw in t for kw in TENNIS_KEYWORDS):
        return "TENNIS"
    if any(kw in t for kw in VIDEOGAME_KEYWORDS):
        return "GAMES"
    if any(kw in t for kw in NBA_TEAMS) or any(kw in t for kw in NBA_CONTEXT):
        return "NBA"
    return "OTHER"


def _bar(n: int) -> str:
    filled = round(n / 10)
    return "█" * filled + "░" * (10 - filled)

def _format_est(ts_str: str) -> str:
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        est = dt.astimezone(timezone(timedelta(hours=-5)))
        return est.strftime("%b %d %I:%M %p EST")
    except Exception:
        return "unknown"


def send_alert(trade: dict, market: dict, s: Score, same_side: int):
    title   = market.get("title") or trade.get("ticker", "Unknown")
    webhook = _get_webhook(title)
    if not webhook:
        return

    ticker  = trade.get("ticker", "")
    taker   = trade.get("taker_side", "yes")
    side    = "YES" if taker == "yes" else "NO"
    side_e  = "🟢" if side == "YES" else "🔴"

    try:
        yes_price   = float(trade.get("yes_price_dollars") or 0)
        no_price    = float(trade.get("no_price_dollars") or 0)
        count       = float(trade.get("count_fp") or trade.get("count", 0))
        price_cents = yes_price * 100 if taker == "yes" else no_price * 100
        usd         = trade.get("_usd") or (count * yes_price if taker == "yes" else count * no_price)
    except Exception:
        return

    ts         = trade.get("created_time", "")
    cons_str   = f"{same_side + 1} trades this side" if same_side > 0 else "first trade this side"
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
        log.info(f"✅ [KALSHI {_route_name(title)}] ${usd:,.0f} {side} @ {price_cents:.1f}¢ [{s.total}/100] — {title[:50]}")
    except Exception as e:
        log.error(f"Discord failed: {e}")
