"""
Kalshi whale trade scorer (0-100).

No wallet PnL available on Kalshi public API so scoring is based on:
  1. Trade Size       — 50 pts
  2. Consensus        — 30 pts (same side, same market, last hour)
  3. Price Conviction — 20 pts (only counts if trade >= $10k)
"""
from dataclasses import dataclass


@dataclass
class Score:
    total: int
    size_pts: int
    consensus_pts: int
    conviction_pts: int
    label: str
    emoji: str
    reason: str


def score(usd: float, price_cents: float, same_side: int) -> Score:

    # --- 1. Trade Size (50 pts) ---
    if usd >= 100_000:   sz = 50
    elif usd >= 50_000:  sz = 40
    elif usd >= 25_000:  sz = 28
    elif usd >= 10_000:  sz = 16
    elif usd >= 5_000:   sz = 7
    else:                sz = 0

    # --- 2. Consensus (30 pts) ---
    if same_side >= 4:   cons = 30
    elif same_side >= 3: cons = 22
    elif same_side >= 2: cons = 14
    elif same_side == 1: cons = 7
    else:                cons = 0

    # --- 3. Price Conviction (20 pts) — only if $10k+ ---
    if usd >= 10_000:
        p = price_cents
        if   p <= 15 or p >= 85: conv = 20
        elif p <= 25 or p >= 75: conv = 16
        elif p <= 35 or p >= 65: conv = 11
        elif p <= 45 or p >= 55: conv = 6
        else:                    conv = 3
    else:
        conv = 0

    total = min(100, sz + cons + conv)

    if total >= 80:   label, emoji = "STRONG SIGNAL", "🔥"
    elif total >= 60: label, emoji = "DECENT SIGNAL", "⚡"
    elif total >= 40: label, emoji = "MILD SIGNAL",   "👀"
    else:             label, emoji = "INFORMATIONAL", "📊"

    parts = []
    if sz >= 40:   parts.append(f"massive trade (${usd:,.0f})")
    elif sz >= 28: parts.append(f"large trade (${usd:,.0f})")
    elif sz >= 16: parts.append(f"solid trade (${usd:,.0f})")
    else:          parts.append(f"small trade (${usd:,.0f})")

    if cons >= 22: parts.append(f"{same_side + 1} trades same side 🐋")
    elif cons >= 14: parts.append(f"{same_side} other trades same side")
    elif cons >= 7:  parts.append("1 other trade same side")

    if conv >= 16:  parts.append(f"high conviction ({price_cents:.0f}¢)")
    elif conv >= 6: parts.append(f"moderate conviction ({price_cents:.0f}¢)")
    elif conv == 3: parts.append(f"near 50/50 ({price_cents:.0f}¢)")

    return Score(total, sz, cons, conv, label, emoji,
                 ", ".join(parts) or "no standout factors")
