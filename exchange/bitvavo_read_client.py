import os
import sys
import json
from datetime import datetime, timezone

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from python_bitvavo_api.bitvavo import Bitvavo
from config import API_KEY, API_SECRET


SNAPSHOT_PATH = os.path.join(PROJECT_ROOT, "state", "exchange_snapshot.json")


class BitvavoReadClient:
    def __init__(self):
        self.client = Bitvavo({
            "APIKEY": API_KEY,
            "APISECRET": API_SECRET,
            "RESTURL": "https://api.bitvavo.com/v2",
            "WSURL": "wss://ws.bitvavo.com/v2/",
            "ACCESSWINDOW": 10000
        })

    def get_balance(self):
        return self.client.balance({})

    def get_ticker_price(self, market="SOL-USDC"):
        return self.client.tickerPrice({"market": market})

    def get_open_orders(self, market="SOL-USDC"):
        return self.client.ordersOpen({"market": market})

    def get_wallet_snapshot(self, market="SOL-USDC"):
        balance = self.get_balance()
        ticker = self.get_ticker_price(market)
        open_orders = self.get_open_orders(market)

        selected_balances = {}

        for item in balance:
            symbol = item.get("symbol")

            if symbol in ["USDC", "SOL", "EUR"]:
                selected_balances[symbol] = {
                    "available": item.get("available"),
                    "in_order": item.get("inOrder")
                }

        return {
            "mode": "LIVE_READ",
            "api_write": False,
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "market": market,
            "ticker": ticker,
            "balances": selected_balances,
            "open_orders": open_orders,
            "raw_balance_count": len(balance)
        }


def save_snapshot(snapshot, path=SNAPSHOT_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)

    tmp_path = path + ".tmp"

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
        f.write("\n")

    os.replace(tmp_path, path)


def main():
    client = BitvavoReadClient()
    snapshot = client.get_wallet_snapshot("SOL-USDC")

    save_snapshot(snapshot)

    print(json.dumps(snapshot, indent=2))
    print("")
    print(f"Snapshot saved to: {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
