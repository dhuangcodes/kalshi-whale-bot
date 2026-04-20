import time
import logging
from collections import defaultdict
from datetime import datetime, timezone
from api import get_nba_markets, get_market_trades, get_global_trades
from scorer import score
from alerts import send_alert
from config import MIN_TRADE_USD, POLL_INTERVAL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("kalshi_whale.log"),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)

MARKET_REFRESH   = 3600   # refresh market list every hour
CONSENSUS_WINDOW = 3600   # 1 hour consensus window


def run():
    log.info("🏀 Kalshi NBA Whale Bot Starting")
    log.info(f"Threshold: ${MIN_TRADE_USD:,.0f} | Poll interval: {POLL_INTERVAL}s")

    seen             = set()
    markets          = []
    market_map       = {}   # ticker -> market info
    last_refresh     = 0
    consensus_log    = defaultdict(list)  # ticker -> [(ts, side)]

    while True:
        try:
            now = int(datetime.now(timezone.utc).timestamp())

            # Refresh NBA market list hourly
            if now - last_refresh > MARKET_REFRESH or not markets:
                log.info("Refreshing Kalshi NBA markets...")
                markets = get_nba_markets()
                market_map = {m["ticker"]: m for m in markets if m.get("ticker")}
                last_refresh = now
                log.info(f"Tracking {len(markets)} NBA markets")

            if not markets:
                log.warning("No NBA markets found, retrying in 60s")
                time.sleep(60)
                continue

            # Poll each market for recent trades
            new_trades = []
            for market in markets:
                ticker = market.get("ticker", "")
                if not ticker:
                    continue

                trades = get_market_trades(ticker, limit=20)
                for trade in trades:
                    tid = trade.get("trade_id") or trade.get("id", "")
                    if not tid or tid in seen:
                        continue

                    # Calculate USD size
                    try:
                        yes_price = float(trade.get("yes_price_dollars") or 0)
                        count     = float(trade.get("count_fp") or trade.get("count", 0))
                        taker     = trade.get("taker_side", "yes")
                        usd       = count * yes_price if taker == "yes" else count * (1 - yes_price)
                    except Exception:
                        seen.add(tid)
                        continue

                    if usd < MIN_TRADE_USD:
                        seen.add(tid)
                        continue

                    seen.add(tid)
                    trade["ticker"] = ticker
                    trade["_usd"]   = usd
                    new_trades.append((trade, market))

            for trade, market in new_trades:
                ticker = trade["ticker"]
                usd    = trade["_usd"]
                taker  = trade.get("taker_side", "yes")
                side   = "YES" if taker == "yes" else "NO"

                try:
                    yes_price   = float(trade.get("yes_price_dollars") or 0)
                    price_cents = yes_price * 100 if taker == "yes" else (1 - yes_price) * 100
                except Exception:
                    price_cents = 50.0

                # Consensus
                cutoff = now - CONSENSUS_WINDOW
                consensus_log[ticker] = [
                    (t, s) for t, s in consensus_log[ticker]
                    if t > cutoff
                ]
                same_side = sum(1 for t, s in consensus_log[ticker] if s == side)
                consensus_log[ticker].append((now, side))

                s = score(usd, price_cents, same_side)
                send_alert(trade, market, s, same_side)

            if not new_trades:
                log.info(f"No whale trades (tracking {len(markets)} markets)")

            # Cleanup
            if len(seen) > 50_000:
                seen = set(list(seen)[-10_000:])
            for ticker in list(consensus_log.keys()):
                consensus_log[ticker] = [
                    (t, s) for t, s in consensus_log[ticker]
                    if t > now - CONSENSUS_WINDOW
                ]

        except Exception as e:
            log.error(f"Loop error: {e}", exc_info=True)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    run()
