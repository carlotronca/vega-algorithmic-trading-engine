import os
import sys
import time


PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

sys.path.append(
    PROJECT_ROOT
)

from exchange.bitvavo_rest_client import (
    BitvavoRESTClient
)


# =====================================================
# CONFIG
# =====================================================

MARKET = "SOL-USDC"

USDC_SIZE = 10

TP_PCT = 0.03

SL_PCT = 0.015


# =====================================================
# START
# =====================================================

print("\n" + "=" * 80)
print("FULL REST PROTECTION TEST")
print("=" * 80 + "\n")


client = BitvavoRESTClient()


# =====================================================
# MARKET BUY
# =====================================================

buy_response = client.place_market_buy(

    market=MARKET,

    amount_quote_usdc=USDC_SIZE
)


print("\nBUY RESPONSE:\n")

print(buy_response)


# =====================================================
# EXTRACT FILLS
# =====================================================

fills = buy_response.get(
    "fills",
    []
)

if len(fills) == 0:

    raise RuntimeError(
        "No fills returned"
    )


fill = fills[0]

amount = float(
    fill["amount"]
)

fill_price = float(
    fill["price"]
)


print(f"\nFILLED AMOUNT => {amount}")

print(f"FILL PRICE => {fill_price}")


# =====================================================
# CALCULATE TP / SL
# =====================================================

tp_price = round(
    fill_price * (1 + TP_PCT),
    3
)

sl_price = round(
    fill_price * (1 - SL_PCT),
    3
)


print(f"\nTP PRICE => {tp_price}")

print(f"SL PRICE => {sl_price}")


# =====================================================
# STOP LOSS
# =====================================================

sl_response = client.place_stop_loss(

    market=MARKET,

    amount=amount,

    trigger_price=sl_price
)


print("\nSTOP LOSS RESPONSE:\n")

print(sl_response)


# =====================================================
# TAKE PROFIT LIMIT
# =====================================================

tp_response = (
    client.place_take_profit_limit(

        market=MARKET,

        amount=amount,

        trigger_price=tp_price,

        limit_price=tp_price
    )
)


print("\nTAKE PROFIT RESPONSE:\n")

print(tp_response)


print("\nTEST COMPLETE\n")
