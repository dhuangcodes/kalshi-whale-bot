import time
import logging
from collections import defaultdict
from datetime import datetime, timezone
from api import get_recent_trades_global, get_market_info
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

CONSENSUS_WINDOW = 3600


def run():
    log.info("🏀 Kalshi Whale Bot Starting")
    log.info(f"Threshold: ${MIN_TRADE_USD:,.0f} | Poll interval: {POLL_INTERVAL}s")

    seen          = set()
    market_cache  = {}  # ticker -> market info
    consensus_log = defaultdict(list)  # ticker -> [(ts, side)]
    last_cursor   = None

    while True:
        try:
            now    = int(datetime.now(timezone.utc).timestamp())
            trades = get_recent_trades_global(limit=100, cursor=last_cursor)

            if trades:
                # Update cursor to latest trade for next poll
                new_trades = []
                for trade in trades:
                    tid = trade.get("trade_id") or trade.get("id", "")
                    if not tid or tid in seen:
                        continue

                    # Calculate USD size
                    try:
                        yes_price = float(trade.get("yes_price_dollars") or 0)
                        no_price  = float(trade.get("no_price_dollars") or 0)
                        count     = float(trade.get("count_fp") or trade.get("count", 0))
                        taker     = trade.get("taker_side", "yes")
                        price     = yes_price if taker == "yes" else no_price
                        usd       = count * price
                    except Exception:
                        seen.add(tid)
                        continue

                    if usd < MIN_TRADE_USD:
                        seen.add(tid)
                        continue

                    seen.add(tid)
                    trade["_usd"] = usd
                    new_trades.append(trade)

                for trade in new_trades:
                    ticker = trade.get("ticker", "")

                    # Get market info for title
                    if ticker not in market_cache:
                        info = get_market_info(ticker) or {}
                        market_cache[ticker] = info
                    market = market_cache.get(ticker, {})

                    taker       = trade.get("taker_side", "yes")
                    side        = "YES" if taker == "yes" else "NO"
                    yes_price   = float(trade.get("yes_price_dollars") or 0)
                    no_price    = float(trade.get("no_price_dollars") or 0)
                    price_cents = (yes_price if taker == "yes" else no_price) * 100
                    usd         = trade["_usd"]

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

                if new_trades:
                    log.info(f"Fired {len(new_trades)} alerts")
                else:
                    log.info("No whale trades")

            # Cleanup
            if len(seen) > 50_000:
                seen = set(list(seen)[-10_000:])
            if len(market_cache) > 2000:
                market_cache.clear()
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
