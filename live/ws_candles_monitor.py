import json
import time
import csv
import os
import websocket
from datetime import datetime, timezone

WS_URL = "wss://ws.bitvavo.com/v2/"

MARKETS = ["SOL-USDC", "XRP-USDC"]
INTERVAL = "1h"

LOG_FILE = "logs/ws_candles_monitor.csv"

counts = {market: 0 for market in MARKETS}


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def ensure_log():
    os.makedirs("logs", exist_ok=True)

    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "received_at_utc",
                "market",
                "interval",
                "timestamp_ms",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "market_count"
            ])


def log_candle(market, interval, row):
    counts[market] = counts.get(market, 0) + 1

    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            utc_now(),
            market,
            interval,
            row[0],
            row[1],
            row[2],
            row[3],
            row[4],
            row[5],
            counts[market]
        ])

    print(
        f"[{utc_now()}] {market} | {interval} | "
        f"C={row[4]} V={row[5]} | "
        f"COUNT={counts[market]}"
    )


def on_open(ws):
    print(f"[{utc_now()}] CONNECTED")

    payload = {
        "action": "subscribe",
        "channels": [
            {
                "name": "candles",
                "markets": MARKETS,
                "interval": [INTERVAL]
            }
        ]
    }

    ws.send(json.dumps(payload))
    print(f"[{utc_now()}] SUBSCRIBED REQUEST SENT")


def on_message(ws, message):
    data = json.loads(message)

    if isinstance(data, dict) and data.get("event") == "subscribed":
        print(f"[{utc_now()}] SUBSCRIPTION OK")
        print(json.dumps(data, indent=2))
        return

    if isinstance(data, dict) and data.get("event") == "candle":
        market = data.get("market")
        interval = data.get("interval")
        candles = data.get("candle", [])

        for row in candles:
            log_candle(market, interval, row)

        return

    print(f"[{utc_now()}] OTHER MESSAGE:")
    print(json.dumps(data, indent=2))


def on_error(ws, error):
    print(f"[{utc_now()}] ERROR: {error}")


def on_close(ws, code, msg):
    print(f"[{utc_now()}] CLOSED: {code} {msg}")


def main():
    ensure_log()

    while True:
        print(f"[{utc_now()}] START WS CANDLE MONITOR")

        ws = websocket.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )

        ws.run_forever(
            ping_interval=30,
            ping_timeout=10
        )

        print(f"[{utc_now()}] RECONNECT IN 5s")
        time.sleep(5)


if __name__ == "__main__":
    main()
