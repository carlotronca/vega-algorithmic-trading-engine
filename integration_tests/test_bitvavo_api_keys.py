import os
import sys

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from python_bitvavo_api.bitvavo import Bitvavo
from config import API_KEY, API_SECRET


bitvavo = Bitvavo({
    "APIKEY": API_KEY,
    "APISECRET": API_SECRET,
    "RESTURL": "https://api.bitvavo.com/v2",
    "WSURL": "wss://ws.bitvavo.com/v2/",
    "ACCESSWINDOW": 10000
})


print("Testing Bitvavo API keys...")

try:
    balance = bitvavo.balance({})
    print("BALANCE OK")
    print(balance)

except Exception as e:
    print("BALANCE ERROR")
    print(e)


try:
    ticker = bitvavo.tickerPrice({"market": "SOL-USDC"})
    print("TICKER OK")
    print(ticker)

except Exception as e:
    print("TICKER ERROR")
    print(e)
