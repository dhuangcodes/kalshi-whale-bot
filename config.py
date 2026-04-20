import os
from dotenv import load_dotenv
load_dotenv()

WEBHOOK_NBA        = os.getenv("WEBHOOK_NBA", "")
MIN_TRADE_USD      = float(os.getenv("MIN_TRADE_USD", "3000"))
POLL_INTERVAL      = int(os.getenv("POLL_INTERVAL", "60"))
