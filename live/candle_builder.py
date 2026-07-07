import json
import csv
import time
import os
import websocket
from dataclasses import dataclass
from datetime import datetime, timezone


WS_URL = "wss://ws.bitvavo.com/v2/"

MARKETS = [
    "SOL-USDC",
    "XRP-USDC"
]

INTERVAL = "1h"

LOG_DIR = "logs"
EVENT_LOG = os.path.join(LOG_DIR, "candle_builder_events.csv")
CLOSED_LOG = os.path.join(LOG_DIR, "closed_candles.csv")


@dataclass
class BuiltCandle:
    market: str
    interval: str
    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    updates: int


class CandleBuilder:
    def __init__(self):
        self.current = {}

    def process(self, market, interval, row):
        timestamp_ms = int(row[0])

        incoming = BuiltCandle(
            market=market,
            interval=interval,
            timestamp_ms=timestamp_ms,
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
            updates=1
        )

        key = (market, interval)

        if key not in self.current:
            self.current[key] = incoming
            return "OPENED", incoming, None

        current = self.current[key]

        if incoming.timestamp_ms == current.timestamp_ms:
            incoming.updates = current.updates + 1
            self.current[key] = incoming
            return "UPDATED", incoming, None

        closed = current
        self.current[key] = incoming

        return "ROLLED", incoming, closed


builder = CandleBuilder()


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def ensure_logs():
    os.makedirs(LOG_DIR, exist_ok=True)

    if not os.path.exists(EVENT_LOG):
        with open(EVENT_LOG, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "received_at_utc",
                "event_type",
                "market",
                "interval",
                "timestamp_ms",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "updates"
            ])

    if not os.path.exists(CLOSED_LOG):
        with open(CLOSED_LOG, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "closed_at_utc",
                "market",
                "interval",
                "timestamp_ms",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "updates"
            ])


def log_event(event_type, candle):
    with open(EVENT_LOG, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            utc_now(),
            event_type,
            candle.market,
            candle.interval,
            candle.timestamp_ms,
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
            candle.updates
        ])


def log_closed(candle):
    with open(CLOSED_LOG, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            utc_now(),
            candle.market,
            candle.interval,
            candle.timestamp_ms,
            candle.open,
            candle.high,
            candle.low,
            candle.close,
            candle.volume,
            candle.updates
        ])


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

    print(f"[{utc_now()}] SUBSCRIBE")
    print(json.dumps(payload, indent=2))

    ws.send(json.dumps(payload))


def on_message(ws, message):
    try:
        data = json.loads(message)
    except Exception:
        print(f"[{utc_now()}] RAW MESSAGE")
        print(message)
        return

    if not isinstance(data, dict):
        print(f"[{utc_now()}] NON-DICT MESSAGE")
        print(data)
        return

    if data.get("event") != "candle":
        print(f"[{utc_now()}] CONTROL MESSAGE")
        print(json.dumps(data, indent=2))
        return

    market = data.get("market")
    interval = data.get("interval")
    candles = data.get("candle", [])

    for row in candles:
        event_type, current, closed = builder.process(
            market=market,
            interval=interval,
            row=row
        )

        if event_type == "OPENED":
            log_event("OPENED", current)

            print(
                f"[{utc_now()}] OPENED "
                f"{current.market} {current.interval} "
                f"ts={current.timestamp_ms} "
                f"C={current.close} V={current.volume} "
                f"updates={current.updates}"
            )

        elif event_type == "UPDATED":
            log_event("UPDATED", current)

            print(
                f"[{utc_now()}] UPDATED "
                f"{current.market} {current.interval} "
                f"ts={current.timestamp_ms} "
                f"C={current.close} V={current.volume} "
                f"updates={current.updates}"
            )

        elif event_type == "ROLLED":
            log_event("CLOSED", closed)
            log_closed(closed)
            log_event("OPENED", current)

            print("")
            print("=" * 70)
            print(f"[{utc_now()}] CANDLE CLOSED")
            print(
                f"{closed.market} {closed.interval} "
                f"ts={closed.timestamp_ms} "
                f"O={closed.open} H={closed.high} "
                f"L={closed.low} C={closed.close} "
                f"V={closed.volume} updates={closed.updates}"
            )
            print("=" * 70)

            print(
                f"[{utc_now()}] OPENED "
                f"{current.market} {current.interval} "
                f"ts={current.timestamp_ms} "
                f"C={current.close} V={current.volume} "
                f"updates={current.updates}"
            )


def on_error(ws, error):
    print("")
    print("=" * 70)
    print(f"[{utc_now()}] ERROR")
    print(error)
    print("=" * 70)


def on_close(ws, code, msg):
    print("")
    print("=" * 70)
    print(f"[{utc_now()}] CLOSED CONNECTION")
    print(code, msg)
    print("=" * 70)


def main():
    ensure_logs()

    try:
        while True:
            print("")
            print("=" * 70)
            print(f"[{utc_now()}] STARTING CANDLE BUILDER")
            print("=" * 70)

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

    except KeyboardInterrupt:
        print("")
        print(f"[{utc_now()}] SHUTDOWN REQUESTED")
        print("Candle builder stopped cleanly.")


if __name__ == "__main__":
    main()
