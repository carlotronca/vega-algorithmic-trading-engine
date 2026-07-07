import os
import sys


PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

sys.path.append(
    PROJECT_ROOT
)


from execution.protected_live_execution import (
    ProtectedLiveExecution
)


# =====================================================
# CONFIG
# =====================================================

MARKET = "SOL-USDC"

USDC_SIZE = 10.0

ENTRY_PRICE = 71.0

STOP_LOSS = round(
    ENTRY_PRICE * (1 - 0.015),
    3
)

TAKE_PROFIT = round(
    ENTRY_PRICE * (1 + 0.03),
    3
)


# =====================================================
# START
# =====================================================

print("\n" + "=" * 80)
print("V2.5 RUNTIME EXECUTION TEST")
print("=" * 80 + "\n")


execution = ProtectedLiveExecution(

    market=MARKET,

    api_write=True,

    max_notional_usdc=20.0
)


# =====================================================
# TEST OPEN POSITION
# =====================================================

position = (
    execution.open_protected_long_position(

        symbol=MARKET,

        amount_quote_usdc=USDC_SIZE,

        stop_loss_price=STOP_LOSS,

        take_profit_price=TAKE_PROFIT,

        signal_metadata={
            "source": "MANUAL_RUNTIME_TEST"
        }
    )
)


print("\n")
print("=" * 80)
print("POSITION OPENED")
print("=" * 80)

print(position)

print("\nTEST COMPLETE\n")
