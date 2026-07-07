import time
from market.candle import Candle


class CandleBuilder:

    def __init__(self, interval_seconds=3600, symbol="SOL-USDC", callback=None):

        self.interval = interval_seconds
        self.symbol = symbol

        self.callback = callback  # funzione verso engine

        self.current_candle = None
        self.start_time = None

    # =========================
    # MAIN INPUT (TICK PRICE)
    # =========================
    def on_price(self, price):

        now = time.time()

        # inizializza candela
        if self.current_candle is None:
            self.start_time = now
            self.current_candle = {
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 0.0
            }
            return

        # aggiorna candela corrente
        self.current_candle["high"] = max(self.current_candle["high"], price)
        self.current_candle["low"] = min(self.current_candle["low"], price)
        self.current_candle["close"] = price
        self.current_candle["volume"] += 1  # proxy volume (tick count)

        # check fine candela
        if now - self.start_time >= self.interval:

            candle = Candle(
                timestamp=now,
                open=self.current_candle["open"],
                high=self.current_candle["high"],
                low=self.current_candle["low"],
                close=self.current_candle["close"],
                volume=self.current_candle["volume"],
                symbol=self.symbol
            )

            # invia al engine
            if self.callback:
                self.callback(candle)

            # reset candela
            self.start_time = now
            self.current_candle = None
