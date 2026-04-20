import logging
import requests
from datetime import datetime, timezone, timedelta
from config import WEBHOOK_NBA
from scorer import Score

log = logging.getLogger(__name__)

COLORS = {
    "STRONG SIGNAL": 0xFF4500,
    "DECENT SIGNAL": 0xFFD700,
    "MILD SIGNAL":   0x00BFFF,
    "INFORMATIONAL": 0x888888,
}

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
    if not WEBHOOK_NBA:
        log.warning("WEBHOOK_NBA not set")
        return

    title  = market.get("title") or market.get("subtitle") or trade.get("ticker", "Unknown")
    ticker = trade.get("ticker", "")
    taker  = trade.get("taker_side", "yes")
    side   = "YES" if taker == "yes" else "NO"
    side_e = "🟢" if side == "YES" else "🔴"

    try:
        yes_price = float(trade.get("yes_price_dollars") or 0)
        count     = float(trade.get("count_fp") or trade.get("count", 0))
        price_cents = yes_price * 100 if taker == "yes" else (1 - yes_price) * 100
        usd = count * yes_price if taker == "yes" else count * (1 - yes_price)
    except Exception:
        return

    ts = trade.get("created_time", "")
    cons_str = f"{same_side + 1} trades this side" if same_side > 0 else "first trade this side"
    market_url = f"https://kalshi.com/markets/{ticker.split('-')[0].lower()}/{ticker.lower()}" if ticker else "https://kalshi.com"

    embed = {
        "title": f"{s.emoji} {s.label} — Kalshi Whale",
        "color": COLORS.get(s.label, 0x888888),
        "fields": [
            {"name": "📌 Market",
             "value": title,
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
        r = requests.post(WEBHOOK_NBA, json={"embeds": [embed]}, timeout=5)
        r.raise_for_status()
        log.info(f"✅ [KALSHI] ${usd:,.0f} {side} @ {price_cents:.1f}¢ [{s.total}/100] — {title[:50]}")
    except Exception as e:
        log.error(f"Discord failed: {e}")
