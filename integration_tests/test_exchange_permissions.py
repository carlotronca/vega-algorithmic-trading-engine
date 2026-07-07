
import os
import sys

import time
import math

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        ".."
    )
)

sys.path.append(
    PROJECT_ROOT
)

import config

from python_bitvavo_api.bitvavo import Bitvavo


# =====================================================
# CONFIG
# =====================================================

MARKET = "SOL-USDC"

USDC_SIZE = 10.0

TP_PCT = 0.03

SL_PCT = 0.015


# =====================================================
# CLIENT
# =====================================================

bitvavo = Bitvavo({

    "APIKEY": config.API_KEY,

    "APISECRET": config.API_SECRET
})


# =====================================================
# GET PRICE
# =====================================================

ticker = bitvavo.tickerPrice({

    "market": MARKET
})

price = float(
    ticker["price"]
)

print(f"\nMARKET PRICE => {price}")


# =====================================================
# CALCULATE SIZE
# =====================================================

amount = round(
    USDC_SIZE / price,
    8
)

print(f"BUY AMOUNT => {amount} SOL")


# =====================================================
# MARKET BUY
# =====================================================

print("\nSENDING MARKET BUY...\n")

buy_response = bitvavo.placeOrder(

    MARKET,

    "buy",

    "market",

    {

        "amount": str(USDC_SIZE),

        "operatorId": 1

    }
)

print("BUY RESPONSE:")

print(buy_response)


# =====================================================
# TP / SL PRICES
# =====================================================

tp_price = round(
    price * (1 + TP_PCT),
    3
)

sl_trigger = round(
    price * (1 - SL_PCT),
    3
)

sl_limit = round(
    sl_trigger * 0.999,
    3
)

print(f"\nTP PRICE => {tp_price}")

print(f"SL TRIGGER => {sl_trigger}")

print(f"SL LIMIT => {sl_limit}")


# =====================================================
# TAKE PROFIT LIMIT
# =====================================================

print("\nSENDING TAKE PROFIT...\n")

tp_response = bitvavo.placeOrder(

    MARKET,

    "sell",

    "takeProfitLimit",

    {

        "amount": str(amount),

        "price": str(tp_price),

        "triggerType": "price",

        "triggerReference": "lastTrade",

        "triggerAmount": str(tp_price),

        "operatorId": 1

    }
)

print("TP RESPONSE:")

print(tp_response)


# =====================================================
# STOP LOSS LIMIT
# =====================================================

print("\nSENDING STOP LOSS...\n")

sl_response = bitvavo.placeOrder(

    MARKET,

    "sell",

    "stopLossLimit",

    {

        "amount": str(amount),

        "price": str(sl_limit),

        "triggerType": "price",

        "triggerReference": "lastTrade",

        "triggerAmount": str(sl_trigger),

        "operatorId": 1

    }
)

print("SL RESPONSE:")

print(sl_response)


print("\nTEST COMPLETE\n")
