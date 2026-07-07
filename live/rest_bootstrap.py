# live/rest_bootstrap.py

import os
import requests
from contextlib import redirect_stdout

from market.candle import Candle


BITVAVO_BASE_URL = "https://api.bitvavo.com/v2"


class RestBootstrap:
    def __init__(self, market: str, interval: str = "1h", limit: int = 400):
        self.market = market
        self.interval = interval
        self.limit = limit

    def fetch_candles(self):
        url = f"{BITVAVO_BASE_URL}/{self.market}/candles"
        params = {
            "interval": self.interval,
            "limit": self.limit,
        }

        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()

        raw_candles = response.json()

        if not isinstance(raw_candles, list):
            raise ValueError(f"Unexpected Bitvavo response for {self.market}: {raw_candles}")

        # Bitvavo restituisce newest -> oldest.
        # Il motore deve ricevere oldest -> newest.
        raw_candles = list(reversed(raw_candles))

        candles = []

        for item in raw_candles:
            if len(item) < 6:
                continue

            timestamp_ms = int(item[0])

            candle = Candle(
                timestamp=float(timestamp_ms),
                open=float(item[1]),
                high=float(item[2]),
                low=float(item[3]),
                close=float(item[4]),
                volume=float(item[5]),
                symbol=self.market,
            )

            candles.append(candle)

        return candles

    def warmup_engine(self, engine, warmup_mode=True, silent=True):
        candles = self.fetch_candles()

        if warmup_mode:
            engine.is_warming_up = True

        try:
            if silent and warmup_mode:
                with open(os.devnull, "w") as devnull:
                    with redirect_stdout(devnull):
                        for candle in candles:
                            engine.on_candle(candle)
            else:
                for candle in candles:
                    engine.on_candle(candle)

        finally:
            if warmup_mode:
                engine.is_warming_up = False

        return {
            "market": self.market,
            "interval": self.interval,
            "requested_limit": self.limit,
            "loaded_candles": len(candles),
            "first_timestamp_ms": candles[0].timestamp if candles else None,
            "last_timestamp_ms": candles[-1].timestamp if candles else None,
        }
