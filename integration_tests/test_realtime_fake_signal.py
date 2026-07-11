import os
import sys
import time


# =====================================================
# PROJECT ROOT
# =====================================================

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# =====================================================
# IMPORTS
# =====================================================

from live.live_runtime import (
    LiveRealtimeEngine,
    journal,
    state_manager,
    safety_layer
)

from models.signal import Signal

from market.candle import Candle


# =====================================================
# CONFIG
# =====================================================

MARKET = "SOL-USDC"


# =====================================================
# REAL MARKET PRICE
# =====================================================

from python_bitvavo_api.bitvavo import Bitvavo


bitvavo = Bitvavo({})

ticker = bitvavo.tickerPrice({
    'market': MARKET
})

TEST_PRICE = float(ticker['price'])

print("\nREAL MARKET PRICE FETCHED\n")

print(f"{MARKET} => {TEST_PRICE}\n")

# =====================================================
# FAKE STRATEGY
# =====================================================

class FakeStrategy:

    def __init__(self):

        self.signal_sent = False

        self.candles = []

    def on_candle(self, candle, engine):

        self.candles.append(candle)

        print("\nFAKE STRATEGY RECEIVED CANDLE")

        print(f"Close => {candle.close}")

        # only send signal once
        if self.signal_sent:

            print("Signal already sent")

            return None

        self.signal_sent = True

        print("\nGENERATING FAKE BUY SIGNAL\n")

        signal = Signal(

            side="BUY",

            symbol=MARKET,

            entry_price=float(candle.close),

            stop_loss=float(candle.close) * 0.985,

            take_profit=float(candle.close) * 1.03,

            metadata={

                "test": True,

                "source": "fake_strategy_signal"
            }
        )

        return signal


# =====================================================
# START
# =====================================================

print("\n" + "=" * 80)
print("REALTIME ENGINE FAKE SIGNAL TEST")
print("=" * 80 + "\n")

print("WARNING:")
print("- REAL MARKET BUY")
print("- REAL REST EXECUTION")
print("- REAL CANDLE ENGINE")
print("- REAL EXCHANGE ORDER")
print("- REAL 10 USDC POSITION")
print("- FAKE STRATEGY SIGNAL")
print()


# =====================================================
# ENGINE
# =====================================================

strategy = FakeStrategy()

engine = LiveRealtimeEngine(
    strategy=strategy,
    market=MARKET,
    journal=journal,
    state_manager=state_manager,
    safety_layer=safety_layer
)

engine.reconcile_exchange_balance()

state_manager.state["daily"]["max_daily_loss_reached"] = False

state_manager.state["safety"]["locked"] = False

state_manager.state["safety"]["lock_reason"] = None

# =====================================================
# LIMIT TEST SIZE
# =====================================================

engine.max_live_notional_usdc = 10.0


# =====================================================
# FAKE CANDLE
# =====================================================

fake_candle = Candle(

    timestamp=float(time.time()),

    open=TEST_PRICE,

    high=TEST_PRICE,

    low=TEST_PRICE,

    close=TEST_PRICE,

    volume=100.0,

    symbol=MARKET
)

print("\nFAKE CANDLE:\n")

print(fake_candle)


# =====================================================
# EXECUTE
# =====================================================

print("\nSENDING FAKE CANDLE TO REALTIME ENGINE...\n")

try:

    engine.on_candle(fake_candle)

    print("\nTEST FINISHED\n")

except Exception as e:

    print("\nTEST FAILED\n")

    print(str(e))


print("\nDONE\n")
