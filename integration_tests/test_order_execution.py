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

from exchange.bitvavo_rest_client import (
    BitvavoRESTClient
)


# =====================================================
# CONFIG
# =====================================================

MARKET = "SOL-USDC"

USDC_SIZE = 10


# =====================================================
# START
# =====================================================

print("\n" + "=" * 80)
print("REST MARKET BUY TEST")
print("=" * 80 + "\n")


client = BitvavoRESTClient()


# =====================================================
# PLACE BUY
# =====================================================

response = client.place_market_buy(

    market=MARKET,

    amount_quote_usdc=USDC_SIZE
)


print("\nBUY RESPONSE:\n")

print(response)

print("\nTEST COMPLETE\n")
