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
# START
# =====================================================

print("\n" + "=" * 80)
print("BITVAVO REST CLIENT TEST")
print("=" * 80 + "\n")


client = BitvavoRESTClient()


# =====================================================
# BALANCE
# =====================================================

print("\nBALANCE TEST\n")

balance = client.get_balance()

print(balance)


# =====================================================
# TICKER
# =====================================================

print("\nTICKER TEST\n")

ticker = client.get_ticker_price(
    "SOL-USDC"
)

print(ticker)


# =====================================================
# OPEN ORDERS
# =====================================================

print("\nOPEN ORDERS TEST\n")

orders = client.get_open_orders(
    "SOL-USDC"
)

print(orders)


print("\nTEST COMPLETE\n")
